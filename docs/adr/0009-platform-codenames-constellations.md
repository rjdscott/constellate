# 0009 — Platform naming: constellation codenames with architecture epithets

- **Status:** Accepted
- **Date:** 2026-08-04 (rewritten same day, twice, while Proposed: tier ladder
  → descriptive names → codenames-as-canonical after the product framing
  solidified)
- **Deciders:** Rob Scott, Claude

## Context

The prep sketch named the configurations tier0/lite/mid/ent — a quality
ladder contradicting the project's claim that these are different platforms
for different solutions. The names become config keys, Make targets, results
filenames, UI labels, video titles, and the talk's core vocabulary; renaming
after artifacts exist is expensive, so this locks now. The project is also a
product/content asset under the Constellate brand, which favors identity
over description — but engineering contributors must never decode blind.

## Options considered

### Option A — keep tier0 / lite / mid / ent
- Cons: encodes a superiority ladder; "lite" undersells the single-Postgres
  thesis; "tier0" is meaningless to an audience. Rejected.

### Option B — architecture-descriptive keys (embedded / unified / composed / distributed)
- Pros: name = architecture, zero decoding.
- Cons: no product identity; generic words are unbrandable and unsearchable
  as a product ("the composed platform" names nothing you can title a video
  after).

### Option C — hybrid (descriptive keys, codename brands)
- Cons: two vocabularies to keep in sync forever. Rejected on that cost.

### Option D — constellation codenames as canonical keys, architecture terms as fixed epithets
- Pros: one vocabulary with identity (matches the Constellate brand — the
  platforms are its constellations); zero hierarchy; epithet pattern keeps
  engineering clarity ("Lyra, the embedded knowledge plane"); this is how
  durable infrastructure is named (Kubernetes, Kafka, Aurora — identity +
  epithet, not description).
- Cons: requires the epithet discipline; one decoder table to maintain;
  Hydra collides with Meta's Python config library (accepted — we ship no
  package named hydra).

## Decision

**We will name the platforms after constellations, as canonical keys
everywhere (config, Make, results, UI, docs), each carrying a fixed
architecture epithet used at first mention in any doc, slide, or view:**

| Key | Platform | Epithet | Shape |
|---|---|---|---|
| `lyra` | **Lyra** | the embedded knowledge plane | small and self-contained: in-process libraries, no daemons (DuckDB · faiss/hnswlib · Kuzu) |
| `orion` | **Orion** | the unified knowledge plane | one prominent figure: a single Postgres 18 serving all three planes |
| `hydra` | **Hydra** | the composed knowledge plane | many heads: a dedicated engine per plane (Postgres · Qdrant · Memgraph) |
| `eridanus` | **Eridanus** | the distributed knowledge plane | the river: event-driven projections via CDC/streaming (future, post-analysis) |

Make variable: `PLATFORM=lyra` (default). Config: `config/lyra.yaml` etc.
Results: `bench/results/lyra-<sha>-<utc>.json`. The architecture words
(embedded/unified/composed/distributed) are epithets and prose descriptions
only — never keys. Vela deliberately avoided (a Kuzu fork uses it).

## Consequences

- Easier: brandable product surface (videos, talk, UI) coherent with the
  Constellate name; no hierarchy connotations; names survive architecture
  evolution (if Hydra gains an engine, its name still works).
- Harder: decoder table is mandatory in the top-level README and UI; every
  doc's first mention carries the epithet — a review-enforced discipline.
- Committed: renaming later means touching committed results artifacts —
  this decision is effectively final for the project's lifetime.
- **Revisit trigger:** none expected for naming itself; add new platforms by
  picking a new constellation whose shape fits the architecture.

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/README.md` (naming map)
- ADRs: [0002](0002-lyra-vector-exact-first-hnswlib-teaching.md),
  [0003](0003-lyra-graph-pin-kuzu-0-11-3.md),
  [0004](0004-orion-postgres18-cte-default-age-second.md),
  [0005](0005-hydra-graph-memgraph.md)
