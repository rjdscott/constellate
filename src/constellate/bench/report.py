"""Cross-run markdown report over bench/results/*.json.

    uv run python -m constellate.bench.report

The go/no-go verdict lives here: GO when hybrid beats vector_only on probe-set
Recall@10 with p < 0.05 (ranx paired student-t); otherwise NO-GO, reported
loudly per the plan — a null result re-scopes the project, it doesn't hide.
"""

import json
from pathlib import Path
from typing import Any

import yaml

RESULTS_DIR = Path(__file__).resolve().parents[3] / "bench" / "results"
REPORT_PATH = RESULTS_DIR.parent / "report.md"
CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
P_THRESHOLD = 0.05
EQUIVALENCE_METRICS = ("R@10", "nDCG@10")


def _quality_tolerance(platform: str) -> float | None:
    """Equivalence tolerance vs Lyra — stated in config/<platform>.yaml under
    engines.bench (raw yaml read: a bench parameter, deliberately outside the
    PlatformConfig model so platform fingerprints stay comparable)."""
    path = CONFIG_DIR / f"{platform}.yaml"
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text())
    value = raw.get("engines", {}).get("bench", {}).get("quality_tolerance")
    return float(value) if value is not None else None


def equivalence(artifacts: dict[str, dict[str, Any]]) -> list[str]:
    """Hybrid-arm quality deltas of every non-Lyra platform vs the newest
    Lyra run — within tolerance proves the abstraction holds (phase 05)."""
    lyra = [a for a in artifacts.values() if a["platform"] == "lyra"]
    others = {name: a for name, a in artifacts.items() if a["platform"] != "lyra"}
    if not lyra or not others:
        return []
    base = lyra[-1]["quality"]["arms"]["hybrid"]["overall"]
    lines = [
        "## Cross-platform quality equivalence (hybrid arm, vs Lyra)",
        "",
        "| run | " + " | ".join(EQUIVALENCE_METRICS) + " | tolerance | verdict |",
        "|---|" + "---|" * (len(EQUIVALENCE_METRICS) + 2),
    ]
    for name, artifact in others.items():
        overall = artifact["quality"]["arms"]["hybrid"]["overall"]
        deltas = {m: overall[m] - base[m] for m in EQUIVALENCE_METRICS}
        tolerance = _quality_tolerance(artifact["platform"])
        ok = tolerance is not None and all(abs(d) <= tolerance for d in deltas.values())
        cells = " | ".join(f"{deltas[m]:+.4f}" for m in EQUIVALENCE_METRICS)
        tol = f"±{tolerance}" if tolerance is not None else "unset"
        lines.append(f"| {name} | {cells} | {tol} | {'within' if ok else '**OUTSIDE**'} |")
    lines.append("")
    return lines


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


def _graph_adapter(artifact: dict[str, Any]) -> str:
    engines = artifact.get("engines") or {}
    return str(engines.get("graph", {}).get("adapter", "-"))


def render_markdown(artifacts: dict[str, dict[str, Any]]) -> str:
    lines = ["# Constellate benchmark report", ""]
    if len(artifacts) > 1:
        lines += [
            "| run | platform | graph | sha | hybrid R@10 | delta vs vector | verdict |",
            "|---|---|---|---|---|---|---|",
        ]
        for name, artifact in artifacts.items():
            word, _ = verdict(artifact)
            hybrid = artifact["quality"]["arms"]["hybrid"]["overall"]["R@10"]
            delta = artifact["quality"]["ablation_delta_hybrid_vs_vector"]["R@10"]
            lines.append(
                f"| {name} | {artifact['platform']} | {_graph_adapter(artifact)} "
                f"| {artifact['git_sha']} | {hybrid:.4f} | {delta:+.4f} | {word} |"
            )
        lines.append("")
    lines += equivalence(artifacts)
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
