# 0005 — Hydra (composed) graph engine: Memgraph Community (FalkorDB runner-up, Neo4j as reference point)

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob Scott, Claude

## Context

The Hydra runs a dedicated graph engine in docker compose and produces
the project's quotable graph-plane latency numbers: 2–3-hop weighted
expansion and path-between over 5–20M edges, benchmarked p50/p95/p99 at
concurrency 1/8/32 on a 28-core box. The user asked for a FalkorDB-vs-Neo4j
decision; research surfaced a third credible option, Memgraph, and material
2025–2026 changes to all three (FalkorDB dropped Bolt in v4.20; Neo4j moved
to CalVer with the parallel runtime locked to Enterprise; Memgraph 3.12
added light-edge storage).

## Options considered

### Option A — FalkorDB 4.20
- Pros: fastest raw latency in the only independent 3-way benchmark (11/12
  queries); smallest image (~152MB); sparse-matrix memory model.
- Cons: concurrency flattens past ~8 threads (bad for p99 at concurrency 32
  on 28 cores); openCypher subset gaps (no regex, label expressions);
  **Bolt removed in v4.20** → second client codebase (RESP); SSPL optics for
  an "open source" talk.

### Option B — Neo4j Community 2026.06
- Pros: only OSI-licensed option (GPLv3); Cypher reference implementation;
  best-known name — audience familiarity.
- Cons: slowest multi-hop of the three; 5–6× memory (JVM + page cache built
  for datasets ≫ RAM, which ml-25m is not); parallel Cypher runtime disabled
  in CE; offline-only backup.

### Option C — Memgraph Community 3.12
- Pros: near-FalkorDB latency with genuine multi-core scaling (in-memory
  C++), first-class weighted-path syntax (`[*wShortest]`) matching CO_RATED
  edges, `--storage-light-edge` for edge-heavy graphs, 221MB image, **speaks
  Bolt — the same official async neo4j Python driver covers Memgraph and any
  Neo4j comparison run** (client-fair benchmark).
- Cons: BSL 1.1 source-available (not OSI); slightly behind FalkorDB on raw
  p50 in the independent test (which tested a stale 2.21).

## Decision

**We will use Memgraph Community 3.12 as the graph engine of Hydra, the composed knowledge plane, because
it combines near-best latency with real multi-core concurrency scaling and
Bolt compatibility that keeps one async client codebase across engines —
the p95/p99-under-concurrency story is the benchmark's headline, and that is
exactly where FalkorDB's ~8-thread ceiling and Neo4j CE's disabled parallel
runtime lose.** FalkorDB is the named runner-up; Neo4j CE may appear as an
optional reference configuration, not the platform. Scope: Hydra.

## Consequences

- Easier: one Bolt driver everywhere; weighted paths in query syntax; fits
  RAM comfortably (~5–15GB at 20M edges).
- Harder: must say "source-available (BSL 1.1)", never "open source", on
  stage; independent benchmark coverage of 3.x is thin — our numbers help.
- **Revisit trigger:** benchmark shows Memgraph losing to FalkorDB on our
  own probe flows at concurrency 8+; or licensing terms change.

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/01-graph-engines.md`
