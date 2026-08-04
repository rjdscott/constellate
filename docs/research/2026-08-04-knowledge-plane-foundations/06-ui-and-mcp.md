# 06 — Explorer UI + MCP server stack (researched 2026-08-04)

Question: stack for (A) full explorer web UI — query any tier, ranked results,
interactive graph viz of traversal paths, cross-tier benchmark charts; (B) MCP
server exposing the same operations as agent tools.

## 1. Graph viz for explanation subgraphs

State of play (2026):

- **Cytoscape.js** — actively maintained, top-tier popularity, "richest
  all-in-one graph toolkit… when algorithms and layouts are part of the
  product" ([PkgPulse 2026 guide](https://www.pkgpulse.com/guides/cytoscape-vs-vis-network-vs-sigma-graph-visualization-2026)).
  First-class styling selectors, built-in layouts, works as a single
  `<script>` tag from CDN — no build step needed.
- **sigma.js** — WebGL renderer paired with graphology; strength is *large*
  graphs (10k+ nodes) and typed data pipelines. Overkill for tens of nodes;
  more assembly required ([PkgPulse](https://www.pkgpulse.com/blog/cytoscape-vs-vis-network-vs-sigma-graph-visualization-javascript-2026)).
- **react-force-graph** (vasturiano) — alive: v1.29.x Feb 2026, active issues
  through March 2026 ([releases](https://github.com/vasturiano/react-force-graph/releases)).
  React-only wrapper; underlying [force-graph](https://github.com/vasturiano/force-graph)
  (plain canvas) works framework-free via CDN.
- **d3-force** — a physics engine, not a graph component. Hand-write
  rendering, drag, zoom, labels. Not worth it when the above exist.

**Recommendation: Cytoscape.js.** For a small "why was X recommended" path
graph (user → rated → movie → shared-tag → movie), you want per-node-type
styling, edge labels, and a deterministic hierarchical layout — Cytoscape's
stylesheet + layout model does exactly this in ~30 lines. Force-directed
jiggle actually *hurts* readability of explanation paths. If React is used
anyway, still Cytoscape.js directly in a `useEffect` — the react-cytoscapejs
wrapper is stale, skip it.

## 2. Frontend approach

2026 sentiment has swung hard toward no-build for small/internal tools —
htmx/Alpine rebuilds cut CRUD dashboards by 40–60% of frontend code; consensus
split is "htmx/Alpine for server-touching internal tools, React for genuinely
complex client state" ([htmx in 2026](https://dev.to/pockit_tools/htmx-in-2026-when-you-dont-need-react-and-when-you-absolutely-do-2mf4),
[FastAPI + HTMX](https://blakecrosley.com/guides/fastapi-htmx),
[PkgPulse htmx vs React](https://www.pkgpulse.com/blog/htmx-vs-react-2026)).

**Recommendation: no-build.** One `static/index.html` served by FastAPI
`StaticFiles`, **Alpine.js for UI state + plain `fetch`** against the JSON
API, Cytoscape.js + Chart.js vendored locally into `static/vendor/` (a
conference demo must not depend on CDN wifi). htmx is the *wrong* tool here:
it swaps server-rendered HTML fragments, but these payloads are JSON feeding
two JS canvases — plain fetch + Alpine is the honest fit. Zero build step,
zero node_modules. A Vite+React+TS SPA adds a toolchain, second package
ecosystem, and build pipeline to render three panels — take it only if the UI
is expected to outlive the demo and grow real product surface.

## 3. Charts

- **Chart.js** — ~60KB, simplest API, best docs, canvas, framework-free
  ([JS charting guide 2026](https://lalatenduswain.medium.com/the-complete-guide-to-javascript-charting-libraries-in-2026-choosing-the-right-visualization-tool-dac9aeb15f60)).
- **Observable Plot** — lovely grammar, 200–300KB, shines in
  exploratory/notebook contexts ([LogRocket 2026](https://blog.logrocket.com/best-react-chart-libraries-2026/)).
- **Recharts** — still the React-dashboard default, but React-only.

**Recommendation: Chart.js.** Grouped bars of p50/p95 latency and quality
metrics per tier is its bread and butter; smallest bundle, script tag,
matches the no-build choice.

## 4. MCP server in Python

- **Standalone FastMCP** (jlowin/PrefectHQ) hit **stable v3.0 in Feb 2026**,
  de-facto community standard — lowest-boilerplate decorator API, plus
  auth/proxying/composition ([FastMCP](https://gofastmcp.com/getting-started/welcome),
  [comparison](https://mcp.directory/blog/fastmcp-vs-fastapi-mcp-vs-python-sdk-2026)).
  Distinct project from FastMCP 1.x bundled in the official SDK.
- **Official `mcp` SDK** shipped a **v2** rework (FastMCP 1.x renamed
  `MCPServer`, supports the 2026-07-28 spec); v1.x maintenance-mode
  ([python-sdk releases](https://github.com/modelcontextprotocol/python-sdk/releases)).
- **fastapi-mcp bridge** (tadata-org): effectively stale — last release
  v0.4.0, July 2025. Avoid ([repo](https://github.com/tadata-org/fastapi_mcp)).
- **Auto-conversion caveat:** FastMCP's own docs say `FastMCP.from_fastapi()`
  auto-converted servers underperform curated ones — "for bootstrapping and
  prototyping" ([FastMCP FastAPI integration](https://gofastmcp.com/integrations/fastapi)).
- **Transports:** SSE deprecated; Streamable HTTP is the remote default;
  **stdio remains recommended for local servers with Claude Code**
  ([Claude Code MCP docs](https://code.claude.com/docs/en/mcp)).

**Recommendation: standalone FastMCP (v3), hand-written tools, stdio.** Don't
bridge HTTP-to-MCP — we own the code: put recommend/similar/explain in a
shared service layer and write ~3 `@mcp.tool` functions (agent-oriented
docstrings) calling it directly, same functions the FastAPI routes call. Less
machinery than `from_fastapi` *and* better tool descriptions. stdio for
Claude Code; FastMCP flips to Streamable HTTP with one argument later.

## Summary

| Item | Pick | Runner-up (when) |
|---|---|---|
| Graph viz | Cytoscape.js (vendored, hierarchical layout) | react-force-graph (only if React SPA) |
| Frontend | No-build: single static HTML + Alpine + fetch via FastAPI | Vite+React+TS (if UI outlives demo) |
| Charts | Chart.js (~60KB, script tag) | Recharts (if React) |
| MCP | FastMCP v3, hand-written tools over shared service layer, stdio | Official `mcp` SDK v2 (if official-only policy) |

## Addendum 2026-08-04 (same day, post-research)

Requirements changed after this research completed: UX elevated to
product-grade ("second to none"), the UI became a productization/content
asset, and a full live deployment (EKS) is planned post-analysis. This
flips the frontend recommendation to exactly this table's stated runner-up
condition ("if UI outlives demo") — the SPA path, with a custom design
system rather than stock component styling, and Observable Plot over
Chart.js for publication-grade statistical charts. Graph-viz and MCP picks
stand. Decision recorded in ADR 0007 (rewritten while Proposed).
