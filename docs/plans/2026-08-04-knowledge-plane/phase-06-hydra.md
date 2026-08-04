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
- [ ] `planes/vector/qdrant.py` (async client, exclusion via filter)
- [ ] `planes/graph/memgraph.py` — neo4j async driver, `[*wShortest]` for weighted paths
- [ ] `make load PLATFORM=hydra`; `make rebuild PLATFORM=hydra` (relational → projections)
- [ ] Bench at concurrency 1/8/32; ops metrics (ingest/rebuild wall time, container count, peak RSS, on-disk size)
- [ ] Cross-platform report: Lyra vs Orion vs Hydra quality equivalence + latency/footprint table

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
