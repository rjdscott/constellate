# Phase 02 — Data & probes

## Goal

`make seed` downloads ml-25m (checksum-pinned, idempotent, resumable) and
builds the canonical parquet every platform ingests: items, users, interactions
with global temporal split, genome-SVD item/user vectors (256d, seeded),
weighted edges (HAS_GENRE, HAS_TAG ≥0.5, RATED train-only, CO_RATED top-20
min-support-50), and the graph-necessary probe set — all reproducible
byte-for-byte from a fresh clone. Riskiest data assumption (probes can be
generated at all) surfaces here.

## Tasks

- [x] `make seed`: download + sha256 verify to `data/raw/ml-25m/` (gitignored)
- [x] `ingest/canonical.py`: items/users/interactions parquet; global temporal cutoff at 95th-percentile timestamp, pinned in config (ADR-cited RecSys'25 methodology)
- [x] `ingest/embeddings.py`: genome TruncatedSVD → 256d L2-normalized item vectors; `has_genome` flag + genre fallback for long tail (year dropped — genre means already cover it, see progress log); user vectors = rating-weighted mean, mean-centred; cached to parquet
- [x] `ingest/edges.py`: four edge types per prep §6.3; CO_RATED computed offline with popularity cap
- [x] `bench/probes.py`: two-hop tag bridges, cold-start (<10 ratings, has genome tags), cross-genre co-rating bridges, path-required queries; deterministic from seed → `data/canonical/probes.parquet`
- [x] Determinism test: two runs → identical file hashes

## Verification

```
make seed && make seed          # second run is a fast no-op
uv run pytest tests/unit/test_canonical.py -k determinism
uv run python -m constellate.ingest.stats   # row counts, split sizes, probe counts printed
```

## Artifacts

`data/canonical/*.parquet` (gitignored; hashes recorded in
`data/canonical/MANIFEST.json` which IS committed), `src/constellate/ingest/*`,
`bench/probes.py`.

## Progress log

- 2026-08-04 — Phase opened on `feat/seed`. Order: download → canonical →
  embeddings → edges → probes → determinism test → MANIFEST.
- 2026-08-04 — Full pipeline landed and ran against real ml-25m.
  Zip sha256 pinned (`8b21cfb7…`), md5 cross-checked against the
  grouplens-published value. Split cutoff ts=1545602470 (95th pct):
  23,750,090 train / 1,250,005 test. 62,423 items (13,816 with genome
  vectors), 156,604 users with train history. Edges: RATED 23.75M,
  HAS_TAG 615k, CO_RATED 134.5k, HAS_GENRE 107k. Probes: 200 (50 per kind).
  Second `make seed` is a 0.8s no-op. Fallback simplification: non-genome
  items get the mean of their genres' mean genome vectors (year term
  dropped — no signal it adds beyond genre means at this stage; revisit if
  phase-04 cold-start results are noisy).
- 2026-08-04 — Two bugs worth teaching: (1) `df[mask]` with a plain empty
  Python list is *column* selection, not an empty row mask — crashed the
  synthetic determinism fixture where CO_RATED is empty; fixed with a typed
  numpy mask. (2) First probe run produced only 24/50 cold-start probes:
  `groupby().size()` only counts items that appear in train, silently
  excluding never-rated items — the coldest items of all (101 genome items
  have zero train ratings). Reindex-with-zero fix took the pool to 125 and
  the probe count to 50. Popularity–genome correlation is real: of 29,736
  items with <10 train ratings, only 125 have genome tags.
