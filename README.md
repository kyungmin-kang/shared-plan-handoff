# Shared Plan Handoff

`Shared Plan Handoff` is a repo-first planning system that turns approved Markdown plans into a human-readable Notion execution workspace.

The public project name is `Shared Plan Handoff`. The internal Python package remains `notion-pm-bridge` for compatibility with the existing CLI and imports.

## Status

This project is still a work in progress.

- Expect the workflow, docs, and plugin packaging to keep evolving.
- The repo is already usable for real dogfooding, but it is still alpha.
- Connector limits in Notion mean some inline workspace polish still requires a human step.

## Collaboration Notes

- Issues and pull requests are welcome.
- Please prefer small, reviewable changes that preserve the repo-first handoff model.
- If you notice a failure that looks systemic rather than incidental, treat it as a product bug and fix the underlying assumption rather than papering over the symptom.

It ships the `notion-pm-bridge` package plus local Codex skills for:

- turning an approved plan into a normalized task graph
- reviewing that decomposition before anything reaches Notion
- building a fresh Notion project with tasks, phases, and docs
- keeping execution status readable for both humans and agents

The default transport is now:

- Codex Apps Notion MCP first
- REST only as fallback for debug, CI, webhooks, or other headless cases

## What Problem This Solves

Planning often starts in chat or markdown, but execution becomes hard to track once work spreads across agents, branches, docs, and partial ideas.

This repo keeps the upstream planning source of truth in the repo, then pushes only the approved, reviewed handoff into Notion so:

- humans can follow the project from Notion alone
- Codex can keep the workspace current while implementing
- replans and rescue flows preserve history instead of overwriting context

## Core Model

The main workflow is:

1. Planner agent + human settle on an approved Markdown plan in the repo.
2. The PM agent decomposes that plan into a normalized task graph.
3. A reviewer agent validates the decomposition.
4. Only after reviewer pass and an explicit build command does Codex create or reconcile the Notion execution workspace.
5. Execution agents then claim, update, block, review, and finish work directly in Notion.

That means:

- planning is repo-first
- Notion is downstream execution, not upstream planning
- the decomposition review is a real gate, not a formality

## What Gets Created In Notion

Once the handoff is ready, Codex builds:

- a project home page
- a `Tasks` database for day-to-day execution
- a `Phases` database for roadmap sequencing
- a `Docs` database containing Notion copies of key markdown artifacts
- supporting pages such as:
  - `Final Approved Plan`
  - `Shipping Tasks`
  - `Execution Runbook`
  - `Dashboard Snapshot`
  - `Handoff Summary`
  - `Notion MCP Prompts`

The resulting workspace is meant to be understandable without opening the repo.

## Quick Start

1. Connect the Notion app/plugin in Codex so Notion MCP works in-session.
2. Create a parent Notion page where Codex should create project workspaces.
3. Copy `.env.example` to `.env`.
4. Install the repo-local environment with Python 3.11+:

```bash
./scripts/bootstrap_venv.sh
```

If your machine has multiple Python versions, the bootstrap script will pick a compatible interpreter automatically. You can also force one explicitly:

```bash
SHARED_PLAN_HANDOFF_PYTHON=/path/to/python3.11 ./scripts/bootstrap_venv.sh
```

If you want REST fallback, also create a Notion internal integration and share the parent page with it. For normal chat-first use with a working Notion MCP connection, the REST token is optional.

The CLI and coordinator will read `.env` directly. You do not need to `source .env`, which is safer when secrets contain shell-special characters.

Recommended `.env` shape:

```bash
NOTION_TRANSPORT=mcp
NOTION_REST_FALLBACK=1
NOTION_API_TOKEN=your_notion_integration_token_if_using_rest_fallback
NOTION_PARENT_PAGE_ID=your-parent-page-id
NOTION_PROJECT_IDENTIFIER=agent-pm
PM_BRIDGE_PLANS_DIR=plans
```

## Typical Prompts

- `Codex, rescue this messy project and create a current-state snapshot.`
- `Codex, do a deeper rescue scan and make the project goal explicit.`
- `Codex, register this approved plan and companion shipping task sheet for the project.`
- `Codex, decompose the approved plan into a task graph.`
- `Codex, review the decomposition.`
- `Codex, build the workspace from the approved handoff.`
- `Codex, execute the next ready task and keep Notion updated.`

The intended user experience is chat-first. Codex should not ask the user to run the CLI unless debugging.

## Repo Artifact Layout

Each project lives under `plans/<project_slug>/`:

```text
plans/<project_slug>/
  approved-plan.md
  approved-tasks.md
  current-state.md
  detailed-scan.md
  recovery-plan.md
  task-graph.json
  decomposition-review.md
  handoff.json
  revisions/
    r001-approved-plan.md
    r001-approved-tasks.md
    r001-task-graph.json
    r001-decomposition-review.md
    r001-handoff.json
    r002-approved-plan.md
    ...
```

Key files:

- `approved-plan.md`: current approved implementation plan alias
- `approved-tasks.md`: optional companion task-input doc
- `current-state.md`: current rescue snapshot alias
- `detailed-scan.md`: deeper rescue diagnosis
- `recovery-plan.md`: rescue-plan draft before re-entering the normal handoff pipeline
- `task-graph.json`: normalized milestones, tasks, dependencies, routing, and sequence
- `decomposition-review.md`: reviewer findings plus pass/changes-required status
- `handoff.json`: machine-readable payload used to build or reconcile Notion
- `revisions/`: immutable history of approved plans and downstream artifacts

## Example

The example payload in `examples/plan-spec.json` is a small debug/admin sample for the fallback CLI path.

It is useful when you want to:

- inspect the older plan-spec shape
- test the debug CLI manually
- compare the repo-first handoff with the older direct-plan input

For normal use, prefer approved markdown plans plus the repo-first artifact flow instead of authoring raw JSON by hand.

## Local Skills

This repo includes local Codex skills under `.codex/skills`:

- `notion-pm-bridge`
- `pm-plan-translator`
- `pm-rescue`

These are part of the intended local Codex workflow and are now complemented by
the repo-local plugin scaffold.

## Local Plugin

This repo now also ships a repo-local Codex plugin at:

- `plugins/shared-plan-handoff`
- `.agents/plugins/marketplace.json`

Installation and usage notes live in:

- `docs/local_codex_plugin.md`

The plugin is meant to reinforce the same repo-first workflow as the local
skills, not replace it with a second planning model.

## Release Confidence Docs

Phase 5 artifacts for this release live in:

- `docs/release_readiness.md`
- `docs/dogfood_retrospective.md`
- `docs/qa_report.md`

## Coordinator API

The main orchestration surface is `CodexNotionWorkflowCoordinator` in `src/notion_pm_bridge/coordinator.py`.

Primary repo-first methods:

- `rescue_project(project_name, context_markdown=None)`
- `deepen_rescue_scan(project_ref, detailed_scan_markdown, goal_statement, completion_definition=None, maintenance_requirements=None, publish_to_notion=False)`
- `publish_rescue_docs(project_ref)`
- `register_approved_plan(project_name, plan_path, task_plan_path=None)`
- `decompose_approved_plan(project_ref)`
- `review_decomposition(project_ref)`
- `build_workspace_from_handoff(project_ref)`
- `reconcile_workspace_from_handoff(project_ref)`
- `execute_next(project_ref, agent_name)`

## Debug CLI

The `pm` CLI remains a fallback/admin interface:

```bash
./.venv/bin/pm rescue "AI Agent PM Platform" --context-file /path/to/context.md --goal "Ship the maintainable v1."
./.venv/bin/pm deepen-rescue ai-agent-pm-platform --scan-file /path/to/detailed-scan.md --goal "Ship the maintainable v1." --completion-file /path/to/completion.md --maintenance-file /path/to/maintenance.md --publish-to-notion
./.venv/bin/pm publish-rescue-docs ai-agent-pm-platform
./.venv/bin/pm register-plan "AI Agent PM Platform" /path/to/approved-plan.md --tasks-path /path/to/shipping_tasks.md
./.venv/bin/pm decompose ai-agent-pm-platform
./.venv/bin/pm review-decomposition ai-agent-pm-platform
./.venv/bin/pm build-from-handoff ai-agent-pm-platform
./.venv/bin/pm reconcile-from-handoff ai-agent-pm-platform
```

Use it when you want a direct debug surface, not as the primary everyday workflow.

Run the repo-first handoff steps serially, not in parallel:

1. `register-plan`
2. `decompose`
3. `review-decomposition`
4. `build-from-handoff` or `reconcile-from-handoff`

Each step updates the current approved revision alias and its revision-scoped artifacts. If you fire them in parallel, a later step can legitimately read the previous revision.

## Notion Transport Policy

- Default: `NOTION_TRANSPORT=mcp`
- Fallback: REST with `NOTION_API_TOKEN`
- Recommended interactive path: use Codex chat plus the connected Notion app/plugin
- Recommended non-interactive path: use the CLI with the REST token
- The CLI auto-loads `.env` (or `PM_BRIDGE_ENV_FILE`) without requiring shell sourcing
- Do not `source .env` unless you have already shell-escaped the values yourself; dotenv-safe secrets may still contain shell-special characters

This means:

- `register-plan`, `decompose`, and `review-decomposition` remain useful without touching Notion
- page/database/view mutation in everyday use should happen through Codex Apps Notion MCP first
- REST stays available for webhook work, debugging, and headless automation

## Rescue And Replans

For in-flight projects that are hard to track:

1. Run the quick rescue flow to create `current-state.md` and `recovery-plan.md`.
2. Run a deeper rescue scan to create `detailed-scan.md` with an explicit project goal, essential files, in-flight work, noisy legacy artifacts, completion criteria, and maintenance baseline.
3. Keep the rescue docs human-first:
   - `current-state.md` should state the real project goal, current reality, completion requirements, and maintenance requirements
   - `recovery-plan.md` should separate `Rescue Understanding` from `Bring-It-Home Workstreams`
   - only the `Bring-It-Home Workstreams` section should turn into Notion execution tasks
4. Optionally publish the rescue notebook docs to Notion for durable shared context before the execution workspace exists.
5. Review and refine the recovery plan with the human.
6. Register the recovery plan as the next approved revision.
7. Re-run decomposition and reviewer checks.
8. Reconcile Notion from the latest reviewed handoff.

Every new approved plan creates a new revision under `plans/<project_slug>/revisions/`. The top-level files stay as the current aliases, while the revisioned files preserve the full replan history.

## Testing

```bash
./.venv/bin/python -m unittest discover -s tests
python3 -m compileall src tests
./scripts/bootstrap_venv.sh
```

## Dogfood Status

This repo is already dogfooding its own workflow:

- shipping docs are repo-first
- reviewed handoffs can build fresh Notion workspaces
- the project can track and execute its own release plan from Notion
