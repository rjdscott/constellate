# Architecture Decision Records

Conventions for `docs/adr/`. See `CLAUDE.md` for where ADRs sit in the doc
pipeline (research → ADR → plan → audit).

## Conventions

- One decision per ADR. File: `NNNN-slug.md`, 4-digit sequence, never reused or
  renumbered. Slug states the decision, not the topic area.
- Structure: `template.md` (Nygard format + options considered).
- Accepted ADRs are immutable. To change course, write a new ADR and set the
  old one's status line to `Superseded by [NNNN](NNNN-slug.md)` — that line is
  the only permitted edit.
- ADRs cite research (`docs/research/**`) rather than restating it.
- ADRs land in the same PR as the work they govern.
- Every accepted ADR appends a milestone entry to the active research
  workspace's migration narrative
  (`docs/research/2026-08-04-knowledge-plane-foundations/04-migration-narrative.md`).

## Index

| # | Title | Status |
|---|-------|--------|
| [0001](0001-pin-movielens-ml-25m.md) | Pin MovieLens ml-25m as the canonical dataset | Accepted |
| [0002](0002-lyra-vector-exact-first-hnswlib-teaching.md) | Lyra (embedded) vector: exact flat search first, hnswlib as ANN teaching layer | Accepted |
| [0003](0003-lyra-graph-pin-kuzu-0-11-3.md) | Lyra (embedded) graph: pin archived Kuzu 0.11.3, LadybugDB as migration path | Accepted |
| [0004](0004-orion-postgres18-cte-default-age-second.md) | Orion (unified): Postgres 18; CTE graph default, AGE second adapter | Accepted |
| [0005](0005-hydra-graph-memgraph.md) | Hydra (composed) graph: Memgraph Community (FalkorDB runner-up) | Accepted |
| [0006](0006-dual-embedding-ablation-genome-svd-plus-bge.md) | Embeddings: genome-SVD + bge-small dual-arm ablation | Accepted |
| [0007](0007-explorer-ui-react-spa-design-system.md) | Explorer UI: production-grade React SPA with custom design system | Accepted |
| [0008](0008-mcp-fastmcp-shared-service-layer.md) | MCP: FastMCP v3, hand-written tools over shared service layer | Accepted |
| [0009](0009-platform-codenames-constellations.md) | Platform naming: constellation codenames (Lyra/Orion/Hydra/Eridanus) + architecture epithets | Accepted |
| [0010](0010-package-named-constellate.md) | Python package named `constellate`, not `kp` | Accepted |
