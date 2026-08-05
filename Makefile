PLATFORM ?= lyra
ARM ?= svd

# host dirs each platform's compose file bind-mounts (see compose/*.yml) — only
# these, or `make up` litters an unused one under every other platform
BIND_DIRS_orion = data/orion/age-import
BIND_DIRS_hydra = data/hydra/import

.PHONY: check lint type test doc-check seed load rebuild up down bench bench-smoke report ui-snapshot

check: lint type test doc-check

lint:
	uv run ruff check src tests scripts bench
	uv run ruff format --check src tests scripts bench

doc-check:
	uv run python scripts/check_docs.py

type:
	uv run mypy

test:
	uv run pytest -q

# --- lifecycle stubs: implemented phase by phase (docs/plans/2026-08-04-knowledge-plane/) ---

seed:
	uv run python -m constellate.ingest.seed --arm $(ARM)

load:
	uv run python -m constellate.load $(PLATFORM)

# drop + regenerate derived projections (vector, graph) from relational only
rebuild:
	uv run python -m constellate.load $(PLATFORM) rebuild

up:
ifeq ($(PLATFORM),lyra)
	@echo "Lyra is in-process; nothing to start"
else
	@mkdir -p $(BIND_DIRS_$(PLATFORM))  # bind-mount dirs must pre-exist user-owned
	docker compose -f compose/$(PLATFORM).yml up -d --wait
endif

down:
ifeq ($(PLATFORM),lyra)
	@echo "Lyra is in-process; nothing to stop"
else
	docker compose -f compose/$(PLATFORM).yml down
endif

bench-smoke:
	uv run python -m constellate.smoke $(PLATFORM)

BENCH_ARGS ?=

bench:
	uv run python -m constellate.bench.run $(PLATFORM) $(BENCH_ARGS)

report:
	uv run python -m constellate.bench.report

# ui/public/snapshot/ from committed bench artifacts + config/*.yaml — feeds
# `VITE_UI_MODE=snapshot pnpm build` (a static build with no API behind it)
ui-snapshot:
	uv run python scripts/build_ui_snapshot.py
