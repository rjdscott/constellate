---
name: phase-gate
description: Close out a plan phase before starting the next one: run the deterministic doc checks, then walk the judgment checklist (progress logs, narrative, ADRs, runbooks), and only then flip the phase 🟢 and proceed. Use at the end of every plan phase ("close phase NN", "gate the phase", "ready for next phase?"), or whenever the user asks whether docs are current before moving on.
---

# phase-gate: no phase is done until its story is written

A phase is 🟢 when a stranger could resume the project from the docs alone
and a workshop audience could learn from what happened. Machines check what
machines can; you judge the rest. Run this BEFORE starting the next phase.

## Step 1: deterministic gate (must pass first)

```bash
make check       # lint + types + tests
make doc-check   # links, index/status consistency, 🟢-phase invariants
```

Fix failures before proceeding. Never weaken `scripts/check_docs.py` to get
past it: fix the docs.

## Step 2: judgment checklist

Walk every item; each is yes or it gets fixed now, in this PR:

1. **Phase file** (`docs/plans/<plan>/phase-NN-*.md`): every task ticked or
   explicitly moved (new phase / amended scope, never silently dropped);
   verification commands actually run with output confirmed; artifacts
   exist; progress log tells what happened *including what went wrong*:
   incidents are curriculum, not embarrassments.
2. **Status table** (plan README): row 🟢 with today's date; plans index
   (`docs/plans/README.md`) says what's next.
3. **Migration narrative** (`docs/research/.../04-migration-narrative.md`):
   entry appended: what changed, why it matters to the story, artifacts.
4. **ADRs**: every fork hit mid-phase has its ADR, indexed, statused, linked
   from the progress log. No decision lives only in chat.
5. **Runbooks**: any operational procedure touched or incident hit this
   phase → runbook created/updated (`/runbook`), Last verified bumped.
6. **Ripples**: does the change invalidate anything in README.md,
   CONTRIBUTING.md, CLAUDE.md, config docs, or an earlier phase file's
   claims? Grep for the thing you changed; fix staleness now.
7. **Memory**: durable project facts changed (names, goals, constraints) →
   update memory files.
8. **Lessons**: anything this phase taught that generalizes → append to
   `docs/research/2026-08-04-knowledge-plane-foundations/09-lessons-learned.md`
   (what happened, principle, evidence pointer, post angle). That doc is
   the end-of-project reflection + public write-up source; a phase that
   taught nothing is rare enough to say so explicitly.

## Step 3: close

- Re-run `make check && make doc-check` after fixes.
- Everything lands in the phase's PR (or an immediate follow-up docs PR,
  never "later").
- Report the gate result to the user: what was checked, what was fixed,
  what's next. Only then begin the next phase.

## Hard rules

- The gate runs even when "nothing changed in docs": that belief is
  exactly what it exists to test (2026-08-04: a believed-current doc set
  had four gaps).
- Never mark 🟢 with a failing or skipped gate; the phase stays 🟡 with the
  blocker named in the progress log.
