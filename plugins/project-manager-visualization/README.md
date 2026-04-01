# ProjectManagerVisualization Plugin

This plugin packages the repo-first planning workflow from this repository as a
local Codex plugin.

It is intentionally local-first:

- planning artifacts stay in the repo under `plans/`
- Codex Apps Notion MCP is the default Notion mutation path
- the Python bridge remains the deterministic repo, handoff, and reconciliation
  engine
- the `pm` CLI stays available only as a debug and admin fallback

## Bundled Skills

- `notion-pm-bridge`
- `pm-plan-translator`
- `pm-rescue`

## Install Shape

Repo-local plugin files live here:

- `plugins/project-manager-visualization/`
- `.agents/plugins/marketplace.json`

That means a clone of this repo can expose the plugin without copying the skill
bundle elsewhere.

## Prerequisites

- A working Codex session
- The Notion app connected in Codex when you want the MCP-first path
- A workspace opened at the repository root so the plugin can see `plans/`,
  `docs/`, and `src/notion_pm_bridge/`

## Operating Model

Use the plugin for:

- approved plan registration
- decomposition and reviewer-gated handoff generation
- rescue scans for in-flight projects
- building or reconciling the downstream Notion execution workspace
- executing the next ready task while keeping Notion readable for humans

Do not use the plugin to create a separate planning model outside the repo-first
workflow.
