# Phase 03 — Lyra (embedded) end-to-end

## Goal

Full pipeline with no daemon and no docker: DuckDB relational adapter,
exact-flat vector adapter (faiss.IndexFlatIP, mmap persistence) plus hnswlib
ANN adapter (ADR 0002), Kuzu 0.11.3 graph adapter (ADR 0003), the shared
service layer, and the FastAPI REST surface (`/v1/recommend|similar|explain|
health|stats` with per-step timings + config fingerprint). Flows F1–F3 run
end to end from a fresh clone: `make seed load bench-smoke PLATFORM=lyra`.

## Tasks

- [x] Conformance tests written/unskipped FIRST per plane, then adapters:
- [x] `planes/relational/duckdb.py` — user context, hydrate, policy gates, exclusions
- [x] `planes/vector/flat.py` (faiss IndexFlatIP; exclusion via `IDSelectorNot(IDSelectorBatch)` — the ADR's `IDSelectorNotMember` does not exist in faiss 1.15) and `planes/vector/hnsw.py` (hnswlib pinned single-thread+seed, installed from v0.9.0 tag)
- [x] `planes/graph/kuzu.py` — expand with paths, path_between, upsert_edges
- [x] `make load PLATFORM=lyra` from canonical parquet
- [x] `pipeline.py` wired via config factory; steps 2+3 concurrent where independent; per-step timings recorded
- [x] `service.py` + `api/` routes; every response carries timings + fingerprint
- [x] F1 (similar), F2 (personalised top-N), F3 (cold-start) smoke flows

## Verification

```
make check
make load PLATFORM=lyra && uv run pytest tests/conformance -k "duckdb or flat or hnsw or kuzu"
uv run uvicorn constellate.api.app:app &  # then:
curl -s localhost:8000/v1/similar -d '{"seed_item_id":318,"k":10,"explain":true}' | jq .[0].reason
```

## Artifacts

`src/constellate/planes/{relational,vector,graph}/*`, `src/constellate/service.py`,
`src/constellate/api/*`, `data/lyra/` index files, passing conformance suite.

## Progress log

- 2026-08-04 — Phase opened on `feat/lyra`. Order: deps → vector adapters
  (flat, hnsw) → duckdb relational → kuzu graph (conformance per plane as
  each lands) → `make load` → factory/service/API → smoke flows → gate.
- 2026-08-04 — All four adapters landed; conformance suite fully unskipped
  (36 passed / 0 skipped — the 12-skip progress bar hit zero). Deps resolved
  live: duckdb 1.5.5, faiss 1.15.0, hnswlib 0.9.0 (git tag per ADR 0002),
  kuzu 0.11.3 pinned, fastapi 0.141.1. `make load PLATFORM=lyra`: mmap npy
  vector store, hnsw.bin, kuzu graph of 58,552 nodes / 1,684,608 directed
  edges (RATED excluded from the graph — relational's data; revisit if
  phase 04 wants user-seeded walks). Smoke: F1 139ms / F2 345ms / F3 132ms,
  all explained.
- 2026-08-04 — The phase's teaching centerpiece: **the naive graph expand
  hung for minutes** on the first real query. Chain of three causes, each a
  kuzu-planner lesson (adapter docstring + comments carry the detail):
  (1) streaming 321,055 two-hop paths from one seed into Python — fixed by
  a two-stage query: aggregate ranking (hops, support) inside kuzu, then
  SHORTEST paths only for the winners; (2) prepared-statement `$params` and
  `list_contains()` both block predicate pushdown in recursive matches —
  literals + `IN` restore the ~70ms anchored plan; (3) ANY extra predicate
  on the far node (`NOT IN`, even a single `<>`) re-triggers the full-graph
  walk — seed exclusion moved to Python over an over-fetched LIMIT.
  Conformance tests stayed green through all three failures — tiny graphs
  cannot catch planner regressions; only the real 1.7M-edge graph did.
- 2026-08-04 — Deviations written in: faiss exclusion API is
  `IDSelectorNot(IDSelectorBatch(...))` (ADR 0002's `IDSelectorNotMember`
  never existed in 1.15); kuzu read-only databases reject even
  `CREATE ... IF NOT EXISTS`, so schema init is an adapter flag; hnswlib
  raises when a filter leaves fewer than k reachable results — k clamps to
  the tracked id-set size. Verified: `make check` green, live API
  (health/similar/explain/stats) curl-checked with timings + fingerprint.
