---
name: notion-pm-bridge
description: Use when working in this repo to keep Notion as the downstream execution system of record while Codex manages approved-plan handoff, workspace build-out, and execution updates.
---

# Notion PM Bridge

Use this skill when the task should move an approved repo plan into the Notion execution workspace, rescue a messy in-flight project, or keep that workspace updated during delivery.

## Default Behavior

- Treat chat as the main interface. Do not ask the user to run `pm` commands unless debugging.
- Treat `plans/<project_slug>/approved-plan.md` as the only valid pre-Notion source of truth.
- When a separate structured task sheet exists, store it as `plans/<project_slug>/approved-tasks.md` and use it as the task-input companion to the approved plan.
- Treat `plans/<project_slug>/revisions/` as the permanent plan and handoff history.
- Do not mutate Notion until the approved plan has been decomposed, reviewed, and explicitly built.
- Rescue docs may be published to Notion before handoff, but only as shared context pages under the project. Do not create the execution database early.
- Prefer the coordinator in `src/notion_pm_bridge/coordinator.py` for the repo-first handoff flow.
- Prefer Codex Apps Notion MCP as the default Notion mutation path.
- Use REST only as a fallback when MCP is unavailable or when you need debug/headless behavior.
- Use the lower-level bridge in `src/notion_pm_bridge/bridge.py` for deterministic task sync, readiness calculation, reconciliation, and repo-state logic.
- Treat the project home page as the human-first PM start surface after the workspace exists.
- Keep a short notes-style inline-view setup note on the workspace root page so humans know how to add linked `Phases`, `Tasks`, and `Docs` views manually.
- Keep `Phase` as a real roadmap/grouping layer rather than a fake task card.
- Keep `Delivery Status` and `Progress` aligned, and compute an `Execution Slot` field so humans can see order, parallelism, and blocker context from one column.
- Keep a searchable docs library database in Notion so approved plans, rescue docs, task sheets, prompts, dashboards, and runbooks are readable without opening the repo.
- If a task database comes up with a generic `Default view`, rename and reconfigure that view into `All tasks` rather than leaving the generic view behind.
- Treat saved view creation as MCP-first polish layered on top of the REST-built database structure.

## Workflow

1. Register the approved Markdown plan into `plans/<project_slug>/approved-plan.md`.
2. If there is a separate shipping task sheet, register it into `plans/<project_slug>/approved-tasks.md` and treat it as the structured task input for decomposition.
3. For messy projects, create `current-state.md` first, then `detailed-scan.md`, then `recovery-plan.md`.
4. Keep rescue docs human-friendly:
   - `current-state.md` should make the real project goal explicit
   - `recovery-plan.md` should separate `Rescue Understanding` from `Bring-It-Home Workstreams`
   - only the `Bring-It-Home Workstreams` section should become execution tasks
5. Optionally publish those rescue docs to Notion as direct project pages when durable shared context would help.
6. Decompose the current approved plan into `task-graph.json` and `handoff.json`. If `approved-tasks.md` exists, use it as the structured task source while keeping `approved-plan.md` as the narrative source of truth.
7. Run reviewer checks and write `decomposition-review.md`.
8. Only after reviewer pass and an explicit build command should Codex create or reconcile the Notion execution workspace.
9. After build, make sure the Notion workspace includes a separate `Phases` roadmap database, a task database with a single primary `All tasks` view, and a docs library database.
10. Keep the project home page as the PM start page and point to `Tasks`, then `Phases`, then `Docs`.
11. If Notion rejects inline linked-database blocks, keep the project home page polished anyway with direct database links, operating guidance, and a workspace-root note that explains the human workaround.
12. During execution, claim, start, block, and finish tasks in Notion without asking the user to touch the shell.

Critical sequencing rule:

- Never run `register-plan`, `decompose`, `review-decomposition`, and `build/reconcile` in parallel.
- These steps are revision-sensitive and must run serially against the same approved revision.
- The CLI already auto-loads `.env`, so do not ask the user to `source .env` unless they explicitly want shell variables exported for some other reason.

## Prompts To Recognize

- `Rescue this messy project`
- `Do a deeper rescue scan`
- `Publish the rescue notebook to Notion`
- `Register this approved plan`
- `Decompose the approved plan`
- `Review the decomposition`
- `Build the workspace from the approved handoff`
- `Reconcile the workspace from the latest approved handoff`
- `Execute the next ready task`

## References

- Repo-first coordinator workflow: `src/notion_pm_bridge/coordinator.py`
- Notion sync logic: `src/notion_pm_bridge/bridge.py`
- Repo artifact store: `src/notion_pm_bridge/repo_artifacts.py`
- Repo layout and runtime model: `README.md`
