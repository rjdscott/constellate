# 0002 — Lyra (embedded) vector plane: exact flat search first, hnswlib as the ANN teaching layer

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob Scott, Claude

## Context

Lyra, the embedded knowledge plane, must run with no daemon and no docker: pip-installable, persisted to
disk, CI-safe, deterministic. Workload: ~62k item vectors (256–384d f32),
top-k with per-user exclusion sets. The user asked specifically to weigh
hnswlib vs LanceDB. The corpus is small: the full item matrix is 63.5 MB and
one exact cosine query is ~1–3 ms in numpy, sub-ms in faiss-flat — ANN is a
choice here, not a necessity.

## Options considered

### Option A — hnswlib as the primary index
- Pros: ~1 MB dep, the HNSW algorithm naked (pedagogy), fast.
- Cons: PyPI stuck at 0.8.0 sdist-only (2026 fixes need git install);
  exclusion filter = per-candidate Python callback, single-threaded;
  deterministic builds only single-threaded+seeded; recall < 1.0.

### Option B — LanceDB as the primary store+index
- Pros: very active (v0.36.0 Jul 2026), best persistence (versioned tables,
  merge_insert), SQL pre-filtering with correct exclusion semantics, could
  double as Lyra's whole storage layer.
- Cons: ~100+ MB deps (pyarrow mandatory), API classified Alpha and churning,
  no pedagogical visibility into ANN (HNSW only as IVF sub-index), and at 62k
  rows you'd never build its index anyway.

### Option C — exact flat search primary (numpy / faiss.IndexFlatIP), hnswlib alongside as ablation
- Pros: recall = 1.0, deterministic, trivial exact exclusion
  (`scores[seen] = -inf` or C-speed `IDSelectorNotMember`), mmap `.npy`
  persistence, is *required anyway* as recall ground truth for every ANN
  platform; hnswlib then demonstrates the recall/latency/filter tradeoff
  explicitly.
- Cons: two vector adapters in Lyra instead of one; flat search won't scale
  past ~1M vectors (out of scope here).

## Decision

**We will make exact flat search (faiss.IndexFlatIP over mmap-persisted
arrays) Lyra's vector plane, with hnswlib as a second, deliberately
contrasted ANN adapter — because at 62k vectors exact search is ~ms, is the
recall referee for every other platform, and the exact-vs-ANN delta is itself the
teaching artifact.** LanceDB is rejected as primary. Scope: Lyra only.

## Consequences

- Easier: reproducibility, exclusion semantics, recall computation, CI.
- Harder: hnswlib installed from the v0.9.0 git tag (PyPI stale); its builds
  pinned single-thread+seed.
- Committed: "below ~1M vectors, flat is the right index" becomes a stated
  claim in the talk — with the arithmetic to back it.
- **Revisit trigger:** corpus grows past ~1M vectors, or Lyra gains
  relational-store needs that make LanceDB's double-duty attractive.

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/02-embedded-vector.md`
