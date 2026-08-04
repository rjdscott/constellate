# Phase plans

Conventions for `docs/plans/`. A plan executes decisions already recorded in
`docs/adr/`; it never re-litigates them.

## Conventions

- One plan = one dated directory: `<YYYY-MM-DD>-<slug>/`.
- `README.md` per plan: outcome-phrased goal, scope + non-goals, status table,
  critical files, top risks, links to the ADRs/research it implements.
- Status table format: `| NN | Phase | Status | Last update |` with statuses
  🔵 Not started / 🟡 In progress / 🟢 Completed / ⏸ Deferred.
- One phase file per phase: `phase-NN-slug.md` containing **Goal** (one
  paragraph), **Tasks** (checkboxes), **Verification** (exact commands;
  `make check` minimum), **Artifacts** (files that must exist when done),
  **Progress log** (dated appends only, never rewritten).
- Phase sizing: one PR-sized, independently verifiable slice. Order by
  dependency, then risk. 3–8 phases typical.
- Update status table, checkboxes, and progress logs as-you-go, not at the end.
- Scope changes get written in (new phase file or amended goal); renumbering is
  forbidden — new work gets new numbers.
- Bar for every update: a stranger must be able to resume from the README alone.

## Index

| Plan | Goal | Status |
|------|------|--------|
| [2026-08-04-knowledge-plane](2026-08-04-knowledge-plane/README.md) | Three-platform knowledge plane experiment (Lyra/Orion/Hydra — the embedded/unified/composed knowledge planes): probe-set ablation proof, cross-platform equivalence, latency/footprint deltas, explorer UI, MCP | 🟡 In progress (01–07 🟢, explorer SPA + MCP live over all three platforms; next: 08 neural arm + final report) |
