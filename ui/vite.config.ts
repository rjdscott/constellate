import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Tailwind v4 is configured in CSS: the @theme block in src/design/tokens.css
// *is* the config. There is deliberately no tailwind.config file.
// `defineConfig` comes from vitest/config (a superset of vite's) so the
// `test` block below type-checks without a second config file.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // dev is same-origin like production (FastAPI serves dist/): /v1 proxies
    // to the local API, so VITE_API_BASE stays '' in both modes.
    proxy: { '/v1': 'http://localhost:8000' },
  },
  test: {
    environment: 'happy-dom',
  },
})
