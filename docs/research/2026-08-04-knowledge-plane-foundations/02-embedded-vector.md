# 02 — Embedded vector index for tier0 (researched 2026-08-04)

Scope: pip-installable, no daemon, Python 3.12, CI-friendly; ~62k item +
~162k user vectors, 256–384d f32; persistence + exclusion-set top-k.

## The honest arithmetic: ANN is optional at this scale

- Item matrix 62k × 256 × 4B = **63.5 MB**; user matrix ~238 MB. Both RAM-
  trivial; "load" = one memory-mappable `np.load`.
- One cosine query = 62k×256 ≈ 32 MFLOPs, memory-bandwidth-bound: 63.5 MB at
  20–50 GB/s ⇒ **~1.3–3 ms** (numpy `items @ q`); `argpartition` adds ~0.5ms.
  Batched GEMM: tens of µs/query. `faiss.IndexFlatIP`: sub-ms, exact.
- HNSW answers in ~0.05–0.2 ms — buys **~1–3 ms** in exchange for recall<1.0,
  build time, two knobs, nondeterministic parallel build, degraded behavior
  under filters. Pays at ~10⁶+ vectors or ~10³+ QPS. Slide-worthy rule:
  **below ~1M vectors, flat search is usually the right index.**
- **Exclusion sets seal it.** Filtering seen ids is where ANN gets awkward
  (traversal must tunnel through excluded nodes; recall degrades with
  excluded fraction). Brute force: `scores[seen] = -inf; argpartition` —
  exact, deterministic, zero tuning.
- Recall@k of every ANN tier needs ground truth = the flat index. The exact
  tier is the referee, not a strawman.

## hnswlib vs LanceDB (mid-2026 state)

### hnswlib

- **Maintenance:** dormant with a pulse — v0.8.0 Dec 2023, then **v0.9.0
  2026-03-28** (first release in 2.3 yrs; filter/BF fixes). Volunteer-run,
  233 open issues. Stable finished artifact, not active project.
- **⚠️ Packaging:** **PyPI still 0.8.0, sdist-only — no wheels.** Compiles
  C++ at install; 2026 fixes require install-from-git tag.
- **Persistence:** single binary file, sub-second load; `add_items` after
  load; `mark_deleted` soft deletes.
- **Filtering:** `knn_query(filter=callable)` — per-candidate **Python
  callback in the C++ hot loop**, forces single-thread for filtered queries.
  Fine at 62k; the asymmetry vs brute force *is* the teaching point.
- **Determinism:** only with `num_threads=1` + fixed `random_seed`.
- **Footprint:** ~1 MB, numpy in/out, zero runtime deps. The minimal ANN
  teaching object.

### LanceDB

- **Maintenance:** very active — Python v0.36.0 2026-07-29, releases every
  1–2 weeks, LanceDB Inc. backed. Lance format 2.2 (2026); DuckDB queries
  Lance natively; Apache Polaris catalogs Lance (Jan 2026). PyPI still
  classifies "Alpha"; API churns.
- **Embedded still first-class:** `lancedb.connect("./path")` in-process
  remains the OSS core; marketing pivoted to "multimodal lakehouse" but
  local embedded is the foundation, not deprecated.
- **Persistence:** best of any candidate — versioned tables (time-travel),
  native `merge_insert` upserts, persisted incremental indexes.
- **Filtering:** standout — SQL predicates via DataFusion, **pre-filtering by
  default**: `.where("id NOT IN (…)")`, correct exclusion semantics; does
  exact flat search with filters **without any ANN index** (ANN only after
  `create_index()`; HNSW exists only as sub-index inside IVF). At 62k you'd
  never create the index. Caveat: 10k-element `NOT IN` SQL string is clunkier
  and slower than a numpy mask.
- **Footprint:** Rust wheel + mandatory pyarrow etc. — ~100+ MB installed vs
  hnswlib's ~1 MB. Heavy for "tier0 index", reasonable for "tier0 store".
- **Double-duty:** Lance tables hold arbitrary Arrow schemas + scalar indexes
  + FTS + versioning — could replace "parquet + index files" as the entire
  tier0 storage layer; DuckDB can SQL the same files. An architecture
  argument, not a latency one.

**Verdict: different tools.** hnswlib is *an index* (the algorithm, naked —
teaches HNSW itself). LanceDB is *a storage engine that happens to search*.
Neither is needed for raw speed at 62k.

## Context candidates

| | Latest | Health | Persistence | Exclusion | Notes |
|---|---|---|---|---|---|
| faiss-cpu | **1.15.0, 2026-08-03**, wheels now Meta-co-maintained | strong | index file, instant load | `IDSelectorNotMember` — C-speed, exact | `IndexFlatIP` = exact baseline with a real API; ~15MB wheel |
| usearch | 2.26.0, 2026-07-10 | active (Unum) | save/load/mmap `view` | needs Numba `cfunc` — awkward | adds nothing over faiss+hnswlib here |
| sqlite-vec | 0.1.9, Mar 2026 | solo, slow-burn | SQLite | SQL WHERE | **no ANN at all** — brute force in SQL, slower than numpy |
| DuckDB VSS | current | maintained | **still `hnsw_enable_experimental_persistence`, no WAL recovery, full re-serialization per checkpoint — unchanged in 2026** | SQL, limited | disqualified for persistence-first tier0 |
| chroma | 1.5.9, May 2026 | strong | local dir | metadata only | app-framework, wrong altitude for a benchmark |

## Recommendation

**Tier0 primary: exact brute force** — numpy `X @ q` + `argpartition`, or
`faiss.IndexFlatIP` for a named index object with C-speed
`IDSelectorNotMember` exclusion. Persist as mmap-able `.npy` + id array.
Exact, deterministic, ~ms, CI-safe — and it is the recall ground truth for
every other tier anyway.

**ANN teaching layer: hnswlib** — smallest surface to demonstrate the
recall/latency/filter tradeoff against the exact baseline. Accept the
sdist/stale-PyPI wart; pin single-thread + seed for reproducible builds, or
install from the v0.9.0 tag.

**Runner-up: LanceDB** — pick *instead* only if the question is "what stores
tier0" rather than "what indexes tier0" (persistence, versioning, SQL
prefiltering, relational double-duty, DuckDB interop) at the cost of heavy
deps, alpha-churning API, and zero pedagogical visibility into ANN.

## Presenter must not get wrong (late 2026)

1. Don't claim ANN is needed at 10⁴–10⁵ vectors — show the arithmetic.
2. hnswlib is not dead (v0.9.0 Mar 2026) but **PyPI is still 0.8.0 sdist-only**.
3. Filtered HNSW is not free — recall degrades with excluded fraction;
   hnswlib's filter is a per-candidate Python callback.
4. DuckDB VSS persistence is still experimental in 2026.
5. LanceDB ≠ "just a vector DB" (lakehouse positioning, Lance 2.2, Polaris);
   embedded OSS mode is not deprecated; its HNSW lives inside IVF partitions.
6. HNSW builds are reproducible only single-threaded + seeded; faiss-cpu
   wheels are officially Meta-co-maintained now — the "unofficial wheels"
   caveat is outdated.
7. Recall@k ground truth = the flat index; the exact tier is the referee.
