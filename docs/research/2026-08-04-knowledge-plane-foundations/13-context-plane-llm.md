# Context-plane LLM consumers: local vs API, measured

- **Date:** 2026-08-05
- **Question (ADR 0012):** what does it actually cost — in tool-call
  fidelity, latency, dollars, and operational surface — to prove the
  context plane with a local small model versus a frontier API, and what
  does each choice look like from this laptop up to a real platform?
- **Evidence:** `bench/context/anthropic-claude-haiku-4-5-20251001-20260805T064807Z.json`,
  `bench/context/local-qwen3-8b-20260805T065207Z.json` — one fixed
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
| mean task latency | 1.6–7.8 s | 2.9–15.2 s |
| tokens (in/out, full run) | 75.7k / 9.2k | 41.2k / 18.3k |
| cost, full 3-rep run | $0.12 | $0 |
| offline | no | yes |
| new ops surface | an env var | 6.6 GB install + a server process |

Both drivers speak to the identical MCP tools over the identical service
layer — the context plane is provably consumer-agnostic, which was the
point of the demonstration.

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
temperature 0, same wrong call, same confident prose.

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

API: 1.6 s (no-tool) to 7.8 s (two sequential tool calls), network
included. Local: 2.9–15.2 s, dominated by generation at ~10 tok/s on 28
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
  instance breaks even against the API around ~400k such turns/month,
  before engineering time) plus everything phase 06 taught about
  operating one more stateful engine. The knowledge-plane result
  transfers: composition costs latency and ops before it costs quality
  — the same trade, one layer up.

## Strengths and weaknesses

**API (Haiku 4.5).** Strengths: perfect fidelity including chaining;
zero install; cost noise at demo scale; the integration is ~100 lines.
Weaknesses: network dependency on stage (the one offline-story break in
the project); non-reproducible-for-free; model deprecation is someone
else's calendar (ADR 0012 revisit trigger).

**Local (qwen3:8b via Ollama).** Strengths: completes the
everything-on-this-box thesis; deterministic-ish at temperature 0; $0;
audience can reproduce exactly; single-tool fidelity turned out
excellent. Weaknesses: the chaining cliff (0.88 overall, and the miss
is the *interesting* kind of wrong); ~2× task latency; 6.6 GB + a
server process + a version pin (v0.32.5's release-asset rename already
bit us); thinking-mode output needs stripping before scoring.

## Demo-day verdict (per ADR 0012's rehearsal trigger)

The local driver did NOT clear the ≥90% bar (0.88), so the API driver
carries the live demo, with the local model as the offline fallback and
— better — as exhibit A in the "what does model size cost you" segment:
run the multi-step task live on both, show the identical prose quality,
then show the scored tool trajectory. The confabulation is the content.

## Reproduction

`docs/runbooks/run-context-demo.md`. Suite:
`uv run python -m constellate.context.suite --driver {anthropic,local} --reps 3`.
Scoring code `src/constellate/context/suite.py`; scorer failure modes
found during rehearsal (title normalization vs ml-25m alternate titles)
are in the runbook and pinned by unit tests.
