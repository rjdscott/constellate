# 0003 — Lyra (embedded) graph plane: pin archived Kuzu 0.11.3, name LadybugDB as migration path

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob Scott, Claude

## Context

Lyra, the embedded knowledge plane, needs an embedded property graph with real Cypher so the same query
patterns run daemon-free in CI and against server engines in the server-based platforms.
Kuzu was the obvious pick — until its repo was archived on 2025-10-10 (final
release v0.11.3 the same day). The reason became public in Feb 2026: Apple
agreed to acquire Kùzu Inc. Forks exist (LadybugDB — most active, v0.17.0
May 2026; bighorn; Vela) but none yet has the original's institutional
backing.

## Options considered

### Option A — pin `kuzu==0.11.3` (archived upstream)
- Pros: MIT-licensed, deliberately bundles extensions (no dead download
  servers), battle-tested, bit-reproducible for a benchmark; the archive
  story is itself conference material.
- Cons: unmaintained; no fixes ever.

### Option B — LadybugDB (most active fork)
- Pros: maintained (commits through Jul 2026), drop-in-ish lineage.
- Cons: young fork, API drift risk mid-project, less proven; a benchmark
  wants a frozen dependency anyway.

### Option C — drop the graph engine; Lyra graph plane = SQL edge tables in DuckDB
- Pros: one fewer engine.
- Cons: loses Cypher parity with Orion and Hydra; Lyra stops exercising the
  same query patterns — the platform's whole point.

## Decision

**We will pin `kuzu==0.11.3` for Lyra, because a benchmark wants a frozen,
reproducible dependency and MIT + bundled extensions keep the archived
release safe to use — while naming LadybugDB as the migration path.** Scope:
Lyra only.

## Consequences

- Easier: reproducibility; zero churn.
- Harder: any Kuzu bug is ours to work around; must not claim Kuzu is
  maintained on stage (say: archived Oct 2025, Apple acquisition, forks).
- **Revisit trigger:** LadybugDB reaches a stable 1.0 with a compatibility
  statement, or a Kuzu bug actually blocks a flow.

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/01-graph-engines.md`
