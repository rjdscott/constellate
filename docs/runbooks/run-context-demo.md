# Run the context-plane demo (LLM drivers over MCP)

Both drivers (ADR 0012) run the same fixed task suite against the MCP
tools over the shared service layer, score tool-call fidelity
deterministically, and write a demo-class artifact to `bench/context/`
(never `bench/results/` — these numbers are not benchmark-citable).

## When to use

Rehearsing or presenting the context-plane demo; regenerating the
local-vs-API comparison artifact after a model or suite change.

## Steps

1. Dependencies (once per checkout — note `uv sync` replaces the extras
   set, so name every extra you need):

   ```sh
   uv sync --extra context            # add --extra neural if you also need fastembed
   ```

2. API driver — needs `ANTHROPIC_API_KEY` in gitignored `.env`
   (`ANTHROPIC_API_KEY=sk-...`; never commit or echo it):

   ```sh
   uv run python -m constellate.context.suite --driver anthropic --reps 3
   ```

   Expected: a per-task fidelity table, then
   `overall fidelity=… tokens(in/out)=… est_cost_usd=…` and an artifact
   path. A full 3-rep run costs ≈ $0.12 at Haiku 4.5 pricing.

3. Local driver — needs Ollama serving and the model pulled. User-space
   install, no root:

   ```sh
   # once: install + model (~1.4 GB tarball + 5.2 GB model)
   curl -sL -o /tmp/ollama.tar.zst \
     https://github.com/ollama/ollama/releases/download/v0.32.5/ollama-linux-amd64.tar.zst
   mkdir -p ~/.local/share/ollama && tar --zstd -xf /tmp/ollama.tar.zst -C ~/.local/share/ollama
   ~/.local/share/ollama/bin/ollama serve &   # listens on 127.0.0.1:11434
   ~/.local/share/ollama/bin/ollama pull qwen3:8b

   uv run python -m constellate.context.suite --driver local --reps 3
   ```

   Expected: same table, much slower (~10 tok/s on the 28-core box;
   qwen3's thinking (returned via Ollama's message.thinking field, counted in the artifact's thinking_chars) inflates wall time per task). `est_cost_usd=0`.

4. Cross-platform task needs hydra up (`make up PLATFORM=hydra`); lyra
   needs seeded canonical data + `make load PLATFORM=lyra`. If a platform
   is down its tasks fail loudly in the transcript — the suite does not
   pre-check engine health.

## Failure modes

- **Ollama `.tgz` release URL 404s** — as of v0.32.5 the Linux assets are
  `.tar.zst` (`ollama-linux-amd64.tar.zst`); the widely documented
  `ollama-linux-amd64.tgz` name is gone. Hit 2026-08-05.
- **Grounding scored 0 for answers that are obviously correct** — the
  scorer matches normalized titles (articles folded, ALL parentheticals
  stripped). ml-25m titles embed original-language alternates
  ("…, The (Scaphandre et le papillon, Le) (2007)") and models freely
  rewrite "X, The" as "The X"; both bit on 2026-08-05 and are handled in
  `_title_key`. A new zero-fidelity-across-all-reps pattern on a task
  that transcripts show succeeding = suspect the scorer first, the model
  second.
- **`uv sync --extra context` silently uninstalled fastembed** — extras
  are a set, not additive across invocations. Name all extras every sync.
  Hit 2026-08-05.
- **Suite hangs at first local task** — model is cold-loading into RAM
  (~5 GB); first request after `ollama serve` takes ~30 s extra. Warm it
  with a trivial prompt before a timed rehearsal.

## Last verified

2026-08-05 — phase 09: anthropic driver fidelity 1.00 (3 reps, $0.12);
local qwen3:8b fidelity 0.88 (3 reps, $0; multi-step chaining 0/3, see
research doc 13).
