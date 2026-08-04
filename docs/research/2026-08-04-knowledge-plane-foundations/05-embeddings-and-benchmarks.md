# 05 — Embedding strategy, dataset, benchmark methodology (researched 2026-08-04)

Verified via live web 2026-08-04 unless marked estimate.

## A) Dataset — decisive fact first

### ml-32m does NOT ship the tag genome

Verified against the [ml-32m README](https://files.grouplens.org/datasets/movielens/ml-32m-README.html):
only `links.csv`, `movies.csv`, `ratings.csv`, `tags.csv`. No
`genome-scores.csv` / `genome-tags.csv`.

| | ml-25m (Dec 2019) | ml-32m (May 2024) |
|---|---|---|
| Ratings | 25M | 32M |
| Movies | ~62,000 | 87,585 |
| Tag genome | **Yes** — 15M relevance scores, 1,129 tags | **No** |
| Status | Stable benchmark | "Recommended for new research" per [grouplens.org](https://grouplens.org/datasets/movielens/) |

**Recommendation: ml-25m.** The genome is load-bearing for the SVD embedding
path and the content-signal narrative; ml-32m buys 7M more ratings and 25k
long-tail movies at the cost of the genome. Frankenstein (ml-32m ratings +
ml-25m genome joined on movieId) works technically but adds a data-provenance
asterisk to every result — not worth it.

## A) Embedding strategy

### Recommendation: both paths, as an ablation axis — "SVD first, neural second"

Two paths measure genuinely different things, which makes the ablation
meaningful rather than decorative:

- **Genome-SVD (256d)**: collaborative/content hybrid signal distilled from
  human tagging. Deterministic, zero ML deps (`TruncatedSVD`), bit-for-bit
  reproducible with fixed seed, runs in seconds. "Understand the
  linear-algebra floor before reaching for a model" — reads as expertise.
- **Neural text embeddings** over title+genres+top-tags: semantic signal,
  covers *all* movies including sparse-genome ones, what production semantic
  search actually uses.
- Talk question the ablation answers: *does a 2026 text embedding beat a
  2011-style tag-genome SVD for movie retrieval, and on which query types?*
  Real finding either way. Matches 2025–2026 consensus: behavioral signal for
  recommendation, semantic text embeddings for search, hybrids fuse both
  ([BentoML 2026 guide](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models),
  [Milvus 2026](https://milvus.io/blog/choose-embedding-model-rag-2026.md)).

### Which neural model (mid-2026)

- **bge-small-en-v1.5 (384d, 33M params)** — pragmatic small-English default,
  fastembed flagship, mature ONNX path. Not leaderboard-topping; nobody calls
  it wrong.
- **Qwen3-Embedding-0.6B** — current SOTA sub-1B: ~71.7 MTEB English v2
  ([BentoML](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models),
  [HF card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)). Matryoshka
  flexible dims — truncate to 256d to match the SVD axis.
- **all-MiniLM-L6-v2** — only "ultra-light edge" option in 2026 roundups;
  choosing it reads dated.
- **snowflake-arctic-embed** — faded from 2026 roundups; skip.

**Pick: bge-small-en-v1.5 primary neural path (fastembed, CPU-fast);
Qwen3-Embedding-0.6B @256d optional third arm** ("current SOTA small model"
checkbox — identical pipeline, cheap to add later).

### fastembed maintenance

Maintained by Qdrant; latest **v0.8.0** (cadence slowed to ~1 minor/quarter-year).
Python 3.10–3.14, ONNX Runtime only, no torch
([PyPI](https://pypi.org/project/fastembed/), [releases](https://github.com/qdrant/fastembed/releases)).
Safe to depend on; `sentence-transformers` is the drop-in fallback.

### Embed-time estimates, 62k items, 28-core CPU *(estimate)*

Inputs short (title + genres + ~10 tags ≈ 30–60 tokens):

- bge-small ONNX batched: ~300–800 docs/s → **~2–5 min** for 62k.
- Qwen3-0.6B ONNX CPU: ~20–60 docs/s → **~20–50 min**.
- Genome SVD: **seconds** (~13.8k genome movies × 1,129 tags).

SVD covers only ~13.8k genome movies; neural covers all 62k. Coverage
asymmetry must be handled explicitly in eval (restrict comparison to genome
subset, or report coverage first-class).

## B) Benchmark methodology

### Splits: global temporal split is 2025–2026 consensus

- ["Time to Split" (RecSys 2025)](https://arxiv.org/abs/2507.16289): global
  temporal splitting recommended; split choice reorders model rankings;
  leave-one-out correlates poorly with deployment.
  [Code](https://github.com/monkey0head/time-to-split).
- ["Don't Get Ahead of Yourself" (RecSys 2025)](https://dl.acm.org/doi/10.1145/3705328.3759329)
  + [TOIS leakage study](https://dl.acm.org/doi/full/10.1145/3569930): splits
  ignoring the global timeline leak future data; sampled nDCG@10 drops
  21.7–73.4% when leakage removed.

**Recommendation:** single global timestamp cutoff, train before, test users
filtered to ≥1 train interaction. Deterministic, one line, two RecSys'25
citations from the stage.

### Metrics library: ir_measures for ranking, ranx for fusion

- **[ir_measures](https://pypi.org/project/ir-measures/)** v0.4.3 (Nov 2025,
  Terrier/Glasgow, wraps pytrec_eval) — primary for nDCG@10, RR@10, Recall@k.
- **[ranx](https://github.com/AmenRa/ranx)** v0.3.21 (Aug 2025) — numba-fast,
  **25 fusion algorithms incl. RRF**, significance testing, LaTeX export.
  Pick for fusion layer + run comparison.
- **recpack** — dormant; skip.
- Coverage/diversity/novelty: hand-roll (~20 lines: catalog coverage,
  novelty = mean −log2 popularity, ILD). No maintained lib; a dep = bloat.

### Fusion: RRF k=60 still the 2026 standard baseline

- RRF k=60 near-universal (Cormack et al.; shipped by
  [OpenSearch](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/),
  [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking),
  Qdrant). Rank-based → no score normalization across heterogeneous planes —
  exactly this situation.
- **DBSF** (z-score normalize + sum; native in Qdrant) main challenger; better
  with calibrated scores, worse with incomparable ones
  ([RRF vs DBSF](https://haikel-fazzani.deno.dev/blog/rrf-vs-dbsf-qdrant)).
- **Weighted RRF** standard cheap upgrade; ranx can tune weights on a
  validation split.

**Recommendation:** RRF k=60 baseline → weighted RRF (ranx-tuned) as the "one
step better" result; DBSF as the score-aware footnote.

### Latency methodology checklist

1. **Open-loop, constant arrival rate** — closed-loop hides tail latency via
   coordinated omission ([Gil Tene](https://groups.google.com/g/mechanical-sympathy/c/icNZJejUHfE/m/BfDekfBEs_sJ),
   [ScyllaDB on CO](https://www.scylladb.com/2021/04/22/on-coordinated-omission/)).
2. **Measure `done − scheduled_send`**, not `done − actual_send` (wrk2/vegeta
   semantics — a backed-up server gets charged its queueing delay).
3. **HdrHistogram** recording (`hdrhistogram` on PyPI).
4. **Warmup excluded** — 30–60s discard (JIT, caches, pools, page cache).
5. **Fixed concurrency + fixed rate per run**; sweep rate to find the knee.
   Report p50/p95/p99/p99.9, never mean-only.
6. **≥5,000 samples for a p99** ([ref](https://idle-ti.me/blog/coordinated-omission/)).
7. Same box, pinned versions, single-tenant runs; hardware reported.

Don't build a load generator: `vegeta` (Go binary, open-loop, HDR output) or
asyncio fixed-rate scheduler + hdrhistogram ≈ 40 lines.

### Hybrid vector+graph evaluation — 2025–2026 anchors

- **[GraphRAG-Bench](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark)**
  (ICLR'26, "When to use Graphs in RAG") — reference for *when* graph
  retrieval helps; methodological import: **report graph-plane costs
  (indexing time, latency, storage) alongside quality**.
- **[ORAN vector/graph/hybrid benchmark (arXiv 2507.03608)](https://arxiv.org/abs/2507.03608)**
  — clean three-way template stratified by question complexity; hybrid +8%
  factual correctness, graph +11% context relevance.
- **[RAG vs GraphRAG systematic evaluation (arXiv 2502.11371)](https://arxiv.org/html/2502.11371v3)**
  — documents protocol heterogeneity; fixed-protocol same-dataset same-metric
  design is directly responsive (good talk framing).

Transferable methodology: stratify queries by type (known-item / semantic /
relational-multi-hop), report quality per stratum per plane, always pair
quality deltas with latency+storage deltas.

## Bottom line

| Decision | Pick | Why |
|---|---|---|
| Dataset | **ml-25m** | ml-32m dropped the genome; genome is load-bearing |
| Embedding | **Genome-SVD 256d + bge-small-en-v1.5** (optional Qwen3-0.6B @256d) | Classical baseline vs current practice — the ablation *is* the story |
| Split | **Global temporal cutoff** | RecSys'25 consensus; random/LOO = leakage |
| Metrics lib | **ir_measures + ranx** | Both 2025-released, complementary, no hand-rolled NDCG |
| Extra metrics | Hand-roll coverage + novelty | No maintained lib; dep = bloat |
| Fusion | **RRF k=60 → weighted RRF via ranx** | 2026 standard; DBSF footnote |
| Latency | Open-loop fixed-rate, HdrHistogram, warmup discard, ≥5k samples | Coordinated-omission-proof |
