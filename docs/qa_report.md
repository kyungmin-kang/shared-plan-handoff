# QA Report

This report captures the final verification pass for the
`ProjectManagerVisualization` Phase 5 release-confidence sweep.

## Scope

The goal of this QA pass is to verify that the shipped workflow still works
after the public-repo, plugin, and Notion dogfood changes landed.

## Checks Run

### Automated

- `./.venv/bin/python -m unittest discover -s tests`
- `python3 -m compileall src tests`
- `./scripts/bootstrap_venv.sh`
- `./.venv/bin/pm --help`

### Product-level sanity

- Verified the repo includes the local Codex plugin scaffold under
  `plugins/project-manager-visualization/`.
- Verified the repo-local marketplace entry still points at the plugin bundle.
- Verified Phase 5 release-confidence docs exist in `docs/`.
- Verified the bridge now derives `Phase Group` options from the current task
  graph instead of stale hardcoded labels from a previous project.

## Result

QA passed for the scoped first public-share release.

## Systematic Issue Found During QA

One regression surfaced during the final test run:

- the task-database schema was still capable of freezing old phase labels
  because one sync path created or refreshed the `Phase Group` select options
  without the current task graph

This was fixed in the bridge by:

- deriving phase labels from current milestone titles
- updating select-property schemas instead of only adding missing properties
- threading the current task list through the task-database ensure path

## Remaining Manual Checks

- Create or refresh the preferred inline linked-database views in Notion if the
  human-facing workspace needs richer inline composition than the connector can
  create directly.
- Perform the actual public GitHub push and sharing step when you are ready to
  publish the repo.

## Release Confidence

For the scoped release, the repo-first handoff, review gate, local plugin
baseline, Notion dogfood workspace, and execution loop are all in a working
state.
