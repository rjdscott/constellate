# 01: Graph engine for the mid tier; Kuzu status (researched 2026-08-04)

Context: docker-compose on 28-core/62GB Linux; ml-25m derived graph (~62k
movie + ~162k user nodes, 5–20M edges); 2–3-hop expansion, path-between,
weighted edges; Python async client; benchmarked p50/p95/p99.

## FalkorDB (4.20, Jul 2026)

- **License:** SSPL v1, source-available, **not** OSI open source. Fine for
  a benchmark/demo; cannot be called "open source" on stage without caveat.
- **Cypher:** openCypher-9 subset + extensions (`algo.SPpaths` weighted
  paths, v4.20 reworked variable-length traversal). Gaps: no regex, no label
  expressions, no temporal arithmetic, no UDFs
  ([coverage](https://docs.falkordb.com/cypher/cypher-support.html)).
- **Memory:** GraphBLAS sparse matrices in Redis: most compact in the
  independent AIMultiple test (496MB vs Neo4j 2.7GB for 381k/804k graph).
  Image ~152MB.
- **Client:** `falkordb-py` with `falkordb.asyncio`. ⚠️ **v4.20 (Jul 2026)
  removed Bolt**: RESP only; neo4j driver no longer works against it
  ([releases](https://github.com/FalkorDB/FalkorDB/releases)).
- **Performance:** fastest on 11/12 queries in the only independent 3-way
  benchmark ([AIMultiple](https://aimultiple.com/graph-databases)); 2-hop
  ~2.9x faster than Neo4j. **Concurrency flattens past ~8 threads** (Redis
  single main thread; writes serialize). Vendor "500x" numbers: skeptical.
- **Ops/health:** instant start, RDB/AOF; releases every 1–2 weeks, v4.20.1
  2026-07-15.

## Neo4j Community (2026.06)

- **License:** GPLv3, only OSI-approved option of the three.
- **Versioning changed:** CalVer since Jan 2025 (2025.01…2026.06); **5.26 is
  LTS** (to Jun 2028); Cypher language versioned separately (Cypher 5 vs
  Cypher 25) ([blog](https://neo4j.com/blog/developer/neo4j-graph-database-versioning/)).
- **Cypher:** reference implementation, fullest coverage. Weighted shortest
  paths need APOC/GDS.
- **CE limits:** single DB, no clustering, offline-only backup, **parallel
  Cypher runtime disabled in CE**: multi-hop queries single-threaded;
  scaling levels off ~4 cores
  ([CE limitations](https://community.neo4j.com/t/neo4j-community-edition-limitations-deep-dive/71005)).
- **Memory:** JVM heap + page cache; heaviest (2.7GB in test). Image ~374MB.
  JVM boot in seconds.
- **Client:** official `neo4j` v6 driver, best-maintained graph client,
  first-class async.
- **Performance:** consistently slowest for in-memory-scale multi-hop; its
  disk/page-cache architecture targets datasets ≫ RAM, which ml-25m is not.

## Memgraph Community (3.12, Jul 2026)

- **License:** BSL 1.1 (→ Apache 2.0 at Change Date, currently 2030).
  Internal/production use permitted; DBaaS excluded. Source-available, not
  OSI ([BSL.txt](https://github.com/memgraph/memgraph/blob/master/licenses/BSL.txt)).
- **Cypher:** high openCypher compliance + **first-class `[*wShortest]`,
  `[*BFS]` syntax**: weighted shortest path in the language, directly
  matching weighted CO_RATED edges. MAGE algorithm library.
- **Memory:** in-memory C++ (skip-list); RAM ≈ 2× data; ~20M edges ⇒ ~5–15GB,
  fine on 62GB. **v3.12 added `--storage-light-edge`** for edge-heavy
  graphs. Lowest RSS in independent test (415MB). Image ~221MB.
- **Client:** speaks **Bolt**: official recommendation is the standard
  `neo4j` async Python driver
  ([quickstart](https://memgraph.com/docs/client-libraries/python)). One
  driver codebase covers Memgraph *and* Neo4j: client-fair benchmark.
- **Performance:** second to FalkorDB on latency (tested on old 2.21, a
  generation behind 3.12, treat as floor), well ahead of Neo4j; C++
  multi-threaded execution scales across cores: matters for p95/p99 under
  concurrent load on 28 cores.
- **Ops/health:** snapshot+WAL, starts in seconds; monthly releases → v3.12
  2026-07-15.

## Kuzu (tier0 embedded): what actually happened

- Repo **archived 2025-10-10**, final release **v0.11.3** same day
  ([The Register](https://www.theregister.com/software/2025/10/14/kuzudb-graph-database-abandoned-community-mulls-options/1142229)).
- Reason surfaced Feb 2026: EU DMA filing shows **Apple agreed 2025-10-09 to
  acquire Kùzu Inc.** No public plans.
- **Still safe embedded:** MIT license; v0.11.3 deliberately bundles common
  extensions (older versions may fail extension downloads). Pin
  `kuzu==0.11.3`, note unmaintained.
- **Forks:** **LadybugDB** ("DuckDB for graphs", v0.17.0 May 2026, active
  through Jul 2026: most active successor,
  [overview](https://szarnyasg.org/posts/kuzu-forks/)); bighorn (Kineviz);
  Vela-Engineering fork (agent memory). None has original's backing yet;
  pinned upstream 0.11.3 is the reproducible choice, LadybugDB the named
  migration path.

## Comparison

| | FalkorDB 4.20 | Neo4j CE 2026.06 | Memgraph CE 3.12 |
|---|---|---|---|
| License | SSPL (source-available) | **GPLv3 (OSI)** | BSL 1.1 (source-available) |
| Weighted paths | `algo.SPpaths` procs | APOC/GDS procs | **first-class syntax** |
| Footprint (indep. bench) | 496MB | 2,668MB | **415MB** |
| Image | **~152MB** | ~374MB | ~221MB |
| Python async | falkordb-py; **Bolt removed 4.20** | official neo4j v6 | **same neo4j driver (Bolt)** |
| Multi-hop latency | **fastest (11/12)** | slowest | second (on stale 2.21) |
| Concurrency | flattens ~8 threads | parallel runtime CE-disabled | **scales across cores** |
| Cadence | 1–2 weeks | monthly CalVer | monthly |

## Recommendation

**Primary: Memgraph Community 3.12.** Near-FalkorDB latency with genuine
multi-core scaling (p95/p99 under concurrency on 28 cores), first-class
weighted-path syntax matching CO_RATED, in-memory fit, 221MB image, and Bolt:
same official async neo4j driver serves Memgraph and any Neo4j comparison,
keeping the benchmark client-fair. Label it "source-available."

**Runner-up: FalkorDB 4.20.** Raw-latency winner, smallest footprint. Held
back by ~8-thread concurrency ceiling, openCypher gaps, Bolt removal forcing
a second client path, SSPL optics.

**Neo4j CE:** familiar reference point, not the mid tier: slowest multi-hop,
5–6× memory, parallel runtime Enterprise-only. Unique card: only OSI license
+ Cypher gold standard.

## Presenter must not get wrong (late 2026)

1. Kuzu: archived Oct 10 2025; **Apple acquired Kùzu Inc.** (public Feb 2026
   via EU DMA filing). 0.11.3 bundles extensions; MIT keeps embedded use
   safe. Forks: LadybugDB (most active), bighorn, Vela.
2. Neo4j is CalVer now: say "2026.06", not "Neo4j 5/6"; 5.26 = LTS;
   "Cypher 25" is a language version.
3. FalkorDB dropped Bolt in v4.20 (Jul 2026).
4. Memgraph 2.x benchmark numbers are stale: current line 3.x.
5. Licensing precision: only Neo4j CE is OSI open source; "source-available"
   for Memgraph (BSL) and FalkorDB (SSPL).
6. FalkorDB is the RedisGraph successor; RedisGraph is EOL: don't cite its
   era's numbers.
