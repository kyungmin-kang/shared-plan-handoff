# Recovery Plan

## Objective
Stabilize `data-workbench` and convert the repo into one explicit, approved execution plan that can re-enter the normal handoff pipeline.

## Project Goal
Ship a reliable v1 of Data Workbench where humans and agents share one governed source of truth for graph structure, execution state, reviews, briefs, and persistence, with a maintainable codebase and a clear operator workflow.

## How To Read This Plan
- `Rescue Understanding` is for humans. It explains the project boundary, current context, and what should survive the rescue.
- `Bring-It-Home Workstreams` is the only section that should turn into execution work in Notion.
- `Human Decisions Before Approval` and `Notion Handoff Gate` are planning guardrails, not execution tasks.

## Rescue Understanding
- Current state snapshot: `plans/data-workbench/current-state.md`
- Detailed rescue scan: `plans/data-workbench/detailed-scan.md`
- This document separates rescue diagnosis from the actual work needed to bring the project home.

### Context Notes
Use the detailed rescue scan as the basis for the next approved plan revision.

## Bring-It-Home Workstreams
### Finish the shippable core
- Keep the graph as structural source of truth, structure bundles/reviews as proposal truth, and `plan_state` as execution truth, matching the operator guide.
- Finish and stabilize the active execution-state surface: source-of-truth payloads, execution endpoints, agent contracts/briefs, execution panel UX, and the supporting persistence layer.
- Preserve the canonical local run path (`PYTHONPATH=src python -m workbench.app`) and the Docker Compose path with app, worker, Postgres, and MinIO.
- Ensure the operator guide, runtime plan artifacts, and UI/API behavior all describe the same day-to-day workflow.
- Keep unit, API, persistence, and browser E2E coverage green for the v1 surface that is being shipped.
- Reduce ambiguity between prototype or in-progress changes and what v1 operators and agents should rely on.

### Keep the project maintainable
- Keep one canonical product story across README, operator guide, runtime plans, and agent playbooks.
- Reduce coupling inside large files such as `src/workbench/app.py` and `static/js/app.js` so future updates stay reviewable.
- Preserve runtime artifacts and persistence behavior in a way that remains inspectable locally under `specs/` and `runtime/`.
- Keep test coverage aligned with the real operator and agent workflows so regressions in execution state, profiling, review UX, or persistence are caught early.
- Distinguish clearly between committed source-of-truth artifacts, generated runtime artifacts, and ephemeral local noise such as caches and browser downloads.

## Human Decisions Before Approval
- Confirm the true project goal and the finishable v1 boundary.
- Confirm which files, commands, artifacts, and evidence are canonical.
- Confirm which old work should be preserved, deferred, or explicitly superseded.

## Notion Handoff Gate
- Do not build or reconcile the execution workspace until this plan is approved, decomposed, and reviewed.
- When the approved plan changes, create a new revision and reconcile instead of editing live tasks ad hoc.
