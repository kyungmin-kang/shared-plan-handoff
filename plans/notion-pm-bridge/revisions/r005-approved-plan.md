# Shipping Plan: Public GitHub Repo and Local Codex Plugin

## Goal

Ship `Notion PM Bridge` as:

- a public GitHub repository that another developer can understand, run, and contribute to
- a local Codex plugin workflow that proves the repo-first plan-to-Notion execution loop works in practice

Use this release to validate the product on itself: the bridge should manage its own plan, tasks, Notion workspace, and execution path well enough that we can ship from the same system we are building.

## Scope

In scope:

- public-repo packaging and contributor-facing documentation
- local Codex plugin scaffold and installation path
- shipping docs and structured task sheet for this repo
- a fresh Notion project workspace built from the approved handoff
- end-to-end dogfooding of plan -> decomposition -> review -> Notion build -> execution
- enough maintainability cleanup that future improvements do not depend on hidden session context

Out of scope for this release:

- hosted SaaS or multi-user deployment
- marketplace publication for the plugin
- perfect Notion automation beyond current connector limits
- a major architectural rewrite of the bridge
- broad UI polish not needed for PM clarity and contributor onboarding

## Summary

The product is already viable in principle:

- planning is repo-first
- decomposition and review artifacts are structured
- Notion is the downstream execution system of record

Shipping work is now about making that credible as a reusable tool:

- freeze the repo identity and public story
- package the local Codex plugin path
- prove a fresh Notion project can be created from approved docs
- use the resulting workspace to execute real shipping work
- document the operating model so a new contributor can follow it without prior chat history

This release should end with a repo that is public-share ready and a Codex-local plugin path that is practical for real project management use.

## Milestone 1: Shipping Source of Truth

Duration: `1-2 focused days with AI-agent help`

Goal:

- create the approved shipping plan and companion task sheet for this repo
- validate the repo-first handoff flow on the bridge itself

Exit criteria:

- `docs/shipping_plan.md` and `docs/shipping_tasks.md` are approved and current
- the plan is registered into `plans/notion-pm-bridge/`
- decomposition and reviewer artifacts pass cleanly

## Milestone 2: Public Repo Baseline

Duration: `2-4 focused days with AI-agent help`

Goal:

- make the repository understandable and safe to share publicly

Exit criteria:

- public-facing `README.md` is accurate
- license and contributor docs are present
- repo structure and example usage are understandable from a clean clone
- no hidden local-only setup is required for the documented happy path

## Milestone 3: Local Codex Plugin Baseline

Duration: `1-2 focused days with AI-agent help`

Goal:

- make the bridge installable and discoverable as a local Codex plugin for personal dogfooding

Exit criteria:

- plugin scaffold exists and is documented
- the local plugin can be discovered by Codex
- the plugin path exercises the repo-first handoff workflow rather than bypassing it

## Milestone 4: Fresh Notion Dogfood Workspace

Duration: `1-2 focused days with AI-agent help`

Goal:

- prove the bridge can create a new project workspace from approved docs and make that workspace understandable to a human PM

Exit criteria:

- a fresh Notion project is created from this repo's approved handoff
- project page, tasks, phases, and docs pages are coherent
- a human can identify what to do next from Notion alone

## Milestone 5: Release Confidence

Duration: `1-2 focused days with AI-agent help`

Goal:

- validate the shipped workflow and remove blockers before public sharing

Exit criteria:

- tests pass for the supported bridge flows
- Notion dogfood loop works end to end
- final repo pass removes stale claims and outdated setup assumptions

## Public Interfaces, Deliverables, and Stability

Freeze and support these deliverables for this release:

- repo-first shipping docs and artifacts under `docs/` and `plans/`
- the existing `pm` debug/admin CLI
- the coordinator API in `src/notion_pm_bridge/coordinator.py`
- the local Notion build and reconciliation flow
- the local Codex skill/plugin install path for this repo

Do not introduce a large new abstraction layer unless it directly simplifies the shipping path.

## Test Scenarios That Must Appear in Both Planning and Validation

- create and approve shipping docs in the repo
- register the approved plan and companion task sheet
- decompose the plan into a task graph and reviewer report
- build a fresh Notion workspace from the reviewed handoff
- use the Notion workspace to identify and execute real next tasks
- verify the local plugin path can discover and use the repo workflow
- verify contributor-facing docs match the actual setup path

## Assumptions and Defaults

- output files are:
  - `docs/shipping_plan.md`
  - `docs/shipping_tasks.md`
- the public repo name can follow the product identity `notion-pm-bridge`
- local plugin support is a release goal, but marketplace publication is not
- Notion remains the downstream execution system of record, not the planning source
- the first shipping cycle should optimize for clarity, reproducibility, and dogfooding value over feature expansion
