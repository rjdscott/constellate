# Knowledge Plane: project prep spec

> **Status (2026-08-04): historical sketch, superseded.** Live decisions are
> the ADRs in `docs/adr/` (grounded in
> `docs/research/2026-08-04-knowledge-plane-foundations/`); execution follows
> `docs/plans/2026-08-04-knowledge-plane/`. Key departures: platforms are
> named Lyra/Orion/Hydra/Eridanus (ADR 0009, not tier0/lite/mid/ent); Hydra's
> graph engine is Memgraph (ADR 0005, not FalkorDB); Lyra's vector plane is
> exact-flat-first (ADR 0002); Kuzu is pinned at 0.11.3 (archived upstream,
> ADR 0003); a production-grade explorer UI is in scope (ADR 0007, reversing
> §1's "do not implement a UI"); package is `src/constellate/` (ADR 0010).
> The core contract (§4–5) and benchmark shape (§8) remain the foundation.

Build spec for an open source recommendation framework backed by three retrieval planes
(relational, vector, graph) behind a single API. Written for Claude Code. Read fully before
scaffolding.

---

## 1. Thesis and non-goals

**Thesis.** The differentiator is not "we use three databases". It is the *retrieval contract*:
a single call that does candidate generation, graph expansion, policy filtering, fusion and
ranking, and returns results with their traversal path so an agent can quote a reason.

**Success criteria.** The project succeeds if it can demonstrate, on a reproducible benchmark:
1. A probe set where vector-only retrieval measurably fails and vector + graph succeeds.
2. Identical results across storage tiers, proving the abstraction holds.
3. A published latency and quality delta between a single-engine and a multi-engine deployment.

**Non-goals.** Not a model training framework. Not a feature store. Not a RAG library. Do not
implement a UI. Do not build cloud-specific integrations.

---

## 2. Stack decisions (fixed)

- Python 3.12, `uv` for dependency management, `ruff` + `mypy --strict`
- FastAPI + uvicorn, pydantic v2 models, pydantic-settings for config
- pytest, with a conformance suite that every adapter must pass
- Containerised tiers run via `docker compose`, one profile each. `tier0` runs with no containers
  and no daemons at all, purely `pip install`
- Canonical dataset: MovieLens **ml-25m**, downloaded locally, normalised to parquet
- No cloud-proprietary services anywhere. Everything must run offline after dataset download.

---

## 3. Repo layout

```
constellate/
  CLAUDE.md                  # agent working rules, generated from section 12
  pyproject.toml
  Makefile
  compose/
    lite.yml  mid.yml  ent.yml     # tier0 has no compose file by design
  docker/
    lite/Dockerfile          # postgres 16 + pgvector + apache age
  config/
    tier0.yaml  lite.yaml  mid.yaml  ent.yaml
  src/constellate/
    api/          app.py  routes.py  schemas.py
    core/         protocol.py  types.py  pipeline.py  fusion.py  policy.py  errors.py
    planes/
      relational/ base.py  duckdb.py  postgres.py
      vector/     base.py  hnsw.py  pgvector.py  qdrant.py
      graph/      base.py  kuzu.py  age.py  cte.py  falkordb.py
    ingest/       movielens.py  canonical.py  embeddings.py  edges.py  loader.py
    bench/        harness.py  flows.py  metrics.py  probes.py  report.py  latency.py
  tests/
    conformance/  test_relational.py  test_vector.py  test_graph.py  test_pipeline.py
    unit/
  bench/results/             # committed JSON artefacts, one per run
  data/                      # gitignored: raw + canonical parquet + embeddings
```

---

## 4. Core contract

Three plane protocols plus a pipeline that orchestrates them. Engine-specific types must never
escape a plane module.

```python
# core/types.py
ItemId = int; UserId = int

class Candidate(BaseModel):
    item_id: ItemId
    score: float
    source: Literal["vector", "graph", "relational"]
    path: list[str] | None = None      # graph traversal, e.g. ["u:5","rated","m:318","tag:redemption","m:527"]
    hops: int | None = None

class Recommendation(BaseModel):
    item_id: ItemId
    rank: int
    score: float
    sources: list[str]
    reason: str | None                 # rendered from path
    metadata: dict

class RetrievalRequest(BaseModel):
    user_id: UserId | None = None
    seed_item_id: ItemId | None = None
    k: int = 20
    max_hops: int = 2
    policy: dict = {}                  # eligibility filters applied as hard gates
    explain: bool = False
    planes: list[str] | None = None    # None = all; used for ablation
```

```python
# core/protocol.py  (Protocol classes, not ABCs)
class RelationalPlane(Protocol):
    async def get_user_context(self, user_id: UserId) -> UserContext: ...
    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]: ...
    async def apply_policy(self, ids: Sequence[ItemId], ctx: UserContext, policy: dict) -> list[ItemId]: ...
    async def exclusions(self, user_id: UserId) -> set[ItemId]: ...

class VectorPlane(Protocol):
    async def search(self, vec: Vector, k: int, exclude: set[ItemId]) -> list[Candidate]: ...
    async def get_vector(self, item_id: ItemId) -> Vector: ...
    async def upsert(self, rows: Iterable[tuple[ItemId, Vector]]) -> None: ...

class GraphPlane(Protocol):
    async def expand(self, seeds: Sequence[ItemId], max_hops: int, limit: int,
                     edge_types: Sequence[str] | None = None) -> list[Candidate]: ...
    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None: ...
    async def upsert_edges(self, edges: Iterable[Edge]) -> None: ...
```

**Rules.** Adapters never import each other. The pipeline never imports a concrete adapter.
Wiring happens once in a factory keyed off config.

---

## 5. Retrieval pipeline (core/pipeline.py)

Fixed six-step order. Instrument each step separately.

1. **Relational**: resolve user context, load exclusion set and policy attributes.
2. **Vector**: candidate generation, top-k nearest to user vector or seed item. Ids and scores only.
3. **Graph**: expand from seed and from top vector candidates, up to `max_hops`. Return ids plus path.
4. **Fusion**: reciprocal rank fusion over the vector and graph lists. `k` constant and per-plane
   weights come from config, never hardcoded.
5. **Relational**: hydrate survivors, apply hard policy gates. Policy is a gate, not a score penalty.
6. **Return**: ranked items with score, contributing sources, and traversal path when `explain=true`.

Steps 2 and 3 run concurrently where the graph seeds do not depend on vector output. Record both
the concurrent wall time and the per-plane time.

---

## 6. Dataset: MovieLens ml-25m

Download to `data/raw/ml-25m/` via `make seed` (script + checksum, do not vendor the data,
GroupLens restricts redistribution). Roughly 25M ratings, 62k movies, 162k users, 1M tag
applications, plus the tag genome (~15M relevance scores over ~1.1k tags).

### 6.1 Canonical form (`data/canonical/*.parquet`)

Every tier ingests these identical files. Written once by `ingest/canonical.py`.

| File | Columns |
|---|---|
| `items.parquet` | item_id, title, year, genres[], popularity, n_ratings, mean_rating |
| `users.parquet` | user_id, n_ratings, first_ts, last_ts, region, tier (synthetic policy attrs) |
| `interactions.parquet` | user_id, item_id, rating, ts, split ("train"/"eval") |
| `item_vectors.parquet` | item_id, vector (float32[256]) |
| `user_vectors.parquet` | user_id, vector (float32[256]) |
| `edges.parquet` | src, src_type, dst, dst_type, edge_type, weight |

### 6.2 Embeddings: use the tag genome, not a language model

Default embedding path has **zero ML dependencies**. The genome gives a dense relevance vector per
movie over ~1.1k tags. Reduce with truncated SVD to 256 dims, L2 normalise. Deterministic, fast,
and semantically meaningful. Cache to parquet so it is computed once.

- User vector = rating-weighted mean of item vectors over their train interactions, mean-centred.
- Movies missing from the genome (long tail) get a genre-and-year fallback vector, flagged
  `has_genome=false` so cold-start probes can target them.
- Optional secondary path behind a flag: `fastembed` ONNX MiniLM over `title + genres + top tags`.
  Used to check the framework is not overfit to one embedding source. Never required for `make bench`.

### 6.3 Graph edges

| Edge type | From | To | Weight |
|---|---|---|---|
| HAS_GENRE | item | genre | 1.0 |
| HAS_TAG | item | tag | genome relevance, threshold >= 0.5 |
| RATED | user | item | rating, train split only |
| CO_RATED | item | item | normalised co-occurrence, top 20 per item, min support 50 |

CO_RATED is the expensive one. Compute offline in the ingest step with a popularity cap, do not
compute at query time. The graph plane stores ids, types and weights only. **No text, no metadata,
no duplicated item attributes in the graph.**

### 6.4 Splits

Temporal, never random. Global timestamp cutoff at the 95th percentile of all rating timestamps.
Interactions after the cutoff form the eval set. Users with fewer than 5 train interactions are
excluded from user-conditioned flows. Seed everything, pin the cutoff in `config/*.yaml`.

---

## 7. Tiers

All tiers take the same canonical parquet and expose the same API. Only the adapter wiring changes.

### 7.0 `tier0`: no daemon, no containers

Three genuinely separate engines, all in-process, all pip installable. No docker, no servers.
This is the development and CI tier and it is where most of the work happens.

| Plane | Engine                                                           | Notes |
|---|------------------------------------------------------------------|---|
| Relational | DuckDB                                                           | In-process, single file, fast parquet ingest |
| Vector | `hnswlib` over a numpy array, index persisted to disk | No daemon, loads in milliseconds |
| Graph | Kuzu                                                             | Embedded property graph, real Cypher, single file, no JVM |

Kuzu is the piece that makes this tier honest. Every other credible graph store needs a server
process, and Neo4j drags in a JVM. Kuzu gives real Cypher and real traversal semantics as a
library, so tier0 exercises the same query patterns that AGE and FalkorDB will later serve.

**Deliberately not using DuckDB VSS for the vector plane.** Its HNSW index only works on in-memory
databases unless an experimental persistence flag is set, WAL recovery for custom indexes is
incomplete, and index serialisation is non-incremental. `hnswlib` with a persisted index file
sidesteps all of it and is a truer analogue of what Qdrant does in `mid`.

**Latency numbers from tier0 are indicative only and must be labelled as such in the report.**
DuckDB is an analytical engine with noticeable per-query overhead on point lookups. Use tier0 for
correctness, recall quality, ablation and probe validation. Quote latency only from `lite` and `mid`.

Total footprint: a venv and three files under `data/tier0/`. Starts in about a second, runs in CI
with no docker daemon.

### 7.1 `lite`: one container, three planes

`docker/lite/Dockerfile`: Postgres **16** (pin for Apache AGE compatibility) with `pgvector` and
`apache/age` installed. Relational = tables. Vector = pgvector HNSW. Graph = AGE openCypher.

Fallback variant `lite-cte` if the AGE build proves brittle: same container, graph adapter is
`graph/cte.py` using an indexed edge table and recursive CTEs. Ship both, they share the graph
conformance tests. This is the lowest-footprint configuration and the honest baseline everything
else must beat.

### 7.2 `mid`: three engines, purpose-built

- Relational: `postgres:17`
- Vector: `qdrant/qdrant`
- Graph: `falkordb/falkordb` (Cypher, Redis-light footprint, no JVM)

Postgres remains the only writable source of truth. Vector and graph are derived projections,
rebuilt by `make rebuild` from canonical parquet. This is the tier that tests fan-out latency,
tail behaviour and the projection rebuild path.

### 7.3 `ent`: deferred

Do **not** build yet. Recorded scope for after lite and mid are benchmarked:
streaming CDC rebuild (Debezium + Redpanda), offline GNN embeddings and graph algorithms,
full OTel + Grafana per-plane tracing, MCP server plus agent eval harness.
Leave `compose/ent.yml` and `config/ent.yaml` as stubs with a comment pointing here.

---

## 8. Benchmark suite

Same flows, same dataset, same metrics, every tier. `make bench TIER=lite` writes
`bench/results/<tier>-<git-sha>-<utc>.json`.

### 8.1 Flows

| ID | Flow | Exercises |
|---|---|---|
| F1 | Similar items to a seed | vector + graph, no user |
| F2 | Personalised top-N for a user | full pipeline |
| F3 | Cold-start item (no ratings, has tag edges) | graph carries it, vector is weak |
| F4 | Policy-constrained recommendation | hard gates, eligibility filtering |
| F5 | Multi-hop explanation query | path return correctness |
| F6 | Agent sequence: 3 chained calls with a refinement | per-call latency budget under repetition |

### 8.2 Metrics

- **Quality**: Recall@10, Recall@50, NDCG@10, MRR
- **Beyond accuracy**: catalogue coverage, intra-list diversity, novelty (mean inverse popularity)
- **Latency**: p50/p95/p99 per flow, and per plane, at fixed concurrency (1, 8, 32). Tier0 results
  are tagged `latency_indicative: true` in the JSON artefact and rendered with a caveat in the report
- **Ops**: ingest wall time, rebuild wall time, container count, peak RSS, on-disk size

Report beyond-accuracy metrics from the start. Without them the system optimises straight into a
popularity-bias trap and the numbers look great while the product is worthless.

### 8.3 Probe set (the most important artefact)

`bench/probes.py` generates **graph-necessary** probes: cases where the ground-truth relevant item
is outside the vector top-50 but within `max_hops` in the graph. Categories:

- Two-hop tag bridges: user rated A, A and C share a high-relevance genome tag, C is not vector-near A
- Cold-start items with genome tags but under 10 ratings
- Cross-genre bridges where genre overlap is zero but co-rating is strong
- Path-required queries where the expected output is the traversal path, not just the item

Generate deterministically from a seed and cache to `data/canonical/probes.parquet`. If the probe
set cannot be built such that vector-only recall is clearly below vector+graph recall, say so
loudly in the report. That result is itself the project's central finding.

### 8.4 Ablation

`--planes vector` and `--planes vector,relational` must run the same flows with the graph plane
disabled. Every report includes the ablation delta. If the delta is negligible on the probe set,
either the probes are too easy or the graph plane is not earning its place.

### 8.5 Report

`make report` renders a markdown comparison table across all result JSON files in
`bench/results/`, tier by tier, with the ablation delta and latency breakdown. Commit the JSON so
regressions across commits are visible.

---

## 9. API surface

```
POST /v1/recommend    RetrievalRequest -> list[Recommendation]
POST /v1/similar      seed_item_id, k -> list[Recommendation]
POST /v1/explain      user_id, item_id -> path + contributing planes
GET  /v1/health       per-plane liveness and projection lag
GET  /v1/stats        counts per plane, index status, config fingerprint
```

Every response carries `timings: {relational_ms, vector_ms, graph_ms, fusion_ms, total_ms}` and
`config_fingerprint` so a benchmark result can always be traced to the exact configuration.

---

## 10. Make targets

```
make up TIER=lite        # docker compose up; no-op for TIER=tier0
make down TIER=lite
make seed                # download ml-25m, verify checksum, build canonical parquet
make load TIER=tier0     # ingest canonical parquet into the tier's engines
make rebuild TIER=mid    # drop and regenerate derived planes from relational only
make test                # unit + conformance, runs against tier0, no docker required
make bench TIER=tier0    # full benchmark, writes JSON artefact
make report              # cross-tier markdown comparison
make bench-all           # tier0, lite, mid, then report
```

`TIER` defaults to `tier0`, so a fresh clone runs `make seed load bench` with no docker installed.
`make up` and `make down` are no-ops for tier0. `make seed` must be idempotent and resumable.

`make rebuild` completing successfully is the proof that the CDC design in the enterprise tier
will work.

---

## 11. Optional Rust track (phase 3, not before)

Purpose is learning with a scoreboard, not a rewrite. The API is I/O bound so a full Rust port buys
little. The fusion and reranking kernel is CPU-bound over a few thousand candidates and is a clean,
bounded target.

- `rust/constellate-fusion/`: RRF plus reranking plus diversity (MMR) as a `pyo3` extension
- Exposes exactly the same signature as `core/fusion.py`, selected by config flag `fusion.impl: rust|python`
- Must pass the identical fusion unit tests
- `make bench` records which implementation ran, so the two are directly comparable

Only after that lands is a full `axum` implementation of the serving path worth considering, and
only if the benchmark shows the Python API layer is a measurable fraction of p99.

---

## 12. Working rules for the agent

1. Build in the milestone order in section 13. Do not scaffold the enterprise tier.
2. The pipeline must not import any concrete adapter. Wiring lives in one factory.
3. Adapters must not import each other. Engine types must not leak past the protocol boundary.
4. Only the relational plane is writable. Vector and graph are derived and must be rebuildable.
5. No network calls at query time. No LLM calls anywhere in the default path.
6. Seed every random operation. Pin dataset checksums, the split cutoff and the embedding config.
7. Every new adapter must pass the existing conformance suite unchanged before any new code lands.
8. Config over constants. Fusion weights, hop limits, thresholds and k values all live in
   `config/*.yaml`.
9. Write the conformance test before the adapter it tests.
10. When a design choice is genuinely ambiguous, implement the simplest option, add a `# DECISION:`
    comment stating what was chosen and what was rejected, and continue. Do not stall.

---

## 13. Milestones

**M0 Scaffold.** Repo layout, `pyproject.toml`, Makefile, protocols and types, empty conformance
suite, tier0 config, compose files for lite and mid. *Done when* `make test` runs green with all
adapters skipped.

**M1 Data.** `make seed` downloads ml-25m, builds all canonical parquet including genome SVD
embeddings, edges and temporal split. *Done when* canonical parquet is reproducible byte-for-byte
from a fresh clone and probe generation succeeds.

**M2 Tier 0.** DuckDB, hnswlib and Kuzu adapters, full pipeline, F1 to F3 end to end, no docker.
*Done when* `make seed load bench` runs from a fresh clone on a machine with no docker installed.
Build this before any container work: it is the fastest feedback loop and it forces the adapter
boundary to be real from day one.

**M3 Harness.** All six flows, all metrics, ablation mode, latency breakdown, report generation,
running against tier0. *Done when* the report shows a measurable ablation delta on the probe set.
This is the go/no-go gate for the whole project.

**M4 Lite tier.** Single container, all three planes, adapters passing the unchanged conformance
suite. *Done when* `make up load bench TIER=lite` produces a result JSON and quality metrics match
tier0 within tolerance.

**M5 Mid tier.** Qdrant and FalkorDB adapters passing the unchanged conformance suite, plus
`make rebuild`. *Done when* all three tiers produce equivalent quality metrics and the report shows
the latency and footprint delta between them.

**M6 Review.** Write up the findings. Then, and only then, design the enterprise tier from what the
first three tiers actually taught us.
