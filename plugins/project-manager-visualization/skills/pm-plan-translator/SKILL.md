---
name: pm-plan-translator
description: Translate an approved implementation plan into a normalized task graph, handoff package, and reviewer-ready decomposition artifacts before anything reaches Notion.
---

# PM Plan Translator

Use this plugin skill when the user has an approved implementation plan and
wants Codex to turn it into structured execution artifacts.

## Inputs

- `../../../../plans/<project_slug>/approved-plan.md`
- optionally `../../../../plans/<project_slug>/approved-tasks.md`
- rescue artifacts when the project is being stabilized before re-entry into the
  normal handoff flow

## Outputs

- `../../../../plans/<project_slug>/task-graph.json`
- `../../../../plans/<project_slug>/handoff.json`
- `../../../../plans/<project_slug>/decomposition-review.md`

## Responsibilities

- Read only the approved repo-tracked plan, not a draft Notion page.
- Produce a unified hierarchy across milestones, tasks, bugs, research, and
  executor-ready units of work.
- Add stable task ids, parent-child links, blocking dependencies, sequence,
  routing, and preferred skills.
- Keep decomposition artifacts repo-tracked and inspectable.
- Write revisioned artifacts under `../../../../plans/<project_slug>/revisions/`
  so replans preserve history.
- Refuse to send work into Notion until reviewer status is `pass`.

## Handoff Rule

Do not build or reconcile the Notion workspace until:

1. the approved plan exists
2. the task graph exists
3. the decomposition review exists
4. the review status is `pass`
5. the user explicitly asks to build or reconcile
