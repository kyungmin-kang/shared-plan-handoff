# Plans Directory

Repo-tracked project handoff artifacts live here.

Each project should use:

```text
plans/<project_slug>/
  approved-plan.md
  current-state.md
  detailed-scan.md
  recovery-plan.md
  task-graph.json
  decomposition-review.md
  handoff.json
  revisions/
    r001-approved-plan.md
    r001-task-graph.json
    r001-decomposition-review.md
    r001-handoff.json
    ...
```

`approved-plan.md` is the current approved pre-Notion source artifact.
`current-state.md`, `detailed-scan.md`, and `recovery-plan.md` support rescue and rethink flows for messy in-flight projects.
Use the quick scan first, then the detailed scan to make the project goal, preserve set, cleanup set, completion target, and maintenance baseline explicit before approving a new plan.
Keep `recovery-plan.md` split into:
- a human-first `Rescue Understanding` section
- a task-ready `Bring-It-Home Workstreams` section

Only the `Bring-It-Home Workstreams` section should become execution work in Notion.
`revisions/` preserves the approved-plan and handoff history across replans.

Nothing should be pushed into Notion until:

- the approved plan exists
- the decomposition exists
- the reviewer report exists
- the reviewer status is `pass`
- a human explicitly asks Codex to build or reconcile the Notion workspace
