# 09 — Lessons learned (living document)

Updated **continuously — every implementation that teaches something
appends here in the same PR**, not just at phase gates (the gate's item 8
is the backstop, not the cadence). Each lesson carries:

- **What happened** — tied to the concrete implementation (files,
  commits, artifacts), never abstract.
- **Principle** — the generalization.
- **Do differently next time** — if we rebuilt from zero, what changes.
- **For builders** — what someone following this path into their own
  knowledge plane should take, stated as advice.
- **Evidence** + **post angle** — pointers for the end-of-project
  reflection and public write-ups.

Chronology lives in `04-migration-narrative.md`; this doc is thematic.
Append, never rewrite; date every addition.

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
**Do differently:** run the first real-data query the same day the adapter lands — don't let conformance green defer it.
**For builders:** budget a "production-shaped shakedown" per engine before trusting any adapter; graph engines especially — planner behavior is invisible at toy scale.
**Post angle:** "Your integration tests can't see query plans."

## L2 — Engineer equivalence at the semantics level, not the query level (phase 05)

Three graph engines (Kuzu Cypher, Postgres self-join SQL, AGE openCypher)
produce retrieval quality identical to 4 decimals — because all three
implement the same *ranking contract* (min-hops, path support, tie-break)
rather than translating the same query. Stage-2 metadata may differ;
ranks, which fusion consumes, cannot.
**Evidence:** `08-orion-benchmark-findings.md` finding 1; graph_only
0.0965 across platforms.
**Do differently:** write the ranking contract down (ordering keys, tie-breaks) as a spec *before* the second adapter, not extract it from the first one's code.
**For builders:** define your cross-engine contract as "what ordering reaches fusion", then let each engine implement it natively; translating queries verbatim couples you to the weakest dialect.
**Post angle:** "Portable retrieval isn't portable queries."

## L3 — Architecture beats transport: price the process model, not the network hop (phase 05)

The embedded platform (no daemon, no serialization) was assumed to own
latency. Measured: Orion's Postgres — daemon, TCP, SQL parsing — is ~3×
*faster* at p50 and keeps scaling with concurrency, because the embedded
design's synchronous in-process engine calls serialize everything. The
"saturation" run at 1.2× estimated capacity didn't saturate.
**Evidence:** doc 07 vs doc 08 latency tables (p50 127 ms flat across
concurrency vs 43 ms and dropping).
**Do differently:** measure the concurrency ceiling of the embedded arm in phase 1, not phase 5 — it reframes every "no daemon" claim early.
**For builders:** if your workload has any concurrency, an in-process engine stack needs a process/executor story (or accept the serialized ceiling); benchmark concurrency 1 vs N before choosing embedded for latency reasons.
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
**Do differently:** build the fidelity check the same day as the tuner — it's ~10 lines and it defines whether the tuner is meaningful at all.
**For builders:** any offline re-ranking/tuning harness must first reproduce the online system bit-for-bit on the identity configuration; treat that as a failing test until it passes.
**Post angle:** "Your offline eval is grading its own homework."

## L5 — Keep an exact-search referee (phase 04–05)

pgvector HNSW-on-halfvec halved vector-only recall vs faiss exact flat —
concentrated on cold-start items whose fallback vectors bunch tightly in
embedding space. Without Lyra's exact baseline this would have read as a
probe-set quirk; with it, it's cleanly attributable to the index.
**Evidence:** doc 08 finding 1 (vector_only 0.0108 vs 0.0213;
cold_start 0.0300 vs 0.0680).
**Do differently:** nothing — exact-first was designed in (ADR 0002) and paid off exactly as intended.
**For builders:** keep one exact-search configuration permanently runnable, whatever your production index is; every ANN recall number is unanchored without it.
**Post angle:** "ANN benchmarks need an exact-search control arm."

## L6 — Latency methodology is itself a result (phase 04)

Same service, same run: open-loop (charged from scheduled send) reports
p50 = 54 *seconds* past the knee; a closed-loop harness would have
reported ~120 ms while silently throttling. A ~450× difference with no
code change — coordinated omission isn't a footnote.
**Evidence:** doc 07 latency section; `bench/latency.py` docstring.
**Do differently:** add a rate *sweep* to find the knee instead of a single 0.7×/1.2× pair — the concurrent-backend run outran the sequential capacity estimate (doc 08).
**For builders:** use open-loop load generation with latency charged from scheduled send; if your harness can't overload the target, your p99 is fiction.
**Post angle:** "The load generator decides your p99."

## L7 — Adversarial self-review catches what green checks cannot (phase 04–05)

Every phase's independent review pass found real defects after all
checks were green: the fusion-depth mismatch (touched a headline
number), non-atomic load steps (crash + rerun silently duplicates 25M
rows), CI able to pass with the entire Orion conformance surface
silently deregistered. Pattern: build → adversarial review by a fresh
context → fix → re-verify, every phase, no exceptions.
**Evidence:** phase-04/05 progress logs, review-fix commits.
**Do differently:** run the reviewer *before* the first full benchmark run, not after — the phase-04 fusion-depth fix forced a 1.5 h rerun.
**For builders:** a second pair of eyes with fresh context and an adversarial brief finds classes of bugs the author structurally cannot; automate the habit, not just the checks.
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
**Do differently:** nothing structural — but write the failure mode down *in the same commit* as the fix; backfilled incidents lose their diagnostic detail.
**For builders:** keep per-surface runbooks with dated failure modes; the second occurrence of any incident should cost seconds, not the original hours.
**Post angle:** "An incident not written down is scheduled to repeat."

## L9 — Determinism is a feature you build, then get to lean on (phases 02–05)

Seeded everything (SVD, sampling, splits), sorted-before-sampled, byte-
determinism tests, committed manifests. Payoff: quality metrics
byte-identical across benchmark reruns and even across the review-fix
rerun — so any observed delta is a real change, never noise, and
latency reruns are free.
**Evidence:** MANIFEST.json + two-run determinism test (phase 02);
"quality byte-identical" notes in phase 04/05 logs.
**Do differently:** nothing — seeding everything from day one is the cheapest decision that kept paying.
**For builders:** determinism (seeds, sorted-before-sampled, committed manifests, byte-level checks) is what makes benchmark deltas mean something; add it before your first measurement, retrofitting it is misery.
**Post angle:** "Make your benchmark boring so your findings can be
interesting."
