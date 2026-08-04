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

- [ ] `make seed`: download + sha256 verify to `data/raw/ml-25m/` (gitignored)
- [ ] `ingest/canonical.py`: items/users/interactions parquet; global temporal cutoff at 95th-percentile timestamp, pinned in config (ADR-cited RecSys'25 methodology)
- [ ] `ingest/embeddings.py`: genome TruncatedSVD → 256d L2-normalized item vectors; `has_genome` flag + genre/year fallback for long tail; user vectors = rating-weighted mean, mean-centred; cached to parquet
- [ ] `ingest/edges.py`: four edge types per prep §6.3; CO_RATED computed offline with popularity cap
- [ ] `bench/probes.py`: two-hop tag bridges, cold-start (<10 ratings, has genome tags), cross-genre co-rating bridges, path-required queries; deterministic from seed → `data/canonical/probes.parquet`
- [ ] Determinism test: two runs → identical file hashes

## Verification

```
make seed && make seed          # second run is a fast no-op
uv run pytest tests/unit/test_canonical.py -k determinism
uv run python -m kp.ingest.stats   # row counts, split sizes, probe counts printed
```

## Artifacts

`data/canonical/*.parquet` (gitignored; hashes recorded in
`data/canonical/MANIFEST.json` which IS committed), `src/kp/ingest/*`,
`bench/probes.py`.

## Progress log
