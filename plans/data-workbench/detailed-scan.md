# Detailed Rescue Scan

- Project identifier: `data-workbench`
- Generated at: `2026-03-31T23:34:50+00:00`
- Quick scan reference: `plans/data-workbench/current-state.md`

## Project Goal
Ship a reliable v1 of Data Workbench where humans and agents share one governed source of truth for graph structure, execution state, reviews, briefs, and persistence, with a maintainable codebase and a clear operator workflow.

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

## Detailed Findings
### Clear Goal
- The repo’s goal is to ship `Data Workbench` as a usable product, not just to accumulate graph tooling experiments.
- The core promise is that humans and agents can work against one governed system where structure, execution state, reviews, and briefs stay aligned.

### Essential Active Files And Paths
- `README.md`: product overview, canonical run paths, and testing expectations.
- `pyproject.toml`: package metadata, runtime dependencies, optional persistence and E2E dependencies, and console scripts.
- `src/workbench/app.py`: main FastAPI application surface and the place where graph, execution, profiling, onboarding, review, and artifact endpoints come together.
- `src/workbench/store.py`: persistence layer for graph state, plans, artifacts, and mirrored storage.
- `src/workbench/types.py`: validation and core payload contracts.
- `src/workbench/execution.py`: current execution-truth logic and task derivation path.
- `src/workbench/agent_contracts.py` and `src/workbench/agent_briefs.py`: active agent-facing workbench surface.
- `src/workbench/project_profiler.py`, `src/workbench/sql_scanner.py`, and `src/workbench/orm_scanner.py`: discovery/profiling intelligence that underpins onboarding and drift detection.
- `static/index.html`, `static/js/app.js`, `static/js/execution-panel.js`, `static/js/execution-briefs.js`, and `static/css/app.css`: the operator-facing UI surface.
- `docs/workbench_v1_operator_guide.md`: the clearest current statement of how graph, structure review, and execution state should work together.
- `docs/agent_playbooks/*.md`: role-specific operating guidance for architect, builder, QA, and scout agents.
- `runtime/plans/latest.plan.md` and `runtime/coordination/*.md`: current execution/planning traces from real work.
- `docker-compose.yml` and `Dockerfile`: containerized local stack.
- `tests/`: broad regression surface including API, persistence, browser E2E, graph engine, SQL/ORM coverage, and regression tests.

### Evidence That The Product Already Exists
- `README.md` describes implemented graph node types, filtered views, lineage, profiling, save-to-plan flow, browser UI, and Docker Compose support.
- `docs/workbench_v1_operator_guide.md` defines a coherent operating model with graph truth, proposal truth, and execution truth.
- The repo has active runtime plans and coordination notes, which means people or agents are already using it as a live system rather than a toy scaffold.
- The test suite is broad and product-shaped, covering API behavior, persistence integration, browser E2E, graph engine, SQL/ORM coverage, and regressions.
- The git working tree shows a large active change set around execution state, review UX, agent briefs/contracts, and persistence, which suggests the current v1 push is underway rather than hypothetical.

### Work In Progress And Ambiguity
- The current in-flight branch is substantial and touches core backend, frontend, and tests at once, which makes it harder to tell what the true v1 boundary is.
- `src/workbench/app.py` and `static/js/app.js` are carrying a lot of responsibility, so maintainability risk is already visible.
- Runtime plans and coordination notes exist, but it is not yet obvious that there is one approved completion plan tying together operator UX, execution state, profiling/discovery, and persistence.
- There is local runtime state, caches, browser binaries, and untracked docs/assets, so the preserve set versus ephemeral noise needs to be made explicit.
- Because agents are part of the product concept, completion requires more than just working endpoints; it needs a stable governance story around briefs, execution updates, evidence, and review routing.

### Likely Preserve Set
- Active `src/workbench/` modules that define the product’s runtime behavior.
- `docs/workbench_v1_operator_guide.md` and `docs/agent_playbooks/*.md` because they describe the intended operating model.
- `runtime/plans/latest.plan.md` and useful coordination notes that show the current execution trajectory.
- `specs/workbench.graph.json` as the canonical structural artifact.
- `docker-compose.yml`, `Dockerfile`, and the local run instructions in `README.md`.
- The current broad test suite, especially API, persistence, SQL/ORM coverage, and browser E2E slices.

### Likely Noisy Or Local-Only Material To Quarantine
- `.pytest_cache/`, `.playwright-browsers/`, and other local environment debris.
- Local `.env` contents and any machine-specific runtime caches.
- Potentially stale runtime plan history once one approved plan exists, if older plans stop being useful for current execution.
- Large monolithic files should not be deleted, but they should be treated as maintainability hotspots rather than canonical design ideals.

### What The Rescue Should Solve
- Define the actual v1 finish line for the current product push.
- Decide which parts of the current execution-state and agent-workflow branch are required for v1 versus better left as follow-on work.
- Turn runtime coordination traces and operator docs into one approved plan with explicit milestones, dependencies, and acceptance checks.
- Clarify which artifacts are canonical for operators and agents and which are generated/local.

### What Will Make Future Maintenance Easier
- One approved plan that ties together product goal, operator workflow, execution-state behavior, and test expectations.
- Clear ownership boundaries between structure-governance code, execution-state code, profiling/discovery code, and frontend UI modules.
- Smaller reviewable seams in `app.py` and `app.js` over time.
- Stable playbooks and docs that match the actual API/UI behavior.
- A durable PM/rescue notebook in Notion once the plan is approved, so long-lived context does not depend on agent memory alone.
