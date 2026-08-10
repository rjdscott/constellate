# 08: Orion benchmark findings (phase 05)

- **Date:** 2026-08-04
- **Platform:** Orion, the unified knowledge plane: one Postgres 18.1
  container (AGE 1.7.0 base image + PGDG pgvector 0.8.6, ADR 0004)
- **Method:** identical harness and probe set as Lyra
  (`07-lyra-benchmark-findings.md`); two committed runs, one per graph
  adapter: CTE (`orion-8187751-20260804T101625Z`, full 5,000-sample
  latency) and AGE (reduced 2,000-sample latency, disclosed below)
- **Reproduce:** `make up load bench PLATFORM=orion && make report`
  (`docs/runbooks/run-orion.md`)
- **Verdict: the abstraction holds.** Hybrid-arm quality within tolerance
  of Lyra (R@10 +0.0021, nDCG@10 +0.0002, tolerance ±0.02), and the
  graph plane reproduces Lyra's numbers *exactly*.

## Headline numbers (CTE arm, 200 probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0108 | 0.0231 | 0.0128 | 0.0264 | 0.0192 | 19.49 |
| graph_only | **0.0965** | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0376 | 0.2462 | 0.0364 | 0.0746 | 0.0202 | 16.44 |

Ablation gate re-confirmed on a second platform: hybrid beats vector-only
R@10 +0.0267 (p=4.1e-06). Fusion fidelity check exact again (0.0364 =
0.0364).

## The two findings that matter

### 1. Graph equivalence is exact; vector recall is the platform delta

- **graph_only matches Lyra to four decimals on every metric and every
  probe kind** (R@10 0.0965, cross_genre 0.3520, …). The CTE adapter's
  two-stage expansion, full per-hop aggregation ranked `(min hops,
  support)`, best-path per winner, reproduces the Kuzu adapter's
  semantics down to the candidate ordering. This is the strongest possible
  evidence for the plane-contract thesis: same data, same contract, two
  wildly different engines, identical retrieval.
- **vector_only halves vs Lyra** (R@10 0.0108 vs 0.0213): pgvector HNSW
  on halfvec at ef_search=200 vs faiss exact flat. The loss concentrates
  on `cold_start` probes (0.0300 vs Lyra's 0.0680): cold items sit in
  the genre-mean fallback region of vector space where neighbours are
  tightly bunched and ANN recall suffers most. Lyra's exact-search
  "recall referee" role (ADR 0002) is doing its job: without it this
  would look like a probe-set quirk, not an index property.
- Hybrid absorbs the vector loss (graph dominates these probes) and lands
  within tolerance of Lyra, slightly *above* it (+0.0021), because the
  weaker vector arm dilutes the graph less.

### 2. The embedded ceiling was the bottleneck, not the network

CTE arm, open-loop, 5,000 samples/run:

| rate/s | conc | p50ms | p95ms | p99ms | max ms |
|---|---|---|---|---|---|
| 18.4 | 1 | 46.7 | 81.7 | 100.3 | 117.3 |
| 18.4 | 8 | 43.4 | 78.3 | 109.2 | 212.2 |
| 18.4 | 32 | 43.6 | 75.4 | 90.2 | 160.8 |
| 31.5 | 32 | 40.8 | 73.8 | 104.5 | 234.1 |

Orion is ~3× *faster* than Lyra (warm mean 38 ms vs 115 ms; p50 43 ms vs
127 ms): the daemon, the network hop, and SQL parsing cost less than
Lyra's in-process kuzu expansion. And the intended saturation run (1.2×
the sequentially-estimated 26.2/s capacity) **failed to saturate**: p50
*dropped* to 40.8 ms: Postgres serves requests concurrently, so
single-stream calibration underestimates a multi-process backend. Lyra
physically cannot do this (blocking engine calls in one process: its
p50/p99 were flat across concurrency because concurrency bought only
queueing). Talk framing: *"the embedded platform's ceiling was never the
missing network hop, it was the single process."* Caveat recorded: the
harness's capacity estimator is sequential; for concurrent backends the
knee lies above 1.2×: a rate sweep is future work.

## Fusion tuning (CTE arm)

Validation half: weights 0.25–0.75 score ~0.009, 1.0 → 0.0305, 1.5 →
0.0564, **2.0 → 0.0585 (best, grid edge again)**. Held-out test: baseline
0.0423 → tuned **0.0671** (+59% relative: larger lever than Lyra's +24%
because the weaker vector arm hurts equal-weight fusion more). Same
caveats as Lyra: grid-edge, probe-set-specific; config keeps 1.0.

## CTE vs AGE (the ADR 0004 published delta)

Smoke timings (same box, same data): CTE F1 141 ms / F2 633 ms / F3
64 ms; AGE F1 404 ms / F2 1,484 ms / F3 238 ms: AGE ~3× slower at every
flow, consistent with research 03's "AGE buys syntax, not speed" at 2–3
hops. AGE-arm bench numbers land below; its latency run used 2,000
samples (AGE's ~2.5/s single-stream capacity makes 5,000-sample sweeps a
multi-hour affair; p50/p95 are trustworthy at 2,000, read p99 with care).

AGE-arm run `orion-e3526c7-20260804T110915Z` (2,000 latency samples):

- **Quality: identical to the CTE arm on every metric** (graph_only R@10
  0.0965, hybrid nDCG@10 0.0364, fidelity exact). Four graph adapters
  across two platforms now produce the same retrieval to 4 decimals:
  ranking-contract equivalence (L2) holds for AGE too. R@50 differs in
  the 3rd decimal (0.2473 vs 0.2462): deep-tail tie-ordering, the only
  daylight between the arms.
- **Latency: CTE ~6× faster than AGE**: the ADR 0004 delta, measured:

| arm | warm mean | p50 | p95 | p99 (read with care at n=2000) |
|---|---|---|---|---|
| CTE @18.4/s c32 | 38 ms | 43.6 | 75.4 | 90.2 |
| AGE @3.2/s c32 | 221 ms | 243.8 | 356.6 | 426.5 |

  AGE at 1.2× estimated capacity (5.4/s) degrades mildly (p50 259 ms):
  the Postgres server still absorbs concurrency; the cost is per-query
  Cypher→plan compilation and the unindexed property-anchored MATCHes,
  exactly research 03's "AGE buys syntax, not speed" at 2–3 hops.
  Conclusion the ADR predicted: the thesis rests correctly on the CTE
  adapter; AGE remains the ergonomics arm, revisit at 1.8.0
  (`shortest_path`, predicate functions).

## Platform configuration & tuning record

Orion-specific setup; shared knobs (fusion, retrieval, data) identical to
Lyra's record in doc 07, single source: `config/orion.yaml`, fingerprint
`21fa5e19b24643dc` (CTE arm).

| setting | value | why / when to revisit |
|---|---|---|
| image | `apache/age:release_PG18_1.7.0` + PGDG `postgresql-18-pgvector` | AGE is the hard-to-build one, never compile it (ADR 0004); revisit at AGE 1.8.0 final |
| host port | 15432 (`ORION_DSN` overrides) | convention: engine default + 10000, all platforms simultaneously |
| `shared_buffers` | 2GB | 25M-row interactions + 1.7M-edge table stay hot |
| `maintenance_work_mem` | 2GB | HNSW build in one pass; **needs `shm_size` ≥ this (4g set)**: 1g died with "could not resize shared memory segment" |
| `engines.graph.adapter` | `cte` (default) / `age` | the thesis vs the syntax; flip = new fingerprint = different measured system |
| pgvector index | HNSW `halfvec_ip_ops`, m=16, ef_construction=200, ef_search=200 | parity with Lyra's hnsw arm; halfvec = 50% storage; **known cost: cold-start recall** (finding 1) |
| `hnsw.iterative_scan` | `relaxed_order` (per session) | filtered queries keep yielding until k survive the exclusion anti-join |
| CTE edge table | doubled directions, PK (src,dst,edge_type), covering index `(src, edge_type) INCLUDE (dst, weight)` | each hop index-only; full per-hop aggregation (no LATERAL top-k) to mirror kuzu support counts exactly |
| AGE graph | bulk-loaded via `load_labels_from_file` (jailed under `/tmp/age/`, bind mount), node property `key` (loader reserves `id`), weights `toFloat()`-cast (CSV loader lands them as strings) | every quirk documented in run-orion runbook failure modes |
| pool | one asyncpg pool (2–8 conns) shared by all three planes; relational adapter owns teardown | one database is the whole point |
| loader | COPY-based, idempotent via `load_manifest` table | 25M interactions in 43 s; fresh volume ~90 s total |

## Incidents (teaching value)

Full list with recovery steps in `docs/runbooks/run-orion.md` failure
modes: shm vs parallel HNSW build; AGE 1.7 path jail; agtype string
weights breaking multi-hop products; pandas `count` column shadowing the
`itertuples` namedtuple method (mypy caught it pre-commit); compose
project-name collision (directory-name default) fixed with per-platform
`name:`.

## Artifacts

- `bench/results/orion-<sha>-<utc>.json` × 2 (CTE + AGE arms, committed)
- `bench/report.md`: cross-run tables + equivalence section
- Progress log: `docs/plans/2026-08-04-knowledge-plane/phase-05-orion.md`
