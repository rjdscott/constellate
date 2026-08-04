# Knowledge-plane foundations — research workspace

- **Date opened:** 2026-08-04
- **Question:** what is the best-practice, conference-defensible technology
  lineup for a three-tier local knowledge-plane experiment (relational +
  vector + graph planes behind one retrieval API), and how should it be
  benchmarked?
- **Feeds:** ADRs 0001–000N (`docs/adr/`), plan
  `docs/plans/2026-08-04-knowledge-plane/`.

## Contents

| File | Topic |
|------|-------|
| `01-graph-engines.md` | FalkorDB vs Neo4j vs Memgraph for the mid tier; Kuzu status for tier0 |
| `02-embedded-vector.md` | hnswlib vs LanceDB (vs usearch/faiss/brute-force) for tier0 |
| `03-postgres-lite-tier.md` | Apache AGE vs recursive CTE; pgvector state; single-Postgres thesis |
| `04-migration-narrative.md` | dated milestone log (ADR acceptances, phase completions) — the talk arc |
| `05-embeddings-and-benchmarks.md` | embedding strategy, dataset choice, metrics + latency methodology |
| `06-ui-and-mcp.md` | explorer UI stack, graph viz library, MCP server approach |

## Naming map (ADR 0009, decided after these docs were written)

Research docs 01–06 use the prep sketch's platform names as historical
snapshots. Mapping — constellation codename (canonical key) + architecture
epithet (permanent technical descriptor):

| Old | Codename | Epithet |
|---|---|---|
| `tier0` | **Lyra** (`lyra`) | the embedded knowledge plane |
| `lite` | **Orion** (`orion`) | the unified knowledge plane |
| `mid` | **Hydra** (`hydra`) | the composed knowledge plane |
| `ent` | **Eridanus** (`eridanus`) | the distributed knowledge plane |

## Inputs

- `docs/constellate-prep.md` — original idea sketch (superseded by this
  workspace where they disagree).
- User constraints: local machine (28 cores / 62 GB RAM / Docker 29),
  engineering excellence first, educational value (conference talk) explicit
  goal, full explorer UI with graph viz in scope, REST first + early MCP.
