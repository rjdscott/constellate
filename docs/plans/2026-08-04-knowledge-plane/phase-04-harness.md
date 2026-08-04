# Phase 04 — Benchmark harness (go/no-go)

## Goal

All six flows (F1–F6), quality via ir_measures (Recall@10/50, NDCG@10,
MRR@10) + hand-rolled coverage/novelty, fusion + significance via ranx,
ablation mode (`--planes vector` etc.), open-loop fixed-rate latency harness
(HdrHistogram, warmup discard, scheduled-send timestamps, ≥5k samples,
concurrency 1/8/32), JSON artifacts + markdown report — run against Lyra.
**Go/no-go gate for the whole project: the report must show a measurable
ablation delta on the probe set (vector-only vs vector+graph). If it
doesn't, that finding is reported loudly and the plan is re-scoped before
any container work.** Lyra latency tagged `latency_indicative: true`.

## Tasks

- [x] `bench/flows.py` F1–F6; `bench/metrics.py` (ir_measures + coverage/novelty); `bench/latency.py` (open-loop scheduler + hdrhistogram) — landed as `src/constellate/bench/{flows,metrics,latency}.py` (typed + unit-tested; see progress log)
- [x] Ablation flag threaded through pipeline (`planes` subset) — already existed on `RetrievalRequest` since phase 01; harness drives it, no pipeline change
- [x] Weighted-RRF tuning on validation slice via ranx (baseline RRF k=60 kept) — grid search reuses the pipeline's own `rrf` so the tuned weight is config-pluggable; ranx does the significance stats
- [x] `bench/report.py`: cross-run markdown table incl. ablation delta + latency breakdown; results JSON committed to `bench/results/`
- [x] `make bench PLATFORM=lyra`, `make report`

## Verification

```
make bench PLATFORM=lyra && make report
# report shows: probe-set Recall@10 vector-only vs vector+graph, delta + significance
uv run pytest tests/unit/test_metrics.py tests/unit/test_latency.py
```

## Artifacts

`bench/results/lyra-<sha>-<utc>.json` (committed), `bench/report.md`
snapshot, go/no-go verdict appended to this progress log AND the migration
narrative.

## Progress log

- 2026-08-04 — Phase opened on `feat/bench` from `5f45c85`. Layout decision
  (same precedent as `bench/probes.py`): typed harness logic lives in
  `src/constellate/bench/` so mypy --strict and unit tests cover it; `bench/`
  keeps thin CLIs and the committed `results/` artifacts. Ablation arms ride
  the existing `RetrievalRequest.planes` subset — no pipeline changes needed.
  Fusion tuning design: capture vector-only and graph-only runs once, tune
  weighted RRF offline with ranx on a validation half of the probes, score on
  the held-out half; pipeline baseline RRF k=60 unchanged.
- 2026-08-04 — Harness landed (48 tests green, mypy --strict clean). Deps:
  ir-measures 0.4.3, ranx 0.3.21, hdrhistogram 0.10.7; cost: numba 0.66
  ceiling downgraded numpy 2.5.1 → 2.4.6 (uv.lock; all suites still green).
  Deviation from task wording: harness modules live in
  `src/constellate/bench/` not `bench/` — same split as
  `bench/probes.py`/`constellate.ingest.probes`, so mypy --strict and unit
  tests cover the logic; `bench/` keeps CLIs + committed `results/`. Fusion
  tuning reuses `constellate.core.fusion.rrf` (not ranx fusion) so the tuned
  weight drops straight into `config/<platform>.yaml`; ranx provides the
  paired student-t significance table. One shakeout incident: runner read
  `n_ratings` from `items.parquet` — that aggregate only exists in the
  relational plane; novelty popularity now computed from train interactions.
- 2026-08-04 — **Shakeout ablation (no latency): GO.** Hybrid beats
  vector-only on probe-set R@10 +0.0141 (0.0355 vs 0.0213, p=0.0054
  paired student-t); R@50 +0.186. Louder finding: **graph_only dominates
  both** (R@10 0.0965, R@50 0.3516) — equal-weight RRF *dilutes* graph
  signal on graph-necessary probes; tuned graph weight 1.5 lifts held-out
  nDCG@10 0.0418 → 0.0479. Honest negatives, stratified: `cross_genre` is
  graph's blowout (R@10 0.352 vs vector 0.002); `cold_start` vector wins
  (0.068 vs 0.030 — genome-SVD vectors carry cold items, they were built
  from tags); `path_required` + `tag_bridge` near zero for *every* arm —
  the expander's hops-ASC ordering fills the candidate budget with 1-hop
  neighbours before any 2-hop target survives. That expansion-policy gap is
  a phase-05+ retrieval question (ADR-worthy if we change it), not a
  harness bug: the harness exists precisely to surface it.
- 2026-08-04 — **Full committed run `lyra-c368e54-20260804T071640Z`:
  VERDICT GO.** Quality byte-identical to shakeout (deterministic:
  R@10 +0.0141, p=0.0054; graph_only dominance confirmed). Latency
  (indicative, in-process): warm mean 114.8ms, capacity 8.7/s;
  p50 ~127ms / p99 ~170ms **identical across concurrency 1/8/32** — the
  embedded single-process ceiling measured, the axis Orion/Hydra attack.
  Saturation run (10.5/s arrival vs 8.7/s capacity): p50 61s — open-loop
  charging queue delay from scheduled send; a closed-loop harness would
  have shown ~115ms. Full analysis + platform config/tuning record:
  `docs/research/2026-08-04-knowledge-plane-foundations/07-lyra-benchmark-findings.md`
  (one findings doc per platform, per user direction). Artifacts committed:
  results JSON + `bench/report.md`. Container work (phase 05) unblocked.
- 2026-08-04 — **Independent review pass: 1 major, 7 minor — all fixed,
  bench rerun.** The major was real and instructive: fusion tuning fused
  depth-truncated top-50 arm lists while the pipeline fuses 250-deep
  candidates; the artifact itself proved divergence (offline w=1.0 nDCG
  0.042 vs actual hybrid 0.036). Fixed by collecting single-plane arms at
  the pipeline's true fusion depth + an in-artifact fidelity check —
  rerun shows exact agreement (0.0362 = 0.0362) and the best weight moved
  1.5 → 2.0 (grid edge; widen before adopting). Minors: histogram
  `recorded` count now exposed + asserted, errors split measured/warmup,
  `achieved_hz` renamed `completion_hz`, p99.9 dropped from tables (5k
  samples), `evaluate()` zero-fills run-absent queries, F6 times all 9
  calls, runbook duration corrected (~1 h latency total). Final artifact:
  `lyra-f7eb799-20260804T082917Z` (quality byte-identical again; latency
  drift ~1% vs prior run). PR #9, CI green.
