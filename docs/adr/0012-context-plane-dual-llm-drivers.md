# 0012: Context plane demonstration: dual LLM drivers, local and API, behind one adapter

- **Status:** Accepted
- **Date:** 2026-08-05
- **Deciders:** Rob Scott, Claude

## Context

Phases 01–08 proved the knowledge plane: one retrieval contract, three
platforms, measured. The MCP server (ADR 0008) exposes it to agents, but
"an agent could use this" is asserted, not demonstrated: the context
plane needs a real LLM consumer driving the MCP tools end to end. The
project is educational and ends in a conference talk from this machine
(28 cores / 62 GB, no discrete GPU), where venue connectivity is
untrusted; the whole stack so far runs offline by design. LLM output is
non-deterministic, so whatever is measured here must not blur into the
benchmark harness's citable results (ADR 0011 discipline). Cost matters
at two scales: this demo (cents) and the honest story about what each
choice costs at platform scale.

## Options considered

### Option A: Anthropic API only (Haiku-class)
- Pros: best tool-calling reliability per dollar; zero local ops; fastest
  to build against.
- Cons: breaks the offline-demo property for the only time in the
  project; audience cannot reproduce for free; "we called a frontier
  API" is a thin finding.

### Option B: local small model only (Ollama-class, CPU)
- Pros: completes the everything-on-this-box thesis; free, reproducible,
  wifi-proof.
- Cons: small-model tool-calling is the weak link: the demo's failure
  mode becomes the model, not the platform; CPU latency is watchable,
  not snappy; one more moving part.

### Option C: both, behind one driver adapter, compared as content
- Pros: the comparison is itself the deliverable: implementation,
  fidelity, latency, cost, small-to-large-scale trade-offs measured on
  fixed tasks; mirrors the project's own pattern (one contract, multiple
  engines); demo day picks whichever rehearses better with the other as
  fallback.
- Cons: two integrations; a fixed task suite with deterministic scoring
  must be built for the comparison to mean anything.

## Decision

**We will build both drivers behind one adapter interface, Anthropic
API (`claude-haiku-4-5-20251001`) and a local model
(Qwen3 8B via user-space Ollama, CPU-only), driving the existing MCP
tools through the in-process FastMCP client, scored on a fixed task
suite, because the local-vs-API comparison is the educational payload
and either driver alone tells half the story.** Scope: demonstration
and comparison only. Fidelity/latency/cost numbers are labeled
demo-class, never citable alongside the benchmark harness; artifacts
live in `bench/context/`, deliberately outside `bench/results/` so the
benchmark report never ingests them. The API key lives in gitignored
`.env`, read at runtime, never logged or committed.

## Consequences

- Easier: demo day has a rehearsal-based choice plus a fallback; the
  talk gains a measured "what does model size cost you in tool
  fidelity" segment; MCP layer gets exercised by real consumers, not
  just its selftest.
- Harder: task-suite scoring must be deterministic against
  non-deterministic actors (score tool-call behavior, not prose);
  Ollama becomes a documented, versioned dependency of the demo (not of
  the benchmark).
- Committed: anthropic SDK + python-dotenv behind a `context` extra
  (core stays ML- and network-free); qwen3:8b (~5 GB) on this box.
- Risked: local tool-calling may prove too unreliable to demo; that
  result is reported, not hidden, and the API driver carries the live
  demo.
- **Revisit trigger:** a demo rehearsal where the local driver completes
  the suite at ≥90% fidelity (drop the API dependency from the talk), or
  Anthropic model deprecation forcing a model bump, or phase-09 findings
  showing neither driver fit for stage use.

## Related

- ADRs: [0008](0008-mcp-fastmcp-shared-service-layer.md) (MCP surface),
  [0011](0011-multi-platform-api-single-process.md) (citability
  discipline), [0006](0006-dual-embedding-ablation-genome-svd-plus-bge.md)
  (the dual-arm pattern this mirrors)
- Plan: `docs/plans/2026-08-04-knowledge-plane/phase-09-context-plane-llm.md`
- Decision conversation: 2026-08-05 (local-vs-API pros/cons, user chose both)
