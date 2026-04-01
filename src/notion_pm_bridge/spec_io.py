from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DocSpec, PlanSpec, ProjectSpec, TaskSpec


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected non-empty string for '{key}'")
    return value


def _string_or_none(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Expected string for '{key}'")
    return value


def load_plan_spec(path: str | Path) -> PlanSpec:
    source_path = Path(path)
    data = json.loads(source_path.read_text())

    project_payload = data.get("project")
    if not isinstance(project_payload, dict):
        raise ValueError("PlanSpec requires a 'project' object")

    project = ProjectSpec(
        identifier=_require_string(project_payload, "identifier"),
        name=_require_string(project_payload, "name"),
        description=str(project_payload.get("description", "")),
    )

    docs_payload = data.get("docs")
    if docs_payload is None:
        docs_payload = data.get("wiki_pages", [])
    docs: list[DocSpec] = []
    for raw_doc in docs_payload:
        if not isinstance(raw_doc, dict):
            raise ValueError("docs entries must be objects")
        docs.append(
            DocSpec(
                title=_require_string(raw_doc, "title"),
                content=str(raw_doc.get("content", "")),
                parent_title=_string_or_none(raw_doc, "parent_title"),
            )
        )

    tasks_payload = data.get("tasks")
    if tasks_payload is None:
        tasks_payload = data.get("work_packages", [])

    tasks: list[TaskSpec] = []
    seen_keys: set[str] = set()
    for raw_task in tasks_payload:
        if not isinstance(raw_task, dict):
            raise ValueError("tasks entries must be objects")
        key = _require_string(raw_task, "key")
        if key in seen_keys:
            raise ValueError(f"Duplicate task key '{key}'")
        seen_keys.add(key)

        dependencies = raw_task.get("dependencies", [])
        if dependencies is None:
            dependencies = []
        if not isinstance(dependencies, list):
            raise ValueError(f"dependencies for '{key}' must be a list")

        progress = raw_task.get("progress", raw_task.get("percentage_done"))
        if progress is not None:
            progress = int(progress)

        tasks.append(
            TaskSpec(
                key=key,
                title=_require_string(raw_task, "title"),
                description=str(raw_task.get("description", "")),
                type=str(raw_task.get("type", "Task")),
                status=_string_or_none(raw_task, "status"),
                priority=_string_or_none(raw_task, "priority"),
                parent_key=_string_or_none(raw_task, "parent_key"),
                start_date=_string_or_none(raw_task, "start_date"),
                due_date=_string_or_none(raw_task, "due_date"),
                assignee=_string_or_none(raw_task, "assignee"),
                progress=progress,
                dependencies=[str(item) for item in dependencies],
                execution_mode=_string_or_none(raw_task, "execution_mode"),
                parallelizable=raw_task.get("parallelizable"),
                repo_ref=_string_or_none(raw_task, "repo_ref"),
                branch_ref=_string_or_none(raw_task, "branch_ref"),
                pr_url=_string_or_none(raw_task, "pr_url"),
                commit_sha=_string_or_none(raw_task, "commit_sha"),
                notes=_string_or_none(raw_task, "notes"),
                plan_revision=_string_or_none(raw_task, "plan_revision"),
                superseded_by_revision=_string_or_none(raw_task, "superseded_by_revision"),
                agent_role=_string_or_none(raw_task, "agent_role"),
                preferred_skill=_string_or_none(raw_task, "preferred_skill"),
                sequence=int(raw_task["sequence"]) if raw_task.get("sequence") is not None else None,
                source_revision=_string_or_none(raw_task, "source_revision"),
                decomposition_review=_string_or_none(raw_task, "decomposition_review"),
                review_status=_string_or_none(raw_task, "review_status"),
            )
        )

    return PlanSpec(project=project, docs=docs, tasks=tasks)
