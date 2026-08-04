# 09 — Lessons learned (living document)

Cumulative, append-per-phase. Each lesson: what happened, the general
principle, and where the evidence lives — so end-of-project reflection and
public write-ups (blog posts, the talk) can be assembled straight from
here. Chronology lives in `04-migration-narrative.md`; this doc is
thematic. Append, never rewrite; date every addition.

---

## L1 — Conformance tests prove contracts; benchmarks prove systems (phase 03–04)

Tiny-graph conformance suites stayed green through *every* Kuzu planner
regression — prepared params, `list_contains()`, far-node predicates each
silently turned a 70 ms anchored expansion into a minutes-long full-graph
walk, and 12 correctness tests noticed nothing. Only production-shaped
data exposed it.
**Principle:** correctness suites and production-shaped benchmarks answer
different questions; passing one says nothing about the other.
**Evidence:** phase-03 progress log; `run-lyra` runbook failure modes.
**Post angle:** "Your integration tests can't see query plans."

## L2 — Engineer equivalence at the semantics level, not the query level (phase 05)

Three graph engines (Kuzu Cypher, Postgres self-join SQL, AGE openCypher)
produce retrieval quality identical to 4 decimals — because all three
implement the same *ranking contract* (min-hops, path support, tie-break)
rather than translating the same query. Stage-2 metadata may differ;
ranks, which fusion consumes, cannot.
**Evidence:** `08-orion-benchmark-findings.md` finding 1; graph_only
0.0965 across platforms.
**Post angle:** "Portable retrieval isn't portable queries."

## L3 — Architecture beats transport: price the process model, not the network hop (phase 05)

The embedded platform (no daemon, no serialization) was assumed to own
latency. Measured: Orion's Postgres — daemon, TCP, SQL parsing — is ~3×
*faster* at p50 and keeps scaling with concurrency, because the embedded
design's synchronous in-process engine calls serialize everything. The
"saturation" run at 1.2× estimated capacity didn't saturate.
**Evidence:** doc 07 vs doc 08 latency tables (p50 127 ms flat across
concurrency vs 43 ms and dropping).
**Post angle:** "Everyone prices the network hop; nobody prices the
single process."

## L4 — Offline evaluation must prove it reconstructs the online system (phase 04–05)

The fusion tuner fused depth-truncated top-50 lists while the live
pipeline fused 250-deep candidates; the committed artifact itself
contained the contradiction (offline baseline out-scoring the arm it
claimed to reproduce), and the "best" weight moved 1.5 → 2.0 once inputs
were faithful. Fix: a permanent in-artifact fidelity check — offline
baseline must equal the live arm before any tuned number is believed.
Both platforms now show exact fidelity.
**Evidence:** phase-04 review addendum in the narrative; `fidelity_check`
in every artifact since.
**Post angle:** "Your offline eval is grading its own homework."

## L5 — Keep an exact-search referee (phase 04–05)

pgvector HNSW-on-halfvec halved vector-only recall vs faiss exact flat —
concentrated on cold-start items whose fallback vectors bunch tightly in
embedding space. Without Lyra's exact baseline this would have read as a
probe-set quirk; with it, it's cleanly attributable to the index.
**Evidence:** doc 08 finding 1 (vector_only 0.0108 vs 0.0213;
cold_start 0.0300 vs 0.0680).
**Post angle:** "ANN benchmarks need an exact-search control arm."

## L6 — Latency methodology is itself a result (phase 04)

Same service, same run: open-loop (charged from scheduled send) reports
p50 = 54 *seconds* past the knee; a closed-loop harness would have
reported ~120 ms while silently throttling. A ~450× difference with no
code change — coordinated omission isn't a footnote.
**Evidence:** doc 07 latency section; `bench/latency.py` docstring.
**Post angle:** "The load generator decides your p99."

## L7 — Adversarial self-review catches what green checks cannot (phase 04–05)

Every phase's independent review pass found real defects after all
checks were green: the fusion-depth mismatch (touched a headline
number), non-atomic load steps (crash + rerun silently duplicates 25M
rows), CI able to pass with the entire Orion conformance surface
silently deregistered. Pattern: build → adversarial review by a fresh
context → fix → re-verify, every phase, no exceptions.
**Evidence:** phase-04/05 progress logs, review-fix commits.
**Post angle:** "Green CI is necessary, never sufficient."

## L8 — Boring failure modes are curriculum (all phases)

shm_size vs parallel HNSW builds; AGE 1.7 jailing bulk-load paths under
`/tmp/age/`; CSV-loaded numeric properties arriving as agtype strings;
a pandas column named `count` shadowing the `itertuples` namedtuple
method; docker compose namespacing every platform under the *directory*
name absent an explicit project `name:`. Each cost minutes-to-hours once
and is now a dated runbook failure-mode entry costing the next person
seconds.
**Evidence:** `run-lyra`, `run-orion`, `run-benchmarks` runbook failure
modes.
**Post angle:** "An incident not written down is scheduled to repeat."

## L9 — Determinism is a feature you build, then get to lean on (phases 02–05)

Seeded everything (SVD, sampling, splits), sorted-before-sampled, byte-
determinism tests, committed manifests. Payoff: quality metrics
byte-identical across benchmark reruns and even across the review-fix
rerun — so any observed delta is a real change, never noise, and
latency reruns are free.
**Evidence:** MANIFEST.json + two-run determinism test (phase 02);
"quality byte-identical" notes in phase 04/05 logs.
**Post angle:** "Make your benchmark boring so your findings can be
interesting."
