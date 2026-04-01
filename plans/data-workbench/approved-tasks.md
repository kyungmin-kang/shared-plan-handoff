# Shipping Tasks: Dogfood and Contributor-Ready Public Share

## Goal

Deliver a Docker-first, contributor-ready public GitHub version of the workbench that is already usable in your own real projects and clear enough that outside contributors can run it, understand it, and improve it safely.

## Scope

This shipping track covers Docker-first setup, stable standalone and agent-enhanced flows, public docs, contributor scaffolding, CI confidence, and enough maintainability cleanup that future work does not get trapped in the remaining hotspot files.

It does not cover hosted deployment, multi-user features, Windows first-class support, full runtime-mode parity, or a large execution-model redesign.

## Summary

Total estimate: `11-19 focused days with AI-agent help`, expected to land in `2-3 weeks`.

Some tasks can run in parallel, especially frontend versus backend cleanup and docs versus repo hygiene, but final docs alignment, contract freeze, and release validation remain serial gates.

## Phase 1 — Dogfood Baseline

Phase estimate: `2-3 focused days`

- `P1.1 Docker smoke path stabilization` — Explanation: make `docker compose up --build` the default happy path for a clean clone and remove avoidable startup ambiguity; Goal: app, worker, and mirrored persistence come up predictably enough for daily use; Tests: clean-clone Docker smoke, `/healthz`, onboarding page load, graph load; AI-assisted estimate: `0.5-1 day`; Parallelization: serial anchor for all other Docker and docs work.
- `P1.2 Environment contract cleanup` — Explanation: create `.env.example`, document required env vars, and make local machine-specific `.env` unnecessary for first run; Goal: reproducible setup without hidden local knowledge; Tests: run Docker using only documented env flow; AI-assisted estimate: `0.25-0.5 day`; Parallelization: can run after `P1.1` defines the real config shape.
- `P1.3 Demo project dogfood path` — Explanation: add one small example project that exercises discovery, bootstrap, execution state, and structure review; Goal: provide a repeatable dogfood target for docs, tests, and demos; Tests: run project discovery and at least one review plus execution cycle against the example; AI-assisted estimate: `0.5-0.75 day`; Parallelization: can run alongside `P1.2`.
- `P1.4 Personal Codex-agent dogfood loop` — Explanation: validate architect, scout, builder, and QA workflows against one real or example project using the current endpoints and playbooks; Goal: prove the agent story is usable for your own work before public sharing; Tests: successful brief, workflow, and launch flow plus one task handoff cycle; AI-assisted estimate: `0.5-1 day`; Parallelization: starts after `P1.1` and `P1.3`.
- `P1.5 Critical bug sweep from dogfood` — Explanation: fix only issues that block real usage in onboarding, execution authoring, structure review, or run handoff; Goal: personal reliability rather than extra polish; Tests: rerun targeted API and browser flows for each bugfix; AI-assisted estimate: `0.5-1 day`; Parallelization: serial with dogfood findings.

## Phase 2 — Public Repo and Docs Baseline

Phase estimate: `2-3 focused days`

- `P2.1 README rewrite for public readers` — Explanation: rewrite `README.md` around Docker-first quickstart, project purpose, supported modes, test commands, and support boundaries; Goal: a stranger can understand and run the repo without prior context; Tests: follow the README from a clean clone; AI-assisted estimate: `0.5-0.75 day`; Parallelization: can begin once `P1.1` is stable.
- `P2.2 Repo hygiene for public sharing` — Explanation: add `LICENSE` with Apache-2.0, `CONTRIBUTING.md`, `.env.example`, and clean public-facing ignore and config state; Goal: a repo you can share confidently; Tests: manual repo review and clean clone sanity check; AI-assisted estimate: `0.5 day`; Parallelization: parallel with `P2.1`.
- `P2.3 Architecture and maintenance doc` — Explanation: add `docs/architecture.md` describing module boundaries, truth layers, and where new code belongs; Goal: lower contributor onboarding cost and make future maintenance easier; Tests: verify docs match actual module layout and route split; AI-assisted estimate: `0.5 day`; Parallelization: parallel with `P2.1`.
- `P2.4 Public operator docs cleanup` — Explanation: update `docs/workbench_v1_operator_guide.md` and related docs so they read coherently for public readers instead of only internal context; Goal: clearer human and agent workflows; Tests: doc walkthrough against the running app; AI-assisted estimate: `0.25-0.5 day`; Parallelization: parallel after `P2.1`.
- `P2.5 Contribution scaffolding` — Explanation: add issue templates, PR template, and a short “good first areas” section in docs or GitHub templates; Goal: invite useful contributions without heavy triage cost; Tests: manual review of issue and PR scaffolding; AI-assisted estimate: `0.25-0.5 day`; Parallelization: parallel with `P2.2`.

## Phase 3 — Maintainability Hardening

Phase estimate: `4-6 focused days`

- `P3.1 Frontend shell reduction` — Explanation: move remaining graph, review, and network orchestration out of [app.js](/Users/kmkang/Documents/New%20project/static/js/app.js) so it becomes bootstrap and composition only; Goal: easier future updates and a smaller blast radius per feature; Tests: browser E2E, `node --check`, UI smoke for graph, edit, review, and execution paths; AI-assisted estimate: `1.5-2 days`; Parallelization: can run in parallel with `P3.2`.
- `P3.2 Backend orchestration reduction` — Explanation: keep pulling non-orchestrator logic out of [structure_memory.py](/Users/kmkang/Documents/New%20project/src/workbench/structure_memory.py) and [project_profiler.py](/Users/kmkang/Documents/New%20project/src/workbench/project_profiler.py); Goal: future changes land in smaller focused modules; Tests: targeted API, profile, and hybrid suites plus full suite; AI-assisted estimate: `1.5-2 days`; Parallelization: parallel with `P3.1`.
- `P3.3 Shared fixture and test helper pass` — Explanation: add factories and builders for graph, bundle, and `plan_state` fixtures and use them where they reduce duplication; Goal: lower maintenance cost for future tests and clearer diffs; Tests: all affected suites still pass and fixture usage becomes simpler; AI-assisted estimate: `0.75-1 day`; Parallelization: can run after `P3.1` and `P3.2` interfaces stop moving.
- `P3.4 Public contract freeze` — Explanation: freeze endpoint and model expectations for this release, add capability or version metadata to `/api/source-of-truth`, and document the supported surface; Goal: make future changes intentional rather than accidental; Tests: contract tests for endpoint keys and critical shapes; AI-assisted estimate: `0.5-0.75 day`; Parallelization: starts after `P3.2` stabilizes.
- `P3.5 Non-blocking Codex packaging track` — Explanation: if dogfood says it is worthwhile, add a minimal repo-local Codex plugin and skill scaffold that wraps the existing playbooks and agent endpoints; Goal: easier personal agent experimentation before or just after public sharing; Tests: local plugin discovery and one end-to-end skill invocation path; AI-assisted estimate: `0.5-1 day`; Parallelization: parallel with late `P3.3` or `P4.1`; Non-blocking: yes, not required for first public share.

## Phase 4 — Release Confidence

Phase estimate: `2-3 focused days`

- `P4.1 CI hardening pass` — Explanation: keep unit, browser E2E, and persistence integration as required lanes and fix flaky assumptions exposed by Docker-first and public-docs work; Goal: trustworthy contribution safety rails; Tests: green CI on all lanes; AI-assisted estimate: `0.5-0.75 day`; Parallelization: serial gate for release.
- `P4.2 Browser E2E expansion for shipped flows` — Explanation: cover onboarding and import, graph edit basics, execution save and derive, review actions, and at least one agent brief or workflow path; Goal: confidence in the public demo surface; Tests: browser suite itself; AI-assisted estimate: `0.75-1 day`; Parallelization: parallel with `P4.3`.
- `P4.3 Demo walkthrough verification` — Explanation: make the example project and docs match exactly, then validate the README and operator-guide walkthroughs against the running app; Goal: eliminate “docs say X, app does Y” mismatch; Tests: human walkthrough from clean clone; AI-assisted estimate: `0.5 day`; Parallelization: parallel with `P4.2`.
- `P4.4 Docker and contributor smoke matrix` — Explanation: run the documented Docker-first path plus the documented local contributor path on supported environments; Goal: verify the two public entrypoints actually work; Tests: clean-clone Docker run and clean local contributor setup; AI-assisted estimate: `0.5-0.75 day`; Parallelization: after docs settle.

## Phase 5 — Publish Prep

Phase estimate: `0.5-1 day`

- `P5.1 Release notes and positioning` — Explanation: write concise release notes describing what the workbench is, what is stable, what is experimental, and where contributions are welcome; Goal: a clear public framing that matches reality; Tests: manual review against actual release state; AI-assisted estimate: `0.25-0.5 day`; Parallelization: can start once Phase 4 is nearly complete.
- `P5.2 Final repo pass and tag prep` — Explanation: do a final sweep for version alignment, stale docs, unsupported claims, and release-blocking rough edges; Goal: a clean public first impression; Tests: rerun the final smoke checklist and full CI; AI-assisted estimate: `0.25-0.5 day`; Parallelization: final serial gate.

## Public APIs, Interfaces, and Types

Keep the current truth model and endpoint model intact for this release.

Publicly supported backend surfaces for the share:

- `/api/source-of-truth`
- `/api/plan-state`
- `/api/agent-contracts`
- `/api/agent-contracts/{id}/brief`
- `/api/agent-contracts/{id}/workflow`
- `/api/agent-contracts/{id}/launch`
- structure scan, review, rebase, and merge endpoints

Publicly supported runtime modes:

- Docker Compose: primary
- local Python: contributor path

Publicly supported platforms:

- macOS
- Linux

Do not introduce new core truth layers or a major type redesign in this shipping cycle.

## Test Scenarios That Must Appear in Both Planning and Validation

- clean-clone Docker startup
- onboarding, discovery, and bootstrap flow
- graph save and latest plan flow
- execution authoring flow
- structure scan, review, rebase, and merge flow
- agent brief, workflow, launch, and handoff flow
- persistence integration round trip
- docs-to-demo walkthrough parity

## Assumptions and Defaults

- Output files are:
  - `docs/shipping_plan.md`
  - `docs/shipping_tasks.md`
- Public share target is a contributor-ready GitHub repo, not a polished mass-market product
- Docker-first is the default support path
- Apache-2.0 is the chosen license
- Codex-native plugin packaging is useful for your own dogfooding, but is not a blocker for the first public GitHub share
