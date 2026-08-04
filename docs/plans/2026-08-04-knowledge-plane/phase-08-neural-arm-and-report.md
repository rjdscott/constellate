# Phase 08 — Neural embedding arm + final report

## Goal

The second embedding arm (ADR 0006): bge-small-en-v1.5 via fastembed over
title+genres+top-tags for all 62k items, as a config-selectable alternative
to genome-SVD. Re-run the benchmark matrix across both arms; eval handles
the coverage asymmetry explicitly (genome-subset comparison + coverage
metric). Then the write-up: findings document synthesizing quality deltas
(per probe stratum), SVD-vs-neural verdict, CTE-vs-AGE delta, per-platform
latency/footprint story — the raw material for the conference talk. Only
after this does Eridanus design begin (out of scope here).

## Tasks

- [ ] `ingest/embeddings.py`: `--arm neural` path (fastembed ONNX, batched, cached to parquet, seeded ordering)
- [ ] Optional third arm stub: Qwen3-Embedding-0.6B @256d behind a flag (documented, not required)
- [ ] Eval stratification: genome-subset restriction + coverage reporting wired into report
- [ ] Full matrix: {lyra, orion, hydra} × {svd, neural} × {all-planes, vector-only} on the probe set
- [ ] `docs/research/2026-08-04-knowledge-plane-foundations/07-findings.md` — the results document, every claim traceable to a committed results JSON
- [ ] Migration-narrative closing entry; plan status table finalized

## Verification

```
make seed ARM=neural            # embeds 62k items, cached
make bench-all && make report   # matrix complete, ablation + arm deltas rendered
```

## Artifacts

Neural vectors parquet (hash in MANIFEST), full `bench/results/` matrix
(committed), `07-findings.md`.

## Progress log
