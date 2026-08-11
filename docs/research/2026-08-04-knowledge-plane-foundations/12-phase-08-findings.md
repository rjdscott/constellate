# Phase 08 findings: the embedding-arm ablation

- **Date:** 2026-08-05
- **Question (ADR 0006):** does a 2026 neural text embedding (bge-small-en-v1.5,
  384d) beat 2011-style tag-genome SVD (256d) for movie retrieval on a
  graph-necessary probe set: on which query types, and at what cost?
- **Evidence:** six committed artifacts, one per {platform} × {arm}, all at
  sha `fa9623e`: `bench/results/{lyra,orion,hydra}-fa9623e-20260805T*.json`
  (svd: T012152Z / T023925Z / T035422Z; neural: T022106Z / T030508Z /
  T044906Z). Cross-run tables in `bench/report.md`. The plan task named this
  doc `07-findings.md`; the workspace had grown per-platform findings docs
  (07/08/10) by then, so it lands here as `12-`.

## Headline results

1. **SVD wins on this probe set.** Vector-only R@10: svd 0.0213 (lyra,
   exact search) vs neural 0.0145: a ~32% relative drop. Hybrid: 0.0355
   vs 0.0321. The 2011-style behavioral/curated signal beats the 2026
   text embedding for recommendation-shaped, graph-flavored questions.
   This matches the literature consensus (behavioral signal for
   recommendation; text embeddings for search-shaped queries, which this
   probe set deliberately contains none of), but now it's measured, not
   cited.
2. **The knowledge-plane thesis survives the arm swap.** Hybrid beats
   vector-only on *both* arms, every platform: svd p = 4.1e-6 (orion),
   3.8e-3 (hydra), 5.4e-3 (lyra); neural p = 3.8e-4 everywhere. (Orion's
   svd p is *smaller* because its halfvec-weakened vector arm makes the
   hybrid's win larger and more consistent per probe.) The graph plane's
   relative contribution is *larger* on the weaker neural arm (+0.0176 vs
   +0.0141 R@10 on lyra). A worse vector arm makes the graph matter more.
3. **The neural arm is rank-stable at the reported depth across every
   engine stack.** All three platforms return *identical* neural-arm
   R@10 and nDCG@10, overall and by kind, plus the same p-value:
   vector-only 0.0145, hybrid 0.0321, across faiss exact (lyra),
   pgvector halfvec HNSW (orion), and qdrant HNSW (hydra). Scope stated
   precisely: deeper metrics do differ by engine in the third decimal
   (e.g. hybrid cross_genre R@50 0.6729 lyra vs 0.6754 orion; novelty
   16.32–16.34): top-10 rankings agree, the depth-50 tail does not,
   which is exactly where ANN and fp16 effects should live. The graph
   arm stays 0.0965 on all engines and both arms, as it must
   (embeddings never touch it): a built-in no-contamination check the
   arm switch passed.

## The sleeper finding: 384d bge is quantization- and ANN-robust; 256d SVD is not

The svd arm's vector-only R@10 *varies by engine*: 0.0213 exact (lyra),
0.0200 qdrant HNSW (hydra), 0.0108 pgvector halfvec (orion, the fp16
recall gap recorded in `08-orion-benchmark-findings.md`). The neural
arm's does not vary at all: 0.0145 on all three, including the same
halfvec fp16 storage and the same HNSW parameters that dent SVD.

Working explanation: TruncatedSVD concentrates variance in its leading
components by construction, so fp16 rounding and approximate neighbor
search both bite where the signal lives; bge embeddings spread signal
far more isotropically across dimensions, so per-dimension noise washes
out. Practical consequence, worth stating on stage: **the more "modern"
embedding is also the more portable one**: it made three different
vector engines interchangeable to four decimals, while the classical
embedding leaked engine-specific artifacts into quality numbers.

## By probe kind (hybrid R@10, lyra syntax; all platforms in artifacts)

| kind | svd | neural | read |
|---|---|---|---|
| cold_start | 0.066 | 0.064 | wash |
| cross_genre | 0.067 | 0.047 | **svd's whole margin lives here** |
| path_required | 0.002 | 0.008 | neural slightly better; both near floor |
| tag_bridge | 0.007 | 0.009 | wash, both near floor |

SVD's overall win is almost entirely cross-genre: genome tags encode
"this drama and that thriller share dystopia/heist/noir DNA" precisely
the way a title+genres+tags sentence does not. path_required and
tag_bridge stay near-floor for every vector arm: they're the probes
built to *need* the graph, and the graph duly dominates them
(graph-only 0.0965 overall).

## Latency and footprint

384d costs roughly nothing at this scale. Warm-mean hybrid recommend:
lyra 116.9 → 117.0 ms, orion 37.5 → 36.7 ms, hydra 100.8 → 111.6 ms
(the only visible dent, ~+10% on the composed platform's extra hop);
c=8 p50/p99 unchanged within noise on all three (e.g. orion 43.1/87.9
→ 42.9/88.8 ms). Neural ingest: roughly two minutes wall-clock for
62,423 items on 28 CPU cores, operator-observed; the seed step isn't
instrumented, so unlike every other number here this one has no
artifact behind it. Inside ADR 0006's estimate. Storage: 1.5× vector bytes
(384/256), invisible next to the 25M-row interactions table.

## Coverage stratification: the machinery worked, the asymmetry didn't bite

ADR 0006 required handling the genome-coverage asymmetry (SVD native on
13,816 items = 22.1%; neural on 100%). The genome-subset slice came back
**200 of 200 probes** on every run: the probe set is *fully*
genome-covered by construction: probes were generated from graph
structure (tag bridges need genome tags), so they never touch the 48k
uncovered movies. Consequences stated honestly: (a) the svd-vs-neural
comparison above is already apples-to-apples, no fallback vectors
involved; (b) SVD's real-world weakness, 78% of the catalog riding on
genre-mean fallback vectors, is *invisible to this probe set* and shows
up only in the catalog-coverage metric (both arms ~2.5–2.7% of catalog
in top-10s; the neural arm's advantage there is small because retrieval
is popularity-anchored either way). A probe set that exercised the long
tail would likely flip the verdict toward neural; building one is future
work, noted in the plan's parked list.

## Verdict against ADR 0006's question

On graph-flavored, genome-covered probes: **SVD beats neural, the graph
plane beats both, and hybrid fusion beats everything**: on every
platform, both arms, p < 0.004 throughout. The neural arm earns its
place not by winning quality but by (a) covering the full catalog, (b)
proving the contract is embedding-agnostic end to end (config flip +
reload, zero code), and (c) being the arm that made three vector engines
statistically indistinguishable.

## Threats to validity

- One dataset (ml-25m), one probe generator, 200 probes; absolute R@10
  values are small and probe-set-specific: only deltas and orderings
  travel.
- The probe set cannot see SVD's fallback-vector weakness (above).
- bge-small embeds a *constructed sentence* (title + genres + top-15
  genome tags); a different corpus template is a different neural arm.
- Latency remains `latency_indicative: true` per ADR 0011: in-process,
  single-tenant, one box; the harness is the only citable source, and
  cross-platform latency comparisons still favor whoever's engine fits
  this box best (orion's single-process advantage: research doc 08).
- AGE re-ran only implicitly (orion runs use the CTE adapter, its
  default); the four-graph-engine equivalence claim for the *neural* arm
  covers kuzu/cte/memgraph directly, age by architecture (graph inputs
  unchanged: same edges, same queries, and graph-arm numbers are
  arm-invariant on every measured engine).

## Config record

`data.embedding_arm: neural` (yaml, per platform, reverted to svd
default after each run); model BAAI/bge-small-en-v1.5 via fastembed
0.7.4 ONNX, batch 256, item_id-ordered; vectors L2-normalized float32,
native 384d (no truncation, ADR 0006); corpus = "{title}. Genres: {…}.
Tags: {top-15 genome tags by relevance, tagId tie-break}". Engines and
fingerprints inside each artifact; `embedding_arm` recorded top-level.
