# 07 — Lyra benchmark findings (phase 04, go/no-go)

- **Date:** 2026-08-04
- **Platform:** Lyra, the embedded knowledge plane (DuckDB · faiss flat ·
  Kuzu 0.11.3, in-process, no daemon)
- **Method:** `docs/plans/2026-08-04-knowledge-plane/phase-04-harness.md` +
  research `05-embeddings-and-benchmarks.md`; harness in
  `src/constellate/bench/`; machine artifacts in `bench/results/*.json`
  (committed, one per run), generated tables in `bench/report.md`
- **Reproduce:** `make bench PLATFORM=lyra && make report`
  (`docs/runbooks/run-benchmarks.md`)
- **Verdict: GO** — the multi-plane contract measurably beats vector-only
  retrieval on the graph-necessary probe set (details below)

Sibling docs will cover Orion (phase 05) and Hydra (phase 06); this one is
Lyra only. Cross-platform synthesis comes with the phase-08 report.

## Setup

200 probes, 4 kinds × 50 (`tag_bridge`, `cold_start`, `cross_genre`,
`path_required` — construction in `constellate.ingest.probes`), each a
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
graph weight in the pipeline's own `rrf` on a stratified validation half of
the probes, scores on the held-out half — so the winning weight drops
straight into `config/lyra.yaml` `fusion.weights`.

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
  not a free lunch — weighting is a real lever, not a checkbox.

## Findings by probe kind (R@10, vector / graph / hybrid)

| kind | vector_only | graph_only | hybrid | reading |
|---|---|---|---|---|
| cross_genre | 0.0020 | **0.3520** | 0.0666 | graph's blowout — CO_RATED edges cross genre walls vectors can't |
| cold_start | **0.0680** | 0.0300 | 0.0660 | vector *wins*: genome-SVD vectors are built from tags, so cold items (few ratings, rich tags) sit well in vector space |
| path_required | 0.0060 | 0.0040 | 0.0020 | near zero everywhere — see expansion-policy gap |
| tag_bridge | 0.0093 | 0.0000 | 0.0073 | graph literally zero — same gap |

Two lessons worth the stage:

1. **"Graph-necessary" is not one thing.** cross_genre probes need edges
   and graph delivers 176× vector's recall. cold_start probes were
   *expected* to need the graph, but the embedding construction (SVD over
   the tag genome) already encodes the tag signal — the vector plane covers
   them. Stratified reporting caught this; a single aggregate would have
   buried it.
2. **The expansion-policy gap.** `path_required` and `tag_bridge` both
   require the expander to surface *2-hop* targets. The Kuzu two-stage
   expansion ranks stage-1 winners by `hops ASC, support DESC` and fills
   its candidate budget (`candidate_multiplier × k`) with 1-hop
   neighbours before any 2-hop target survives. All three arms score ~0 —
   these probes aren't separating planes today, they're measuring the
   expansion policy itself. Changing that policy (hop interleaving, per-hop
   quotas, larger budget) is a retrieval fork → ADR if/when we take it
   (phase 05+). The harness's job was to surface exactly this; a
   conformance suite on tiny graphs never would have (same lesson as the
   phase-03 planner traps).

## Fusion tuning (weighted RRF)

Validation half (100 probes, stratified per kind, seed 42) → test half:

| graph weight | validation nDCG@10 |
|---|---|
| 0.25 | 0.0303 |
| 0.5 | 0.0302 |
| 0.75 | 0.0297 |
| 1.0 (baseline) | 0.0427 |
| **1.5 (best)** | **0.0481** |
| 2.0 | 0.0475 |

Held-out test half: baseline nDCG@10 0.0418 → tuned **0.0479** (+15%
relative). Consistent with the dilution finding: on this probe set the
graph plane deserves more weight. Baseline k=60 equal weights stays in
`config/lyra.yaml` (the honest default); the tuned weight is reported, not
silently applied — flipping it is a config change with a fingerprint change,
made deliberately per platform.

Note the caveat: this tunes *for the graph-necessary probe set*. A
production system would tune against a traffic-representative query mix;
weight 1.5 here quantifies the lever, it doesn't prescribe the setting.

## Flows F1–F6

All six pass against Lyra (hard checks, not benchmarks): F1 similar with
explanations, F2 personalised, F3 cold-start, F4 policy gates verified on
hydrated metadata (min_year + genres_exclude), F5 multi-hop explanation
path, F6 3×-repeated agent chain (similar → policy-refined → explain).

## Latency (open-loop, coordinated-omission-safe)

Method (research 05): fixed arrival rate, latency = done − scheduled_send
(wrk2 semantics — a backed-up service is charged its queueing delay),
HdrHistogram, 500-sample warmup discarded, ≥5,000 samples per run,
concurrency 1/8/32 at ~70% of measured capacity plus one past-the-knee
saturation run at 1.2×. Workload: hybrid `similar(seed)` k=10 over probe
seeds round-robin.

**`latency_indicative: true`** — Lyra is in-process: no network hop, no
serialization, single-tenant. Numbers bound the platform's shape (and the
single-process ceiling of an embedded design — the adapters' engine calls
are synchronous, so concurrency buys queueing, not parallelism); they are
not comparable to Orion/Hydra service latencies until those exist.

Committed run `lyra-c368e54-20260804T071640Z`: warm mean 114.8ms →
measured capacity 8.7/s.

| rate/s | conc | p50ms | p95ms | p99ms | p99.9ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 6.1 | 1 | 127.7 | 156.0 | 173.3 | 206.3 | 234.2 | 0 |
| 6.1 | 8 | 126.6 | 152.3 | 166.8 | 188.4 | 197.4 | 0 |
| 6.1 | 32 | 126.3 | 151.3 | 166.1 | 185.9 | 216.1 | 0 |
| 10.5 (saturation) | 32 | 61,440 | 107,545 | 111,542 | 113,312 | 113,771 | 0 |

Two findings, both talk-grade:

1. **The single-process ceiling, measured.** p50/p99 are *identical* at
   concurrency 1, 8, and 32 — the embedded design's engine calls are
   synchronous in one process, so added concurrency buys queueing, never
   parallelism. Throughput tops out at 8.7/s regardless. This is the
   honest cost of "no daemon, no docker" — and exactly the axis Orion and
   Hydra (real servers, real connection pools) get to attack.
2. **Coordinated omission, demonstrated.** At 10.5/s arrival (1.2× the
   8.7/s capacity) the open-loop harness reports p50 = **61 seconds** —
   the queue grows without bound and every request is charged from its
   *scheduled* send time. A closed-loop load generator would have reported
   ~115ms while silently throttling itself to 8.7/s. Same service, same
   run — the methodology *is* the result.

## Platform configuration & tuning record

Everything a run depends on, so results are attributable and each platform's
setup can be optimized deliberately. The `config_fingerprint` in every
artifact hashes the validated config — a changed fingerprint means a changed
platform, never comparable silently. Orion/Hydra findings docs must carry
this same section.

### Declarative config (`config/lyra.yaml` → `PlatformConfig`)

| setting | value | why / when to revisit |
|---|---|---|
| `fusion.rrf_k` | 60 | Cormack standard (research 05); revisit only with evidence |
| `fusion.weights` | vector 1.0 / graph 1.0 | honest default; **this run measured graph 1.5 as better on graph-necessary probes** — deliberate config change if adopted |
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
  (`min_year, max_year, genres_any, genres_exclude, min_ratings`) — unknown
  keys raise, gates are hard filters, never score penalties.
- **faiss flat (vector, primary):** `IndexIDMap2(IndexFlatIP(256))`, L2-
  normalized vectors so inner product = cosine. Exclusions via
  `IDSelectorNot(IDSelectorBatch)` search parameter. Recall 1.0 by
  construction — no tuning surface, which is the point.
- **hnswlib (vector, ablation arm):** M=16, ef_construction=200,
  ef_search=200, single-threaded + seeded for byte-determinism,
  k clamped to reachable ids (filter-callback contiguity trap).
- **Kuzu 0.11.3 (graph):** opened `read_only`, schema init skipped.
  Queries **literal-inlined** — prepared params, `list_contains()`, and any
  far-node predicate all silently kill recursive-match predicate pushdown
  (phase-03 finding; `docs/runbooks/run-lyra.md`). Two-stage expansion:
  aggregate `(target, min-hops, support)` in-engine, then one SHORTEST
  path per winner for the explanation.
- **Graph load:** `HAS_GENRE`, `HAS_TAG`, `CO_RATED` edges only — `RATED`
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

- `bench/results/lyra-<sha>-<utc>.json` — committed machine-readable run
- `bench/report.md` — generated cross-run tables + verdicts (`make report`)
- Progress log: `docs/plans/2026-08-04-knowledge-plane/phase-04-harness.md`
- Narrative milestone: `04-migration-narrative.md`
