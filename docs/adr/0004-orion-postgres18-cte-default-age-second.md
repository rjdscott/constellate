# 0004: Orion (unified): single Postgres 18; recursive-CTE graph adapter as default, Apache AGE as second adapter

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob Scott, Claude

## Context

Orion, the unified knowledge plane, tests the thesis "one Postgres is a credible knowledge plane
before you reach for dedicated engines": one container serving relational
source-of-truth, vector search, and 2–3-hop weighted graph traversal over
5–20M edges. Apache AGE historically lagged Postgres majors and carried
build pain; recursive CTEs have a known depth ceiling. pgvector is mature
(0.8.6); newer extensions (VectorChord, pgvectorscale) win only at scales
far beyond this corpus.

## Options considered

### Option A: AGE as the graph plane, CTE as fallback
- Pros: openCypher in Postgres; official `apache/age` PG18 image exists
  (1.7.0, Feb 2026); cadence has improved (PG18 lag ~4 months).
- Cons: AGE compiles Cypher to recursive-CTE-like plans anyway: at 2–3 hops
  it buys syntax, not speed; build-from-source outside the official image;
  extension risk owns the platform's headline numbers.

### Option B: CTE/self-join edge tables as default, AGE as second adapter (ship both)
- Pros: 2–3 hops at 5–20M edges is exactly the regime where indexed CTEs are
  credible; zero extension risk; planner-visible; works on any Postgres;
  and the CTE-vs-AGE delta is itself a publishable result.
- Cons: hand-written SQL traversal; no Cypher ergonomics in the default path.

### Option C: swap pgvector for VectorChord/pgvectorscale
- Pros: better QPS-at-recall at large scale.
- Cons: at 62k vectors differences are noise; AGPL/ELv2 (VectorChord)
  licensing; extra moving part. Rejected, noted as upgrade path.

## Decision

**We will build Orion on PostgreSQL 18 with pgvector 0.8.6 (HNSW on
halfvec, iterative scans for filtered queries) and ship two graph adapters
(recursive-CTE/self-join edge tables as the default the thesis rests on, AGE
as the second adapter) because at this hop depth CTEs match AGE's compiled
plans without extension risk, and the measured delta between them is a
result worth publishing.** Image: ~6-line Dockerfile based on
`apache/age:release_PG18_1.7.0` + PGDG `postgresql-18-pgvector` (AGE is the
hard-to-build one; never compile it). Scope: Orion only.

## Consequences

- Easier: honest baseline, zero-extension default path, PG18 async I/O helps
  25M-row relational scans.
- Harder: two graph adapters to keep conformant; SQL traversal code with
  covering-index discipline (`(src, edge_type) INCLUDE (dst, weight)`).
- **Revisit trigger:** AGE 1.8.0 final ships (`shortest_path`, predicate
  functions): re-run the delta; or corpus growth pushes vectors past ~1M
  (VectorChord/pgvectorscale re-enter).

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/03-postgres-lite-tier.md`
- ADRs: [0001](0001-pin-movielens-ml-25m.md)
