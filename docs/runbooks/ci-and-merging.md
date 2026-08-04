# CI and merging PRs

## When to use

Understanding what CI enforces, and merging any PR — especially stacked ones.

## CI anatomy (`.github/workflows/check.yml`)

Runs on every PR and on pushes to main. Design choices, each deliberate:

- `permissions: contents: read` — least privilege; the workflow can't write
  to the repo even if a dependency is compromised.
- `concurrency` + `cancel-in-progress` — a new push cancels the stale run.
- `timeout-minutes: 10` — a hung job fails instead of billing an hour.
- `uv sync --frozen` — installs exactly `uv.lock`; CI never resolves
  dependencies. Lockfile drift fails loudly.
- Split steps (Lint / Format / Types / Tests) — a failure names itself in
  the PR UI without opening logs.
- `ruff --output-format=github` — lint errors annotate the diff inline.

## Merging

1. CI green: `gh pr checks <n>` — every line `pass`.
2. Squash-merge only, delete branch:

   ```bash
   gh pr merge <n> --squash --delete-branch
   ```

3. Sync and verify main:

   ```bash
   git checkout main && git pull && make check
   ```

> Branch protection (requiring the `check` status) is currently **not
> enforced**: GitHub gates it behind Pro or a public repo (403 on the API
> for private+free). Until the repo goes public, "CI green before merge" is
> discipline, not machinery. Revisit when visibility changes.

## Failure modes

- **Stacked PR auto-closed on base merge (hit 2026-08-04).** PR B was based
  on PR A's branch. Merging A with `--delete-branch` deleted B's base →
  GitHub closed B, and reopening after a force-push fails
  (`Could not open the pull request`). Recovery:

  ```bash
  git fetch origin main
  # replay only B's own commits onto the new main:
  git rebase --onto origin/main <last-commit-of-A> <B-branch>
  git push -f origin <B-branch>
  gh pr create --base main ...   # fresh PR; reference the closed one
  ```

  Prevention: avoid `--delete-branch` while a stacked child is open, or
  retarget the child (`gh pr edit <n> --base main`) *before* merging the
  base.

- **CI passes locally, fails on `Install (locked)`** → uncommitted
  `uv.lock`; see [local-dev-loop](local-dev-loop.md).

## Last verified

2026-08-04 — PRs #1 and #3 merged this way; #2 is the stacked-PR casualty
documented above.
