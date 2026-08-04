# Phase 06 — Hydra, the composed knowledge plane

## Goal

Dedicated engines (ADR 0005): Postgres 18 (source of truth) + Qdrant
(vector) + Memgraph Community 3.12 (graph, `--storage-light-edge`, Bolt via
the official async neo4j driver). Vector and graph are derived projections:
`make rebuild PLATFORM=hydra` drops and regenerates them from relational only —
the proof that a future CDC design can work. All adapters pass the unchanged
conformance suite; all three platforms produce equivalent quality; the report
shows latency + footprint deltas (this platform's numbers are the quotable ones).

## Tasks

- [x] `compose/hydra.yml`: postgres:18, qdrant, memgraph (pinned tags, healthchecks, memory limits)
- [x] `planes/vector/qdrant.py` (async client, exclusion via filter)
- [x] `planes/graph/memgraph.py` — neo4j async driver. *Scope note:* planned
  `[*wShortest]` abandoned — variable-length patterns are the engine's slow
  path here (progress log 2026-08-04, lesson L11); implemented as
  UNWIND-anchored unrolled chains matching the CTE ranking contract instead.
- [x] `make load PLATFORM=hydra`; `make rebuild PLATFORM=hydra` (relational → projections)
- [x] Bench at concurrency 1/8/32; ops metrics (ingest/rebuild wall time, container count, peak RSS, on-disk size)
- [x] Cross-platform report: Lyra vs Orion vs Hydra quality equivalence + latency/footprint table

## Verification

```
make up PLATFORM=hydra && make load PLATFORM=hydra
uv run pytest tests/conformance -k "qdrant or memgraph"
make rebuild PLATFORM=hydra            # completes; row/point/edge counts match
make bench PLATFORM=hydra && make report
```

## Artifacts

`compose/hydra.yml`, two adapters, rebuild path,
`bench/results/hydra-*.json` (committed), cross-platform report.

## Progress log

- 2026-08-04 — Phase opened on `feat/hydra`. Infra up: `compose/hydra.yml`
  (postgres:18.4 @15433, qdrant v1.18.3 @16333/16334, memgraph 3.12.0
  @17687, project `constellate-hydra`, all healthchecks green).
  `--storage-light-edge=true` verified compatible with edge properties
  (edge_type/weight round-trip via mgconsole). Deps: qdrant-client 1.18.0,
  neo4j 6.2.0. `make rebuild` target added (projections from relational —
  the CDC proof). Note: ADR 0005 pinned Memgraph 3.12 = image 3.12.0;
  qdrant healthcheck uses bash /dev/tcp (image ships no curl).
- 2026-08-04 — Adapters + loader landed (parallel subagent build; Fable
  design/verify). Conformance 40 green incl. qdrant/memgraph params.
  Memgraph ranking contract pre-proven: 432-case differential vs CteGraph,
  identical at hops 1–2. Full load 98.9s; rebuild-from-postgres 41s,
  counts verified across engines; idempotence proven. Two incidents,
  both now lessons (L10, L11 in research 09): qdrant silently ran
  brute-force (default indexing_threshold never triggered at 62k points
  / 8 segments — HNSW config moved into adapter, forced build), and
  memgraph's variable-length + `IN`-seed query hung >312s on production
  data (planner ignores :Node(key) index for IN; DFS path explosion
  through hubs) — rewritten as UNWIND-anchored flat chains per hop.
- 2026-08-04 — Independent adversarial review (fresh context, live-engine
  probes): 2 major, 8 minor, 6 nits. Majors: qdrant projection count
  "verification" compared postgres to itself (tautology — could never
  fail) and no index-state barrier/record (bench could measure an
  unindexed collection; artifact still listed kuzu/faiss versions for a
  hydra run). Ranking contract independently confirmed sound (68/68
  adversarial differential cases vs CteGraph). All majors + minors
  queued as fixes; first bench run discarded, clean re-run after fixes
  (L7's "review before the bench" — cost accepted, again). Note: m8 fix
  moves `bench.quality_tolerance` out of `engines`, so orion/hydra
  config fingerprints change vs the committed phase-05 artifacts —
  intended; old artifacts remain valid snapshots of their configs.
- 2026-08-04 — All review fixes landed (0b36d7c: real qdrant count
  verification, HNSW index barrier, artifact engine_state, leak-proofing,
  committed parity test — 48 conformance green). Clean bench:
  `hydra-0b36d7c-20260804T134236Z` — GO (hybrid vs vector p=0.0038);
  graph_only R@10 0.0965 identical to all prior engines to 4 decimals;
  equivalence gate within ±0.02 of Lyra (−0.0017 R@10); p50 115ms flat
  at concurrency 1/8/32, sustained 11.6Hz (1.2× estimated capacity)
  without saturating. Determinism note: unseeded multi-threaded qdrant
  HNSW build shifts hybrid metrics slightly between rebuilds (nDCG@10
  0.0353→0.0337, drift originating in the vector arm) — an L9 boundary
  lyra's seeded hnswlib build doesn't have; equivalence gate unaffected.
