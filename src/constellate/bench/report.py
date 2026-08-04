"""Cross-run markdown report over bench/results/*.json.

    uv run python -m constellate.bench.report

The go/no-go verdict lives here: GO when hybrid beats vector_only on probe-set
Recall@10 with p < 0.05 (ranx paired student-t); otherwise NO-GO, reported
loudly per the plan — a null result re-scopes the project, it doesn't hide.
"""

import json
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parents[3] / "bench" / "results"
REPORT_PATH = RESULTS_DIR.parent / "report.md"
P_THRESHOLD = 0.05


def _p_value(artifact: dict[str, Any], metric: str = "recall@10") -> float | None:
    sig = artifact["quality"]["significance"]
    try:
        return float(sig["hybrid"]["comparisons"]["vector_only"][metric])
    except (KeyError, TypeError, ValueError):
        return None


def verdict(artifact: dict[str, Any]) -> tuple[str, str]:
    """(GO|NO-GO, reason) from the ablation delta and its significance."""
    delta = artifact["quality"]["ablation_delta_hybrid_vs_vector"]["R@10"]
    p = _p_value(artifact)
    p_text = f"p={p:.4g}" if p is not None else "p unavailable"
    if delta > 0 and p is not None and p < P_THRESHOLD:
        return "GO", f"hybrid beats vector-only on Recall@10 by {delta:+.4f} ({p_text})"
    return "NO-GO", (
        f"no significant hybrid win on Recall@10 (delta {delta:+.4f}, {p_text}) — "
        "re-scope before container work"
    )


def _quality_table(artifact: dict[str, Any]) -> list[str]:
    arms = artifact["quality"]["arms"]
    cov, nov = artifact["quality"]["coverage"], artifact["quality"]["novelty"]
    lines = [
        "| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm, data in arms.items():
        o = data["overall"]
        lines.append(
            f"| {arm} | {o['R@10']:.4f} | {o['R@50']:.4f} | {o['nDCG@10']:.4f} "
            f"| {o['RR@10']:.4f} | {cov[arm]:.4f} | {nov[arm]:.2f} |"
        )
    return lines


def _by_kind_table(artifact: dict[str, Any]) -> list[str]:
    arms = artifact["quality"]["arms"]
    kinds = sorted(next(iter(arms.values()))["by_kind"])
    lines = [
        "| probe kind | " + " | ".join(f"{arm} R@10" for arm in arms) + " |",
        "|---|" + "---|" * len(arms),
    ]
    for kind in kinds:
        cells = " | ".join(f"{arms[arm]['by_kind'][kind]['R@10']:.4f}" for arm in arms)
        lines.append(f"| {kind} | {cells} |")
    return lines


def _latency_table(artifact: dict[str, Any]) -> list[str]:
    latency = artifact.get("latency")
    if not latency:
        return ["_latency skipped for this run_"]
    lines = [
        f"Workload: {latency['workload']} — warm mean "
        f"{latency['calibration']['warm_mean_ms']}ms, "
        f"est. capacity {latency['calibration']['est_capacity_hz']}/s. "
        "**Indicative**: in-process, no network hop.",
        "",
        # p99.9 stays in the JSON but is decorative at 5k samples (~5 tail
        # events), so the table stops at p99 — same standard the runbook
        # applies to p99 under 5k samples
        "| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for run in latency["runs"]:
        p = run["percentiles_ms"]
        lines.append(
            f"| {run['rate_hz']} | {run['concurrency']} | {run['samples']} "
            f"| {p['p50']:.1f} | {p['p95']:.1f} | {p['p99']:.1f} "
            f"| {run['max_ms']:.1f} | {run['errors']} |"
        )
    return lines


def _run_section(artifact: dict[str, Any], name: str) -> list[str]:
    word, reason = verdict(artifact)
    fusion = artifact["fusion_tuning"]
    flows = ", ".join(f"{f['flow']} {'ok' if f['passed'] else 'FAILED'}" for f in artifact["flows"])
    lines = [
        f"## {name}",
        "",
        f"- platform `{artifact['platform']}` · sha `{artifact['git_sha']}` · "
        f"{artifact['utc']} · config `{artifact['config_fingerprint']}`",
        f"- flows: {flows}",
        "",
        f"### Verdict: **{word}** — {reason}",
        "",
        f"### Quality ({artifact['quality']['n_probes']} graph-necessary probes)",
        "",
        *_quality_table(artifact),
        "",
        "#### By probe kind",
        "",
        *_by_kind_table(artifact),
        "",
        "### Fusion tuning (weighted RRF, validation half)",
        "",
        f"Best graph weight **{fusion['best_graph_weight']}** on {fusion['metric']} "
        f"(baseline 1.0). Held-out test half: baseline nDCG@10 "
        f"{fusion['test']['baseline_w1.0']['nDCG@10']:.4f} vs tuned "
        f"{fusion['test']['tuned']['nDCG@10']:.4f}.",
        "",
        "### Latency (open-loop, coordinated-omission-safe)",
        "",
        *_latency_table(artifact),
        "",
    ]
    return lines


def render_markdown(artifacts: dict[str, dict[str, Any]]) -> str:
    lines = ["# Constellate benchmark report", ""]
    if len(artifacts) > 1:
        lines += [
            "| run | platform | sha | hybrid R@10 | delta vs vector | verdict |",
            "|---|---|---|---|---|---|",
        ]
        for name, artifact in artifacts.items():
            word, _ = verdict(artifact)
            hybrid = artifact["quality"]["arms"]["hybrid"]["overall"]["R@10"]
            delta = artifact["quality"]["ablation_delta_hybrid_vs_vector"]["R@10"]
            lines.append(
                f"| {name} | {artifact['platform']} | {artifact['git_sha']} "
                f"| {hybrid:.4f} | {delta:+.4f} | {word} |"
            )
        lines.append("")
    for name, artifact in artifacts.items():
        lines += _run_section(artifact, name)
    return "\n".join(lines)


def main() -> None:
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        raise SystemExit(f"no results in {RESULTS_DIR} — run `make bench` first")
    artifacts = {f.stem: json.loads(f.read_text()) for f in files}
    REPORT_PATH.write_text(render_markdown(artifacts))
    print(f"report: {REPORT_PATH}")
    for name, artifact in artifacts.items():
        word, reason = verdict(artifact)
        print(f"  {name}: {word} — {reason}")


if __name__ == "__main__":
    main()
