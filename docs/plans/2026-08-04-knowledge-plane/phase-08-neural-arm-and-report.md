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

- [x] `ingest/embeddings.py`: `--arm neural` path (fastembed ONNX, batched, cached to parquet, seeded ordering)
- [x] Optional third arm stub: Qwen3-Embedding-0.6B behind `--model` flag (documented, not required; native dim per model, not forced to 256)
- [x] Eval stratification: genome-subset restriction + coverage reporting wired into report
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

- 2026-08-05 — Phase opened on `feat/neural-arm`. Scope amendment approved
  same day: context-plane LLM comparison (local vs Anthropic API) added as
  [phase 09](phase-09-context-plane-llm.md), executing after this phase.
  Design settled before implementation: `data.embedding_arm: svd|neural`
  config axis (svd default keeps CI ML-free per ADR 0006), neural vectors in
  separate parquets (`item_vectors_neural.parquet`, `user_vectors_neural.parquet`,
  bge-small native 384d vs SVD 256d), loaders resolve source parquet by arm
  and must rebuild engine-side vector stores on dim mismatch (row counts are
  identical across arms, so count-based skip checks cannot detect an arm
  switch). fastembed lands behind an optional `neural` extra. Known ripple:
  adding the config field shifts every config fingerprint; committed
  artifacts are snapshots and keep their old fingerprints.
- 2026-08-05 — PR A (#19) merged: neural ingest + arm-aware loaders.
  `make seed ARM=neural` embedded 62,423 items @ 384d + 156,604 users in
  ~2 min on CPU (well inside ADR 0006's 2–5 min estimate). Lyra dim-switch
  rebuild verified end to end; first qualitative signal visible in a Matrix
  smoke query: neural vector arm surfaces text-semantic neighbors (Matrix
  sequels) where SVD surfaces behavioral ones. PR B: bench artifact gains
  `embedding_arm`, quality section gains `genome_subset` (probes whose seed
  + all expected items are genome-covered — the fair svd-vs-neural slice)
  and `embedding_coverage`; report partitions equivalence by arm and renders
  an svd-vs-neural ablation section once both arms have artifacts. Existing
  svd-only report output verified byte-stable apart from the new arm column.
