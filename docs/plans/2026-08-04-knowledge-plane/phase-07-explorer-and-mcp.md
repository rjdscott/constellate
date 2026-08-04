# Phase 07 — Explorer app + MCP

*Amended 2026-08-04: requirements changed from no-build page to
production-grade SPA (ADR 0007 rewritten while still Proposed). This is now
the largest phase; tasks are ordered so the design system lands before any
feature component.*

## Goal

The productized face of the project (ADRs 0007, 0008): a Vite + React + TS
SPA (`ui/`) with a custom design system — dark-first tokens, Radix
primitives, Motion transitions — delivering four surfaces: (1) explanation
graphs that wow (Cytoscape.js: typed node styling, animated path
highlighting, click-to-expand, smooth zoom); (2) publication-quality
benchmark dashboards (Observable Plot: latency percentile curves, quality
deltas, ablation significance — screenshot-ready for slides/videos); (3) a
rich query playground (user/seed search pickers, policy controls, platform +
ablation toggles, side-by-side platform comparison); (4) product polish
(loading/empty/error states, keyboard nav, both themes). Plus the MCP
server: FastMCP v3 stdio, three tools over the shared service layer. The
SPA consumes a configurable API base URL or a static results snapshot —
EKS-ready artifact, EKS itself deferred.

## Tasks

- [x] PR A — API foundation (ADR 0011): lazy platform registry + `platform`
  param + `/v1/platforms`, `/v1/search/items`, `/v1/users/{id}`,
  `/v1/bench-results`, structured `path` on `Recommendation`, CORS for Vite
- [x] `ui/` scaffold: Vite + React + TS + pnpm; Tailwind v4; CI job builds `dist/`
- [x] Design tokens FIRST: color system (both themes, accessible chart palette validated per dataviz method), type scale, spacing, elevation; documented in `ui/src/design/README.md`
- [x] App shell: navigation, theme toggle, layout grid, state (TanStack Query), API client with base-URL/snapshot-mode config
- [ ] Explanation graph view: Cytoscape.js wrapper component, typed nodes (user/movie/tag/genre), hierarchical layout, animated path highlight, expand-on-click via `/v1/explain`
- [ ] Playground: query builder (searchable pickers backed by `/v1/*`), platform/ablation toggles, side-by-side comparison panes, per-step timing readout
- [ ] Benchmark dashboards: Observable Plot components fed from `/v1/bench-results` (serves committed `bench/results/*.json`); latency percentiles, quality bars with significance, ablation delta view
- [ ] Polish pass: motion choreography, states, keyboard nav, responsive check
- [ ] FastAPI serves `ui/dist/` locally; snapshot-mode build verified (no API)
- [ ] `src/constellate/mcp_server.py`: 3 tools, agent-oriented docstrings; `.mcp.json`; driven from Claude Code against Lyra + Hydra

## Verification

```
cd ui && pnpm build && pnpm lint && pnpm typecheck
uv run uvicorn constellate.api.app:app     # full app at localhost:8000: playground, graphs, dashboards, both themes
UI_MODE=snapshot pnpm build       # dashboard-only build renders with no API
uv run python -m constellate.mcp_server --selftest
make check
```

## Artifacts

`ui/` project with `design/README.md` (tokens documented), built `dist/`,
`src/constellate/mcp_server.py`, `.mcp.json`, screen recordings/screenshots for talk +
content in `docs/research/2026-08-04-knowledge-plane-foundations/assets/`.

## Progress log

- 2026-08-05 — Phase opened. Delivery split into five PRs (largest phase;
  one logical change each): A api-foundation, B ui-scaffold+tokens+shell,
  C playground+graph, D dashboards+polish+snapshot, E mcp. Design
  direction set with Rob: **Observatory** identity — celestial dark-first,
  restrained/instrument-grade ("excellence not gimmicky"), explanation
  graphs styled as constellations; entry surface = cinematic overview
  (constellation map of the three platforms, live health, headline
  numbers). ADR 0011 accepted: one API process, lazy platform registry,
  `platform` param on retrieval routes, `/v1/platforms` — side-by-side
  comparison needs it; bench harness stays the only citable latency
  source. API gaps identified for PR A: `/v1/search` (pickers),
  `/v1/bench-results` (dashboards), structured `path` on Recommendation
  (graph view renders typed nodes, not prose reasons).
- 2026-08-05 — PR A landed. `create_app` holds a lazy per-platform registry
  (valid platforms = `config/*.yaml`, discovered not hardcoded); unknown
  platform → 404, build failure → 503 and never cached, lifespan closes
  every warmed service. Verified all three platforms alive in one process
  (`/v1/platforms`) with the orion + hydra containers up. New:
  `/v1/search/items` (relational `search_items` on the plane contract,
  literal substring via `contains`/`strpos` — a typed `%` is a character,
  not a wildcard; popularity DESC), `/v1/users/{id}` (404 when the user has
  no ratings), `/v1/bench-results[/{name}]` (directory listing is also the
  traversal guard; artifacts keep their own `utc` timestamp key).
  `Recommendation.path` now carries the unrendered path alongside `reason`
  under `explain=true`; bench artifacts are unaffected (the harness never
  serializes recommendations). Conformance gained two relational
  `search_items` cases (duckdb + postgres).
- 2026-08-05 — PR B landed: scaffold (Vite 8 + React 19 + TS strict + pnpm,
  Tailwind v4 CSS-first, oxlint), tokens + design README, shell (rail,
  theme toggle, route transitions), overview, CI ui job. Three rounds of
  design direction from Rob reshaped it (lesson L12): the first
  agent-built pass was structurally sound but visually generic
  ("vibecoded") — replaced with a full-bleed star-atlas overview
  (magnitude-weighted starfield + aurora wash, chart-marker stars,
  labels beside stars); bare stat cards replaced with a **live proof
  strip** — same graph-arm query fired at all three platforms, identical
  top-3 rendered side by side with per-platform latency (honest:
  graph-arm results are byte-identical, verified live before building);
  Fraunces serif retired (Inter-only, medium-weight display); em-dashes
  and prose stripped from copy. Taste rules 5–7 added to
  ui/src/design/README.md. Vite dev now proxies /v1 → :8000 (same-origin
  in dev and prod). Incidents: worker found `.gitignore`'s unanchored
  `lib/` silently hiding ui/src/lib (anchored); Radix asChild
  string-merges className, stringifying NavLink's function prop (active
  state moved to useLocation).
- 2026-08-05 — PR B landed: `ui/` scaffold + Observatory tokens wired + app
  shell + the overview page. Vite 8 / React 19 / TS 6 strict / pnpm 9;
  Tailwind v4 is configured CSS-first — the authored `@theme inline` block in
  `src/design/tokens.css` *is* the config, no `tailwind.config` file. Token
  layering works because `tokens.css` is imported unlayered after
  `@import 'tailwindcss'`: its `:root` / `[data-theme=light]` hex values beat
  the self-referential copies Tailwind emits into `@layer theme`, so utilities
  resolve per theme. One fetch layer (`src/lib/api.ts`) with `VITE_API_BASE` +
  `VITE_UI_MODE`; snapshot mode maps a GET path to `/snapshot/<path>.json` and
  makes retrieval POSTs throw a typed `SnapshotModeError` (the snapshot JSON
  artifacts themselves are PR D's job). Shell: 220/64px collapsible rail
  (localStorage), Radix tooltips only on the collapsed rail, theme toggle with
  a pre-paint script in `index.html` so there is no flash of the wrong sky,
  route transitions via Motion with the duration *read from the CSS token* —
  `prefers-reduced-motion` already zeroes it, so the JS never hardcodes ms.
  Overview: seeded static starfield (canvas, 180 stars, ≤6% opacity, dark
  theme only, drawn once per resize), SVG constellation of the three
  platforms with live `/v1/platforms` liveness (pulse-once dot + config
  fingerprint, hollow + "unreachable" when dead), thesis line and three stat
  cards quoting the committed bench artifacts. Fonts self-hosted via
  fontsource — `dist/` contains no runtime external URL. CI gained an
  independent `ui` job (pnpm 9 / node 20 / lint + typecheck + build).
  *Incident:* every rail item rendered gold — Radix `Trigger asChild`
  string-merges `className`, so NavLink's `className={({isActive}) => …}`
  function was stringified onto the element (and Tailwind matched
  `text-accent` inside the stringified source). Fixed by computing the active
  state from `useLocation` and passing a plain string; the rule is that no
  `asChild` child may take a function prop that Radix composes.
  *Second incident:* the python `.gitignore`'s unanchored `lib/` silently
  swallowed `ui/src/lib/` — the whole API client would have been missing from
  the PR. Both `lib/` and `lib64/` are now root-anchored.
