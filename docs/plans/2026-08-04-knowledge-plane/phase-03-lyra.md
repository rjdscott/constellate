# Phase 03 — Lyra (embedded) end-to-end

## Goal

Full pipeline with no daemon and no docker: DuckDB relational adapter,
exact-flat vector adapter (faiss.IndexFlatIP, mmap persistence) plus hnswlib
ANN adapter (ADR 0002), Kuzu 0.11.3 graph adapter (ADR 0003), the shared
service layer, and the FastAPI REST surface (`/v1/recommend|similar|explain|
health|stats` with per-step timings + config fingerprint). Flows F1–F3 run
end to end from a fresh clone: `make seed load bench-smoke PLATFORM=lyra`.

## Tasks

- [ ] Conformance tests written/unskipped FIRST per plane, then adapters:
- [ ] `planes/relational/duckdb.py` — user context, hydrate, policy gates, exclusions
- [ ] `planes/vector/flat.py` (faiss IndexFlatIP + IDSelectorNotMember) and `planes/vector/hnsw.py` (hnswlib pinned single-thread+seed, installed from v0.9.0 tag)
- [ ] `planes/graph/kuzu.py` — expand with paths, path_between, upsert_edges
- [ ] `make load PLATFORM=lyra` from canonical parquet
- [ ] `pipeline.py` wired via config factory; steps 2+3 concurrent where independent; per-step timings recorded
- [ ] `service.py` + `api/` routes; every response carries timings + fingerprint
- [ ] F1 (similar), F2 (personalised top-N), F3 (cold-start) smoke flows

## Verification

```
make check
make load PLATFORM=lyra && uv run pytest tests/conformance -k "duckdb or flat or hnsw or kuzu"
uv run uvicorn kp.api.app:app &  # then:
curl -s localhost:8000/v1/similar -d '{"seed_item_id":318,"k":10,"explain":true}' | jq .[0].reason
```

## Artifacts

`src/kp/planes/{relational,vector,graph}/*`, `src/kp/service.py`,
`src/kp/api/*`, `data/lyra/` index files, passing conformance suite.

## Progress log
