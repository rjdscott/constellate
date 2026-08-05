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

- [ ] ADR: dual-driver context-plane demonstration (Anthropic + local; model picks; what is and is not a citable claim)
- [ ] Driver adapter: one interface, `anthropic` and `local` (OpenAI-compatible or Ollama) implementations; MCP tool-use loop shared
- [ ] Task suite: fixed context-plane tasks (recommend, explain-connection, multi-step) with deterministic scoring of tool-call fidelity
- [ ] Comparison runs: both drivers over the suite; latency + token cost + fidelity captured to a committed artifact
- [ ] Research doc: implementation notes, performance, strengths/weaknesses, cost model from small (this box) to large scale
- [ ] Runbook: run the context-plane demo (both drivers), offline fallback story for the talk

## Verification

```
make check
# suite runs both drivers end to end; artifact committed; docs indexed
```

## Artifacts

Driver adapter + suite code, committed comparison artifact, research doc in
`docs/research/`, ADR, runbook.

## Progress log
