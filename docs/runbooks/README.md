# Runbooks

Operational how-tos for this repo. The doc pipeline's division of labor:
**ADRs record why, runbooks record how, research records analysis.** Written
to double as workshop teaching material — each runbook tells a stranger
exactly what to type and what they should see.

## Conventions

- One task per runbook: `<slug>.md`, imperative title ("Run the dev loop",
  not "Dev loop notes").
- Structure: **When to use** (one or two lines), **Steps** (numbered, exact
  commands, expected output for anything non-obvious), **Failure modes**
  (what goes wrong + recovery — incidents we actually hit belong here, they
  are the most instructive part), **Last verified** (date + context).
- Commands must be copy-pasteable from a fresh clone. If a step's output
  matters, show it.
- Update the runbook in the same PR as the change that invalidates it; bump
  **Last verified**.
- Created/maintained via the `/runbook` skill (`.claude/skills/runbook/`).

## Index

| Runbook | Task |
|---------|------|
| [local-dev-loop](local-dev-loop.md) | Clone → verify → branch → PR → merge cycle |
| [ci-and-merging](ci-and-merging.md) | CI anatomy; merging PRs safely, incl. stacked-PR recovery |
| [seed-the-dataset](seed-the-dataset.md) | Build/rebuild `data/canonical/` from ml-25m; verify against MANIFEST |
| [run-lyra](run-lyra.md) | Bring up Lyra end to end: load, smoke flows, REST API, adapter ablation |
| [run-benchmarks](run-benchmarks.md) | Produce a committed benchmark artifact + report; go/no-go verdict |
| [run-orion](run-orion.md) | Bring up Orion: container, load, conformance, CTE↔AGE switch, bench |
| [run-hydra](run-hydra.md) | Bring up Hydra: postgres+qdrant+memgraph, load, rebuild proof, health checks |
| [run-explorer](run-explorer.md) | Explorer SPA + API: dev loop, production serve, static snapshot, MCP selftest |
