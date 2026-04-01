---
name: pm-rescue
description: Rescue an in-flight project that lacks a clean current plan by generating a quick current-state snapshot, a deeper rescue scan, and a recovery-plan draft before re-entering the normal handoff pipeline.
---

# PM Rescue

Use this plugin skill when a project is already underway, tracking is messy, and
the team needs to re-establish a single approved plan before Notion execution
tracking can stay reliable.

## Outputs

- `../../../../plans/<project_slug>/current-state.md`
- `../../../../plans/<project_slug>/detailed-scan.md`
- `../../../../plans/<project_slug>/recovery-plan.md`

## Workflow

1. Run a quick scan first to capture the current known state of the project.
2. Run a deeper rescue scan that makes the project goal explicit and separates
   essential files, work-in-progress, archived artifacts, completion
   requirements, and maintenance requirements.
3. Draft or refresh a recovery plan that can be reviewed, edited, and later
   promoted into the next approved plan revision.
4. Optionally publish the rescue docs to Notion as direct project pages when
   durable shared context would help, but do not create the execution database
   yet.
5. Once the recovery plan is approved, use the normal repo-first handoff:
   register plan, decompose, review, then build or reconcile.

## Rules

- Rescue does not mutate Notion execution work on its own.
- Rescue should always articulate the true project goal before proposing
  execution milestones.
- Rescue docs should stay easy to scan in Notion, so publish them as direct
  project pages rather than burying them under a nested notebook.
