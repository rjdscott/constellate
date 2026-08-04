# Phase 01 — Scaffold

## Goal

A fresh clone runs `make check` green with every adapter skipped: uv-managed
Python 3.12 project, ruff + mypy --strict + pytest wired, core contract
(types, plane Protocols, six-step pipeline skeleton, RRF fusion) defined with
no concrete adapter, conformance suite present but skipping, config files per
platform, compose/docker stubs for Orion and Hydra. This forces the adapter boundary
to be real before any engine code exists.

**Gate before starting:** ADRs 0001–0009 ratified — ✅ done 2026-08-04.

## Tasks

- [x] `pyproject.toml` (uv, py3.12), ruff + mypy --strict + pytest config
- [x] `Makefile`: `check` (lint+type+test), stubs for `seed/load/up/down/bench/report` with `PLATFORM` default `lyra`
- [x] `src/kp/core/`: `types.py`, `protocol.py` (Relational/Vector/GraphPlane Protocols per prep §4), `pipeline.py` (six-step order, instrumented per step), `fusion.py` (RRF k=60, weights from config), `errors.py`
- [x] `src/kp/config.py`: pydantic-settings; `config/{lyra,orion,hydra}.yaml`; config fingerprint
- [x] `tests/conformance/`: relational/vector/graph/pipeline suites, parametrized by adapter fixture, all skipping (no adapters yet)
- [x] `compose/{orion,hydra}.yml` + `docker/orion/Dockerfile` stubs (contents in phases 05/06)
- [x] CI workflow: `make check` on push (no docker needed)
- [x] `.github/pull_request_template.md`

## Verification

```
make check          # green, conformance suites report skipped
uv run python -c "from kp.core import protocol, pipeline, fusion"
```

## Artifacts

`pyproject.toml`, `Makefile`, `src/kp/core/*`, `config/*.yaml`,
`tests/conformance/*`, `compose/*.yml`, CI workflow.

## Progress log

2026-08-04 — ADRs ratified; foundations PR #1 opened (merge pending user).
Phase started on `feat/scaffold` stacked on the docs branch.

2026-08-04 — Phase complete. `make check` green (ruff, mypy --strict, 16
passed / 12 conformance skips by design). Core contract implemented for
real, not stubbed: weighted RRF fusion (unit-tested against known values),
six-step pipeline with per-step timings, concurrent vector+graph on seed
flows, ablation via `planes` subset — all verified against in-memory
protocol fakes. Config fingerprinting stable+sensitive. PR #2.
