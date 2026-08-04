# 0008 — MCP server: standalone FastMCP v3 with hand-written tools over a shared service layer

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob Scott, Claude

## Context

The architecture is agent-facing: "MCP tool or REST" at the top of the
diagram. The user chose REST-first with an early MCP wrapper (not deferred
to Eridanus, the future distributed knowledge plane). The MCP ecosystem moved in 2026: standalone FastMCP
hit stable v3.0 (Feb 2026); the official `mcp` SDK shipped a v2 rework; the
fastapi-mcp bridge is stale (last release Jul 2025); SSE transport is
deprecated; stdio remains the recommended local transport for Claude Code.

## Options considered

### Option A — auto-bridge the FastAPI app (`FastMCP.from_fastapi()` / fastapi-mcp)
- Pros: near-zero code.
- Cons: FastMCP's own docs say auto-converted servers underperform curated
  ones; fastapi-mcp is stale; tool descriptions come out REST-shaped, not
  agent-shaped.

### Option B — official `mcp` SDK v2
- Pros: officially backed, boring dependency.
- Cons: more boilerplate than FastMCP v3 for the same three tools.

### Option C — standalone FastMCP v3, hand-written tools, stdio
- Pros: recommend/similar/explain live in one shared service layer; the
  FastAPI routes and ~3 `@mcp.tool` functions both call it — no bridging
  machinery, and each tool gets an agent-oriented docstring; stdio works
  with Claude Code today; one argument flips to Streamable HTTP later.
- Cons: community project (though de-facto standard); a second entrypoint to
  maintain.

## Decision

**We will expose the retrieval operations via standalone FastMCP v3 with
hand-written tools calling the same service layer as the REST routes, over
stdio — because we own the code, so curated tools cost less than bridge
machinery and produce better agent-facing descriptions.** Scope: local agent
access; remote transport deferred until a remote client exists.

## Consequences

- Easier: agent testing from Claude Code against every platform; tool docs
  written for agents, not OpenAPI.
- Harder: service layer must stay the single home of business logic (routes
  and tools both stay thin) — a discipline, enforced by review.
- **Revisit trigger:** an "official-only dependencies" policy, or FastMCP v3
  breaking-changes churn exceeding one adaptation per quarter.

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/06-ui-and-mcp.md`
