# Shipping Tasks: Shared Plan Handoff Public Repo and Local Codex Plugin

## Goal

Ship `Shared Plan Handoff` as a public GitHub repository plus a working local Codex plugin path, and prove the workflow by building a fresh Notion project for this repo and using it as the active PM surface.

## Scope

This shipping track covers approved shipping docs, repo publication readiness, plugin packaging, fresh Notion workspace creation, and end-to-end dogfooding of the repo-first handoff flow.

It does not cover hosted deployment, marketplace publication, a major bridge rewrite, or broad UI work beyond what is needed to make the PM surface understandable.

## Summary

Total estimate: `5-10 focused days with AI-agent help`, expected to land in `1-2 weeks`.

The most serial gates are the approved-doc handoff, the first fresh Notion build, and the final release-confidence sweep. Repo packaging, plugin scaffolding, and some docs work can run in parallel after the handoff is stable.

## Phase 1 — Shipping Source of Truth

Phase estimate: `0.5-1.5 focused days`

- `P1.1 Approve shipping plan and task sheet` — Explanation: create and lock the repo-facing shipping docs that describe what this bridge is shipping now; Goal: one approved source of truth for the release; Tests: human review of `docs/shipping_plan.md` and `docs/shipping_tasks.md`; AI-assisted estimate: `0.25-0.5 day`; Parallelization: serial anchor for all later shipping work.
- `P1.2 Register handoff artifacts` — Explanation: register the approved plan and companion task sheet into `plans/shared-plan-handoff/` so the bridge uses its own repo-first artifact pipeline; Goal: prove the handoff path on the bridge itself; Tests: `register-plan`, `decompose`, and generated artifact sanity check; AI-assisted estimate: `0.25 day`; Parallelization: starts after `P1.1`.
- `P1.3 Reviewer gate pass` — Explanation: generate and pass the decomposition review before any fresh Notion workspace is created; Goal: validate the reviewer step is a real release gate; Tests: reviewer report status is `pass`; AI-assisted estimate: `0.25 day`; Parallelization: serial with `P1.2`.

## Phase 2 — Public Repo Baseline

Phase estimate: `1.5-3 focused days`

- `P2.1 Public README and positioning pass` — Explanation: rewrite the repo story around what the bridge does, how the repo-first handoff works, and how a new user should start; Goal: a public reader understands the tool without private chat context; Tests: follow the documented setup and usage story from a clean read; AI-assisted estimate: `0.5-0.75 day`; Parallelization: can run after `P1.1`.
- `P2.2 Repo publication scaffolding` — Explanation: add or validate `LICENSE`, contribution docs, ignore rules, and public-facing metadata for a GitHub share; Goal: a repo that can be published confidently; Tests: manual repo review and clean-clone sanity check; AI-assisted estimate: `0.5 day`; Parallelization: parallel with `P2.1`.
- `P2.3 Example and docs consistency pass` — Explanation: make the examples, plan docs, and README describe the same workflow and supported limitations; Goal: no mismatch between docs and actual bridge behavior; Tests: walkthrough of the documented plan -> handoff -> Notion path; AI-assisted estimate: `0.5-0.75 day`; Parallelization: parallel after `P2.1`.
- `P2.4 Public repo initialization` — Explanation: initialize the repo for public GitHub publication, including branch, remote, and first publish-ready commit structure; Goal: the repo can actually be pushed and shared; Tests: `git status` is clean and the intended publish structure exists; AI-assisted estimate: `0.25-0.5 day`; Parallelization: starts after `P2.2`.

## Phase 3 — Local Codex Plugin Baseline

Phase estimate: `1-2 focused days`

- `P3.1 Plugin scaffold creation` — Explanation: add the local Codex plugin manifest and required repo structure so Codex can discover this project as a plugin; Goal: the bridge is installable locally as a Codex plugin; Tests: local plugin discovery; AI-assisted estimate: `0.25-0.5 day`; Parallelization: can run after `P1.1`.
- `P3.2 Plugin workflow wiring` — Explanation: point the plugin at the repo-first planning and Notion execution workflow instead of creating a second competing path; Goal: plugin use reinforces the main product model; Tests: one local plugin invocation path reaches the expected repo workflow; AI-assisted estimate: `0.5-0.75 day`; Parallelization: starts after `P3.1`.
- `P3.3 Plugin install and usage docs` — Explanation: document how to install and use the local plugin in the public repo; Goal: a user can try the plugin without hidden setup knowledge; Tests: docs walkthrough for local installation; AI-assisted estimate: `0.25-0.5 day`; Parallelization: parallel with late `P3.2`.

## Phase 4 — Fresh Notion Dogfood Workspace

Phase estimate: `1-2 focused days`

- `P4.1 Fresh project workspace build` — Explanation: create a brand-new Notion project for `Shared Plan Handoff` from the reviewed handoff; Goal: prove the bridge can build a clean workspace from zero; Tests: project page, tasks, phases, and docs exist in Notion; AI-assisted estimate: `0.25-0.5 day`; Parallelization: serial after `P1.3`.
- `P4.2 Human-readable PM surface pass` — Explanation: polish the new project page, tasks view, and docs surface so a human PM can understand the project without opening the repo; Goal: the Notion workspace stands on its own as the execution surface; Tests: manual scan of project page, `All tasks`, phases, and docs; AI-assisted estimate: `0.5-0.75 day`; Parallelization: starts after `P4.1`.
- `P4.3 Start execution from Notion` — Explanation: use the fresh Notion workspace to identify and execute the next real shipping tasks for this repo; Goal: validate that the PM system is good enough to drive its own shipping work; Tests: at least one task claimed, started, and updated through the workspace; AI-assisted estimate: `0.5 day`; Parallelization: starts after `P4.2`.

## Phase 5 — Release Confidence

Phase estimate: `1-1.5 focused days`

- `P5.1 Bridge regression pass` — Explanation: run the bridge tests and confirm the shipping workflow still works after repo and plugin changes; Goal: avoid breaking the core PM workflow while shipping it; Tests: unit suite and compile checks; AI-assisted estimate: `0.25-0.5 day`; Parallelization: parallel with `P4.2`.
- `P5.2 Publish-readiness sweep` — Explanation: do a final pass on versioning, stale docs, unsupported claims, and release blockers before public sharing; Goal: a clean first public impression; Tests: final checklist and manual repo review; AI-assisted estimate: `0.25-0.5 day`; Parallelization: serial near the end.
- `P5.3 Dogfood retrospective and next-cut backlog` — Explanation: capture what worked, what still felt rough, and what should land after the first public share; Goal: make the next iteration easier and more intentional; Tests: short written retrospective and backlog note; AI-assisted estimate: `0.25 day`; Parallelization: after `P4.3`.

## Public APIs, Interfaces, and Types

Keep the existing bridge surfaces intact for this shipping cycle:

- repo-first artifacts under `plans/`
- coordinator-driven handoff and Notion build flow
- `pm` debug/admin CLI
- local skills and plugin-facing entrypoints

Do not introduce a second planning model or a competing execution surface during this release.

## Test Scenarios That Must Appear in Both Planning and Validation

- approved docs exist and are current
- handoff artifacts generate cleanly from the approved docs
- reviewer gate blocks Notion until it passes
- a fresh Notion project is created from the reviewed handoff
- the Notion workspace is understandable enough to drive next-task selection
- the local Codex plugin path is discoverable and documented
- public repo docs match the actual setup and dogfood path

## Assumptions and Defaults

- output files are:
  - `docs/shipping_plan.md`
  - `docs/shipping_tasks.md`
- project slug should be `projectmanagervisualization`
- plugin packaging is local-first, not marketplace-first
- GitHub publication and plugin baseline are both part of this shipping cycle
