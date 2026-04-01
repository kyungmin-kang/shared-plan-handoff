# Release Readiness

This document is the Phase 5 publish-readiness sweep for
`ProjectManagerVisualization`.

## Release Goal

Ship the repository as:

- a public GitHub repo another developer can understand, run, and contribute to
- a local Codex plugin workflow that reinforces the repo-first plan-to-Notion
  execution loop

## What Was Checked

### Repo surfaces

- `README.md` matches the current repo-first and MCP-first workflow.
- `LICENSE` is present and referenced by package metadata.
- `CONTRIBUTING.md` exists and matches the current local-dev expectations.
- `.gitignore` excludes local-only state, venv output, and common build noise.
- `docs/shipping_plan.md`, `docs/shipping_tasks.md`, and
  `docs/local_codex_plugin.md` all describe the same operating model.

### Product surfaces

- The coordinator remains the primary repo-first orchestration surface.
- The `pm` CLI is still documented as a fallback debug and admin interface.
- The repo-local plugin exists under `plugins/project-manager-visualization/`.
- The repo marketplace entry exists at `.agents/plugins/marketplace.json`.
- The plugin uses the same repo-first workflow instead of introducing a second
  planning model.

### Notion surfaces

- A fresh `ProjectManagerVisualization` workspace exists in Notion.
- The project page points to `Tasks`, `Phases`, and `Docs` in that order.
- Phase 1 through Phase 4 are complete in the live workspace.
- The Docs library now includes the local plugin guide.

## Systematic Issues Fixed During This Sweep

- Fixed a stale hardcoded `Phase Group` option set in the bridge so the task DB
  can track the actual phase labels from the current handoff instead of
  inheriting labels from an older project.
- Confirmed MCP-first remains the default transport in both code and docs, with
  REST retained only as fallback.
- Treated git branch creation failure as a sandbox/system constraint, not a
  one-off, and used the required elevated path for nested `codex/...` refs.

## Known Limitations

- Notion inline linked-database blocks still require a human to create the
  linked views manually. Agents can maintain the underlying databases once those
  views exist.
- The repo-local plugin is local-install only for now; marketplace publication
  is still out of scope for this release.
- Some Notion connector responses render underscore-heavy `Repo Path` values
  awkwardly, even though the stored content is still usable.

## Release Blockers

None currently identified for the scoped first public share.

## Ready For

- final regression and QA pass
- public GitHub publication
- continued dogfooding from the shipped Notion workspace
