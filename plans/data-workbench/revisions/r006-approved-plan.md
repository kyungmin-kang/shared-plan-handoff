# Shipping Plan: Dogfood to Contributor-Ready GitHub Release

## Goal

Ship a Docker-first, contributor-ready public GitHub project that you can already use in your own work.

Make the repo understandable, runnable, and safe to contribute to without turning this release into a full public-product polish cycle.

## Scope

In scope:

- Docker-first setup
- stable standalone workbench flows
- stable execution/review/agent API surface
- public docs and contributor docs
- CI confidence
- enough maintainability cleanup that future changes are not painful

Out of scope for this release:

- hosted SaaS or deploy product
- multi-user or auth
- Windows first-class support
- perfect parity between local and mirrored persistence
- major execution-model redesign
- public release blocked on Codex plugin polish

## Summary

The current product shape is already valid:

- `graph` is structure truth
- bundles and review are proposal truth
- `plan_state` is execution truth

Shipping work is now about:

- Docker-first reliability
- docs and public repo hygiene
- keeping remaining hotspots maintainable
- freezing the current contract surface
- validating the end-to-end flows others will actually use

This is a contributor-ready public GitHub release target, not a mass-market product polish cycle. The release should be good enough for your own real project use first, then clear and trustworthy enough that others can clone it, run it, understand it, and contribute safely.

## Milestone 1: Dogfood Ready

Duration: `4-7 focused days with AI-agent help`

Goal:

- use the workbench yourself in real projects with confidence
- validate the human loop and the agent-enhanced loop before public sharing

Exit criteria:

- Docker Compose clean-clone startup works
- onboarding, discovery, and bootstrap work on a demo project
- execution panel flows are reliable enough for real use
- structure scan, review, rebase, and merge work end to end
- agent APIs and playbooks are good enough for your own Codex-agent experiments

Maintenance rule:

- no new logic should be added to monolith hotspots unless it is part of an extraction or clear simplification

## Milestone 2: Contributor-Ready GitHub Share

Duration: `7-12 focused days with AI-agent help`

Goal:

- strangers can clone the repo, run it with Docker, understand the architecture, and safely contribute

Exit criteria:

- `README.md` is public-facing and accurate
- Apache-2.0 license is present
- contributor docs exist
- CI is green in unit, browser, and persistence lanes
- demo or example flow matches docs
- remaining large files are reduced enough that future updates are not intimidating

## Public Interfaces and Stability

Freeze the following as the public support surface for this share:

- `/api/source-of-truth`
- `/api/plan-state`
- `/api/agent-contracts`
- `/api/agent-contracts/{id}/brief`
- `/api/agent-contracts/{id}/workflow`
- `/api/agent-contracts/{id}/launch`
- existing structure scan, review, rebase, and merge endpoints

Do not add new public endpoints unless they are needed to fix a release blocker.

Add lightweight capability and version metadata to `/api/source-of-truth` during this release so external tooling can detect contract support without guessing.

Supported runtime modes for this share:

- Docker Compose: primary
- local Python setup: contributor path

Supported local platforms for this share:

- macOS
- Linux

## Maintainability Before Ship

Keep [app.py](/Users/kmkang/Documents/New%20project/src/workbench/app.py) as a thin entrypoint.

Continue reducing the remaining hotspots:

- [app.js](/Users/kmkang/Documents/New%20project/static/js/app.js)
- [structure_memory.py](/Users/kmkang/Documents/New%20project/src/workbench/structure_memory.py)
- [project_profiler.py](/Users/kmkang/Documents/New%20project/src/workbench/project_profiler.py)

Document and preserve module boundaries for:

- frontend shell and bootstrap
- graph editing
- execution UI
- review UI
- profiling and context building
- reconciliation and patch helpers

Add shared test fixtures and factories so future work does not keep enlarging the large API test files.

Use this release to make future maintenance easier by enforcing a simple rule: new work should land in focused modules with clear ownership instead of expanding orchestration files.

## Release Gates

The release is ready only when all of the following are true:

- Docker-first quickstart succeeds from a clean clone
- `README.md`, architecture docs, and contributing docs are complete
- unit suite passes
- browser E2E passes
- persistence integration passes
- demo or example project walkthrough matches docs
- no unresolved blocker remains in shipping-critical paths

## Deferred After Public Share

- first-class Windows support
- deeper Codex plugin polish if the dogfood track is not ready
- broader UI polish that is not needed for contributor clarity
- hosted deployment concerns
- stronger multi-user operational features

## Assumptions and Defaults

- Public share target is a contributor-ready GitHub repo, not a polished mass-market product
- Docker-first is the default support path
- Apache-2.0 is the chosen license
- Codex-native plugin packaging is useful for your own dogfooding, but is not a blocker for the first public GitHub share
- The current truth model is stable enough to ship without introducing new core layers or a major redesign
