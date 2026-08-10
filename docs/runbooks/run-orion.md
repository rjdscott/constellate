# Run Orion (the unified knowledge plane)

## When to use

Bringing up Orion, one Postgres 18 container serving all three planes
(ADR 0004), loading it from canonical data, verifying conformance, running
flows/API/bench against it, or switching its graph adapter (CTE ↔ AGE).

## Steps

1. Build + start the container (image = AGE 1.7.0 base + PGDG pgvector
   0.8.6; first build downloads ~600 MB):

   ```sh
   make up PLATFORM=orion
   ```

   Expected: `Container constellate-orion Healthy`. Port convention: host
   `15432` (= engine default + 10000, so every platform can run at once).
   Override with `ORION_DSN` if taken.

2. Load canonical data (idempotent; `make seed` first if `data/canonical/`
   is missing):

   ```sh
   make load PLATFORM=orion
   ```

   Expected (fresh volume, ~90 s total): interactions 25,000,095 rows in
   ~45 s, graph_edges 1,684,608, hnsw_index ~3 s, age_graph ~8 s, then
   `load: orion ready`. Steps skip with `up to date` on reruns; full
   rebuild = `make down PLATFORM=orion && docker volume rm
   constellate-orion_orion-data`.

3. Conformance (orion adapters register automatically when the DB answers):

   ```sh
   uv run pytest tests/conformance -q     # 32 passed — includes postgres/pgvector/cte/age
   ```

4. Smoke + API:

   ```sh
   make bench-smoke PLATFORM=orion
   PLATFORM=orion uv run uvicorn constellate.api.app:app --port 8000
   ```

5. Switch graph adapter for the AGE arm: edit `config/orion.yaml`
   `engines.graph.adapter: cte → age` (changes the config fingerprint:
   that's the point: it is a different measured system), rerun smoke/bench.

6. Benchmark (see `run-benchmarks.md` for the harness itself):

   ```sh
   make bench PLATFORM=orion && make report
   ```

   The report's equivalence table compares Orion's hybrid arm to Lyra's
   within the tolerance stated in `config/orion.yaml` (top-level `bench`).

## Failure modes

- **`could not resize shared memory segment ... No space left on device`
  during load**: pgvector's parallel HNSW build needs shm ≥
  `maintenance_work_mem`; compose sets `shm_size: 4g` for this reason.
  Hit 2026-08-04 with `shm_size: 1g`.
- **`File or path does not exist [/tmp/age//...]` during load**: AGE 1.7
  jails `load_labels_from_file`/`load_edges_from_file` paths under
  `/tmp/age/` on the **server**; the compose file bind-mounts
  `data/orion/age-import` to `/tmp/age/age-import`. A remote DSN needs the
  CSVs shipped to the server's `/tmp/age/` yourself. Hit 2026-08-04.
- **`Invalid input parameter types for agtype_mul` from the AGE adapter**:
  the CSV bulk loader lands numeric properties as agtype *strings*; any
  multi-hop weight product must go through `toFloat()` (the adapter does;
  don't remove it). Hit 2026-08-04.
- **`type "halfvec" does not exist`**: fresh volume without extensions;
  `make load` creates them, and the conformance probe bootstraps them too.
  Seen after the compose project rename orphaned the old volume.
- **Port 15432 taken**: set `ORION_DSN` and map another host port; the
  scheme (default+10000) exists precisely so 5432-range clashes don't bite.
- **Tables vanish on reload / `relation "item_vectors" does not exist`
  right after `load: orion ready`**: `search_path` defaults to
  `"$user", public`, the role is `constellate`, and AGE's graph schema is
  *also* named `constellate` (created by the age_graph step). Any reload
  after that schema exists sends unqualified CREATEs into the graph
  schema, where `drop_graph(cascade)` then destroys them. The loader now
  pins `SET search_path = public`; if you see this on an old checkout,
  that's the fix. Symptom fingerprint: a `load_manifest` row stamped
  today next to siblings stamped earlier, and `db.schema.table` triples
  like `constellate.constellate.interactions` in the server log. Hit
  2026-08-05 mid bench matrix (see lessons L14).

## Last verified

2026-08-05: phase 08, PG 18.1 / AGE 1.7.0 / pgvector 0.8.6, svd + neural
arm loads green, dim-change rebuild verified (256 → 384 → 256).
