# 0007: Explorer UI: production-grade React SPA with a custom design system

- **Status:** Accepted
- **Date:** 2026-08-04 (rewritten same day after requirements changed; original
  no-build proposal preserved as Option C below)
- **Deciders:** Rob Scott, Claude

## Context

The explorer is no longer just a lens on the benchmark. Requirements set
2026-08-04: visualization and UX "second to none"; the UI is the productized
face of the project: conference demos, videos, content, public excitement;
a full live deployment (EKS) is planned after the analysis completes, so the
frontend must be built for the most demanding target now even though it runs
locally first. It must still not become a bog: the retrieval thesis remains
the project's core. Four surfaces are in scope: interactive explanation
graphs (the centerpiece), publication-quality benchmark dashboards, a rich
query playground with side-by-side platform comparison, and product-level polish
(design coherence, dark mode, states, motion).

## Options considered

### Option A: Vite + React + TS with a custom design system
Headless primitives (Radix), Tailwind v4 with bespoke design tokens (not the
stock shadcn look), Cytoscape.js for explanation graphs, Observable Plot for
statistical charts, Motion for transitions, TanStack Query for data.
- Pros: product-grade ceiling with a distinctive visual identity; builds to
  static files (FastAPI-served locally, S3/CloudFront or an nginx container
  on EKS later, same artifact); every piece is boring, well-trodden 2026
  standard practice; SPA keeps the API the single contract (same API the
  MCP tools use).
- Cons: a real frontend project (toolchain, node_modules); custom tokens
  cost design effort up front.

### Option B: Next.js
- Pros: SSR/SEO if the public site becomes a content property; one framework
  for landing + app.
- Cons: server runtime to operate (or awkward static export); SEO is for the
  eventual content site, not the app; a marketing page can be added beside
  the SPA later; heaviest option for a dashboard.

### Option C: no-build static page (Alpine + Cytoscape + Chart.js), the original proposal
- Pros: zero toolchain, one reviewable file, offline-trivial.
- Cons: polish ceiling is real: "fine for engineers" is exactly what this
  UI must no longer be; product feel, motion, component reuse, and
  side-by-side playground layouts all fight the pattern.

## Decision

**We will build the explorer as a Vite + React + TypeScript SPA with a
custom design system: Radix primitives + Tailwind v4 design tokens
(dark-first, light supported), Cytoscape.js for explanation subgraphs,
Observable Plot for benchmark statistics, Motion for choreographed
transitions, TanStack Query for data, because the UI is now a product
surface and content asset, and a static-building SPA is the only option that
reaches that ceiling while staying deployment-agnostic (local FastAPI today,
S3/CloudFront or EKS container later).** Design authorship: Claude, with
review iterations; chart color/form decisions follow a validated accessible
palette system in both themes. The UI consumes either a live API base URL or
a static results snapshot (same fetch layer) so the public-showcase door
stays open before EKS exists. Scope: this project's explorer; EKS deployment
itself stays deferred until the analysis completes.

## Consequences

- Easier: product-level polish, videos/screenshots straight from the app,
  side-by-side playground layouts, future hosting in any mode.
- Harder: a second toolchain in the repo (`ui/`, pnpm, CI build step);
  design tokens must be defined before the first component lands, not after.
- Committed: UI talks only to the public API: no backdoor coupling to
  engine internals; API responses must carry everything the explanations
  render (typed nodes/edges, timings).
- Risked: frontend scope creep. Contained by phase gating: playground +
  explanation graphs + dashboards are in scope; anything beyond needs a plan
  amendment.
- **Revisit trigger:** a public content site with SEO needs goes live:
  re-evaluate Next.js for the marketing/writeup shell around the SPA (not
  as a rewrite).

## Related

- Research: `docs/research/2026-08-04-knowledge-plane-foundations/06-ui-and-mcp.md`
  (graph-viz comparison stands: Cytoscape.js remains the pick; the
  no-build-vs-SPA recommendation is overridden by the requirements change
  recorded here)
- ADRs: [0008](0008-mcp-fastmcp-shared-service-layer.md)
