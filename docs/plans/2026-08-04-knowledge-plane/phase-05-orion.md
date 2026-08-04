# Phase 05 — Orion, the unified knowledge plane

## Goal

One Postgres 18 container serving all three planes (ADR 0004): Dockerfile
based on `apache/age:release_PG18_1.7.0` + PGDG pgvector; Postgres
relational adapter; pgvector adapter (HNSW on halfvec, iterative scans for
filtered queries); TWO graph adapters — recursive-CTE/self-join edge tables
(default) and AGE openCypher — both passing the unchanged conformance suite.
`make up load bench PLATFORM=orion` produces a result JSON with quality metrics
matching Lyra within tolerance, proving the abstraction holds.

## Tasks

- [ ] `docker/orion/Dockerfile` (~6 lines: AGE base + `postgresql-18-pgvector`), `compose/orion.yml`, pinned tags
- [ ] `planes/relational/postgres.py` (asyncpg)
- [ ] `planes/vector/pgvector.py` — halfvec HNSW, `iterative_scan=relaxed_order`, exclusion via `NOT IN`/anti-join
- [ ] `planes/graph/cte.py` — covering index `(src, edge_type) INCLUDE (dst, weight)`, per-hop top-k LATERAL, explicit self-joins for fixed 2–3 hop
- [ ] `planes/graph/age.py` — same conformance suite, unchanged
- [ ] `make load PLATFORM=orion`; `make up/down PLATFORM=orion`
- [ ] Bench run; quality-equivalence check vs Lyra (tolerance stated in config)

## Verification

```
make up PLATFORM=orion && make load PLATFORM=orion
uv run pytest tests/conformance -k "postgres or pgvector or cte or age"
make bench PLATFORM=orion && make report   # quality within tolerance of Lyra; CTE-vs-AGE latency delta visible
```

## Artifacts

`docker/orion/Dockerfile`, `compose/orion.yml`, four adapters,
`bench/results/orion-*.json` (committed).

## Progress log
