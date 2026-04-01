---
name: pm-plan-translator
description: Translate an approved implementation plan into a normalized task graph, handoff package, and reviewer-ready decomposition artifacts before anything reaches Notion.
---

# PM Plan Translator

Use this skill when the user has an approved implementation plan and wants Codex to turn it into structured execution artifacts.

## Inputs

- `plans/<project_slug>/approved-plan.md`
- optionally `plans/<project_slug>/current-state.md` and `plans/<project_slug>/recovery-plan.md` during rescue or replan work

## Outputs

- `plans/<project_slug>/task-graph.json`
- `plans/<project_slug>/handoff.json`
- `plans/<project_slug>/decomposition-review.md`

## Responsibilities

- Read only the approved repo-tracked plan, not a draft Notion page.
- During rescue mode, use `current-state.md` to produce or refine `recovery-plan.md`, then wait for the approved revision before decomposition.
- Produce a unified hierarchy across milestones, epics, tasks, subtasks, bugs, and research items.
- Add stable task ids, parent-child links, blocking dependencies, sequence, routing, and preferred skills.
- Keep decomposition artifacts repo-tracked and inspectable.
- Write revisioned artifacts under `plans/<project_slug>/revisions/` so replans preserve history.
- Refuse to send work into Notion until reviewer status is `pass`.

## Review Standard

The decomposition must be checked for:

- missing or contradictory dependencies
- broken hierarchy for Board and Timeline views
- unclear ownership or routing
- missing milestone coverage
- tasks that are too large or too granular
- work that should stay outside Notion

## Handoff Rule

Do not build or reconcile the Notion workspace until:

1. the approved plan exists
2. the task graph exists
3. the decomposition review exists
4. the review status is `pass`
5. the user explicitly asks to build or reconcile
