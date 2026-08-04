# Run Hydra (the composed knowledge plane)

## When to use

Bringing up Hydra — dedicated engines per plane (ADR 0005): Postgres 18
(source of truth) + Qdrant (vector) + Memgraph (graph) — loading it from
canonical data, proving the derived-projection rebuild, or verifying engine
health after a load.

## Steps

1. Start the three containers (project `constellate-hydra`; ports = engine
   default + 10000 so every platform runs simultaneously — Postgres `15433`,
   Qdrant `16333` REST / `16334` gRPC, Memgraph `17687`):

   ```sh
   make up PLATFORM=hydra
   ```

   Expected: all three healthchecks green (`docker compose -f
   compose/hydra.yml ps`). Override a DSN/URI if a port is taken:
   `HYDRA_DSN`, `HYDRA_QDRANT_URL`, `HYDRA_MEMGRAPH_URI`.

2. Load canonical data (`make seed` first if `data/canonical/` is missing).
   Postgres steps are manifest-gated and idempotent; the projection rebuild
   at the end always runs:

   ```sh
   make load PLATFORM=hydra
   ```

   Expected (fresh volumes, ~99 s total): items 62,423/0.6 s, users
   156,604/0.2 s, interactions 25,000,095/40.7 s, item_vectors 62,423/2.3 s,
   user_vectors 156,604/6.0 s, graph_edges 1,684,608/5.0 s, then a chained
   rebuild (~41 s) projects Postgres into Qdrant + Memgraph.

3. Rebuild the projections on their own — drops and regenerates Qdrant +
   Memgraph from Postgres alone, nothing else touched. This is the CDC-shape
   proof (ADR 0005). Idempotent and safe to re-run whenever nothing is
   *serving* — it is **not** atomic: collections and the graph are deleted
   before they are repopulated, so queries during the ~40 s window (or after
   a crash mid-rebuild) hit a missing collection / empty graph until the
   next successful rebuild. Stop the API first. (Revisit with staged
   Qdrant aliases + label swap if Hydra ever serves during rebuilds.)

   ```sh
   make rebuild PLATFORM=hydra
   ```

   Expected: ~41 s (Qdrant items ~8 s, users ~20 s, CSV export ~2 s;
   Memgraph wipe ~1.5 s, nodes <1 s, edges ~8 s).

4. Full reset (drop everything, including Postgres — the source of truth):

   ```sh
   make down PLATFORM=hydra
   docker volume rm constellate-hydra_hydra-pg constellate-hydra_hydra-qdrant constellate-hydra_hydra-memgraph
   ```

5. Verify health per engine:

   Qdrant — check the collection actually indexed, not just that it answers:

   ```sh
   curl -s http://localhost:16333/collections/items | python3 -m json.tool
   ```

   Expect `status: "green"` and `indexed_vectors_count` ≈ `points_count`
   (61,440 / 62,423 on a full load — the tail segment under the indexing
   threshold stays plain, that's expected, not a bug).

   Memgraph — edge count:

   ```sh
   echo "MATCH ()-[r:REL]->() RETURN count(r);" | docker exec -i constellate-hydra-memgraph-1 mgconsole
   ```

   Expect `1684608`.

   Postgres — load manifest:

   ```sh
   docker exec -i constellate-hydra-postgres-1 psql -U constellate -d constellate -c "SELECT step, rows, completed_at FROM load_manifest ORDER BY completed_at;"
   ```

6. Stop:

   ```sh
   make down PLATFORM=hydra
   ```

## Footprint (measured 2026-08-04, post-load)

- 3 containers; idle RSS ≈ 2.3 GiB (Postgres 1.57 GiB, Memgraph 378 MiB,
  Qdrant 335 MiB).
- Volumes ≈ 9.9 GB total (hydra-pg 6.51 GB, hydra-memgraph 2.07 GB,
  hydra-qdrant 1.32 GB).
- Compare Orion (one container, 794 MiB RSS, 6.8 GB volume) and Lyra
  (in-process, 348 MB on disk) — Hydra's cost is the price of dedicated,
  independently-scalable engines per plane.

## Failure modes

- **Qdrant silently ran brute-force, `indexed_vectors_count: 0` at 62,423
  points over 8 segments.** Qdrant's default `indexing_threshold` is 20,000
  *per segment*; 8k-point segments never cross it, so HNSW never builds and
  every query falls back to exact search without error. Diagnose with the
  `collections/items` curl above — `indexed_vectors_count` stuck at 0 (or far
  below `points_count`) with `status: green` is the tell, since Qdrant
  considers brute-force a valid served state. Fix: the collection config is
  adapter-owned, not a runtime toggle — `src/constellate/planes/vector/qdrant.py`
  sets `INDEXING_THRESHOLD = 1000` (with `M=16`, `EF_CONSTRUCTION=200`) on
  `ensure_collections`. Rerun `make rebuild PLATFORM=hydra` to apply it to an
  existing collection (config is set at creation time). Hit 2026-08-04.
- **Memgraph query hang: `[*1..2]` variable-length expansion with
  `WHERE s.key IN $seeds` ran >312 s at 100% of one core, no result.**
  Diagnose live with `SHOW TRANSACTIONS;` via mgconsole to find the stuck
  query's id, then kill it with `TERMINATE TRANSACTIONS "<id>";` — don't
  restart the container, the transaction is what's pinned. Root cause: the
  `IN` form makes Memgraph's planner skip the `:Node(key)` index entirely
  (plan is `ScanAll(d) -> Expand -> Filter s.key`, ~962k edges read before
  the filter even runs), and `[*1..2]` on top of that does per-path DFS
  materialisation through hub nodes (`genre:Drama` alone has 25,606 edges).
  Fix: adapter rewritten (`src/constellate/planes/graph/memgraph.py`) to
  anchor with `UNWIND $seeds AS sk MATCH (s:Node {key: sk})` (compiles to
  index lookups per seed) and to unroll hops into flat chains — one MATCH
  per hop, aggregated in-engine — instead of a variable-length pattern. The
  flat 2-hop equivalent on the same seeds: 629 ms.
- **`DROP GRAPH` rejected: "can only be used in the analytical mode".**
  Memgraph's fast whole-graph drop requires switching the instance out of
  transactional storage mode, which we don't want to do on a durable
  instance mid-operation. `rebuild_hydra()` in `src/constellate/load_hydra.py`
  uses batched `MATCH (n:Node) WITH n LIMIT $b DETACH DELETE n` instead —
  slower, but keeps every transaction bounded and the instance in normal
  mode throughout. Don't "fix" this by toggling storage mode.
- **`max_hops=3` on hub-heavy seeds took ~124 s.** Not a hang — expected
  fan-out. The 10 popular seeds alone generate 2.98M 2-hop paths through hub
  nodes; a third hop multiplies that by another hub's degree, and `support`
  is defined as counting every path, so there's nothing to short-circuit.
  `RetrievalRequest` defaults `max_hops=2`; treat 3 as a small-seed/typed-edge
  option, never a default for open-ended expansion.

## Last verified

2026-08-04 — phase 06, Postgres 18.4 / Qdrant v1.18.3 / Memgraph 3.12.0,
full load + rebuild verified, qdrant/memgraph conformance green.
