---
name: pm-rescue
description: Rescue an in-flight project that lacks a clean current plan by generating a quick current-state snapshot, a deeper rescue scan, and a recovery-plan draft before re-entering the normal handoff pipeline.
---

# PM Rescue

Use this skill when a project is already underway, tracking is messy, and the team needs to re-establish a single approved plan before Notion execution tracking can stay reliable.

## Outputs

- `plans/<project_slug>/current-state.md`
- `plans/<project_slug>/detailed-scan.md`
- `plans/<project_slug>/recovery-plan.md`

## Workflow

1. Run a quick scan first to capture the current known state of the project, including existing Notion execution state if available.
2. Run a deeper rescue scan that makes the project goal explicit and separates essential files, work-in-progress, archived/noisy artifacts, completion requirements, and maintenance requirements.
3. Draft or refresh a recovery plan that can be reviewed, edited, and eventually promoted into the next approved plan revision.
   - keep `Rescue Understanding` human-first
   - keep `Bring-It-Home Workstreams` explicit and task-ready
   - do not let planning guardrails or context headings turn into execution tasks
4. Optionally publish the rescue docs to Notion when durable shared context would help, but do not create the execution database yet.
5. Once the recovery plan is approved, use the normal repo-first handoff:
   - register approved plan
   - decompose
   - review
   - build or reconcile Notion

## Rules

- Rescue does not mutate Notion execution work on its own.
- Rescue should always articulate the true project goal before proposing execution milestones.
- Rescue docs should stay easy to scan in Notion, so publish them as direct project pages rather than burying them under a nested notebook.
- Rescue is for stabilization, not automatic replanning.
- The recovery plan remains a draft until the human explicitly approves it as the next plan revision.
