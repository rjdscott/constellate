# Run Lyra end to end

## When to use

Bringing up Lyra, the embedded knowledge plane, locally or on a fresh
clone. No docker, no daemon; everything is in-process.

## Steps

1. Build data + platform stores (both idempotent):

   ```bash
   make seed                  # canonical parquet (see seed-the-dataset.md)
   make load PLATFORM=lyra    # npy vectors + hnsw.bin + kuzu graph → data/lyra/
   ```

   Expect on first load: `kuzu graph 58,552 nodes, 1,684,608 directed edges`.

2. Prove the three flows:

   ```bash
   make bench-smoke PLATFORM=lyra
   ```

   Expect `smoke: all flows green` with per-step timings and an explained
   reason per flow (e.g. `item:318 → CO_RATED → item:356`).

3. Serve the REST API:

   ```bash
   uv run uvicorn constellate.api.app:app
   curl -s localhost:8000/v1/health
   curl -s -X POST localhost:8000/v1/similar \
     -H 'content-type: application/json' \
     -d '{"seed_item_id":318,"k":10,"explain":true}'
   ```

   Every response carries `timings` + `config_fingerprint`: quote both when
   reporting any number.

4. Switch the vector adapter (ADR 0002 ablation): edit `config/lyra.yaml`
   `engines.vector.adapter` to `hnsw`, restart. The fingerprint changes:
   results are no longer comparable to `flat` runs by construction.

## Failure modes

- `no lyra artifacts — run make seed && make load`: factory found no
  `data/lyra/`; run step 1.
- Graph queries take minutes instead of milliseconds after touching
  `planes/graph/kuzu.py`: you probably reintroduced a kuzu planner trap.
  Prepared `$params`, `list_contains()`, or any extra predicate on the far
  node of a recursive match all silently disable predicate pushdown
  (2026-08-04 incident, phase-03 progress log). Keep literals + `IN`, filter
  in Python, and always re-run `make bench-smoke`: conformance tests won't
  catch it.
- `Cannot execute write operations in a read-only database`: something
  called DDL/upsert on the served graph; the factory opens kuzu read-only by
  design. Rebuild via `make load`, don't write at runtime.

## Last verified

2026-08-04: phase 03 (`feat/lyra`), full clean-clone sequence on the
benchmark machine.
