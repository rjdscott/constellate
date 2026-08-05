# Plan: three-platform knowledge plane experiment

- **Date:** 2026-08-04
- **Goal (outcome):** a reproducible local experiment proving (or honestly
  refuting) that a multi-plane retrieval contract (relational + vector +
  graph behind one API) beats vector-only retrieval on a graph-necessary
  probe set — with identical quality across three storage platforms, published
  latency/footprint deltas, an interactive explorer UI, and an MCP surface —
  all runnable offline on this machine, conference-presentable.
- **Scope:** three platforms (naming: ADR 0009 — constellation codename +
  architecture epithet): **Lyra**, the embedded knowledge plane (in-process:
  DuckDB · faiss/hnswlib · Kuzu); **Orion**, the unified knowledge plane
  (one Postgres 18 serving all planes); **Hydra**, the composed knowledge
  plane (Postgres · Qdrant · Memgraph); ml-25m; benchmark suite; explorer
  UI; MCP.
- **Non-goals:** Eridanus, the distributed knowledge plane (CDC/streaming — designed only after
  results), model training, Rust track (post-benchmark option only), and
  **EKS/public deployment — explicitly deferred until the analysis
  completes**, but everything ships deployment-ready (UI builds to a static
  artifact with configurable API base; services containerized).

## Status

| NN | Phase | Status | Last update |
|----|-------|--------|-------------|
| 01 | [Scaffold](phase-01-scaffold.md) | 🟢 Completed | 2026-08-04 |
| 02 | [Data & probes](phase-02-data-and-probes.md) | 🟢 Completed | 2026-08-04 |
| 03 | [Lyra (embedded) end-to-end](phase-03-lyra.md) | 🟢 Completed | 2026-08-04 |
| 04 | [Benchmark harness (go/no-go)](phase-04-harness.md) | 🟢 Completed | 2026-08-04 |
| 05 | [Orion (unified)](phase-05-orion.md) | 🟢 Completed | 2026-08-04 |
| 06 | [Hydra (composed)](phase-06-hydra.md) | 🟢 Completed | 2026-08-04 |
| 07 | [Explorer UI + MCP](phase-07-explorer-and-mcp.md) | 🟢 Completed | 2026-08-05 |
| 08 | [Neural arm + final report](phase-08-neural-arm-and-report.md) | 🟢 Completed | 2026-08-05 |
| 09 | [Context plane: LLM consumers, local vs API](phase-09-context-plane-llm.md) | 🟢 Completed | 2026-08-05 |

## Handover

Session-end state + ranked next steps: [handover-2026-08-05.md](handover-2026-08-05.md).
Decisions recorded there: talk = conference slot 30–45 min; publication =
blog post series off research doc 13's threads.

## Parked experiments (triggered, not scheduled)

Run after phase 08 when the harness is final, unless a trigger fires earlier:

- **Neo4j CE reference arm in Hydra** (agreed 2026-08-05). ADR 0005
  pre-authorized Neo4j as "an optional reference configuration, not the
  platform". Shape: `engines.graph.adapter: neo4j` arm exactly like Orion's
  cte/age split — same Bolt driver the Memgraph adapter already uses, port
  the three UNWIND-anchored queries (Neo4j's planner handles `IN` +
  index correctly, so the L11 hang class shouldn't recur), compose service,
  conformance + parity test validate the contract, one bench artifact +
  report row. Est. ~half a day. Value: the audience-calibration number —
  the best-known engine measured against four others producing identical
  retrieval. Expectations to test: slowest multi-hop (CE slotted runtime,
  single-threaded per query), 2–4× memgraph's graph-leg latency, 2–4GB JVM
  RSS on a dataset that fits in RAM everywhere.
- **AGE 1.8.0 delta re-run** — trigger: AGE 1.8.0 final ships (ADR 0004).
- **Expansion-policy ADR** — trigger: any change to retrieval ranking
  (phase-04 finding: hops-ASC crowds out 2-hop path_required/tag_bridge
  targets).
- **Latency-harness rate sweep** — L6 do-differently; fold into any future
  harness change.
- **Small-model size sweep on the context suite** (noted 2026-08-05,
  research doc 13) — run qwen3:4b / llama3.2:3b / a 14B through the same
  8-task suite to locate the chaining-fidelity cliff precisely; the suite
  and scoring already exist, each run is one CLI invocation. Publication
  feed: "how small can your agent be" with measured trajectories.
- **Long-tail probe set** (noted 2026-08-05, findings 12) — probes drawn
  from non-genome items would test SVD's fallback weakness and could flip
  the svd-vs-neural verdict; probe generator currently cannot see that
  population (L15).

## Decisions this plan executes

ADRs [0001](../../adr/0001-pin-movielens-ml-25m.md)–[0010](../../adr/0010-package-named-constellate.md)
(all **Accepted** 2026-08-04), grounded in
`docs/research/2026-08-04-knowledge-plane-foundations/`. The prep sketch
`docs/constellate-prep.md` is superseded where they disagree; its core
contract (§4–5: plane protocols, six-step pipeline, conformance-first
adapters) is retained.

## Critical files (once built)

- `src/constellate/core/` — types, protocols, pipeline, fusion (engine types never
  escape a plane module; wiring in one factory)
- `src/constellate/planes/` — one directory per plane, one module per adapter
- `src/constellate/service.py` — shared service layer (REST routes and MCP tools both
  call it)
- `bench/` — harness, probes, results JSON artifacts (committed)
- `compose/` + `docker/` — Orion and Hydra definitions
- `Makefile` — `seed / load / up / down / bench / report / check`

## Top risks

1. **Probe set fails to separate vector-only from vector+graph** — the
   go/no-go at phase 04. Mitigation: probes generated from graph structure
   (tag bridges, cold-start, cross-genre); if no separation, that finding is
   itself the talk's centerpiece — report it loudly, don't bury it.
2. **AGE adapter friction** (build/behavior) — mitigated: CTE adapter is the
   default path (ADR 0004); AGE can slip a phase without blocking.
3. **Kuzu is frozen** (archived upstream) — any blocking bug forces the
   LadybugDB migration path (ADR 0003 revisit trigger).
4. **Latency methodology invalidated by coordinated omission** — mitigated:
   open-loop fixed-rate harness + HdrHistogram from day one (research 05).
5. **Scope creep in the explorer UI** — now the largest phase by design
   (production-grade SPA, ADR 0007 rewritten 2026-08-04). Contained by hard
   scope: playground + explanation graphs + dashboards + polish; anything
   beyond requires a plan amendment. Design tokens land before feature
   components to prevent restyling churn.

## Conventions

Per `docs/plans/README.md`: branch + PR per phase, `make check` green before
🟢, progress logs append-only, migration-narrative entry per completed phase.
