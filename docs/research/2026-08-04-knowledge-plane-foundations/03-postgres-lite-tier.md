# 03 — One-Postgres "lite" tier: relational + vector + graph (researched 2026-08-04)

State as of Aug 2026, verified via live web/GitHub/Docker Hub.

## 1. Apache AGE — alive, cadence fixed, still build-from-source ecosystem

| Release | Date | PG versions |
|---|---|---|
| v1.8.0-rc0 | Jul 9, 2026 | PG18, PG19(beta) |
| v1.7.0 | Jan–Feb 2026 | PG18, PG17 |
| v1.6.0 | Sep–Nov 2025 | PG14–17 |
| v1.5.0 | Jan 2024 | PG11–16 |

- Historical lag real but improving: PG17 support took ~1 yr; PG18 landed in
  ~4 months; PG19-beta build already exists. v1.7.0 added RLS + id-column
  indexes; v1.8.0 adds `all()/any()/none()`, `shortest_path`, `reduce()`,
  agtype↔jsonb casts ([release notes](https://age.apache.org/release-notes/),
  [releases](https://github.com/apache/age/releases)).
- **Docker**: official `apache/age` images maintained:
  `release_PG18_1.7.0` (Feb 2026), `release_PG17_1.6.0` (Nov 2025). Newest
  *release* image is on **PG18**; PG17 stuck at 1.6.0
  ([Docker Hub](https://hub.docker.com/r/apache/age)).
- **No distro/PGDG packages** — outside the official image you build from
  source ([yonk.dev GraphRAG guide](https://yonk.dev/blog/graphrag-part2-postgres-age-pgvector/)).
- **Performance pain persists**: AGE translates openCypher into
  recursive-CTE-like plans. May 2026 comparison: "at 3–4 hops on a few
  million edges, performance is reasonable; at 10 hops queries start timing
  out; at 15–20 they do not return"
  ([evokoa — Postgres as a Graph Database: Four Approaches](https://evokoa.com/blog/postgres-as-a-graph-database/),
  [PG18 issue #2229](https://github.com/apache/age/issues/2229)).

## 2. Recursive CTE on edge tables

- Bounded-depth (2–3 hop) traversal with good indexes is credible at millions
  of edges; failure modes are unbounded depth, no visited-set, duplicate
  explosion. At 10+ hops or full-graph algorithms it falls over (47s
  recursive-CTE traversal of 335k-node tree vs 227ms in-memory BFS)
  ([dev.to — Your PostgreSQL Already Has a Graph Engine](https://dev.to/ineron/your-postgresql-already-has-a-graph-engine-2ng7),
  [oneuptime CTE guide, Jan 2026](https://oneuptime.com/blog/post/2026-01-22-postgresql-recursive-cte-queries/view)).
- Standard pattern for 2–3 hop weighted queries: `WITH RECURSIVE` + depth
  column + `LATERAL`-limited fan-out per hop (top-k by weight, not
  exhaustive); covering index `(src, edge_type) INCLUDE (dst, weight)` so
  each hop is index-only; dedup per iteration. For fixed 2–3 hops, explicit
  self-joins often beat the recursive executor and give the planner full
  visibility.
- **Key ADR point: this benchmark is exactly the regime where CTEs work**
  (2–3 hops, 5–20M edges, top-k weighted expansion), and AGE's Cypher
  compiles to roughly the same plans — AGE buys syntax, not speed, here.
- Existing direct benchmark repo:
  [postgres_pgvector_age_benchmarking](https://codeberg.org/trisolar.faculty/postgres_pgvector_age_benchmarking).

## 3. pgvector — mature, 0.8.6 current

- **v0.8.6** current (Docker images Jul 29, 2026, pg13–pg18). No 0.9 line
  ([Docker Hub](https://hub.docker.com/r/pgvector/pgvector)).
- 0.8.x features: `halfvec` (fp16, 50% storage), `bit` binary quantization,
  `sparsevec`, **iterative index scans** (`hnsw.iterative_scan =
  relaxed_order`) fixing filtered-search overfiltering — directly relevant to
  genre/year-filtered vector queries
  ([0.8.0 announcement](https://www.postgresql.org/about/news/pgvector-080-released-2952),
  [dbi-services index guide, Mar 2026](https://www.dbi-services.com/blog/pgvector-a-guide-for-dba-part-2-indexes-update-march-2026/)).
- **HNSW build at ~62k–100k vectors is a non-issue**: parallel builds since
  0.6.0 (~30x), `maintenance_work_mem` sized so graph fits (~100k × 768d ≈
  0.6 GB) → seconds-to-minutes
  ([Neon 30x](https://neon.com/blog/pgvector-30x-faster-index-build-for-your-vector-embeddings),
  [Crunchy HNSW guide](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)).

## 4. Newer vector extensions — real, irrelevant at 100k vectors

- **VectorChord** (pgvecto.rs successor): v1.1.1 (Feb 2026), repo moved to
  `supervc-stack`, active. Dual **AGPLv3 / ELv2**. Wins QPS-at-high-recall
  benchmarks ([repo](https://github.com/supervc-stack/VectorChord)).
- **pgvectorscale** (Timescale StreamingDiskANN): v0.9.0 (Nov 2025),
  PostgreSQL-licensed, slower cadence. Wins at 50M+ vectors on disk
  ([repo](https://github.com/timescale/pgvectorscale)).
- **Verdict: skip both.** At 62k vectors everything is in shared_buffers;
  differences vs pgvector are noise. pgvector is MIT, everywhere, one fewer
  moving part. Note as upgrade path in ADR.

## 5. Prebuilt images combining the planes

- **No maintained official image ships pgvector + AGE together.** Vendor
  "Postgres for AI" images pick vector+search, never graph (timescaledb-ha,
  Supabase = pg_graphql not traversal, ParadeDB). Community combo images are
  stale one-offs (PG15).
- **Azure Database for PostgreSQL offers AGE + pgvector together as managed
  extensions**; Microsoft published a combined reference architecture
  (Jul 2025) — legitimacy citation for the thesis
  ([Microsoft Community Hub](https://techcommunity.microsoft.com/blog/adforpostgresql/combining-pgvector-and-apache-age---knowledge-graph--semantic-intelligence-in-a-/4508781)).

## 6. Postgres 17 vs 18

- **PG18 released Sept 25, 2025** — async I/O (up to 3x read throughput),
  faster upgrades; ~11 months mature by now
  ([press kit](https://www.postgresql.org/about/press/presskit18/)).
- PG18 extension matrix: pgvector 0.8.6 ✓, AGE 1.7.0 ✓ (official image),
  1.8.0-rc ✓, VectorChord ✓. PG17 is *worse* for AGE-via-Docker.
- **Pin PG18.**

## "Just use Postgres" — citable advocates (2025–2026)

- Pro: [Tiger Data — "It's 2026, Just Use Postgres"](https://www.tigerdata.com/blog/its-2026-just-use-postgres)
  (+ [HN thread](https://news.ycombinator.com/item?id=46905555));
  [Chris Davies — "Just Use Postgres"](https://chrisdavies.dev/posts/just-use-postgres/);
  SO 2025 survey: Postgres #1, ~49% of developers.
- Con (steelman): [Gunnar Morling — "'Just Use Postgres' Considered Harmful"](https://www.morling.dev/blog/you-dont-need-kafka-just-use-postgres-considered-harmful/).
- Canon: Stephan Schmidt, "Just Use Postgres for Everything".

## Recommendation

**Graph plane: recursive-CTE/self-join edge tables as default adapter; AGE as
second adapter, not the foundation.** Ship both — the CTE-vs-AGE delta at 2–3
hops / 5–20M edges *is a publishable result* — but the thesis rests on the
CTE adapter: zero extension risk, planner-visible, any Postgres. Index:
`(src, edge_type) INCLUDE (dst, weight)`; per-hop top-k `LATERAL`; explicit
self-joins for fixed depth.

**Vector plane: pgvector 0.8.6, HNSW on `halfvec`,
`iterative_scan=relaxed_order` for filtered queries.** Skip
VectorChord/pgvectorscale (upgrade path; AGPL a further reason).

**Pin PostgreSQL 18.**

**Image: small custom Dockerfile, base `apache/age:release_PG18_1.7.0`** (AGE
is the hard-to-build one — never compile it), add pgvector via PGDG apt
(`postgresql-18-pgvector`). ~6 lines. Don't base on the pgvector image and
build AGE; don't adopt stale combo images. Pin exact tags; re-evaluate at AGE
1.8.0 final (`shortest_path` strengthens the AGE adapter).
