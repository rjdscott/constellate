# Run the local dev loop

## When to use

Any change to this repo, from a fresh clone to an open PR.

## Steps

1. **Setup** (once): install [uv](https://docs.astral.sh/uv/), then

   ```bash
   git clone https://github.com/rjdscott/constellate.git && cd constellate
   uv sync          # creates .venv from uv.lock, Python 3.12
   make check       # expect: ruff clean, mypy clean, "81 passed" (49 without Orion + Hydra up), "doc-check: ok"
   make seed        # first run: ~262MB download + a few min build; see seed-the-dataset.md
   make load PLATFORM=lyra && make bench-smoke PLATFORM=lyra   # see run-lyra.md
   ```

   Conformance suites (`tests/conformance/`) run against every registered
   adapter; they skipped until phase 03 registered Lyra's four. New adapters
   register in `tests/conformance/conftest.py` and must pass unchanged.

2. **Branch**: never commit to main:

   ```bash
   git checkout -b feat/<slug>    # or fix/ chore/ docs/
   ```

3. **Work the change.** Rules that bite:
   - Platform vocabulary is codenames (ADR 0009): `PLATFORM=lyra|orion|hydra`,
     `config/<platform>.yaml`. Prose introduces each as "Lyra, the embedded
     knowledge plane" on first mention.
   - The pipeline never imports a concrete adapter; adapters never import
     each other. New adapters must pass the conformance suite unchanged.
   - Executing a plan phase? Tick checkboxes and append to the progress log
     as you go (`docs/plans/`), not at the end.
   - Deciding between real alternatives? Write the ADR (`/adr`) in the same
     PR.

4. **Verify before pushing:**

   ```bash
   make check
   ```

5. **PR**: push, open with `gh pr create` (template auto-fills), title
   `<type>(<scope>): <imperative summary>`. CI must be green before merge:
   see [ci-and-merging](ci-and-merging.md).

## Failure modes

- `uv sync --frozen` fails in CI but works locally → you changed
  `pyproject.toml` without committing the regenerated `uv.lock`. Run
  `uv sync` and commit the lockfile.
- `make check` lint failures → `uv run ruff check --fix src tests && uv run
  ruff format src tests`, re-run, review what it changed.
- Conformance tests error (not skip) after registering an adapter → the
  adapter violates the contract; fix the adapter, never the suite.

Closing out a plan phase? Run the `/phase-gate` skill before starting the
next one: `make doc-check` is its deterministic half and runs in CI anyway.

## Last verified

2026-08-04: phase 05 (`feat/orion`): 65 tests with Orion up (49 without); bench + report
targets now real (`docs/runbooks/run-benchmarks.md`).
2026-08-04: phase 06 (`feat/hydra`): 81 tests with Orion + Hydra up (49 without, 8 parity tests skip unless both); run-hydra runbook added
