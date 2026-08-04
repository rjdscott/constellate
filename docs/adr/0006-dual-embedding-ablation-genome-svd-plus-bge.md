# 0006 — Embeddings: genome-SVD and bge-small as a dual-arm ablation axis

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob Scott, Claude

## Context

The project is explicitly educational: the author wants to walk every step,
feel the tradeoffs, and present as an industry expert. Embeddings are the
vector plane's input; the choice is between a deterministic classical signal
(tag-genome SVD — zero ML deps, seconds to compute, bit-reproducible) and a
neural text embedding (what production semantic search uses, covers all 62k
movies where the genome covers only ~13.8k). 2025–2026 consensus: behavioral
signal for recommendation, semantic text embeddings for search — hybrids
fuse both.

## Options considered

### Option A — genome-SVD only
- Pros: deterministic, zero ML deps, fastest.
- Cons: 2011-style signal only; no claim about modern practice; ~13.8k-movie
  coverage.

### Option B — neural embeddings only (fastembed / bge-small-en-v1.5)
- Pros: current practice; full coverage.
- Cons: loses the reproducible classical baseline; slower ingest; "we used a
  model" is not a finding.

### Option C — both, as a first-class ablation axis
- Pros: the ablation *is* the story — "does a 2026 text embedding beat a
  tag-genome SVD for movie retrieval, and on which query types?" is a real
  finding either way; SVD stays the deterministic default for CI.
- Cons: two embedding pipelines; coverage asymmetry must be handled
  explicitly in eval.

## Decision

**We will ship both arms: tag-genome TruncatedSVD (256d) as the
deterministic default, and bge-small-en-v1.5 via fastembed (ONNX, CPU) as
the neural arm, compared as a first-class ablation — because the SVD-vs-
neural delta per query stratum is the educational payload, not a side
effect.** Optional third arm later: Qwen3-Embedding-0.6B truncated to 256d
(current sub-1B SOTA, Matryoshka dims). Coverage asymmetry (13.8k genome vs
62k total) is reported explicitly; comparisons restricted to the genome
subset where required. Scope: all platforms (embeddings are computed once in
ingest, platforms consume identical parquet).

## Consequences

- Easier: CI stays ML-free (SVD default); talk gets a real experiment.
- Harder: eval must stratify by genome coverage; fastembed's slowed cadence
  accepted (sentence-transformers is the drop-in fallback).
- **Revisit trigger:** fastembed stops supporting a needed model, or the
  neural arm's ingest cost (est. 2–5 min at 62k) proves wrong by >10×.

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/05-embeddings-and-benchmarks.md`
- ADRs: [0001](0001-pin-movielens-ml-25m.md), [0002](0002-lyra-vector-exact-first-hnswlib-teaching.md)
