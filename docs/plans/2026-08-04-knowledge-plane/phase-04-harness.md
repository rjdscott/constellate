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

- [ ] `bench/flows.py` F1–F6; `bench/metrics.py` (ir_measures + coverage/novelty); `bench/latency.py` (open-loop scheduler + hdrhistogram)
- [ ] Ablation flag threaded through pipeline (`planes` subset)
- [ ] Weighted-RRF tuning on validation slice via ranx (baseline RRF k=60 kept)
- [ ] `bench/report.py`: cross-run markdown table incl. ablation delta + latency breakdown; results JSON committed to `bench/results/`
- [ ] `make bench PLATFORM=lyra`, `make report`

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
