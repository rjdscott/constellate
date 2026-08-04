# CLAUDE.md — constellate

Workflow rules for any Claude (or human) working in this repo.

## Branch + PR discipline

- **Never push to `main`.** Always branch + PR + squash-merge.
- **Branch naming:** `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`. Slug is short, hyphen-separated, lowercase. Example: `feat/dev-prod-workflow`, `fix/blind-tab-bar`.
- **One PR per logical change.** Don't bundle unrelated fixes — they're hard to review and harder to revert.
- **PR title:** `<type>(<scope>): <imperative summary>` matching recent history (`fix(mobile-nav): keep bottom tab bar visible on /blind`).
- **PR body:** use the template (`.github/pull_request_template.md`). Always fill the test plan.
- **Squash-merge only.** History stays linear.

## Documentation pipeline (research → ADR → plan → audit)

Four doc surfaces, four skills, one flow:
`docs/research/` (analysis) → `docs/adr/` (decisions) → `docs/plans/`
(execution) → `docs/audits/` (verification). Dated-directory convention
everywhere: `<YYYY-MM-DD>-<slug>/`.

### ADRs — `docs/adr/`, `/adr` skill

- **Every significant decision gets an ADR** (`NNNN-slug.md`) — any fork between
  technologies/patterns/schemas, any point demanding deeper research before
  committing, any deliberate rejection of an obvious option, any accepted
  trade-off.
- Nygard format + options considered (`docs/adr/template.md`); conventions in
  `docs/adr/README.md`. Accepted ADRs are immutable — supersede, never edit.
- ADRs land in the same PR as the work they govern.

### Plans — `docs/plans/`, `/plan` skill

- Multi-phase work gets a plan: `docs/plans/<date>-<slug>/` with a status-table
  README + `phase-NN-slug.md` files. Conventions in `docs/plans/README.md`.
- **Resumable by a stranger** is the bar. Status table, checkboxes, and progress
  logs update as-you-go, not at phase end.
- Gates per phase: `make check` green, verification commands run, ADR captured
  at any mid-plan fork.

### Audits — `docs/audits/`, `/audit` skill

- Point-in-time audits of a surface (code, security, UX, data):
  `docs/audits/<date>-<slug>/` with `00-executive-summary.md`, `NN-topic.md`
  findings, and a `todo.md` punchlist. Conventions in `docs/audits/README.md`.
- Findings carry evidence or get dropped; severity codes `C/H/M/L-NN`; audits
  are snapshots — never silently edited after publication.
- Research analysis stays in `docs/research/` (dated workspaces, e.g. the
  Palate Graph initiative); ADRs/plans/audits cite it, never restate it.

## Linked docs

- `CONTRIBUTING.md` — new-developer onboarding, branch model, PR conventions.
- `docs/adr/README.md` — ADR conventions + index of recorded decisions.
- `docs/plans/README.md` — plan conventions + index of phase plans (resumable).
- `docs/audits/README.md` — audit conventions + index of completed audits.
- `docs/research/` — dated research workspaces (analysis feeding ADRs + plans).
