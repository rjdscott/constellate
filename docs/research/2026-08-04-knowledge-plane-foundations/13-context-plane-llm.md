# Context-plane LLM consumers: local vs API, measured

- **Date:** 2026-08-05
- **Question (ADR 0012):** what does it actually cost — in tool-call
  fidelity, latency, dollars, and operational surface — to prove the
  context plane with a local small model versus a frontier API, and what
  does each choice look like from this laptop up to a real platform?
- **Evidence:** `bench/context/anthropic-claude-haiku-4-5-20251001-20260805T070920Z.json`,
  `bench/context/local-qwen3-8b-20260805T071251Z.json` — one fixed
  8-task suite, 3 reps each, deterministic scoring of tool *behavior*
  (right tool, exact args, answer grounded in returned data), not prose.
  Demo-class numbers by decree: nothing here is citable next to the
  benchmark harness (ADR 0011 discipline; that's why these artifacts
  live in `bench/context/`).

## Headline

| | Haiku 4.5 (API) | qwen3:8b (local, CPU) |
|---|---|---|
| overall fidelity | **1.00** (24/24) | **0.88** (21/24) |
| single-tool tasks | 1.00 | 1.00 |
| multi-step chaining | 1.00 | **0.00** (3/3 reps) |
| mean task latency | 1.6–7.9 s | 2.3–13.2 s |
| tokens (in/out, full run) | 75.7k / 8.7k | 41.2k / 18.8k (57k chars of it thinking) |
| cost, full 3-rep run | $0.12 | $0 |
| offline | no | yes |
| new ops surface | an env var | 6.6 GB install + a server process |

Both drivers speak to the identical MCP tools over the identical service
layer — the context plane is provably consumer-agnostic, which was the
point of the demonstration.

## Model selection: why these two

The API side was uncontroversial: Haiku 4.5
(`claude-haiku-4-5-20251001`) is the cheapest current Anthropic model
with first-class tool use — the demo needs reliable tool calling per
dollar, not frontier reasoning, and at $1/M in · $5/M out the entire
rehearsal budget is pocket change. Using a bigger model would only make
the comparison less interesting: the question is how *little* model the
context plane needs, from both directions.

The local side had real alternatives, all runnable on a 62 GB/28-core
CPU box via Ollama:

- **Llama-class 8B (Llama 3.1 8B Instruct)** — the default name people
  reach for; tool calling works but its format adherence on
  multi-call conversations lagged Qwen-family models in 2025–26
  community evals, and its license is more encumbered than Apache.
- **Qwen3 8B** (chosen) — strongest small-model tool calling as of
  early 2026, Apache-2.0, native thinking mode, well-packaged in
  Ollama. 5.2 GB at q4, ~10 tok/s on this box.
- **Smaller (Qwen3 4B / Llama 3.2 3B)** — would sharpen the "how small
  can you go" question but pre-rehearsal expectations put them below
  the useful-demo floor on multi-step tasks; parked as a follow-up
  sweep, not the headline.
- **Bigger local (14B–32B)** — defeats the purpose: at CPU speeds the
  latency becomes hostile to a live demo, and "you need a GPU" is just
  the API trade-off with extra steps.

The result validated the middle pick in an unexpected direction: qwen3:8b's
*formatting* and single-call fidelity were flawless — the 2026 failure
line for small models runs through argument chaining (below), a distinction
a smaller/larger sweep can now measure precisely (parked experiment).

## The instructive failure

qwen3:8b scored 100% on every single-tool task — including exact
argument fidelity (user_id, k, platform all correct 21/21 times) and the
no-tool trap (answered a general-knowledge question without touching a
tool, all reps). Where it failed, it failed *deterministically and
invisibly*: the multi-step task ("find the movie most similar to 2571,
then explain the connection to it") had it correctly retrieve Inception
(79132) in step one, then call
`explain_connection(item_a=2571, item_b=589)` — an id appearing nowhere
in the conversation — and then write a fluent final answer describing
the Inception connection *as if that were the call it made*. Three reps,
temperature 0, same wrong call, same confident prose — and the identical
wrong call (item_b=589) reproduced again in a second full run after the
scorer hardening, so it is a stable property of this model on this task,
not a sampling accident.

Two lessons worth the stage time:

1. **Small-model tool use degrades at argument *chaining*, not argument
   *formatting*.** The failure isn't malformed JSON (the 2023 story);
   it's carrying a value from one tool result into the next call.
2. **The failure is invisible to prose-level evaluation.** The answer
   reads perfectly. Only scoring the actual tool arguments against the
   actual prior results catches it — which is why the suite scores
   behavior, and why "the demo looked right" is not evidence.

Haiku 4.5 passed the same chaining task 3/3 with the correct id
threaded through.

## Latency shape

API: 1.6 s (no-tool) to 7.9 s (the two-call multi-step task), network
included. Local: 2.3–13.2 s, dominated by generation at ~10 tok/s on 28
CPU cores (measured off-suite; no GPU on this box). Both are
conversational-demo speed; neither is interactive-product speed. The
composed multi-call tasks scale linearly with call count on both — the
retrieval itself (30–120 ms per MCP call, per the benchmark) is noise
against LLM generation time.

## Cost, from this box to a platform

- **This demo:** $0.12 per full API rehearsal vs $0 local. Irrelevant
  either way.
- **A workshop of 30 people re-running the suite:** ~$4 API vs $0 local
  + a 6.6 GB download each. Local wins on reproducibility-for-free;
  API wins on nobody-debugs-Ollama-on-conference-wifi.
- **Platform scale** (modeled, honestly labeled as such): at the
  benchmark's measured ~113 ms hybrid p50 (hydra, c=8), one box serves
  ~70 retrievals/s; the context layer on top costs per *agent turn*, not
  per retrieval. At Haiku pricing ($1/M in, $5/M out, 2026-08) a
  ~3.2k-in/380-out average task-turn costs ~$0.005 — $5 per thousand
  agent interactions, elastic, zero ops. Self-hosting an equivalent
  open model at real throughput means GPU serving (a single ~$2/hr GPU
  instance costs ~$1,440/month and so breaks even against the API around
  ~290k such turns/month, before engineering time) plus everything phase 06 taught about
  operating one more stateful engine. The knowledge-plane result
  transfers: composition costs latency and ops before it costs quality
  — the same trade, one layer up.

## Strengths and weaknesses

**API (Haiku 4.5).** Strengths: perfect fidelity including chaining;
zero install; cost noise at demo scale; the Anthropic-specific integration is ~70 lines.
Weaknesses: network dependency on stage (the one offline-story break in
the project); non-reproducible-for-free; model deprecation is someone
else's calendar (ADR 0012 revisit trigger).

**Local (qwen3:8b via Ollama).** Strengths: completes the
everything-on-this-box thesis; deterministic-ish at temperature 0; $0;
audience can reproduce exactly; single-tool fidelity turned out
excellent. Weaknesses: the chaining cliff (0.88 overall, and the miss
is the *interesting* kind of wrong); ~2× task latency; 6.6 GB + a
server process + a version pin (v0.32.5's release-asset rename already
bit us); reasoning arrives via Ollama's `message.thinking` field
(counted as thinking_chars; the inline `<think>`-tag strip is a second
guard for models that emit tags in content).

## Demo-day verdict (per ADR 0012's rehearsal trigger)

The local driver did NOT clear the ≥90% bar (0.88), so the API driver
carries the live demo, with the local model as the offline fallback and
— better — as exhibit A in the "what does model size cost you" segment:
run the multi-step task live on both, show the identical prose quality,
then show the scored tool trajectory. The confabulation is the content.

## Publication threads

This comparison is deliberately written as source material for talks and
posts, not just a phase record. The threads that stand alone:

1. **"The demo looked perfect. The tool call was for the wrong movie."**
   The chaining confabulation (L16): identical fluent prose over a wrong
   trajectory, invisible to every prose-level eval and every human
   watching a stage. Carries the argument for trajectory scoring on its
   own.
2. **"Small-model tool use in 2026: formatting is solved, chaining is
   not."** 21/21 exact-argument fidelity from an 8B model — then 0/3 the
   moment a value had to travel from one tool result into the next call.
   The malformed-JSON era is over; the failure moved up a level.
3. **"Debug your scorer before you accuse your model."** Two rounds of
   the scorer flagging perfect answers as hallucinations (article
   rewrites, ml-25m alternate-title parentheticals) before it earned the
   right to report the real failure. Rhymes with every phase of this
   project: the proof machinery fails before the system does (L7, L10,
   L13, the report's filename sort, now this).
4. **"Local vs API is not a religion, it's a table."** Fidelity, latency,
   dollars, ops surface, offline resilience — measured on one suite, and
   the honest answer is a hybrid: API on stage, local as fallback and
   exhibit. Generalizes to any team's build-vs-buy agent argument, with
   the ~290k turns/month GPU breakeven as the anchor number.
5. **"The context plane is consumer-agnostic."** Two wildly different
   models drove identical MCP tools over the identical service layer the
   benchmark measures — the same one-contract-many-engines thesis the
   storage layer proved, one layer up.

## Reproduction

`docs/runbooks/run-context-demo.md`. Suite:
`uv run python -m constellate.context.suite --driver {anthropic,local} --reps 3`.
Scoring code `src/constellate/context/suite.py`; scorer failure modes
found during rehearsal (title normalization vs ml-25m alternate titles)
are in the runbook and pinned by unit tests.
