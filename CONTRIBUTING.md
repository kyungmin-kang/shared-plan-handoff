# Contributing

Thanks for helping improve `Shared Plan Handoff`.

This repo ships the `notion-pm-bridge` package and its repo-first planning workflow. The intended operating model is:

1. plans are approved in the repo
2. approved plans are decomposed and reviewed in the repo
3. Notion is the downstream execution surface

## Before You Start

- Use Python `3.11+`
- Prefer the repo-local virtualenv, not your global Python
- Prefer Codex Apps Notion MCP for interactive Notion work
- Treat REST as fallback for debug, CI, or headless automation

## Local Setup

```bash
./scripts/bootstrap_venv.sh
source .venv/bin/activate
```

The bootstrap script requires Python 3.11+ and will auto-select a compatible interpreter when possible. To force a specific interpreter:

```bash
SHARED_PLAN_HANDOFF_PYTHON=/path/to/python3.11 ./scripts/bootstrap_venv.sh
```

If you want REST fallback locally, copy `.env.example` to `.env` and fill in the Notion settings. For normal chat-first work with a connected Notion MCP app, the REST token is optional.

The CLI reads `.env` directly, so contributors should not need to `source .env` in the shell.

## Core Workflow

For a new planned project:

1. create or update the approved plan markdown
2. optionally create a companion task sheet
3. register the plan into `plans/<project_slug>/`
4. decompose the plan
5. review the decomposition
6. only then build or reconcile Notion

For a messy in-flight project:

1. run the rescue flow
2. write `current-state.md`, `detailed-scan.md`, and `recovery-plan.md`
3. approve the recovery plan as the next plan revision
4. re-enter the normal handoff flow

## Tests

Run these before you consider a change ready:

```bash
./.venv/bin/python -m unittest discover -s tests
python3 -m compileall src tests
```

## Contribution Expectations

- Keep planning repo-first; do not move upstream planning into Notion
- Preserve human readability in Notion surfaces
- Prefer incremental changes over large rewrites
- Add or update tests when changing bridge behavior
- Document product-facing workflow changes in `README.md`

## Pull Request Scope

Good PRs here usually do one of these well:

- improve the repo-first handoff pipeline
- improve the Notion execution surface
- fix state isolation, reconciliation, or view usability bugs
- improve contributor and operator documentation

If a change alters the PM model, explain:

- what the new mental model is
- what a human PM will see in Notion
- how the repo artifacts and Notion data stay aligned
