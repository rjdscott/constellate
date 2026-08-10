# Constellate

[![CI](https://github.com/rjdscott/constellate/actions/workflows/check.yml/badge.svg)](https://github.com/rjdscott/constellate/actions/workflows/check.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

An open experiment in building **knowledge planes**: the same retrieval
contract — relational + vector + graph candidate generation, fusion, policy
gating, and explainable ranking behind one API — served by three deliberately
different platforms, benchmarked head-to-head on MovieLens ml-25m, locally
and reproducibly.

The question under test: *when does a graph plane earn its place beside
vector search, and how much infrastructure does that actually take?*

![Explorer overview](docs/research/2026-08-04-knowledge-plane-foundations/assets/explorer-overview-dark.jpg)

![Playground — three panes](docs/research/2026-08-04-knowledge-plane-foundations/assets/explorer-playground-three-panes.jpg)

## Key findings

- **Cross-engine equivalence is a semantics contract, not a query dialect.**
  Three graph engines (Kuzu Cypher, Postgres SQL, AGE openCypher) produce
  retrieval quality identical to four decimals — because they implement the
  same ranking contract, not translations of the same query.
  ([findings](docs/research/2026-08-04-knowledge-plane-foundations/08-orion-benchmark-findings.md))
- **Architecture beats transport.** The embedded, no-daemon platform was
  assumed to own latency; measured, Postgres over TCP is ~3× faster at p50
  and keeps scaling with concurrency, because in-process synchronous engine
  calls serialize everything.
  ([lessons L3](docs/research/2026-08-04-knowledge-plane-foundations/09-lessons-learned.md))
- **A local 8B model demos the context plane — until the task chains.**
  Haiku 4.5 scored 1.00 tool-call fidelity on the MCP suite; qwen3:8b scored
  0.88 overall but 0.00 on multi-step chaining, confabulating grounded-looking
  answers from wrong tool calls.
  ([context-plane comparison](docs/research/2026-08-04-knowledge-plane-foundations/13-context-plane-llm.md))
- **Conformance tests prove contracts; benchmarks prove systems.** Three
  separate query-planner regressions turned a 70 ms graph expansion into a
  minutes-long full-graph walk while every correctness test stayed green.
  ([lessons L1](docs/research/2026-08-04-knowledge-plane-foundations/09-lessons-learned.md))

Full set: [lessons learned](docs/research/2026-08-04-knowledge-plane-foundations/09-lessons-learned.md)
(L1–L16) and the numbered findings docs alongside it.

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

## Data & attribution

Benchmarks run on the [MovieLens ml-25m](https://grouplens.org/datasets/movielens/25m/)
dataset, downloaded at first use (sha256-pinned) and never committed to this
repo — GroupLens's terms prohibit redistribution and commercial use of the
data ([ADR 0001](docs/adr/0001-pin-movielens-ml-25m.md)). If you use results
derived from it, cite:

> F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets:
> History and Context. ACM Transactions on Interactive Intelligent Systems
> (TiiS) 5, 4: 19:1–19:19. <https://doi.org/10.1145/2827872>

The connection-string credentials in `config/` and `compose/` are
throwaway defaults for the local docker services — not secrets.

## License

Code is [MIT](LICENSE). The MovieLens dataset has its own terms (above).
