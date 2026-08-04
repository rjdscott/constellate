"""Benchmark runner: one committed JSON artifact per run.

    uv run python -m constellate.bench.run lyra [--samples N] [--skip-latency]

Sections: flows (F1-F6 hard checks), quality ablation over the probe set
(vector_only / graph_only / hybrid via the pipeline's `planes` subset — the
project go/no-go), weighted-RRF tuning on a validation half (the pipeline's
own rrf at the pipeline's fusion depth, with a fidelity check against the
hybrid arm, so the tuned weight transfers to config), open-loop latency.
Lyra numbers are in-process, hence `latency_indicative: true`.
"""

import argparse
import asyncio
import json
import os
import platform as host_platform
import subprocess
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from constellate.bench.flows import run_flows
from constellate.bench.latency import run_open_loop
from constellate.bench.metrics import (
    QrelsDict,
    RunDict,
    coverage,
    evaluate,
    evaluate_by_kind,
    novelty,
    significance,
)
from constellate.config import load_config
from constellate.core.fusion import rrf
from constellate.core.types import Candidate, PlaneName, RetrievalRequest
from constellate.factory import build_service
from constellate.ingest import CANONICAL_DIR
from constellate.service import Service

RESULTS_DIR = Path(__file__).resolve().parents[3] / "bench" / "results"

ARMS: dict[str, list[PlaneName]] = {
    "vector_only": ["relational", "vector"],
    "graph_only": ["relational", "graph"],
    "hybrid": ["relational", "vector", "graph"],
}
FETCH_K = 50  # retrieval depth: Recall@50 ceiling, everything else cut at 10
WEIGHT_GRID = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0)
FLOWS_USER_ID = 1
CONCURRENCIES = (1, 8, 32)
UTILISATION = 0.7  # fixed-rate runs sit below the knee; one extra run sits past it


async def collect_arm_runs(
    service: Service, probes: pd.DataFrame, deep_k: int
) -> tuple[QrelsDict, dict[str, RunDict], dict[str, RunDict]]:
    """One retrieval per probe per arm; scores stored as 1/rank.

    Single-plane arms are fetched `deep_k` deep — the pipeline's true
    per-plane fusion depth for a k=FETCH_K hybrid request — so offline
    fusion tuning fuses the same inputs the pipeline does. Metrics runs
    truncate those to FETCH_K (single-plane rankings are monotone, so the
    truncation equals a k=FETCH_K request exactly).
    Returns (qrels, metric_runs@FETCH_K, deep_single_plane_runs@deep_k).
    """
    qrels: QrelsDict = {}
    metric_runs: dict[str, RunDict] = {arm: {} for arm in ARMS}
    deep_runs: dict[str, RunDict] = {arm: {} for arm in ARMS if arm != "hybrid"}
    for _, row in probes.iterrows():
        qid = f"{row['kind']}:{int(row['seed_item_id'])}"
        qrels[qid] = {str(int(item)): 1 for item in row["expected_items"]}
        for arm, planes in ARMS.items():
            k = FETCH_K if arm == "hybrid" else deep_k
            response = await service.recommend(
                RetrievalRequest(seed_item_id=int(row["seed_item_id"]), k=k, planes=planes)
            )
            recs = response.recommendations
            if arm != "hybrid":
                deep_runs[arm][qid] = {str(r.item_id): 1.0 / r.rank for r in recs}
                recs = recs[:FETCH_K]
            metric_runs[arm][qid] = {str(r.item_id): 1.0 / r.rank for r in recs}
    return qrels, metric_runs, deep_runs


def split_validation(qids: Sequence[str], seed: int) -> set[str]:
    """Half of each probe kind, seeded — tuning never sees the test half."""
    by_kind: dict[str, list[str]] = {}
    for qid in sorted(qids):
        by_kind.setdefault(qid.split(":", 1)[0], []).append(qid)
    rng = np.random.default_rng(seed)
    validation: set[str] = set()
    for _, kind_qids in sorted(by_kind.items()):
        picks = rng.permutation(len(kind_qids))[: len(kind_qids) // 2]
        validation.update(kind_qids[i] for i in picks)
    return validation


def _fuse_offline(
    vector_run: RunDict, graph_run: RunDict, qids: set[str], *, rrf_k: int, graph_weight: float
) -> RunDict:
    """Re-fuse captured per-plane rankings with the pipeline's own rrf."""
    out: RunDict = {}
    plane_runs: tuple[tuple[PlaneName, RunDict], ...] = (
        ("vector", vector_run),
        ("graph", graph_run),
    )
    for qid in qids:
        ranked: dict[PlaneName, list[Candidate]] = {}
        for plane, run in plane_runs:
            docs = sorted(run.get(qid, {}).items(), key=lambda kv: -kv[1])
            if docs:
                ranked[plane] = [
                    Candidate(item_id=int(doc), score=score, source=plane) for doc, score in docs
                ]
        fused = rrf(ranked, k=rrf_k, weights={"vector": 1.0, "graph": graph_weight})
        out[qid] = {str(f.item_id): 1.0 / rank for rank, f in enumerate(fused, start=1)}
    return out


def tune_graph_weight(
    qrels: QrelsDict,
    vector_run: RunDict,
    graph_run: RunDict,
    validation_qids: set[str],
    *,
    rrf_k: int,
    grid: Sequence[float] = WEIGHT_GRID,
    metric: str = "nDCG@10",
) -> dict[str, Any]:
    """Grid-search the graph weight on the validation half, score on the rest."""
    test_qids = set(qrels) - validation_qids

    def score(weight: float, qids: set[str]) -> dict[str, float]:
        subset = {qid: qrels[qid] for qid in qids}
        return evaluate(
            subset, _fuse_offline(vector_run, graph_run, qids, rrf_k=rrf_k, graph_weight=weight)
        )

    validation_scores = {w: score(w, validation_qids)[metric] for w in grid}
    # ties resolve toward the 1.0 baseline — don't move the knob for nothing
    best = max(grid, key=lambda w: (validation_scores[w], -abs(w - 1.0)))
    return {
        "metric": metric,
        "rrf_k": rrf_k,
        "validation_size": len(validation_qids),
        "test_size": len(test_qids),
        "validation_scores": {str(w): round(s, 4) for w, s in validation_scores.items()},
        "best_graph_weight": best,
        "test": {"baseline_w1.0": score(1.0, test_qids), "tuned": score(best, test_qids)},
    }


def quality_section(qrels: QrelsDict, runs: dict[str, RunDict]) -> dict[str, Any]:
    catalog_size = len(pd.read_parquet(CANONICAL_DIR / "items.parquet", columns=["item_id"]))
    # popularity for novelty comes from train interactions (items.parquet
    # carries no aggregates; those live in the relational plane)
    train_items = pd.read_parquet(
        CANONICAL_DIR / "interactions.parquet",
        columns=["item_id"],
        filters=[("split", "=", "train")],
    )["item_id"]
    counts = train_items.value_counts()
    n_ratings = {int(item): int(count) for item, count in counts.items()}  # type: ignore[call-overload]
    total_interactions = int(counts.sum())

    arms: dict[str, Any] = {}
    top10: dict[str, list[list[int]]] = {}
    for arm, run in runs.items():
        arms[arm] = {"overall": evaluate(qrels, run), "by_kind": evaluate_by_kind(qrels, run)}
        top10[arm] = [
            [int(doc) for doc, _ in sorted(docs.items(), key=lambda kv: -kv[1])[:10]]
            for docs in run.values()
        ]
    delta = {
        m: round(arms["hybrid"]["overall"][m] - arms["vector_only"]["overall"][m], 4)
        for m in arms["hybrid"]["overall"]
    }
    return {
        "n_probes": len(qrels),
        "arms": arms,
        "ablation_delta_hybrid_vs_vector": delta,
        "significance": significance(qrels, runs),
        "coverage": {a: round(coverage(t, catalog_size), 4) for a, t in top10.items()},
        "novelty": {
            a: round(novelty(t, n_ratings, total_interactions), 2) for a, t in top10.items()
        },
    }


async def latency_section(
    service: Service, probes: pd.DataFrame, *, samples: int, warmup: int
) -> dict[str, Any]:
    seeds = [int(s) for s in probes["seed_item_id"]]

    async def request(i: int) -> None:
        await service.recommend(RetrievalRequest(seed_item_id=seeds[i % len(seeds)], k=10))

    t0 = time.perf_counter()
    for i in range(30):  # warm caches, then estimate single-stream capacity
        await request(i)
    warm_mean_s = (time.perf_counter() - t0) / 30
    capacity_hz = 1.0 / warm_mean_s

    runs = []
    for concurrency in CONCURRENCIES:
        rate = round(UTILISATION * capacity_hz, 1)
        runs.append(
            await run_open_loop(
                request, rate_hz=rate, concurrency=concurrency, samples=samples, warmup=warmup
            )
        )
    # saturation probe: past the knee, queueing delay charged honestly
    runs.append(
        await run_open_loop(
            request,
            rate_hz=round(1.2 * capacity_hz, 1),
            concurrency=max(CONCURRENCIES),
            samples=samples,
            warmup=warmup,
        )
    )
    return {
        "workload": "hybrid similar(seed), k=10, probe seeds round-robin",
        "calibration": {
            "warm_mean_ms": round(warm_mean_s * 1000, 2),
            "est_capacity_hz": round(capacity_hz, 1),
        },
        "runs": [r.to_json() for r in runs],
    }


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


async def run_bench(platform: str, *, samples: int, warmup: int, skip_latency: bool) -> Path:
    cfg = load_config(platform)
    probes = pd.read_parquet(CANONICAL_DIR / "probes.parquet")
    service = await build_service(platform)
    try:
        print(f"flows: F1-F6 against {platform} ...")
        flow_results = await run_flows(service, probes, user_id=FLOWS_USER_ID)
        for f in flow_results:
            status = "ok" if f.passed else f"FAILED {f.failures}"
            print(f"  {f.flow}: {status}")

        print(f"quality: {len(probes)} probes x {len(ARMS)} arms ...")
        deep_k = cfg.retrieval.candidate_multiplier * FETCH_K
        qrels, runs, deep = await collect_arm_runs(service, probes, deep_k)
        quality = quality_section(qrels, runs)
        delta = quality["ablation_delta_hybrid_vs_vector"]
        print(f"  ablation delta (hybrid - vector_only): {delta}")

        fusion = tune_graph_weight(
            qrels,
            deep["vector_only"],
            deep["graph_only"],
            split_validation(list(qrels), cfg.data.random_seed),
            rrf_k=cfg.fusion.rrf_k,
        )
        # fidelity: offline w=1.0 over the deep runs must reproduce the
        # pipeline's own hybrid arm, or the tuned weight doesn't transfer
        offline_baseline = evaluate(
            qrels,
            _fuse_offline(
                deep["vector_only"],
                deep["graph_only"],
                set(qrels),
                rrf_k=cfg.fusion.rrf_k,
                graph_weight=1.0,
            ),
        )
        fusion["fidelity_check"] = {
            "offline_w1.0_full_set": offline_baseline,
            "pipeline_hybrid_arm": quality["arms"]["hybrid"]["overall"],
        }
        print(f"  fusion tuning: best graph weight {fusion['best_graph_weight']}")
        print(
            f"  fidelity: offline w=1.0 nDCG@10 {offline_baseline['nDCG@10']:.4f} "
            f"vs hybrid arm {quality['arms']['hybrid']['overall']['nDCG@10']:.4f}"
        )

        latency = None
        if not skip_latency:
            print(f"latency: open-loop, {samples} samples/run, concurrency {CONCURRENCIES} ...")
            latency = await latency_section(service, probes, samples=samples, warmup=warmup)
    finally:
        service.close()

    artifact: dict[str, Any] = {
        "platform": platform,
        "git_sha": _git_sha(),
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "config_fingerprint": cfg.fingerprint(),
        "latency_indicative": True,  # in-process, single-tenant, no network hop
        "host": {
            "machine": host_platform.machine(),
            "cpu_count": os.cpu_count(),
            "python": host_platform.python_version(),
        },
        "versions": {
            name: version(name)
            for name in ("numpy", "duckdb", "kuzu", "faiss-cpu", "ir-measures", "ranx")
        },
        "flows": [f.to_json() for f in flow_results],
        "quality": quality,
        "fusion_tuning": fusion,
        "latency": latency,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"{platform}-{_git_sha()}-{stamp}.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n")
    print(f"artifact: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Constellate benchmark runner")
    parser.add_argument("platform", nargs="?", default="lyra")
    parser.add_argument("--samples", type=int, default=5000, help=">=5000 for a trustworthy p99")
    parser.add_argument("--warmup", type=int, default=500)
    parser.add_argument("--skip-latency", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        run_bench(
            args.platform, samples=args.samples, warmup=args.warmup, skip_latency=args.skip_latency
        )
    )


if __name__ == "__main__":
    main()
