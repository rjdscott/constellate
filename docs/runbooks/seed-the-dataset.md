# Seed the dataset

## When to use

Fresh clone, or any time `data/canonical/` is missing/suspect. Every platform
(Lyra, Orion, Hydra) loads from the canonical parquet this produces — no
platform ever reads raw CSVs.

## Steps

1. ```bash
   make seed
   ```
   First run downloads ml-25m (~262 MB, sha256-verified, resumable — rerun on
   a dropped connection and it continues), extracts, then builds canonical
   parquet: items, users, interactions (global temporal split), item/user
   vectors (genome SVD, ADR 0006), edges (HAS_GENRE / HAS_TAG / RATED /
   CO_RATED), probes. Second run is a fast no-op ("up to date" per step).

2. Inspect what was built:

   ```bash
   uv run python -m constellate.ingest.stats
   ```

3. Verify reproducibility: compare `data/canonical/MANIFEST.json` against the
   committed copy — `git diff data/canonical/MANIFEST.json` must be empty.
   A hash drift means your build is not the experiment's build; do not bench
   on it.

## Rebuilding

Steps are skipped when their outputs exist. To force a rebuild:

```bash
rm -rf data/canonical && make seed        # everything
rm data/canonical/probes.parquet && make seed   # just probes (or: uv run python bench/probes.py)
```

Deleting an upstream file does NOT cascade — delete everything downstream of
it too (order: canonical → item_vectors → user_vectors → edges → probes).

## Failure modes

- `ml-25m.zip sha256 mismatch` — corrupt/partial download already renamed to
  `.zip`; the bad zip is deleted automatically, rerun `make seed`.
- `MANIFEST.json` differs from committed — dependency drift (numpy/sklearn
  SVD internals) or a code change without a manifest refresh. If the change
  is intentional, commit the new manifest in the same PR; if not, `uv sync
  --frozen` and rebuild.

## Last verified

2026-08-04 — phase 02, full run from fresh download on the benchmark machine.
