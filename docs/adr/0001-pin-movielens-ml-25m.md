# 0001 — Pin MovieLens ml-25m as the canonical dataset

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob Scott, Claude

## Context

The benchmark needs one canonical dataset every platform ingests identically. It
must be free, offline after download, large enough to stress the planes
(millions of interactions, millions of graph edges), and must supply a dense
content signal for the classical embedding path. GroupLens now recommends
ml-32m (May 2024) for new research, which makes it the obvious default.

## Options considered

### Option A — ml-32m (newest, GroupLens-recommended)
32M ratings, 87,585 movies.
- Pros: newest, officially recommended, +7M ratings.
- Cons: **ships no tag genome** (verified against its README) — kills the
  SVD embedding path and the content-signal narrative; extra movies are
  long-tail obscura.

### Option B — ml-25m
25M ratings, ~62k movies, **tag genome: 15M relevance scores over 1,129 tags**.
- Pros: genome is load-bearing for the deterministic embedding arm; stable,
  heavily cited benchmark.
- Cons: 2019 vintage; fewer ratings.

### Option C — Frankenstein (ml-32m ratings + ml-25m genome on movieId)
- Pros: most data.
- Cons: data-provenance asterisk on every published result; not worth it.

## Decision

**We will pin ml-25m, because ml-32m dropped the tag genome and the genome is
load-bearing for the SVD embedding path and the ablation story.** Scope: all
platforms, all benchmarks.

## Consequences

- Easier: deterministic zero-ML embeddings; classic citable benchmark.
- Harder: must state on stage why not the newest dataset (one sentence, and
  it's a good sentence).
- Committed: checksum-pinned download, no redistribution (GroupLens terms).
- **Revisit trigger:** GroupLens ships a genome-bearing successor dataset.

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/05-embeddings-and-benchmarks.md`
