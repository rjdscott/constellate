# Constellate

An open experiment in building **knowledge planes**: the same retrieval
contract — relational + vector + graph candidate generation, fusion, policy
gating, and explainable ranking behind one API — served by three deliberately
different platforms, benchmarked head-to-head on MovieLens ml-25m, locally
and reproducibly.

The question under test: *when does a graph plane earn its place beside
vector search, and how much infrastructure does that actually take?*

## The constellations

| Key | Platform | is the… | Engines |
|---|---|---|---|
| `lyra` | **Lyra** | embedded knowledge plane | in-process: DuckDB · faiss/hnswlib · Kuzu |
| `orion` | **Orion** | unified knowledge plane | one Postgres 18 (pgvector + edge tables/AGE) |
| `hydra` | **Hydra** | composed knowledge plane | Postgres 18 · Qdrant · Memgraph |
| `eridanus` | **Eridanus** | distributed knowledge plane | CDC/streaming — future, designed after results |

Names are canonical keys everywhere (`PLATFORM=lyra`, `config/lyra.yaml`);
the architecture terms are their permanent epithets. No hierarchy implied —
right tool for the job ([ADR 0009](docs/adr/0009-platform-codenames-constellations.md)).

## Quickstart

```bash
uv sync
make check                 # ruff + mypy --strict + pytest
make up PLATFORM=lyra      # no-op: Lyra is in-process
```

Full loop: [docs/runbooks/local-dev-loop.md](docs/runbooks/local-dev-loop.md).

## Where everything lives

| Surface | Purpose |
|---|---|
| [`docs/research/`](docs/research/2026-08-04-knowledge-plane-foundations/README.md) | Analysis (web-verified, dated snapshots) feeding decisions |
| [`docs/adr/`](docs/adr/README.md) | Decisions — why, with options considered |
| [`docs/plans/`](docs/plans/README.md) | Execution — phased, resumable by a stranger |
| [`docs/runbooks/`](docs/runbooks/README.md) | Operations — how, with exact commands |
| [`docs/audits/`](docs/audits/README.md) | Point-in-time verification sweeps |
| [`CLAUDE.md`](CLAUDE.md) | Working rules (branch/PR discipline, doc pipeline) |

Current status: see the [plan status table](docs/plans/2026-08-04-knowledge-plane/README.md)
and the [migration narrative](docs/research/2026-08-04-knowledge-plane-foundations/04-migration-narrative.md)
— the project's running story.
