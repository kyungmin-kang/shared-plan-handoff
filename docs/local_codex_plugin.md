# Local Codex Plugin

`Shared Plan Handoff` now ships a repo-local Codex plugin so the
repo-first planning workflow is discoverable without copying the skill bundle
into another workspace by hand.

## What Ships

- plugin root:
  `plugins/shared-plan-handoff/`
- marketplace entry:
  `.agents/plugins/marketplace.json`
- bundled skills:
  - `notion-pm-bridge`
  - `pm-plan-translator`
  - `pm-rescue`

The plugin is intentionally MCP-first:

- use Codex Apps Notion MCP as the normal mutation path
- keep REST as fallback for debug, CI, webhooks, or headless work

## Repo-Local Install

Use this path when you are working directly from this repository.

1. Open the repo root in Codex.
2. Keep the plugin files in place:
   - `plugins/shared-plan-handoff/`
   - `.agents/plugins/marketplace.json`
3. In Codex, install or enable the local plugin entry
   `Shared Plan Handoff` from the repo marketplace.
4. Make sure the Notion app is connected in Codex before asking the plugin to
   build or reconcile Notion workspaces.

## Home-Local Fallback

Use this if you want the plugin available outside the repo-local marketplace.

1. Copy `plugins/shared-plan-handoff/` to
   `~/plugins/shared-plan-handoff/`.
2. Copy the marketplace entry into `~/.agents/plugins/marketplace.json` using
   the same `./plugins/shared-plan-handoff` source path shape.
3. Install the plugin from your home-local marketplace.

## Typical Prompts

- `Use Shared Plan Handoff to register the approved plan and build the reviewed Notion handoff.`
- `Use Shared Plan Handoff to rescue this messy repo and make the true goal explicit before task generation.`
- `Use Shared Plan Handoff to execute the next ready task and keep Notion current.`

## Notes

- The plugin reinforces the existing repo-first workflow; it does not create a
  separate planning model.
- The `pm` CLI remains a fallback admin/debug surface, not the intended everyday
  interface.
