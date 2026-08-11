# 0011: Explorer API: one process serving all platforms via a platform registry

- **Status:** Accepted
- **Date:** 2026-08-05
- **Deciders:** Rob Scott, Claude

## Context

The explorer's playground promises side-by-side platform comparison (ADR
0007): one query, answered by Lyra, Orion, and Hydra at once, differences
visible. Today the API process binds to exactly one platform at startup
(`$PLATFORM`, default lyra): a comparison UI has nothing to compare
against. All engines already run simultaneously on this machine by design
(per-platform compose projects, offset ports), so the constraint is purely
the API's process model. Whatever shape is chosen also becomes the MCP
server's shape (ADR 0008: both are thin layers over the same service) and
the eventual EKS deployment's ingress shape. A second force: the benchmark
harness is the project's source of truth for latency; the API must not
become a second, subtly-different latency oracle.

## Options considered

### Option A: one process, platform registry, `platform` parameter
Factory builds a `Service` per requested platform, cached in an in-process
registry; routes accept an optional `platform` (default `$PLATFORM`);
lazy-init on first use so unreachable platforms cost nothing until asked
for; `/v1/platforms` reports which are configured and alive.
- Pros: one origin for the UI (no CORS matrix, one base URL in config); the
  MCP tools get a `platform` argument for free; one uvicorn to run locally
  and one container later; comparison requests fan out server-side.
- Cons: platforms share one event loop, so side-by-side latencies are
  illustrative, not benchmark-grade; one process holds connections to
  every engine (three pools + qdrant + two bolt drivers when all warm).

### Option B: one process per platform, UI multiplexes three base URLs
- Pros: honest isolation (no shared-loop contention); matches "three
  services on EKS" literally.
- Cons: three uvicorns to babysit locally; CORS + three-URL config in the
  UI; MCP would need three server entries or an aggregator anyway; the
  playground's fan-out logic moves into the browser.

### Option C: gateway in front of per-platform processes
- Pros: Option B's isolation with Option A's single origin.
- Cons: a reverse proxy and N+1 processes for a local demo tool; the
  gateway is pure ceremony until EKS exists.

## Decision

**We will serve all platforms from one API process holding a lazy platform
registry, with an optional `platform` parameter on retrieval routes
(defaulting to `$PLATFORM`) and a `/v1/platforms` liveness listing:
because every consumer (SPA, MCP, future ingress) wants one origin, and the
per-process isolation Option B buys is only needed for numbers the
benchmark harness already owns.** Scope: the explorer/MCP serving path;
the bench harness keeps building services directly and remains the only
citable latency source. Playground timing readouts are labeled as
illustrative.

## Consequences

- Easier: side-by-side comparison, one-URL UI config, MCP platform
  argument, local ops (one `uvicorn`).
- Harder: `close()` must tear down every warmed service; a platform whose
  engines are down must degrade to a clear per-platform error, not take the
  process down.
- Committed: API latency numbers are never quoted as benchmark results;
  the harness (open-loop, direct service) stays the truth source.
- Risked: shared-loop contention distorting side-by-side impressions
  during demos. Mitigated by sequential-by-default comparison fan-out and
  the illustrative label.
- **Revisit trigger:** EKS deployment planning starts, or a remote MCP
  client needs per-platform scaling: re-evaluate Option C's gateway shape
  then.

## Related

- ADRs: [0007](0007-explorer-ui-react-spa-design-system.md),
  [0008](0008-mcp-fastmcp-shared-service-layer.md)
- Research: `docs/research/2026-08-04-knowledge-plane-foundations/06-ui-and-mcp.md`
