# Migration narrative — the talk arc

Dated milestone log. Every accepted ADR and completed plan phase appends an
entry: what changed, why it matters to the story, artifacts. Appends only.

---

## 2026-08-04 — Workspace opened

Project reframed from `docs/constellate-prep.md` sketch into the repo's
research → ADR → plan pipeline. Five research threads launched (graph engines,
embedded vector, Postgres lite tier, embeddings + benchmark methodology,
UI + MCP). Machine baseline: 28 cores, 62 GB RAM, Docker 29 / Compose v5.

## 2026-08-04 — Research complete; ADRs 0001–0008 proposed

All five threads returned same-day. Findings that overturned the prep doc:
Kuzu archived Oct 2025 (Apple acquired Kùzu Inc. — public Feb 2026);
ml-32m ships no tag genome (pins ml-25m); FalkorDB dropped Bolt in v4.20;
Memgraph 3.12 displaces both FalkorDB and Neo4j for the mid tier on
concurrency scaling + client fairness; at 62k vectors exact flat search is
the honest tier0 baseline (ANN becomes the *teaching* layer, not the
default); AGE is alive with an official PG18 image but CTEs remain the
honest lite-tier default at 2–3 hops. Eight ADRs proposed, awaiting
ratification. Artifacts: `docs/research/2026-08-04-knowledge-plane-foundations/01–06`,
`docs/adr/0001–0008`.

## 2026-08-04 — UI requirements elevated; ADR 0007 rewritten pre-acceptance

On review, the explorer's role changed: from benchmark lens to productized
face of the project (content, videos, public excitement), with a full live
EKS deployment planned after the analysis. ADR 0007 rewritten (legitimate —
still Proposed): no-build page → Vite/React/TS SPA with a custom design
system (Radix + Tailwind v4 tokens, Cytoscape.js, Observable Plot, Motion).
EKS itself stays deferred; the SPA artifact is deployment-agnostic. Phase 07
amended accordingly — now the largest phase, design tokens gated first.
Story beat for the talk: requirements moved, the ADR trail shows exactly
when and why.

## 2026-08-04 — Platform naming reframed (ADR 0009)

tier0/lite/mid/ent rejected: it encodes a superiority ladder the project
explicitly argues against. New vocabulary — the **embedded**, **unified**,
**composed**, and **distributed** knowledge planes ("right tool for the
job"); Make variable `PLATFORM=`, config keys match. Constellation codenames
(lyra/orion/hydra/eridanus) considered and kept in reserve as a future
branding layer. Docs/plan swept; research snapshots keep old names with a
mapping note. Story beat: "unified vs composed" now states the central
comparison in two words.

## 2026-08-04 — Naming finalized: constellation codenames + architecture epithets

Same-day refinement after the product framing solidified: descriptive words
alone are unbrandable ("the composed platform" titles no video). Final form
(ADR 0009 rewritten while Proposed): constellation codenames as canonical
keys everywhere — **Lyra** (embedded), **Orion** (unified), **Hydra**
(composed), **Eridanus** (distributed, future) — with the architecture terms
kept as permanent technical epithets at first mention. The platforms are
Constellate's constellations; `PLATFORM=lyra` is the default. Vela avoided
(Kuzu fork); Hydra's collision with Meta's config lib accepted.

## 2026-08-04 — ADRs 0001–0009 accepted; execution begins

All nine ADRs ratified in one pass: ml-25m pin, Lyra exact-first vector,
Lyra Kuzu 0.11.3 pin, Orion PG18 CTE-default, Hydra Memgraph, dual embedding
ablation, production-grade explorer SPA, FastMCP v3, constellation naming.
Plan `docs/plans/2026-08-04-knowledge-plane/` moves to execution; phase 01
(scaffold) starts on `feat/scaffold`. Foundation era complete — everything
from here is build.

## 2026-08-04 — Phase 01 complete: the contract exists before any engine

Scaffold landed (`feat/scaffold`): uv + ruff + mypy --strict + pytest, core
types and plane Protocols, working weighted-RRF fusion and six-step pipeline
proven against in-memory fakes, per-platform configs with fingerprints,
conformance suites executable-but-skipping, CI. The adapter boundary is now
real: phase 03's engines must fit this contract, not shape it. Artifacts:
`src/kp/core/*`, `tests/`, `config/{lyra,orion,hydra}.yaml`, PR #2.

## 2026-08-04 — ADR 0010: package renamed kp → constellate

Post-phase-01 review caught an inherited non-decision: `src/kp/` came from
the prep sketch unexamined. Same disease ADR 0009 cured for platforms —
opaque acronym vs identity. Renamed to `src/constellate/` while exactly one
PR was open and zero consumers existed; prep sketch updated with a
supersession banner. Lesson for the talk: naming decisions hide in
scaffolding, and the cheapest rename is the one you do before anyone
imports you.

## 2026-08-04 — Runbooks surface added; process becomes curriculum

PRs #1 and #3 merged to main (CI green; #2 was a stacked-PR casualty, now a
documented failure mode). New doc surface `docs/runbooks/` + `/runbook`
skill, wired into CLAUDE.md: ADRs record why, runbooks record how, and the
repo's own incidents become workshop teaching material. First two runbooks:
local-dev-loop, ci-and-merging.

## 2026-08-04 — Phase gate installed: doc discipline becomes machinery

The post-phase-01 audit found four gaps in a doc set believed current —
proof that discipline needs enforcement. Two-layer gate added: `make
doc-check` (`scripts/check_docs.py` — link resolution, ADR index/status
consistency, 🟢-phase invariants, runbook indexing) now runs inside `make
check` and CI on every PR; the `/phase-gate` skill carries the judgment
checklist (story-quality progress logs, narrative entries, ADRs at forks,
runbook bumps, ripple staleness) that must pass before any phase flips 🟢.
Workshop beat: checklists beat memory, and the gate's origin story is the
audit that motivated it.

## 2026-08-04 — Phase 02: the dataset becomes an artifact

`make seed` now builds the canonical layer every platform ingests: 25M
interactions temporally split (cutoff ts=1545602470, 95th percentile —
train on the same past, evaluate on the same future), genome-SVD 256d
vectors with an honest `has_genome` flag, 24.6M weighted edges, and the
200-probe graph-necessary set the phase-04 go/no-go will stand on.
Reproducibility is enforced, not promised: a committed MANIFEST.json of
file hashes plus a two-run determinism test. Best data-story beat so far:
cold start and tag coverage are *anticorrelated* — of 29,736 items with
fewer than 10 train ratings only 125 have genome tags, and the first probe
build silently dropped the never-rated ones because `groupby().size()`
can't count to zero. The graph plane's pitch — reaching items the vector
plane can't see — is exactly the population that's hardest to probe.
