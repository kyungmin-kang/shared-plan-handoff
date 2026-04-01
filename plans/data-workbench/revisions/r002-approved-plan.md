# Recovery Plan Draft

## Objective
Stabilize `Data Workbench` and convert the repo into one explicit, approved execution plan that can re-enter the normal handoff pipeline.

## Goal
Ship a reliable v1 of Data Workbench where humans and agents share one governed source of truth for graph structure, execution state, reviews, briefs, and persistence, with a maintainable codebase and a clear operator workflow.

## Inputs
- Current state snapshot: `plans/data-workbench/current-state.md`
- Detailed rescue scan: `plans/data-workbench/detailed-scan.md`

## Definition Of Completion
- Keep the graph as structural source of truth, structure bundles/reviews as proposal truth, and `plan_state` as execution truth, matching the operator guide.
- Finish and stabilize the active execution-state surface: source-of-truth payloads, execution endpoints, agent contracts/briefs, execution panel UX, and the supporting persistence layer.
- Preserve the canonical local run path (`PYTHONPATH=src python -m workbench.app`) and the Docker Compose path with app, worker, Postgres, and MinIO.
- Ensure the operator guide, runtime plan artifacts, and UI/API behavior all describe the same day-to-day workflow.
- Keep unit, API, persistence, and browser E2E coverage green for the v1 surface that is being shipped.
- Reduce ambiguity between prototype or in-progress changes and what v1 operators and agents should rely on.

## Maintenance Baseline
- Keep one canonical product story across README, operator guide, runtime plans, and agent playbooks.
- Reduce coupling inside large files such as `src/workbench/app.py` and `static/js/app.js` so future updates stay reviewable.
- Preserve runtime artifacts and persistence behavior in a way that remains inspectable locally under `specs/` and `runtime/`.
- Keep test coverage aligned with the real operator and agent workflows so regressions in execution state, profiling, review UX, or persistence are caught early.
- Distinguish clearly between committed source-of-truth artifacts, generated runtime artifacts, and ephemeral local noise such as caches and browser downloads.

## Recovery Milestones
1. Lock the true project goal and narrow the scope to the finishable core.
2. Separate essential active assets from archived, noisy, or superseded material.
3. Freeze one explicit approved plan revision with canonical commands, artifacts, and evidence sources.
4. Re-run decomposition and reviewer checks on that approved plan.
5. Publish or refresh the shared rescue notebook in Notion when durable context would help.
6. Build or reconcile the execution workspace only after the reviewed handoff is ready.

## Immediate Actions
- Review the current-state snapshot with the human and confirm the real end goal.
- Identify the essential files, canonical commands, and saved evidence that must survive the rescue.
- Turn the recovery draft into the next approved plan revision when the scope is stable.

## Additional Rescue Context
Use the detailed rescue scan as the basis for the next approved plan revision.
