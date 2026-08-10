# 07: Lyra benchmark findings (phase 04, go/no-go)

- **Date:** 2026-08-04
- **Platform:** Lyra, the embedded knowledge plane (DuckDB · faiss flat ·
  Kuzu 0.11.3, in-process, no daemon)
- **Method:** `docs/plans/2026-08-04-knowledge-plane/phase-04-harness.md` +
  research `05-embeddings-and-benchmarks.md`; harness in
  `src/constellate/bench/`; machine artifacts in `bench/results/*.json`
  (committed, one per run), generated tables in `bench/report.md`
- **Reproduce:** `make bench PLATFORM=lyra && make report`
  (`docs/runbooks/run-benchmarks.md`)
- **Verdict: GO**: the multi-plane contract measurably beats vector-only
  retrieval on the graph-necessary probe set (details below)

Sibling docs will cover Orion (phase 05) and Hydra (phase 06); this one is
Lyra only. Cross-platform synthesis comes with the phase-08 report.

## Setup

200 probes, 4 kinds × 50 (`tag_bridge`, `cold_start`, `cross_genre`,
`path_required`, construction in `constellate.ingest.probes`), each a
(seed item → expected items) pair reachable through graph structure but
deliberately hostile to pure vector similarity. Three arms, identical
pipeline, only `RetrievalRequest.planes` differs:

| arm | planes |
|---|---|
| `vector_only` | relational + vector (faiss flat over genome-SVD 256d) |
| `graph_only` | relational + graph (Kuzu 2-hop expansion) |
| `hybrid` | all three, fused with RRF k=60, equal weights |

Retrieval depth k=50; metrics via ir_measures; paired student-t via ranx;
coverage/novelty hand-rolled (research 05). Fusion tuning grid-searches the
graph weight in the pipeline's own `rrf` over per-plane candidate lists at
the pipeline's true fusion depth (`candidate_multiplier × k` = 250), on a
stratified validation half, scored on the held-out half. The artifact's
`fidelity_check` proves the offline w=1.0 baseline reproduces the hybrid
arm exactly (nDCG@10 0.0362 = 0.0362). So the winning weight transfers to
`config/lyra.yaml` `fusion.weights`. (The first run tuned over
depth-truncated top-50 lists; the independent review caught the regime
mismatch; best weight moved 1.5 → 2.0 once the inputs were faithful.
Lesson: offline tuning is only as good as its reconstruction of the online
system, and a fidelity check is cheap.)

## Headline numbers (200 probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0213 | 0.0439 | 0.0273 | 0.0746 | 0.0274 | 17.37 |
| graph_only | **0.0965** | **0.3516** | **0.0752** | **0.1025** | 0.0172 | 13.04 |
| hybrid | 0.0355 | 0.2301 | 0.0362 | 0.0844 | 0.0249 | 15.41 |

- **The gate:** hybrid beats vector_only on R@10 by **+0.0141**
  (p=0.0054, paired student-t) and on R@50 by **+0.186**. The
  probe-set separation the whole project hinges on exists. GO.
- **The louder finding:** `graph_only` dominates *both* other arms. On a
  probe set built from graph structure, equal-weight RRF actively
  **dilutes** the graph signal with weaker vector candidates. Fusion is
  not a free lunch: weighting is a real lever, not a checkbox.

## Findings by probe kind (R@10, vector / graph / hybrid)

| kind | vector_only | graph_only | hybrid | reading |
|---|---|---|---|---|
| cross_genre | 0.0020 | **0.3520** | 0.0666 | graph's blowout: CO_RATED edges cross genre walls vectors can't |
| cold_start | **0.0680** | 0.0300 | 0.0660 | vector *wins*: genome-SVD vectors are built from tags, so cold items (few ratings, rich tags) sit well in vector space |
| path_required | 0.0060 | 0.0040 | 0.0020 | near zero everywhere: see expansion-policy gap |
| tag_bridge | 0.0093 | 0.0000 | 0.0073 | graph literally zero: same gap |

Two lessons worth the stage:

1. **"Graph-necessary" is not one thing.** cross_genre probes need edges
   and graph delivers 176× vector's recall. cold_start probes were
   *expected* to need the graph, but the embedding construction (SVD over
   the tag genome) already encodes the tag signal: the vector plane covers
   them. Stratified reporting caught this; a single aggregate would have
   buried it.
2. **The expansion-policy gap.** `path_required` and `tag_bridge` both
   require the expander to surface *2-hop* targets. The Kuzu two-stage
   expansion ranks stage-1 winners by `hops ASC, support DESC` and fills
   its candidate budget (`candidate_multiplier × k`) with 1-hop
   neighbours before any 2-hop target survives. All three arms score ~0:
   these probes aren't separating planes today, they're measuring the
   expansion policy itself. Changing that policy (hop interleaving, per-hop
   quotas, larger budget) is a retrieval fork → ADR if/when we take it
   (phase 05+). The harness's job was to surface exactly this; a
   conformance suite on tiny graphs never would have (same lesson as the
   phase-03 planner traps).

## Fusion tuning (weighted RRF)

Validation half (100 probes, stratified per kind, seed 42) → test half.
Committed run `lyra-f7eb799-20260804T082917Z`:

| graph weight | validation nDCG@10 |
|---|---|
| 0.25 | 0.0276 |
| 0.5 | 0.0275 |
| 0.75 | 0.0271 |
| 1.0 (baseline) | 0.0333 |
| 1.5 | 0.0397 |
| **2.0 (best)** | **0.0443** |

Held-out test half: baseline nDCG@10 0.0391 → tuned **0.0486** (+24%
relative). Consistent with the dilution finding: on this probe set the
graph plane deserves more weight. Two caveats, both honest: (1) the
optimum sits at the *edge* of the grid: the true best weight may be
higher still; widen the grid before ever adopting a value; (2) this tunes
*for the graph-necessary probe set*; a production system would tune
against a traffic-representative mix. Weight 2.0 quantifies the lever, it
doesn't prescribe the setting. Baseline k=60 equal weights stays in
`config/lyra.yaml`; flipping it is a deliberate config change with a
fingerprint change, per platform.

## Flows F1–F6

All six pass against Lyra (hard checks, not benchmarks): F1 similar with
explanations, F2 personalised, F3 cold-start, F4 policy gates verified on
hydrated metadata (min_year + genres_exclude), F5 multi-hop explanation
path, F6 3×-repeated agent chain (similar → policy-refined → explain).

## Latency (open-loop, coordinated-omission-safe)

Method (research 05): fixed arrival rate, latency = done − scheduled_send
(wrk2 semantics: a backed-up service is charged its queueing delay),
HdrHistogram, 500-sample warmup discarded, ≥5,000 samples per run,
concurrency 1/8/32 at ~70% of measured capacity plus one past-the-knee
saturation run at 1.2×. Workload: hybrid `similar(seed)` k=10 over probe
seeds round-robin.

**`latency_indicative: true`**. Lyra is in-process: no network hop, no
serialization, single-tenant. Numbers bound the platform's shape (and the
single-process ceiling of an embedded design: the adapters' engine calls
are synchronous, so concurrency buys queueing, not parallelism); they are
not comparable to Orion/Hydra service latencies until those exist.

Committed run `lyra-f7eb799-20260804T082917Z`: warm mean 118.0ms →
measured capacity 8.5/s. (p99.9 lives in the JSON but is decorative at
5,000 samples, ~5 tail events, so tables stop at p99.)

| rate/s | conc | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|
| 5.9 | 1 | 128.2 | 153.9 | 168.2 | 231.7 | 0 |
| 5.9 | 8 | 128.4 | 154.8 | 169.2 | 198.5 | 0 |
| 5.9 | 32 | 128.4 | 154.2 | 166.8 | 202.9 | 0 |
| 10.2 (saturation) | 32 | 54,231 | 93,192 | 96,666 | 98,763 | 0 |

A prior full run (different sha, ~30% background load on the box) measured
capacity 8.7/s with p50 127.7ms: run-to-run latency drift ~1%, quality
metrics byte-identical.

Two findings, both talk-grade:

1. **The single-process ceiling, measured.** p50/p99 are *identical* at
   concurrency 1, 8, and 32: the embedded design's engine calls are
   synchronous in one process, so added concurrency buys queueing, never
   parallelism. Throughput tops out at ~8.5/s regardless. This is the
   honest cost of "no daemon, no docker", and exactly the axis Orion and
   Hydra (real servers, real connection pools) get to attack.
2. **Coordinated omission, demonstrated.** At 10.2/s arrival (1.2× the
   8.5/s capacity) the open-loop harness reports p50 = **54 seconds**:
   the queue grows without bound and every request is charged from its
   *scheduled* send time. A closed-loop load generator would have reported
   ~120ms while silently throttling itself to capacity. Same service, same
   run: a ~450× difference; the methodology *is* the result.

## Platform configuration & tuning record

Everything a run depends on, so results are attributable and each platform's
setup can be optimized deliberately. The `config_fingerprint` in every
artifact hashes the validated config: a changed fingerprint means a changed
platform, never comparable silently. Orion/Hydra findings docs must carry
this same section.

### Declarative config (`config/lyra.yaml` → `PlatformConfig`)

| setting | value | why / when to revisit |
|---|---|---|
| `fusion.rrf_k` | 60 | Cormack standard (research 05); revisit only with evidence |
| `fusion.weights` | vector 1.0 / graph 1.0 | honest default; **this run measured graph 1.5 as better on graph-necessary probes**: deliberate config change if adopted |
| `retrieval.candidate_multiplier` | 5 (×k fetch per plane) | implicated in the expansion-policy gap: 2-hop targets crowded out at 250 candidates; raising it trades latency for depth |
| `retrieval.graph_seeds` | 10 | top vector hits seeding graph when no item seed |
| `retrieval.max_hops` | 2 | matches probe design; 3 untested at scale |
| `data.embedding_dim` | 256 | TruncatedSVD over item×tag genome (ADR 0002) |
| `data.random_seed` | 42 | everything seeded: SVD, probe sampling, validation split |
| `data.split_cutoff_quantile` | 0.95 | global temporal split, cutoff ts=1545602470 |
| `engines.vector.adapter` | `flat` | exact search = recall referee; `hnsw` is the ablation arm |

### Engine setup (adapters, in-process)

- **DuckDB (relational):** `items` + `users` materialized with train-side
  aggregates; `interactions` stays a *view* over sorted parquet (zonemap
  pruning does the indexing). Policy vocabulary is closed
  (`min_year, max_year, genres_any, genres_exclude, min_ratings`): unknown
  keys raise, gates are hard filters, never score penalties.
- **faiss flat (vector, primary):** `IndexIDMap2(IndexFlatIP(256))`, L2-
  normalized vectors so inner product = cosine. Exclusions via
  `IDSelectorNot(IDSelectorBatch)` search parameter. Recall 1.0 by
  construction: no tuning surface, which is the point.
- **hnswlib (vector, ablation arm):** M=16, ef_construction=200,
  ef_search=200, single-threaded + seeded for byte-determinism,
  k clamped to reachable ids (filter-callback contiguity trap).
- **Kuzu 0.11.3 (graph):** opened `read_only`, schema init skipped.
  Queries **literal-inlined**: prepared params, `list_contains()`, and any
  far-node predicate all silently kill recursive-match predicate pushdown
  (phase-03 finding; `docs/runbooks/run-lyra.md`). Two-stage expansion:
  aggregate `(target, min-hops, support)` in-engine, then one SHORTEST
  path per winner for the explanation.
- **Graph load:** `HAS_GENRE`, `HAS_TAG`, `CO_RATED` edges only: `RATED`
  deliberately excluded (1.6M vs 24.6M edges; revisit if user-seeded walks
  land). Bulk `COPY FROM` parquet, built in `kuzu.tmp` then atomically
  renamed. 58,552 nodes / 1,684,608 directed edges.
- **Vector artifacts:** `.npy` matrices mmap-loaded; user vectors resolved
  through a row-index dict (avoids a ~1.5 GB in-memory dict).

### Harness settings (fixed across platforms for comparability)

Retrieval depth k=50 per arm; latency workload hybrid `similar` k=10;
open-loop rates at 0.7× measured capacity (+1.2× saturation run),
concurrency 1/8/32, ≥5,000 samples, 500 warmup discarded, HdrHistogram
µs-resolution. Single-tenant, same box (28-core/62 GB), pinned versions
recorded per-artifact under `versions`.

## Incidents (teaching value)

- **numpy downgrade:** ranx → numba 0.66 ceiling forced numpy 2.5.1 →
  2.4.6 across the project (uv.lock). All suites stayed green; recorded so
  nobody "upgrades numpy back" without noticing what breaks.
- **`n_ratings` isn't canonical:** first runner draft read `n_ratings`
  from `items.parquet`; that aggregate exists only inside the relational
  plane's materialized table. Novelty popularity now computes from train
  interactions directly. Lesson: canonical parquet is the contract,
  derived aggregates are plane-private.
- **Buffered background runs:** piping a long run through `tail` hides all
  progress until exit; run benchmarks with unbuffered output (or watch the
  artifact directory) when supervising.

## Artifacts

- `bench/results/lyra-<sha>-<utc>.json`: committed machine-readable run
- `bench/report.md`: generated cross-run tables + verdicts (`make report`)
- Progress log: `docs/plans/2026-08-04-knowledge-plane/phase-04-harness.md`
- Narrative milestone: `04-migration-narrative.md`
