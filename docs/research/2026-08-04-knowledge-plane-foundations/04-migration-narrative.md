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

## 2026-08-04 — Phase 03: Lyra answers, and the graph plane teaches its first lesson

Lyra, the embedded knowledge plane, runs end to end with no daemon: DuckDB
relational + faiss-flat (hnswlib alongside) + Kuzu, wired through the
factory into the six-step pipeline, served over FastAPI, all three demo
flows explained ("item:318 → CO_RATED → item:356") in 130–350ms. The
conformance progress bar hit zero skips — every adapter passes the same
suite. The talk gets its first genuine graph-engine war story: a two-hop
expansion from Shawshank is 321,055 paths, and the naive adapter streamed
every one of them into Python. The fix is the lesson — aggregate inside the
engine, fetch paths only for winners — and beneath it, three successive
kuzu planner traps (prepared params, list_contains, any far-node predicate)
each silently turned a 70ms anchored plan into a full-graph walk. Tiny
conformance graphs stayed green the whole time: correctness suites do not
catch planner regressions; only production-shaped data does.

## 2026-08-04 — Phase 04: the go/no-go answers GO, and fusion learns humility

The benchmark harness ran, and the bet the project stands on paid out:
on the 200 graph-necessary probes, hybrid retrieval beats vector-only on
Recall@10 (+0.0141, p=0.0054) and Recall@50 (+0.186). Container work is
unblocked. But the headline belongs to the arm nobody was rooting for:
graph_only dominates *both* (R@10 0.097 vs hybrid's 0.036) — equal-weight
RRF dilutes graph signal with weaker vector candidates, and the tuned
graph weight of 1.5 recovers +15% held-out nDCG. Stratification kept the
story honest: cross_genre is graph's 176× blowout, cold_start goes to the
*vector* plane (genome-SVD already encodes the tags cold items live on),
and path_required/tag_bridge score ~0 for every arm because the expander
fills its budget with 1-hop neighbours before any 2-hop target survives —
a retrieval-policy gap the harness exists to expose, parked for phase 05+.
The latency methodology delivered its own lecture: p50/p99 identical at
concurrency 1/8/32 (the embedded single-process ceiling, measured — 8.7/s
capacity, the axis Orion and Hydra get to attack), and the past-the-knee
run showed p50 = 61 *seconds* where a closed-loop harness would have
reported ~115ms. Coordinated omission isn't a footnote; it's a 500×
difference in the same run. Artifacts: `bench/results/lyra-c368e54-*.json`,
`bench/report.md`, findings + per-platform config record in
`07-lyra-benchmark-findings.md`.

## 2026-08-04 — Phase 04 addendum: the review catches the tuner grading its own homework

An independent review pass over the harness branch found the one flaw that
touched a headline number: fusion tuning had been fusing depth-truncated
top-50 lists while the real pipeline fuses 250-deep candidates — and the
committed artifact itself contained the proof (offline baseline nDCG 0.042
vs the actual hybrid arm's 0.036; disjoint halves can't out-average their
own full set). Rerun with faithful inputs plus an in-artifact fidelity
check: exact agreement (0.0362 = 0.0362), and the "best" graph weight
moved from 1.5 to 2.0 — the earlier value was an artifact of the wrong
regime. Story beat for the talk: offline evaluation is only as good as its
reconstruction of the online system, fidelity checks are cheap, and the
final numbers (GO verdict, +24% tuned nDCG on held-out probes, grid-edge
caveat) now rest on a tuner that provably fuses what the pipeline fuses.
Final artifact: `bench/results/lyra-f7eb799-20260804T082917Z.json`.

## 2026-08-04 — Phase 05: one Postgres holds the line, and the ceiling was never the network

Orion, the unified knowledge plane, went from empty container to committed
benchmark in a day: PG 18.1 + AGE 1.7.0 + pgvector 0.8.6 in one image,
25M rows COPYed in 43 seconds, all four new adapters through the unchanged
conformance suite on their first live run — where Kuzu had needed three
planner-trap rewrites, Postgres pushed every parameterized plan without
drama. The headline is equivalence: graph retrieval identical to Lyra to
four decimals (R@10 0.0965) across Kuzu, SQL self-joins, and AGE Cypher,
because the contract was engineered at ranking semantics, not query
syntax. The upset is latency: the daemon-and-TCP platform is ~3× *faster*
than the embedded one (p50 43 ms vs 127 ms) and kept scaling where Lyra's
single process flat-lined — the embedded ceiling was never the missing
network hop. The honest deltas: pgvector's HNSW-on-halfvec halves
vector-only recall against the exact-search referee (concentrated on cold
start), hybrid still lands within tolerance; and the ADR 0004 wager paid
out measured — CTE beats AGE ~6× (p50 43 ms vs 244 ms), so the thesis
rests on plain SQL with AGE as the ergonomics arm. Review pass again
earned its keep: non-atomic load steps (crash + rerun would duplicate 25M
rows) and a CI hole where the entire Orion surface could silently
deregister — both fixed before merge. Lessons L2, L3, L5 landed in the
new living lessons doc (`09-lessons-learned.md`). Artifacts:
`bench/results/orion-*.json` × 2, findings in `08-orion-benchmark-findings.md`.

## 2026-08-04 — Phase 06: three engines, one contract, and the planner tax made visible

Hydra, the composed knowledge plane, brought the count to four graph
engines producing byte-ranked-identical retrieval (R@10 0.0965 to four
decimals across Kuzu, SQL self-joins, AGE, and now Memgraph) — and the
equivalence is no longer prose: a committed parity differential
(`tests/conformance/test_graph_parity.py`) guards it on every CI run. The
composed pitch — best dedicated engine per plane, Postgres as source of
truth with Qdrant and Memgraph as projections rebuilt from it alone in
~41s (the CDC-shape proof) — survived contact with reality in a
complicated way. Qdrant honored it: a real HNSW retains ~94% of the exact-search referee's
recall (0.0200 vs 0.0213 R@10), doubling pgvector's halfvec showing. Memgraph taxed it: the engine's marquee variable-length
syntax hung for 312+ seconds on production data (planner skips the key
index for `IN`; DFS path explosion through hubs) and the salvaged
UNWIND-anchored, unrolled, in-engine-aggregated rewrite — literally the
CTE adapter's query shape transliterated into Cypher — still runs the
graph leg ~2.5× slower than plain Postgres self-joins at identical
semantics. Two silent-failure classes joined the curriculum: Qdrant
brute-forcing behind a green status (L10) and the planner blind spots
(L11). The adversarial review round again reached the proof machinery
itself: the projection "verification" compared Postgres to Postgres and
could never fail, and nothing barriered or recorded HNSW index state —
both now fixed, with the artifact carrying engine-reported index counts.
Quality: all three platforms within ±0.02 of each other, hybrid GO
(p=0.0038); p50 115ms flat across concurrency, between embedded Lyra
(127ms, ceilinged) and unified Orion (43ms, scaling). Artifacts:
`bench/results/hydra-0b36d7c-*.json`, findings in
`10-hydra-benchmark-findings.md`.

## 2026-08-05 — ADR 0011: one API process, every platform (phase 07 opens)

Phase 07 (explorer + MCP) opened by closing the gap between what the API
could serve (one platform per process, `$PLATFORM` at startup) and what
the playground promises (side-by-side platform comparison). ADR 0011:
a single process holds a lazy platform registry; retrieval routes take an
optional `platform`; `/v1/platforms` reports what's configured and alive.
One origin for the SPA, a free `platform` argument for the MCP tools, one
uvicorn to run — with the explicit commitment that API timings stay
illustrative and the open-loop bench harness remains the only citable
latency source. Design direction locked the same day: the Observatory
identity (celestial dark-first, restrained instrument-grade execution —
the explanation graphs render as constellations because the project is
named Constellate) with a cinematic overview as the app's entry surface.

## 2026-08-05 — Phase 07: the project gets a face (explorer SPA + MCP)

Five PRs (#13–#17 + close) turned the benchmark into a product surface.
ADR 0011 first: one API process serving every platform through a lazy
registry, because the playground's side-by-side comparison needs one
origin — with the standing commitment that the open-loop harness stays
the only citable latency source. Then the Observatory design system,
authored before any component (WCAG- and CVD-validated palette, seven
enforceable taste rules) — and immediately stress-tested by the phase's
defining event: the first agent-built UI came back competent and generic
("vibecoded" — Rob), and three rounds of design direction produced the
real thing: a full-bleed star-atlas overview whose stat cards were
replaced by a live proof strip (one graph-arm query, three platforms,
identical top-3 landing side by side — the thesis demonstrated, not
asserted), a playground with URL-shareable state and cross-pane
consensus markers, constellations drawn as concentric star charts with
tag-bridge nodes and expand-by-retrieval, and Observable Plot dashboards
reading the committed artifacts (lesson L12: taste is a spec you
enforce). The MCP server closed the loop ADR 0008 opened: three curated
tools over the same service layer, selftested against live engines. The
adversarial review kept its streak — its majors were again proof
machinery (a health check with no I/O that could never see a platform
die; L13) — fixed with probe-plus-evict and a kill test. Artifacts:
`ui/`, `src/constellate/mcp_server.py`, screenshots in `assets/`,
snapshot build serving the whole bench story from static files.
