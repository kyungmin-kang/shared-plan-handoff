---
name: notion-pm-bridge
description: Use the repo-first handoff workflow from this plugin to keep Notion as the downstream execution system of record while Codex manages approved-plan registration, rescue work, workspace build-out, and execution updates.
---

# Notion PM Bridge

Use this plugin skill when the task should move an approved repo plan into the
Notion execution workspace, rescue a messy in-flight project, or keep that
workspace current during delivery.

## Default Behavior

- Treat chat as the main interface. Do not ask the user to run `pm` commands
  unless debugging.
- Treat `../../../../plans/<project_slug>/approved-plan.md` as the only valid
  pre-Notion source of truth.
- When a structured task sheet exists, store it as
  `../../../../plans/<project_slug>/approved-tasks.md` and use it as the
  companion task input for decomposition.
- Prefer the coordinator in
  `../../../../src/notion_pm_bridge/coordinator.py` for the repo-first handoff
  flow.
- Prefer Codex Apps Notion MCP as the default Notion mutation path.
- Use REST only as fallback for debug, CI, webhooks, or headless work.
- Keep the project home page as the human-first PM start surface after the
  workspace exists.
- Keep the home-page order `Tasks`, then `Phases`, then `Docs`.
- Keep `Phase` as a roadmap grouping layer rather than a fake task card.
- Keep `Delivery Status`, `Progress`, and `Execution Slot` aligned so humans can
  read order, parallelism, and blocker context from the main task table.
- When a phase grows large, generate phase-scoped plan and task docs under
  `plans/<project_slug>/phase-docs/` and sync them into the Notion docs library.
- If the task database comes up with a generic `Default view`, rename and
  reconfigure it into `All tasks`.
- Treat saved view creation as MCP-first polish layered on top of the REST-built
  database structure.
- Surface progress during long Notion build/reconcile commands so successful
  builds do not look hung.

## Workflow

1. Register the approved Markdown plan into
   `../../../../plans/<project_slug>/approved-plan.md`.
2. If there is a separate shipping task sheet, register it into
   `../../../../plans/<project_slug>/approved-tasks.md`.
3. For messy projects, create `current-state.md`, then `detailed-scan.md`, then
   `recovery-plan.md`.
4. Decompose the approved plan into `task-graph.json` and `handoff.json`.
5. Run reviewer checks and write `decomposition-review.md`.
6. Only after reviewer pass and an explicit build or reconcile request should
   Codex mutate Notion.
7. After build, make sure the Notion workspace includes a `Tasks` database, a
   `Phases` roadmap database, and a searchable `Docs` library.
8. During execution, claim, start, block, and finish tasks in Notion without
   asking the user to touch the shell.

Critical sequencing rule:

- Run `register-plan -> decompose -> review-decomposition -> build/reconcile`
  serially, never in parallel.
- The CLI auto-loads `.env`, so do not tell the user to `source .env` unless
  they explicitly need exported shell variables for a separate step.

## References

- `../../../../src/notion_pm_bridge/coordinator.py`
- `../../../../src/notion_pm_bridge/bridge.py`
- `../../../../src/notion_pm_bridge/repo_artifacts.py`
- `../../../../README.md`
