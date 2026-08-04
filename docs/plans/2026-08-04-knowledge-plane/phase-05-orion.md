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

- [x] `docker/orion/Dockerfile` (~6 lines: AGE base + `postgresql-18-pgvector`), `compose/orion.yml`, pinned tags
- [x] `planes/relational/postgres.py` (asyncpg)
- [x] `planes/vector/pgvector.py` — halfvec HNSW, `iterative_scan=relaxed_order`, exclusion via `NOT IN`/anti-join
- [x] `planes/graph/cte.py` — covering index `(src, edge_type) INCLUDE (dst, weight)`, explicit self-joins for fixed 2–3 hop (full per-hop aggregation kept over top-k LATERAL: mirrors kuzu support semantics exactly, see progress log)
- [x] `planes/graph/age.py` — same conformance suite, unchanged
- [x] `make load PLATFORM=orion`; `make up/down PLATFORM=orion`
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

- 2026-08-04 — Phase opened on `feat/orion`. Container live first try:
  PG 18.1 + AGE 1.7.0 + pgvector 0.8.6 (image = AGE base + PGDG pgvector,
  never compile AGE — ADR 0004 held up). Compose hardening after user
  request: explicit per-platform project names (`name: constellate-orion`
  — without it compose namespaces every platform under the *directory*
  name and they collide) and the port convention host = engine default +
  10000 (orion 15432; 5433/5434 were already taken locally, proving the
  point). All four adapters passed the unchanged conformance suite on
  first live run — 32 passed, zero skips. Contrast for the talk: kuzu
  needed three planner-trap rewrites; Postgres pushed every `$n` parameter
  plan without drama.
- 2026-08-04 — Load path: 25M interactions COPY in 43 s, HNSW halfvec
  build 3 s (after `shm_size: 4g` — parallel build wants shm ≥
  maintenance_work_mem), AGE graph bulk-loaded 1.68M edges in 7 s via
  `load_edges_from_file` (jailed under `/tmp/age/` in 1.7 — bind mount
  moved there; numeric CSV properties land as agtype *strings*, so the
  adapter multiplies through `toFloat()`; the loader's node linkage column
  must be literally `id`, so the adapter's node property is `key`). All
  incidents recorded in `docs/runbooks/run-orion.md` failure modes.
  Design decision (documented deviation from task wording): CTE stage-1
  keeps *full* per-hop aggregation instead of top-k LATERAL fan-out
  limiting — support counts then match kuzu exactly, which the
  quality-equivalence gate needs; LATERAL stays in research 03 as the
  optimization lever if stage-1 latency ever matters. mypy caught a real
  bug pre-commit: a pandas column named `count` shadows the namedtuple
  method in `itertuples` — records now built by column zip.
  Smoke: CTE F1 141 ms / F2 633 ms / F3 64 ms; AGE F1 404 ms / F2
  1484 ms / F3 238 ms — the CTE-vs-AGE delta is already visible and AGE
  explanations tie-break differently on equal-weight paths (Adventure vs
  Sci-Fi genre hop to the same item). `build_service` went async (asyncpg
  pool); CI now builds the orion image and runs conformance against it.
