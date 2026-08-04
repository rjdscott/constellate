# Run the explorer (SPA + API + MCP)

## When to use

Serving the explorer UI (overview, playground, bench dashboards) locally,
building the static snapshot for API-less hosting, or wiring the MCP server
into an agent session.

## Steps

1. Engines up for whichever platforms should show alive (lyra needs only its
   local artifacts):

   ```sh
   make up PLATFORM=orion && make up PLATFORM=hydra
   ```

2. Dev loop (hot reload; Vite proxies `/v1` to :8000, so dev is same-origin
   like production):

   ```sh
   uv run uvicorn constellate.api.app:app --port 8000
   cd ui && pnpm install && pnpm dev        # http://localhost:5173
   ```

3. Production shape (FastAPI serves the built SPA at :8000):

   ```sh
   cd ui && pnpm build && cd ..
   uv run uvicorn constellate.api.app:app --port 8000
   ```

   Expected: `/`, `/playground`, `/bench` return the app; `/v1/platforms`
   lists all three platforms `alive: true`; a platform whose engines are
   down shows `alive: false` and its requests 503 without affecting the
   others (health is a real per-plane probe on every call, not a cached
   build result).

4. Static snapshot (dashboards + overview from committed artifacts alone,
   no API — the public-showcase artifact):

   ```sh
   make ui-snapshot
   cd ui && VITE_UI_MODE=snapshot pnpm build
   python3 -m http.server -d dist 8080      # or any static host
   ```

   Expected: `/bench` fully functional from `public/snapshot/*.json`;
   playground renders its "requires a live API" state.

5. MCP server (stdio; `.mcp.json` at repo root wires it into Claude Code):

   ```sh
   uv run python -m constellate.mcp_server --selftest lyra hydra
   ```

   Expected: 6/6 `ok` (three tools × two platforms) against live engines.

6. UI gates before any commit touching `ui/`:

   ```sh
   cd ui && pnpm lint && pnpm typecheck && pnpm test -- --run && pnpm build
   ```

## Failure modes

- **All platforms `offline` in the UI, engines demonstrably up.** The API
  process isn't running or the Vite proxy target is wrong — check
  `uvicorn` on :8000 and `ui/vite.config.ts` proxy. Hit 2026-08-05 (the
  uvicorn process had died silently; UI showed three hollow dots).
- **Vite dev serves a stale or near-empty stylesheet after branch
  switches.** Restart `pnpm dev`; the dev server caches Tailwind's
  CSS-first build across checkouts. Hit 2026-08-05.
- **Platform shows `alive: true` but requests fail.** Cannot happen since
  2026-08-05 (health() runs real per-plane point lookups and failures
  evict the cached service — adversarial-review fix); if seen, that
  regression class returned: check `Service.health()` still does I/O.
- **Port 5173 taken → Vite silently picks 5174.** Use
  `pnpm dev --port 5173 --strictPort` when the port matters. Hit
  2026-08-05.

## Last verified

2026-08-05 — phase 07 close: dev loop, production shape, snapshot build,
MCP selftest (lyra + hydra), all three platforms alive in one process.
