# Phase 09 — Context plane: LLM consumers, local vs API

## Goal

Prove the context plane with real LLM consumers and turn the comparison into
educational content. Two drivers behind one adapter interface: Anthropic API
(Haiku-class model) and a local small model (Ollama-class, CPU-only on this
machine), both driving the existing MCP tools over the shared service layer.
A fixed task suite measures tool-call fidelity, latency, and cost per driver;
the write-up covers implementation, performance, strengths and weaknesses,
and cost from a laptop demo to a large-scale platform. Decision to build both
arms was made 2026-08-05 (conversation); the driver architecture and model
picks get an ADR when this phase opens. Scope amendment approved 2026-08-05;
executes after phase 08 so the report in 07-findings.md stays the benchmark's
citable close and this phase's write-up stands alone.

## Tasks

- [x] ADR: dual-driver context-plane demonstration (Anthropic + local; model picks; what is and is not a citable claim) — [0012](../../adr/0012-context-plane-dual-llm-drivers.md)
- [x] Driver adapter: one interface, `anthropic` and `local` (OpenAI-compatible or Ollama) implementations; MCP tool-use loop shared
- [x] Task suite: fixed context-plane tasks (recommend, explain-connection, multi-step) with deterministic scoring of tool-call fidelity
- [x] Comparison runs: both drivers over the suite; latency + token cost + fidelity captured to a committed artifact
- [x] Research doc: implementation notes, performance, strengths/weaknesses, cost model from small (this box) to large scale
- [x] Runbook: run the context-plane demo (both drivers), offline fallback story for the talk

## Verification

```
make check
# suite runs both drivers end to end; artifact committed; docs indexed
```

## Artifacts

Driver adapter + suite code, committed comparison artifact, research doc in
`docs/research/`, ADR, runbook.

## Progress log

- 2026-08-05 — Phase opened on `feat/context-plane-llm`. ADR 0012 Accepted
  (dual drivers: Anthropic `claude-haiku-4-5-20251001` + local Qwen3 8B via
  user-space Ollama; artifacts in `bench/context/`, outside the benchmark
  report's glob on purpose — demo-class numbers, never citable). API key in
  gitignored `.env` (verified ignored before the key landed). Ollama
  install detour: the documented `.tgz` release asset 404s as of v0.32.5
  (assets moved to `.tar.zst`); installing from the zst tarball,
  user-space, no root.

- 2026-08-05 — Built and rehearsed end to end. `constellate/context/`:
  neutral Driver protocol, Anthropic + Ollama drivers, agent loop over the
  in-process FastMCP client, 8-task suite, deterministic tool-behavior
  scoring, artifacts in `bench/context/`. Live rehearsal found two scorer
  bugs before any model bug (title normalization vs "X, The" rewrites and
  ml-25m alternate-title parentheticals — both unit-pinned now). Results:
  Haiku 4.5 fidelity 1.00 ($0.12/run); qwen3:8b 0.88 — perfect on all
  single-tool tasks, 0/3 on multi-step chaining, where it fetched the
  right answer then called explain_connection with an id from nowhere and
  confabulated fluent prose about the *right* movie over the *wrong*
  call. ADR 0012's ≥90% rehearsal bar not met: API carries the live demo,
  local is the offline fallback + the teaching exhibit. Research doc 13,
  runbook run-context-demo. Next: review round, gate.
