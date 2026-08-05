# Explainer: the embedding ablation, piece by piece

*Written 2026-08-05, mid phase 08, while the six-run matrix was executing.
Audience: someone new to the project — or to embeddings entirely. Companion
to ADR 0006 (the decision) and `05-embeddings-and-benchmarks.md` (the
methodology research); this doc explains, those decide.*

## What an embedding is (the thing being swapped)

Every movie gets turned into a list of numbers (a vector) so that "similar"
movies end up near each other mathematically. When you ask "what's similar
to The Matrix?", the vector plane just finds the nearest points. The whole
question of this phase is: **where do those numbers come from, and does it
matter?**

The project has two ways of making them, called the two "arms":

1. **SVD arm (the classic one).** MovieLens ships a "tag genome":
   human-derived relevance scores linking ~13,800 movies to 1,128 tags
   ("dystopia", "hacking", ...). We compress that big table down to 256
   numbers per movie using TruncatedSVD, a linear-algebra technique from
   long before deep learning. Fast, fully deterministic, zero ML
   dependencies. Its weakness: the other ~48,000 movies have no genome
   data, so they get a crude stand-in (the average of their genres'
   vectors) — deliberately weak, and flagged (`has_genome`) so the effect
   is measurable rather than hidden.

2. **Neural arm (the modern one).** A small language model
   (bge-small-en-v1.5, run locally on CPU via fastembed/ONNX) reads a
   sentence we build for each movie — title, genres, top 15 genome tags —
   and produces 384 numbers capturing its meaning as text. This is what
   production semantic search does in 2026. It covers all 62,423 movies
   equally. Embedding the full catalog took about two minutes on 28 cores.

The personality difference shows up immediately. Seeded with The Matrix,
the neural arm's vector list surfaces Matrix Reloaded and Matrix
Revolutions (things that *sound* similar), while SVD surfaces things
people *rated* similarly. Which instinct wins, and on which kinds of
question, is exactly what the benchmark tells us.

## What the matrix run actually is

Six full benchmark runs: each of the three platforms (Lyra, Orion, Hydra),
once per arm. For each platform the driver:

1. Benchmarks it with SVD vectors (the state it was already in).
2. Flips the config to neural and reloads the engines with the 384-number
   vectors.
3. Benchmarks again, flips back to SVD, and reloads so nothing is left in
   a weird state.

Each individual benchmark run has four sections:

- **Flows.** Six hard sanity checks (can it recommend, explain, search...).
  Fast; catches a broken setup before wasting an hour measuring it.
- **Quality.** For every probe in the probe set (questions where we know
  the right answers, built from graph structure), ask the platform three
  times — vector-only, graph-only, hybrid — and score each against the
  known answers. This is where the SVD-vs-neural verdict comes from.
- **Fusion tuning.** A small grid search over how much weight the graph's
  opinion gets versus the vector's, done on one half of the probes and
  validated on the other half, so we're not grading our own homework.
- **Latency.** The slow part, and slow on purpose — see below.

## Why it takes one to three hours

For each run the harness fires 5,000 timed requests at several concurrency
levels, plus a deliberate overload run past the saturation point — roughly
20,000+ requests per benchmark, six benchmarks. The requests are sent
"open loop": on a fixed schedule, like real users, rather than politely
waiting for each response before sending the next. Open loop matters
because the polite version hides slowness — a stalled server receives
fewer requests, so its bad numbers never get recorded. That trap has a
name, *coordinated omission*, and avoiding it is why honest tail latency
(p99: the experience of the unluckiest 1% of requests) needs thousands of
samples you cannot rush. The requests are the clock.

On top of that, the reloads between arms aren't free. Postgres drops its
vector table and rebuilds an HNSW index (a navigable graph over all
~219,000 vectors) from scratch — minutes of real work per switch, and the
384-dim vectors are 1.5× the data of the 256-dim ones.

## Why it matters

Three reasons, ascending:

1. **It's the honest way to make the claim.** "The neural arm feels
   better" is vibes. Six committed JSON artifacts — same probes, same code
   version, only the embedding swapped — is evidence.
2. **The comparison is the finding.** Per ADR 0006, the payload isn't "we
   used a model"; it's *does a 2026 text embedding beat 2011-style tag
   math for movie retrieval, on which query types, and at what latency
   cost?* Either answer is interesting on stage.
3. **The fairness machinery is teaching material.** SVD only truly covers
   13.8k movies, so the eval carries a "genome subset" slice: probes where
   every movie involved has real genome data. Comparing there is
   apples-to-apples; comparing overall shows what coverage asymmetry does
   to a metric. A benchmark can lie by construction unless you stratify it
   — one of the better lessons this project demonstrates.

## Where the results land

`bench/results/*.json` (committed artifacts, one per run) →
`bench/report.md` (regenerated cross-run report; the svd-vs-neural
ablation section renders once both arms exist) →
`12-phase-08-findings.md`-style findings doc (every claim traceable to an
artifact).
