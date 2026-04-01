# Current State Snapshot

- Project identifier: `data-workbench`
- Rescue stage: `detailed-scan`
- Generated at: `2026-03-31T23:34:50+00:00`
- Detailed scan: `plans/data-workbench/detailed-scan.md`

## Project Goal
Ship a reliable v1 of Data Workbench where humans and agents share one governed source of truth for graph structure, execution state, reviews, briefs, and persistence, with a maintainable codebase and a clear operator workflow.

## Current Reality
- `Data Workbench` already looks like a real product repo with a defined operator model, a live runtime plan surface, Docker/local run paths, and broad tests.
- The strongest active push appears to be execution state plus agent workflow integration: new execution modules, agent contracts/briefs, API route splits, UI execution panels, and matching tests/docs are all in flight.
- The main rescue risk is not lack of direction, but lack of one explicit approved v1 completion plan across a large active branch.
- The preserve set is fairly clear: workbench runtime code, operator guide, agent playbooks, graph spec, runtime plans, compose/local run paths, and the product-shaped test suite.
- The maintenance risk is concentrated in large central files, mixed committed/generated runtime artifacts, and the need to keep docs, UI, API, and execution governance aligned.

## What Completion Requires
- Keep the graph as structural source of truth, structure bundles/reviews as proposal truth, and `plan_state` as execution truth, matching the operator guide.
- Finish and stabilize the active execution-state surface: source-of-truth payloads, execution endpoints, agent contracts/briefs, execution panel UX, and the supporting persistence layer.
- Preserve the canonical local run path (`PYTHONPATH=src python -m workbench.app`) and the Docker Compose path with app, worker, Postgres, and MinIO.
- Ensure the operator guide, runtime plan artifacts, and UI/API behavior all describe the same day-to-day workflow.
- Keep unit, API, persistence, and browser E2E coverage green for the v1 surface that is being shipped.
- Reduce ambiguity between prototype or in-progress changes and what v1 operators and agents should rely on.

## What Maintenance Requires
- Keep one canonical product story across README, operator guide, runtime plans, and agent playbooks.
- Reduce coupling inside large files such as `src/workbench/app.py` and `static/js/app.js` so future updates stay reviewable.
- Preserve runtime artifacts and persistence behavior in a way that remains inspectable locally under `specs/` and `runtime/`.
- Keep test coverage aligned with the real operator and agent workflows so regressions in execution state, profiling, review UX, or persistence are caught early.
- Distinguish clearly between committed source-of-truth artifacts, generated runtime artifacts, and ephemeral local noise such as caches and browser downloads.

## Recovery Questions
- What is already built and should be preserved?
- Which in-flight tasks are still valid?
- What should be explicitly superseded or dropped?
- What new milestones are needed after the rethink?
