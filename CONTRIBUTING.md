# Contributing

Start with [README.md](README.md) for what this is, then:

1. **Setup + dev loop**: [docs/runbooks/local-dev-loop.md](docs/runbooks/local-dev-loop.md):
   clone, `uv sync`, `make check`, branch, PR.
2. **Rules**: [CLAUDE.md](CLAUDE.md): branch/PR discipline (never push main,
   squash-merge only, one PR per logical change) and the doc pipeline
   (research → ADR → plan → audit, + runbooks). They bind humans and agents
   equally.
3. **CI + merging**: [docs/runbooks/ci-and-merging.md](docs/runbooks/ci-and-merging.md).

House invariants worth knowing before writing code:

- The pipeline never imports a concrete adapter; adapters never import each
  other; wiring lives in one config-keyed factory.
- New adapters must pass `tests/conformance/` unchanged: write nothing that
  requires editing the suite.
- Platform names are codenames + epithets ([ADR 0009](docs/adr/0009-platform-codenames-constellations.md));
  config over constants; seed every random operation.
- Docs update in the same PR as the change they describe.
