# 10 — Hydra benchmark findings (phase 06)

- **Date:** 2026-08-04
- **Platform:** Hydra, the composed knowledge plane — three containers, one
  engine per plane: Postgres 18.4 (source of truth + relational plane) ·
  Qdrant v1.18.3 (vector) · Memgraph Community 3.12.0 (graph, ADR 0005)
- **Method:** identical harness and probe set as Lyra and Orion
  (`07-lyra-benchmark-findings.md`, `08-orion-benchmark-findings.md`); one
  committed run, `hydra-0b36d7c-20260804T134236Z`, taken *after* the
  independent review's fixes landed (the pre-review run was discarded, see
  Incidents)
- **Reproduce:** `make up load bench PLATFORM=hydra && make report`
  (`docs/runbooks/run-hydra.md`)
- **Verdict: GO, and the abstraction holds on the third platform.** Hybrid
  beats vector-only R@10 by +0.0138 (p=0.0038), and the hybrid arm lands
  within tolerance of Lyra (R@10 −0.0017, nDCG@10 −0.0025, tolerance ±0.02).
  The graph plane reproduces Lyra's and Orion's numbers *exactly*.

## Headline numbers (200 probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0200 | 0.0366 | 0.0238 | 0.0625 | 0.0279 | 17.29 |
| graph_only | **0.0965** | **0.3516** | **0.0752** | **0.1025** | 0.0172 | 13.04 |
| hybrid | 0.0338 | 0.2377 | 0.0337 | 0.0744 | 0.0252 | 15.35 |

Ablation gate re-confirmed on a third platform: hybrid > vector_only on
R@10 by +0.0138 (p=0.0038, paired student-t; +0.0098 nDCG@10 at p=0.042)
and on R@50 by +0.2011. `graph_only` still dominates both other arms
(p=1.6e-06 vs hybrid) — the equal-weight-RRF dilution finding from Lyra
reproduces here unchanged. Fusion fidelity check exact again (offline
w=1.0 nDCG@10 0.033683 = pipeline hybrid arm 0.033683).

## The findings that matter

### 1. Four engines, one ranking contract — and now a test that guards it

`graph_only` on Hydra matches Lyra (Kuzu) and Orion (CTE **and** AGE) to
four decimals on **every** metric and **every** probe kind: R@10 0.0965,
R@50 0.3516, nDCG@10 0.0752, RR@10 0.1025, cross_genre R@10 0.3520,
coverage 0.0172, novelty 13.04. Four graph engines — an embedded
columnar store, recursive SQL, an in-Postgres Cypher extension, and a
dedicated in-memory C++ graph server — produce byte-identical retrieval
from the same data through the same plane contract. This is the
strongest evidence the project has for its central thesis, and it is now
*stronger than a coincidence of numbers*: phase 06 committed
`tests/conformance/test_graph_parity.py`, a differential test that runs
CteGraph and MemgraphGraph over 8 seeded random graphs across every
(hops × seed-count × type-filter) combination and compares item order,
hops, score and path field by field. Equivalence stopped being an
observation and became a check that fails.

Worth naming precisely *what* was engineered to make that true, because
it was not free (L2, L11): Memgraph's ranking is `cte.py`'s query shape
reproduced almost literally — hop counts unrolled into pre-aggregated
`UNION ALL` branches, a single outer aggregate summing support across
hop lengths, `(hops ASC, support DESC, dst ASC)` ordering applied
*in-engine* before the LIMIT. One MATCH clause per hop, not one pattern:
relationship uniqueness is scoped to a MATCH, so a single pattern is
trail-semantic and diverged from CteGraph on 1 of 144 three-hop cases (a
support tie-flip). Splitting the clauses made the 432-case differential
432/432 exact — and deleted the EdgeUniquenessFilter operator worth
294ms. Correctness and speed pulled the same direction, which is rarer
than it sounds.

### 2. A real HNSW: Qdrant ≈ exact search, and ~2× pgvector halfvec

Qdrant's vector arm scores R@10 **0.0200** — against Lyra's faiss-flat
*exact* referee at 0.0213 and Orion's pgvector HNSW-on-halfvec at 0.0108.
So a properly-built HNSW at M=16 / ef_construction=200 / ef_search=200
retains ~94% of exact-search recall on this probe set, and delivers
roughly **double** what pgvector's halfvec index does at the *same*
M/ef parameters.

The delta between the two ANN indexes is therefore not the algorithm and
not the tuning — it is the arithmetic. Orion stores `halfvec` (fp16) for
the 50% storage win; Hydra stores fp32. At 256 dims over an SVD-of-tag-
genome embedding, the quantisation loss lands hardest exactly where
Orion's loss concentrated: cold_start probes, where items sit in the
genre-mean fallback region and neighbours are tightly bunched. Hydra's
cold_start vector recall is 0.0580, against Orion's 0.0300 and Lyra's
exact 0.0680. Keeping an exact-search referee (L5, ADR 0002) is what
makes this readable as an *index property* rather than a probe-set quirk
— with three points on the line (exact 0.0213, fp32 HNSW 0.0200, fp16
HNSW 0.0108) the cost of half-precision is legible at a glance.

Caveat, stated once and loudly: 0.0200 is what this collection scored
*after* the L10 fix. Before it, Qdrant answered every query correctly,
reported `status: green`, and had built no index at all. The number
above measures HNSW only because the loader now proves the index exists
(engine-reported `engine_state` in the artifact: items 61,440/62,423
indexed, users 155,648/156,604 — the sub-threshold tail segment stays
plain by design).

### 3. Latency: flat, unsaturated — and still slower than one Postgres

Warm mean 103.8ms → estimated capacity 9.6/s. p50 is **flat at ~115ms
across concurrency 1, 8 and 32** at a fixed 6.7/s, and the past-the-knee
run at 11.6/s (1.2× estimated capacity) **did not saturate** — p50
actually *fell* to 109.9ms, zero errors, completion rate matching arrival
rate to four decimals.

That combination is worth unpacking, because it looks like Lyra's flat
curve and means the opposite thing:

- **Lyra** was flat *because it was saturated at any concurrency* — one
  process, synchronous engine calls, so concurrency bought queueing, not
  parallelism. Push it to 1.2× and p50 went to 54 *seconds*.
- **Hydra** is flat because at 6.7/s it is nowhere near its knee. The
  1.2× run proves it: three server engines absorb concurrency the way
  Orion's Postgres did, and the harness's *sequential* capacity estimator
  understates a concurrent backend (same caveat Orion recorded — the real
  knee is above 1.2× and finding it needs a rate sweep, still future
  work).

And then the finding that complicates the pitch. Hydra — "best engine per
plane", three dedicated servers, 28 cores available — is **~2.7× slower
than Orion**, which is one Postgres container doing all three planes in
recursive SQL: p50 115ms vs 43ms, warm mean 103.8ms vs 38.1ms. It beats
only Lyra (p50 127ms), and beats it by less than the container count
would suggest.

The cost is localised. The vector and graph legs are issued concurrently
(`asyncio.gather` in `core/pipeline.py`), so a hybrid request costs
roughly `max(vector, graph) + hydration + fusion` — and the graph leg is
the max by a wide margin. Evidence: Memgraph's measured end-to-end
`expand(max_hops=2, limit=50)` is 132ms for a single seed, 201ms for a
random 10-seed set, 663ms for the hub-heavy popular-10 set, against
Orion's CTE at 43ms on *identical semantics*. It shows up in the flow
timings too — F1 (single item seed) 108.6ms and F3 (cold-start seed)
104.6ms sit right at the p50, while F2 and F4 (user seeds, which fan the
graph out over 10 vector-derived seeds) cost 438.9ms and 416.1ms. The
vector leg is not separately instrumented in this artifact, but it cannot
be the driver: Orion's *entire* request — relational hydration, pgvector
HNSW and a 2-hop CTE expansion — completes in 43ms.

The honest reading, which belongs on stage rather than in a footnote:
**the dedicated graph engine is the slow part of the composed platform.**
The floor is data, not planner incompetence — `genre:Drama` alone has
25,606 edges, 10 popular seeds legitimately generate 2.98M two-hop paths,
and `support` is contractually defined as counting every one of them
(L11). Memgraph walks those paths through Bolt-attached in-memory
structures; Postgres walks them as index-only self-joins over a covering
index inside the same process that holds the data. On *this* workload —
58k nodes, 1.68M edges, comfortably RAM-resident, single-tenant — the
composed architecture buys independent scaling and per-plane operational
isolation, and pays ~2.7× latency plus 3× the containers for it. ADR
0005 chose Memgraph on a concurrency-scaling argument, and the
concurrency scaling is real (the 1.2× run proves it). What the benchmark
adds is the missing half of the sentence: it scales from a slower
starting point than the SQL it was supposed to beat, and this dataset
never gets big enough to collect on the scaling. That is not a reason to
revisit ADR 0005 at this scale — it is the reason the revisit trigger
should be *dataset size*, not disappointment.

### 4. The CDC proof: both projections rebuilt from Postgres alone

`make rebuild PLATFORM=hydra` drops both derived stores and regenerates
them from Postgres and nothing else — no parquet, no canonical data, no
manifest gate. Measured: **40.7–44.3s** (Qdrant items 7.9s, users 19.6s;
CSV export 1.9s; Memgraph wipe 1.5s, nodes 0.1s, edges 7.9s), against a
full cold `make load` of 98.9s including the chained rebuild. That is the
shape a CDC pipeline would take, demonstrated end to end rather than
asserted in an ADR.

Two properties make it evidence instead of a script that exits zero, and
both were retrofitted after review caught their absence:

- **Cross-engine count verification.** Point counts are read back *from
  Qdrant* (`client.count(exact=True)`) and node/edge counts *from
  Memgraph*, then compared against Postgres. The first implementation
  compared Postgres to the loader's own streamed total — a number
  Postgres produced — which could never disagree. A verification step
  that cannot fail is not a verification step.
- **An index barrier.** `_await_indexed` blocks until Qdrant's optimizer
  reports two consecutive identical `indexed_vectors_count` values *and*
  a green status, with a 120s timeout that exits non-zero. Note it does
  not wait for `indexed == total`: the 1000-KB indexing threshold leaves
  each segment's tail unindexed forever, so equality would hang. Polling
  for *stability* is the correct barrier; a benchmark started without it
  can measure a half-built index (L10's lesson, generalised).

### 5. The determinism boundary (an L9 amendment, measured here)

Everything in this project is seeded — SVD, sampling, splits — and
quality metrics have been byte-identical across reruns since phase 02.
Hydra found the edge of that guarantee: **Qdrant's HNSW build is
multi-threaded and unseeded**, so every rebuild produces a slightly
different index. Two otherwise-identical bench runs (same sha, same data,
a rebuild between them) measured hybrid nDCG@10 **0.0353 vs 0.0337** —
drift originating in the vector arm and propagating through fusion.

Lyra never had this because its hnswlib build is pinned single-threaded
and seeded — a knob available in-process that a server engine simply does
not expose. Consequence, recorded in L9's boundary note: **Hydra's
quality metrics are tolerance-reproducible, not byte-reproducible.** The
±0.02 equivalence gate absorbs a 0.0016 wobble comfortably (the gate
passed at −0.0025 nDCG@10 vs Lyra, an order of magnitude inside
tolerance), and `engine_state` in the artifact records what the engine
says about its own index so any drift is attributable rather than
mysterious. For builders: when the index lives in someone else's daemon,
replace "byte-identical" claims with a stated tolerance and record the
engine's own view of its index state.

## Findings by probe kind (R@10, vector / graph / hybrid)

| kind | vector_only | graph_only | hybrid | reading |
|---|---|---|---|---|
| cross_genre | 0.0087 | **0.3520** | 0.0619 | graph's blowout, 40× vector — identical to every other platform |
| cold_start | **0.0580** | 0.0300 | 0.0620 | vector wins again; between Lyra's exact 0.0680 and Orion's halfvec 0.0300 |
| path_required | 0.0060 | 0.0040 | 0.0040 | near zero everywhere — the expansion-policy gap, unchanged |
| tag_bridge | 0.0073 | 0.0000 | 0.0073 | graph literally zero — same gap |

Nothing new in the shape: the expansion-policy gap (2-hop targets crowded
out of the candidate budget by 1-hop neighbours, doc 07) is a *contract*
property, so it reproduces exactly across all four graph engines. Which
is itself the point — a platform-independent weakness stays platform-
independent, and fixing it is a retrieval fork requiring an ADR, not a
tuning exercise on one engine.

## Fusion tuning (weighted RRF)

Validation half (100 probes, stratified per kind, seed 42) → held-out
test half, tuned in the pipeline's own `rrf` at true fusion depth
(`candidate_multiplier × k` = 250):

| graph weight | validation nDCG@10 |
|---|---|
| 0.25 | 0.0258 |
| 0.5 | 0.0243 |
| 0.75 | 0.0249 |
| 1.0 (baseline) | 0.0345 |
| 1.5 | 0.0426 |
| **2.0 (best)** | **0.0482** |

Held-out test half: baseline nDCG@10 0.0329 → tuned **0.0417** (+27%
relative). Third platform, third time the optimum lands at the grid edge
at weight 2.0; the lever size tracks vector-arm strength exactly as
predicted (Orion's weakest vector arm → +59%, Hydra's mid → +27%, Lyra's
exact → +24%). Same two caveats as always: grid-edge optima mean the true
best may be higher, and this tunes *for a graph-necessary probe set*.
`config/hydra.yaml` keeps 1.0/1.0.

## Flows F1–F6

All six pass (hard checks, not benchmarks): F1 similar with explanations
(108.6ms), F2 personalised (438.9ms), F3 cold-start (104.6ms), F4 policy
gates on hydrated metadata (416.1ms), F5 multi-hop explanation path, F6
3×-repeated agent chain (similar → policy-refined → explain: 87.3 /
122.8 / 0.8ms per cycle, stable across all three repeats). The F2/F4
outliers are the 10-seed graph fan-out discussed above, not a policy or
hydration cost.

## Latency (open-loop, coordinated-omission-safe)

Method unchanged (research 05): fixed arrival rate, latency = done −
scheduled_send (wrk2 semantics), HdrHistogram, 500-sample warmup
discarded, 5,000 samples per run, concurrency 1/8/32 at ~70% of measured
capacity plus one past-the-knee run at 1.2×. Workload: hybrid
`similar(seed)` k=10 over probe seeds round-robin.

`latency_indicative: true` is still set in the artifact — the harness
calls the service in-process rather than over the REST API, so these
numbers include the engines' network hops (Bolt, gRPC, the Postgres wire
protocol) but not an HTTP front end.

Committed run `hydra-0b36d7c-20260804T134236Z`: warm mean 103.84ms →
estimated capacity 9.6/s.

| rate/s | conc | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|
| 6.7 | 1 | 114.7 | 165.2 | 193.8 | 239.5 | 0 |
| 6.7 | 8 | 115.1 | 171.1 | 199.7 | 279.8 | 0 |
| 6.7 | 32 | 114.6 | 170.5 | 198.7 | 269.1 | 0 |
| 11.6 (1.2× est.) | 32 | 109.9 | 160.8 | 193.2 | 246.9 | 0 |

Cross-platform, same box, same probe seeds, same workload:

| platform | warm mean | p50 @ c32 | est. capacity | 1.2× run |
|---|---|---|---|---|
| Lyra (embedded) | 118.0ms | 128.4ms | 8.5/s | p50 54,231ms — saturated hard |
| Orion (one Postgres) | 38.1ms | 43.6ms | 26.2/s | p50 40.8ms — did not saturate |
| **Hydra (three engines)** | **103.8ms** | **114.6ms** | **9.6/s** | **p50 109.9ms — did not saturate** |

Hydra sits between the two on wall-clock and shares Orion's *shape*: a
server-backed platform whose capacity estimator undercounts it. The gap
to Orion is the graph leg, per finding 3.

## Footprint and operational cost

Measured post-load, idle (`docs/runbooks/run-hydra.md`):

| platform | containers | idle RSS | volumes | images | load / rebuild |
|---|---|---|---|---|---|
| Lyra | 0 (in-process) | — | 348MB on disk | — | n/a |
| Orion | 1 | 794MiB | 6.8GB | 694MB | 25M interactions in 43s, ~90s fresh |
| **Hydra** | **3** | **~2.27GiB** (pg 1.57GiB, memgraph 378MiB, qdrant 335MiB) | **~9.9GB** (pg 6.51GB, memgraph 2.07GB, qdrant 1.32GB) | **1,851MB** (pg 650 + qdrant 270 + memgraph 931) | 98.9s cold; rebuild 40.7–44.3s |

Plus `data/hydra/import` at 73MB — the CSV staging directory Memgraph's
server-side `LOAD CSV` reads through a bind mount.

Roughly **3× Orion's memory and 1.5× its disk** for the same 25M
interactions and 1.68M edges, because the data is now stored three times:
canonically in Postgres, projected into Qdrant's segments, and projected
into Memgraph's in-memory graph (with its own on-disk snapshot). That
duplication is not waste, it is the architecture — but a talk that says
"best engine per plane" should show this table next to the latency table.

**A correction to the record:** ADR 0005's option analysis cited a
"221MB image" for Memgraph Community 3.12 as a point in its favour
against Neo4j's JVM footprint. The pulled `memgraph/memgraph:3.12.0`
image is **931MB** — 4.2× the researched figure, and the largest of the
three. The decision does not change (the ADR turned on concurrency
scaling and Bolt compatibility, not image size, and 931MB is still well
under a Neo4j CE image), so this is not a supersede — but the research
number was wrong and the ADR should not be quoted for it. Likely a
mismatch between the `-lean`/MAGE-free variants and the plain tag;
whatever the cause, the lesson is the cheap one: **verify vendor size
claims by pulling the image before they enter a decision document.**

## Platform configuration & tuning record

Everything a run depends on, so results are attributable and each
platform's setup can be optimized deliberately. Shared knobs (fusion,
retrieval, data) are identical to Lyra's record in doc 07 — single
source `config/hydra.yaml`, fingerprint `3e16e0cd60325e98`. Note the
fingerprint moved vs the phase-05 artifacts because
`bench.quality_tolerance` was lifted out of `engines` (review fix m8); old
artifacts remain valid snapshots of their own configs.

### Declarative config (`config/hydra.yaml` → `PlatformConfig`)

| setting | value | why / when to revisit |
|---|---|---|
| `fusion.rrf_k` | 60 | Cormack standard (research 05); unchanged across all platforms so fusion is never a confound |
| `fusion.weights` | vector 1.0 / graph 1.0 | honest default; this run measured graph 2.0 as better on graph-necessary probes — adopting it is a deliberate config change with a new fingerprint |
| `retrieval.candidate_multiplier` | 5 (×k per plane) | implicated in the expansion-policy gap on every platform; raising it trades latency for 2-hop depth, and on Hydra that latency is the *graph* leg — most expensive platform to raise it on |
| `retrieval.graph_seeds` | 10 | top vector hits seeding graph when no item seed. **This is Hydra's dominant latency knob**: 10 hub-heavy seeds cost 663ms of expansion vs 132ms for one. Revisit if user-seeded flows (F2/F4) ever need to be interactive |
| `retrieval.max_hops` | 2 | matches probe design. 3 is *usable but not default* here — 124s on hub-heavy seeds (`MAX_HOPS` caps at 3); treat as a small-seed/typed-edge option |
| `data.embedding_dim` | 256 | TruncatedSVD over item×tag genome (ADR 0002) |
| `data.random_seed` | 42 | SVD, probe sampling, validation split — all seeded. Does **not** cover Qdrant's index build (finding 5) |
| `bench.quality_tolerance` | 0.02 | report-layer knob, deliberately top-level so it stays out of the platform fingerprint |

### Compose (`compose/hydra.yml`, project `constellate-hydra`)

| knob | value | why / when to revisit |
|---|---|---|
| image pins | `postgres:18.4`, `qdrant/qdrant:v1.18.3`, `memgraph/memgraph:3.12.0` | exact tags, never `latest` — a benchmark cites a version. Revisit on a deliberate upgrade run, re-benched |
| host ports | pg 15433, qdrant 16333 REST / 16334 gRPC, memgraph 17687 | convention: engine default + 10000, and +1 on Postgres so Hydra and Orion run *simultaneously* (15432 is Orion's) |
| `shared_buffers` | 2GB | 25M-row interactions + 1.68M-edge table stay hot; same as Orion for comparability. Revisit if the dataset grows past ~2× |
| `maintenance_work_mem` | 1GB | **half Orion's 2GB, and no `shm_size` override** — Hydra's Postgres holds vectors as plain `real[]` with no pgvector and therefore builds no HNSW index. Orion needed 2GB + `shm_size: 4g` precisely because its parallel HNSW build died with "could not resize shared memory segment"; Hydra's ANN build happens in Qdrant's own process, so the shared-memory pressure never exists. Revisit only if pgvector is ever added to Hydra's Postgres |
| `max_wal_size` | 4GB | keeps the 25M-row COPY from checkpoint-thrashing; loader-side knob, irrelevant at serve time |
| `--storage-light-edge=true` | on | edge-heavy graph (1.68M directed edges), ADR 0005. Verified compatible with edge properties (`edge_type`/`weight` round-trip). Revisit if edges ever need many properties |
| `--memory-limit=8192` | 8GiB | hard cap so a runaway expansion can't OOM the box mid-benchmark; measured idle RSS is 378MiB, so it is a guard rail, not a budget. Raise before attempting `max_hops=3` benchmarking |
| `--telemetry-enabled=false`, `--log-level=WARNING` | — | no phone-home during a measured run; log noise off the critical path |
| healthchecks | pg `pg_isready` over TCP; qdrant `bash /dev/tcp` (image ships no curl/wget); memgraph `mgconsole` | the TCP form is deliberate — a socket-only init server fools socket-file checks (run-orion runbook, 2026-08-04) |
| bind mount | `../data/hydra/import:/import:ro` | Memgraph's `LOAD CSV` reads files *server-side*; the loader COPYs CSVs to the host and Memgraph reads them back through the mount. Read-only on purpose |

### Qdrant collection config (`planes/vector/qdrant.py`, adapter-owned)

| knob | value | why / when to revisit |
|---|---|---|
| distance | `Dot` on L2-normalised vectors | = cosine, matching pgvector's `ip_ops` and faiss `IndexFlatIP` — score conventions must agree across platforms or fusion isn't comparable |
| point ids | raw int item_id / user_id | Qdrant supports unsigned int ids natively; no id-mapping layer to get wrong |
| `m` | 16 | parity with Lyra's hnswlib arm and Orion's pgvector index. Never change one platform's ANN params alone |
| `ef_construct` | 200 | same parity argument; build-time recall/latency trade |
| `hnsw_ef` (search) | 200 | query-time, passed per search via `SearchParams`. Raise for recall, at latency cost — but only in lockstep across platforms |
| `indexing_threshold` | 1000 | **measured in KILOBYTES per segment, not points.** At 256-dim fp32 a vector is ~1KB, so the number happens to read like a point count — a coincidence that makes this knob unusually easy to misread. The 20,000KB default never triggered at ~62k points over 8 segments (~7.8k each) and the collection silently served brute force (L10). Revisit if segment sizing changes or dimensionality moves off 256, where the KB↔point coincidence breaks |
| index-state verification | `engine_state` in every artifact + `_await_indexed` barrier | the fix for "green means nothing": the artifact records engine-reported indexed/total per collection, and the rebuild blocks on optimizer stability before returning |
| ownership | config lives in the adapter; loader calls `ensure_collections()` | load-time/serve-time config drift is how referee comparisons silently rot. One place, both callers |
| client | `prefer_grpc=True`, grpc_port 16334, 120s loader timeout | gRPC for the hot path; the long timeout is for bulk upserts only |

### Memgraph query-shape decisions (`planes/graph/memgraph.py`)

These are *configuration* in every sense that matters — they were chosen
against measurements, and changing one changes the measured system.
Full derivation in L11 and the adapter docstring; pointers only here.

| decision | why / when to revisit |
|---|---|
| `UNWIND $seeds AS sk MATCH (s:Node {key: sk})`, never `WHERE s.key IN $seeds` | the `IN` form makes the planner skip the `:Node(key)` index entirely — ScanAll + backwards expand over 961,805 edges, 65% of time in the filter. Revisit if a Memgraph release fixes `IN`-list index selection; verify with PROFILE, not release notes |
| hops unrolled into flat chains; no `[:REL*1..2]` | variable-length patterns DFS-materialise every path and ran >312s on hub seeds vs 629ms flat. ADR 0005's planned `[*wShortest]` was abandoned for this reason (phase-06 scope note). Revisit only with a PROFILE showing the planner has changed |
| one MATCH clause per hop | relationship uniqueness is MATCH-scoped; split clauses give the CTE's unrestricted-walk semantics *and* delete EdgeUniquenessFilter (294ms). Correctness first — this is what makes the parity test pass 432/432. **Do not "simplify" back into one pattern** |
| aggregate in-engine, LIMIT in-engine | returning ~50k rows/hop over Bolt cost 815ms wall for ~150ms of engine time; merging + limiting server-side is 201ms. Revisit only if the ranking contract changes |
| pre-aggregate inside each `UNION ALL` branch | hands the union ~50k rows instead of ~3M; Apply+Union 682ms → 13ms |
| predicates after the aggregate | prefix/seed predicates are on the group key, so this is a pure rewrite: 2324ms → 1162ms by keeping two string comparisons off a multi-million-row stream |
| `:Node(key)` index created before the edge load | the edge pass MATCHes both endpoints by key; without it the rebuild is quadratic |
| batched `DETACH DELETE`, never `DROP GRAPH` | `DROP GRAPH` requires analytical storage mode, which we will not leave a durable instance in mid-operation. Keeps every transaction bounded (`DELETE_BATCH` 200,000) |

### Connections, batching and overrides

| knob | value | why / when to revisit |
|---|---|---|
| asyncpg pool | `min_size=2, max_size=8, timeout=5` | identical to Orion's, so the relational plane is not a confound between platforms. Raise only alongside a rate sweep that finds the real knee |
| neo4j async driver | default pool, `auth=None` | Memgraph Community has no auth; one Bolt client codebase across Memgraph and any future Neo4j reference run is precisely what ADR 0005 bought |
| loader batches | interactions 500,000 · vectors 8,192 · qdrant upsert 4,096 · delete 200,000 · `USING PERIODIC COMMIT 50,000` | tuned so no single transaction or request is unbounded; `INDEX_TIMEOUT` 120s bounds the index barrier |
| env overrides | `HYDRA_DSN`, `HYDRA_QDRANT_URL`, `HYDRA_MEMGRAPH_URI` | take precedence over `config/hydra.yaml` in both the factory and the loader — for port collisions and remote engines. They do **not** change the config fingerprint, so a run against a different host is not self-describing: note it manually |
| rebuild atomicity | none, by design | projections are dropped before being repopulated: a ~40s window where queries hit a missing collection / empty graph. Stop the API first. Revisit with staged Qdrant aliases + a Memgraph label swap if Hydra ever serves during rebuilds |

### Harness settings (fixed across platforms for comparability)

Retrieval depth k=50 per arm; latency workload hybrid `similar` k=10;
open-loop rates at 0.7× measured capacity plus a 1.2× run; concurrency
1/8/32; 5,000 samples, 500 warmup discarded; HdrHistogram µs-resolution.
Single-tenant, same box (28-core / 62GB), versions pinned per-artifact
under `versions`.

## Incidents (teaching value)

Recovery steps in `docs/runbooks/run-hydra.md` failure modes; the two
that became lessons are written up in `09-lessons-learned.md` — not
restated here.

- **Qdrant served brute force with a green light** — L10. The
  benchmark-methodology version of the lesson: an ANN engine that fails
  open is worse than one that fails loudly, because the failure mode is
  *a number in your results table*.
- **Memgraph planner hang, >312s** — L11. Also the reason ADR 0005's
  planned `[*wShortest]` syntax never shipped: the engine's marquee
  feature was its slow path on this graph.
- **`DROP GRAPH` rejected in transactional mode** and **`max_hops=3` at
  ~124s on hub seeds** — both expected-behaviour traps rather than bugs,
  both documented as failure modes so the next person doesn't debug them.
- **The review round, and how the numbers earned trust.** An independent
  adversarial review in fresh context (live-engine probes) found 2 major
  and 8 minor issues *before* the bench was trusted. Both majors were
  about evidence, not code: the Qdrant projection "verification" compared
  Postgres against a total Postgres itself had produced — a tautology
  that could never fail — and there was no index-state barrier or record,
  so a bench could measure a half-built or absent index and no artifact
  would show it. The review also independently confirmed the ranking
  contract sound (68/68 adversarial differential cases vs CteGraph). The
  first bench run was **discarded** and re-run clean after the fixes
  (commit `0b36d7c`) — the second time this project has paid L7's
  "review before the bench" cost, and the second time it was worth it.
  Every number in this document comes from the post-fix run.

## Artifacts

- `bench/results/hydra-0b36d7c-20260804T134236Z.json` — committed
  machine-readable run (quality, significance, fusion tuning, four
  latency runs, `engine_state`, versions)
- `bench/report.md` — generated cross-platform tables + the equivalence
  section (`make report`)
- `tests/conformance/test_graph_parity.py` — the committed CteGraph vs
  MemgraphGraph differential
- Progress log: `docs/plans/2026-08-04-knowledge-plane/phase-06-hydra.md`
- Decision under measurement: `docs/adr/0005-hydra-graph-memgraph.md`
- Operations: `docs/runbooks/run-hydra.md`
