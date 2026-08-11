# Phase 05: Orion, the unified knowledge plane

## Goal

One Postgres 18 container serving all three planes (ADR 0004): Dockerfile
based on `apache/age:release_PG18_1.7.0` + PGDG pgvector; Postgres
relational adapter; pgvector adapter (HNSW on halfvec, iterative scans for
filtered queries); TWO graph adapters: recursive-CTE/self-join edge tables
(default) and AGE openCypher, both passing the unchanged conformance suite.
`make up load bench PLATFORM=orion` produces a result JSON with quality metrics
matching Lyra within tolerance, proving the abstraction holds.

## Tasks

- [x] `docker/orion/Dockerfile` (~6 lines: AGE base + `postgresql-18-pgvector`), `compose/orion.yml`, pinned tags
- [x] `planes/relational/postgres.py` (asyncpg)
- [x] `planes/vector/pgvector.py`: halfvec HNSW, `iterative_scan=relaxed_order`, exclusion via `NOT IN`/anti-join
- [x] `planes/graph/cte.py`: covering index `(src, edge_type) INCLUDE (dst, weight)`, explicit self-joins for fixed 2–3 hop (full per-hop aggregation kept over top-k LATERAL: mirrors kuzu support semantics exactly, see progress log)
- [x] `planes/graph/age.py`: same conformance suite, unchanged
- [x] `make load PLATFORM=orion`; `make up/down PLATFORM=orion`
- [x] Bench run; quality-equivalence check vs Lyra (tolerance stated in config): both arms within ±0.02 (report equivalence table); CTE-vs-AGE delta measured ~6×

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

- 2026-08-04: Phase opened on `feat/orion`. Container live first try:
  PG 18.1 + AGE 1.7.0 + pgvector 0.8.6 (image = AGE base + PGDG pgvector,
  never compile AGE: ADR 0004 held up). Compose hardening after user
  request: explicit per-platform project names (`name: constellate-orion`:
  without it compose namespaces every platform under the *directory*
  name and they collide) and the port convention host = engine default +
  10000 (orion 15432; 5433/5434 were already taken locally, proving the
  point). All four adapters passed the unchanged conformance suite on
  first live run: 32 passed, zero skips. Contrast for the talk: kuzu
  needed three planner-trap rewrites; Postgres pushed every `$n` parameter
  plan without drama.
- 2026-08-04: Load path: 25M interactions COPY in 43 s, HNSW halfvec
  build 3 s (after `shm_size: 4g`: parallel build wants shm ≥
  maintenance_work_mem), AGE graph bulk-loaded 1.68M edges in 7 s via
  `load_edges_from_file` (jailed under `/tmp/age/` in 1.7: bind mount
  moved there; numeric CSV properties land as agtype *strings*, so the
  adapter multiplies through `toFloat()`; the loader's node linkage column
  must be literally `id`, so the adapter's node property is `key`). All
  incidents recorded in `docs/runbooks/run-orion.md` failure modes.
  Design decision (documented deviation from task wording): CTE stage-1
  keeps *full* per-hop aggregation instead of top-k LATERAL fan-out
  limiting: support counts then match kuzu exactly, which the
  quality-equivalence gate needs; LATERAL stays in research 03 as the
  optimization lever if stage-1 latency ever matters. mypy caught a real
  bug pre-commit: a pandas column named `count` shadows the namedtuple
  method in `itertuples`: records now built by column zip.
  Smoke: CTE F1 141 ms / F2 633 ms / F3 64 ms; AGE F1 404 ms / F2
  1484 ms / F3 238 ms: the CTE-vs-AGE delta is already visible and AGE
  explanations tie-break differently on equal-weight paths (Adventure vs
  Sci-Fi genre hop to the same item). `build_service` went async (asyncpg
  pool); CI now builds the orion image and runs conformance against it.
- 2026-08-04: **CTE-arm bench**: ablation gate re-confirmed (hybrid vs
  vector_only R@10 +0.0267, p=4.1e-06); **graph_only identical to Lyra to
  4 decimals on every metric and kind**: the abstraction holds exactly
  where the contract promises; vector_only halves (pgvector HNSW/halfvec
  recall vs faiss exact, concentrated on cold_start) yet hybrid lands
  within tolerance (+0.0021 R@10). Latency upset: Orion ~3× *faster* than
  Lyra (p50 43 ms vs 127 ms) and the 1.2× "saturation" run didn't
  saturate: separate-process Postgres serves concurrently; the embedded
  ceiling was the single process, not the missing network hop.
- 2026-08-04: **Independent review: 2 major, 5 minor; all fixed.**
  Majors: load steps weren't atomic with their manifest marks (crash +
  rerun would silently duplicate COPYed interactions: "idempotent" was
  false under failure; now one transaction per step) and CI could go
  green with orion conformance silently deregistered (socket-only init
  server can fool `pg_isready`; healthcheck now forces TCP and
  ORION_REQUIRED=1 makes the probe raise in CI). Minors: dollar-quote
  breakout guard in AGE cypher, factory timeout/pool-leak handling,
  conformance pool teardown, DSNs stripped from committed artifacts,
  unused pgvector dep dropped, "mirrors kuzu exactly" docstrings scoped
  to ranking equivalence. AGE-arm bench (2,000 latency samples,
  disclosed) running.
- 2026-08-04: **AGE-arm bench + phase close.** Quality identical to the
  CTE arm on every metric (fourth adapter producing graph R@10 0.0965 to
  4 decimals: ranking-contract equivalence total); latency CTE ~6×
  faster than AGE (p50 43.6 ms vs 243.8 ms): the ADR 0004 published
  delta, measured; thesis correctly rests on the CTE adapter. Equivalence
  vs Lyra: hybrid +0.0021 R@10 / +0.0002 nDCG@10, within ±0.02 tolerance:
  **the abstraction holds**. Artifacts committed (2 orion runs),
  report regenerated with cross-platform equivalence table, findings doc
  08 complete, lessons L2/L3/L5 appended to 09, narrative milestone
  written. Phase gate walked; 🟢.
