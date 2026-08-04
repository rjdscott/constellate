PLATFORM ?= lyra

.PHONY: check lint type test doc-check seed load up down bench report

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
	uv run python -m constellate.ingest.seed

load:
	@echo "make load PLATFORM=$(PLATFORM): implemented in phase 03+" && exit 1

up:
ifeq ($(PLATFORM),lyra)
	@echo "Lyra is in-process; nothing to start"
else
	docker compose -f compose/$(PLATFORM).yml up -d --wait
endif

down:
ifeq ($(PLATFORM),lyra)
	@echo "Lyra is in-process; nothing to stop"
else
	docker compose -f compose/$(PLATFORM).yml down
endif

bench:
	@echo "make bench PLATFORM=$(PLATFORM): implemented in phase 04" && exit 1

report:
	@echo "make report: implemented in phase 04" && exit 1
