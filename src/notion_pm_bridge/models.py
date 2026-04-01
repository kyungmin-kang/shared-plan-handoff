from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ProjectSpec:
    identifier: str
    name: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectSpec":
        return cls(
            identifier=str(payload.get("identifier", "")),
            name=str(payload.get("name", "")),
            description=str(payload.get("description", "")),
        )


@dataclass(slots=True)
class DocSpec:
    title: str
    content: str
    parent_title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DocSpec":
        return cls(
            title=str(payload.get("title", "")),
            content=str(payload.get("content", "")),
            parent_title=str(payload["parent_title"]) if payload.get("parent_title") is not None else None,
        )


@dataclass(slots=True)
class TaskSpec:
    key: str
    title: str
    description: str = ""
    type: str = "Task"
    status: str | None = None
    priority: str | None = None
    parent_key: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    assignee: str | None = None
    progress: int | None = None
    dependencies: list[str] = field(default_factory=list)
    execution_mode: str | None = None
    parallelizable: bool | None = None
    repo_ref: str | None = None
    branch_ref: str | None = None
    pr_url: str | None = None
    commit_sha: str | None = None
    notes: str | None = None
    plan_revision: str | None = None
    superseded_by_revision: str | None = None
    agent_role: str | None = None
    preferred_skill: str | None = None
    sequence: int | None = None
    human_estimate_hours: int | None = None
    agent_estimate_hours: int | None = None
    source_revision: str | None = None
    decomposition_review: str | None = None
    review_status: str | None = None
    completion_state: str | None = None
    parallel_group: str | None = None
    parallel_with: list[str] = field(default_factory=list)
    phase_group: str | None = None
    execution_slot: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskSpec":
        return cls(
            key=str(payload.get("key", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            type=str(payload.get("type", "Task")),
            status=str(payload["status"]) if payload.get("status") is not None else None,
            priority=str(payload["priority"]) if payload.get("priority") is not None else None,
            parent_key=str(payload["parent_key"]) if payload.get("parent_key") is not None else None,
            start_date=str(payload["start_date"]) if payload.get("start_date") is not None else None,
            due_date=str(payload["due_date"]) if payload.get("due_date") is not None else None,
            assignee=str(payload["assignee"]) if payload.get("assignee") is not None else None,
            progress=int(payload["progress"]) if payload.get("progress") is not None else None,
            dependencies=[str(item) for item in payload.get("dependencies", [])],
            execution_mode=str(payload["execution_mode"]) if payload.get("execution_mode") is not None else None,
            parallelizable=payload.get("parallelizable"),
            repo_ref=str(payload["repo_ref"]) if payload.get("repo_ref") is not None else None,
            branch_ref=str(payload["branch_ref"]) if payload.get("branch_ref") is not None else None,
            pr_url=str(payload["pr_url"]) if payload.get("pr_url") is not None else None,
            commit_sha=str(payload["commit_sha"]) if payload.get("commit_sha") is not None else None,
            notes=str(payload["notes"]) if payload.get("notes") is not None else None,
            plan_revision=str(payload["plan_revision"]) if payload.get("plan_revision") is not None else None,
            superseded_by_revision=str(payload["superseded_by_revision"]) if payload.get("superseded_by_revision") is not None else None,
            agent_role=str(payload["agent_role"]) if payload.get("agent_role") is not None else None,
            preferred_skill=str(payload["preferred_skill"]) if payload.get("preferred_skill") is not None else None,
            sequence=int(payload["sequence"]) if payload.get("sequence") is not None else None,
            human_estimate_hours=int(payload["human_estimate_hours"]) if payload.get("human_estimate_hours") is not None else None,
            agent_estimate_hours=int(payload["agent_estimate_hours"]) if payload.get("agent_estimate_hours") is not None else None,
            source_revision=str(payload["source_revision"]) if payload.get("source_revision") is not None else None,
            decomposition_review=str(payload["decomposition_review"]) if payload.get("decomposition_review") is not None else None,
            review_status=str(payload["review_status"]) if payload.get("review_status") is not None else None,
            completion_state=str(payload["completion_state"]) if payload.get("completion_state") is not None else None,
            parallel_group=str(payload["parallel_group"]) if payload.get("parallel_group") is not None else None,
            parallel_with=[str(item) for item in payload.get("parallel_with", [])],
            phase_group=str(payload["phase_group"]) if payload.get("phase_group") is not None else None,
            execution_slot=str(payload["execution_slot"]) if payload.get("execution_slot") is not None else None,
        )


@dataclass(slots=True)
class PlanRevisionSpec:
    revision_key: str
    revision_number: int
    status: str = "draft"
    title: str = ""
    summary: str = ""
    brief: str = ""
    markdown: str = ""
    tasks: list[TaskSpec] = field(default_factory=list)
    source_revision_key: str | None = None
    change_request: str | None = None
    created_at: str | None = None
    approved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_key": self.revision_key,
            "revision_number": self.revision_number,
            "status": self.status,
            "title": self.title,
            "summary": self.summary,
            "brief": self.brief,
            "markdown": self.markdown,
            "tasks": [task.to_dict() for task in self.tasks],
            "source_revision_key": self.source_revision_key,
            "change_request": self.change_request,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
        }


@dataclass(slots=True)
class PlanningDraft:
    project: ProjectSpec
    brief: str
    prd_markdown: str
    architecture_markdown: str
    revision_markdown: str
    tasks: list[TaskSpec] = field(default_factory=list)
    summary: str = ""

    def to_revision(self, *, revision_key: str, revision_number: int, status: str = "draft", created_at: str | None = None) -> PlanRevisionSpec:
        title = f"Implementation Plan Revision {revision_number}"
        return PlanRevisionSpec(
            revision_key=revision_key,
            revision_number=revision_number,
            status=status,
            title=title,
            summary=self.summary,
            brief=self.brief,
            markdown=self.revision_markdown,
            tasks=list(self.tasks),
            created_at=created_at,
        )


@dataclass(slots=True)
class PlanSpec:
    project: ProjectSpec
    docs: list[DocSpec] = field(default_factory=list)
    tasks: list[TaskSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "docs": [doc.to_dict() for doc in self.docs],
            "tasks": [task.to_dict() for task in self.tasks],
        }


@dataclass(slots=True)
class TaskGraphSpec:
    project: ProjectSpec
    source_plan_path: str
    handoff_id: str = ""
    created_at: str | None = None
    summary: str = ""
    tasks: list[TaskSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "source_plan_path": self.source_plan_path,
            "handoff_id": self.handoff_id,
            "created_at": self.created_at,
            "summary": self.summary,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskGraphSpec":
        return cls(
            project=ProjectSpec.from_dict(dict(payload.get("project", {}))),
            source_plan_path=str(payload.get("source_plan_path", "")),
            handoff_id=str(payload.get("handoff_id", "")),
            created_at=str(payload["created_at"]) if payload.get("created_at") is not None else None,
            summary=str(payload.get("summary", "")),
            tasks=[TaskSpec.from_dict(dict(item)) for item in payload.get("tasks", [])],
        )


@dataclass(slots=True)
class DecompositionReviewSpec:
    project_identifier: str
    source_plan_path: str
    task_graph_path: str
    review_status: str
    findings: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    reviewed_at: str | None = None
    reviewer: str = "reviewer-agent"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecompositionReviewSpec":
        return cls(
            project_identifier=str(payload.get("project_identifier", "")),
            source_plan_path=str(payload.get("source_plan_path", "")),
            task_graph_path=str(payload.get("task_graph_path", "")),
            review_status=str(payload.get("review_status", "")),
            findings=[str(item) for item in payload.get("findings", [])],
            required_fixes=[str(item) for item in payload.get("required_fixes", [])],
            reviewed_at=str(payload["reviewed_at"]) if payload.get("reviewed_at") is not None else None,
            reviewer=str(payload.get("reviewer", "reviewer-agent")),
        )


@dataclass(slots=True)
class HandoffSpec:
    handoff_id: str
    project: ProjectSpec
    source_plan_path: str
    task_graph_path: str
    review_path: str
    review_status: str
    created_at: str | None = None
    summary: str = ""
    docs: list[DocSpec] = field(default_factory=list)
    tasks: list[TaskSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "project": self.project.to_dict(),
            "source_plan_path": self.source_plan_path,
            "task_graph_path": self.task_graph_path,
            "review_path": self.review_path,
            "review_status": self.review_status,
            "created_at": self.created_at,
            "summary": self.summary,
            "docs": [doc.to_dict() for doc in self.docs],
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HandoffSpec":
        return cls(
            handoff_id=str(payload.get("handoff_id", "")),
            project=ProjectSpec.from_dict(dict(payload.get("project", {}))),
            source_plan_path=str(payload.get("source_plan_path", "")),
            task_graph_path=str(payload.get("task_graph_path", "")),
            review_path=str(payload.get("review_path", "")),
            review_status=str(payload.get("review_status", "")),
            created_at=str(payload["created_at"]) if payload.get("created_at") is not None else None,
            summary=str(payload.get("summary", "")),
            docs=[DocSpec.from_dict(dict(item)) for item in payload.get("docs", [])],
            tasks=[TaskSpec.from_dict(dict(item)) for item in payload.get("tasks", [])],
        )


@dataclass(slots=True)
class TaskSnapshot:
    key: str
    page_id: str
    title: str
    status: str
    type: str | None = None
    priority: str | None = None
    assignee: str | None = None
    parent_page_ids: list[str] = field(default_factory=list)
    dependency_page_ids: list[str] = field(default_factory=list)
    start_date: str | None = None
    due_date: str | None = None
    progress: int | None = None
    parallelizable: bool | None = None
    plan_revision: str | None = None
    superseded_by_revision: str | None = None
    agent_role: str | None = None
    preferred_skill: str | None = None
    sequence: int | None = None
    human_estimate_hours: int | None = None
    agent_estimate_hours: int | None = None
    source_revision: str | None = None
    decomposition_review: str | None = None
    review_status: str | None = None
    completion_state: str | None = None
    parallel_group: str | None = None
    parallel_with: list[str] = field(default_factory=list)
    phase_group: str | None = None
    execution_slot: str | None = None
    updated_at: str | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BridgeState:
    project_identifier: str = ""
    project_page_id: str = ""
    project_page_url: str = ""
    phases_database_id: str = ""
    phases_data_source_id: str = ""
    tasks_database_id: str = ""
    tasks_data_source_id: str = ""
    docs_database_id: str = ""
    docs_data_source_id: str = ""
    docs_pages: dict[str, str] = field(default_factory=dict)
    revision_pages: dict[str, str] = field(default_factory=dict)
    revision_numbers: dict[str, int] = field(default_factory=dict)
    revision_statuses: dict[str, str] = field(default_factory=dict)
    active_revision_key: str = ""
    active_revision_page_id: str = ""
    approved_plan_path: str = ""
    approved_plan_revision_key: str = ""
    task_graph_path: str = ""
    review_path: str = ""
    handoff_path: str = ""
    current_state_path: str = ""
    recovery_plan_path: str = ""
    detailed_scan_path: str = ""
    active_handoff_id: str = ""
    active_review_status: str = ""
    phase_pages_by_key: dict[str, str] = field(default_factory=dict)
    task_pages_by_key: dict[str, str] = field(default_factory=dict)
    titles_by_key: dict[str, str] = field(default_factory=dict)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    snapshot: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BridgeState":
        return cls(
            project_identifier=str(payload.get("project_identifier", "")),
            project_page_id=str(payload.get("project_page_id", "")),
            project_page_url=str(payload.get("project_page_url", "")),
            phases_database_id=str(payload.get("phases_database_id", "")),
            phases_data_source_id=str(payload.get("phases_data_source_id", "")),
            tasks_database_id=str(payload.get("tasks_database_id", "")),
            tasks_data_source_id=str(payload.get("tasks_data_source_id", "")),
            docs_database_id=str(payload.get("docs_database_id", "")),
            docs_data_source_id=str(payload.get("docs_data_source_id", "")),
            docs_pages={str(k): str(v) for k, v in payload.get("docs_pages", {}).items()},
            revision_pages={str(k): str(v) for k, v in payload.get("revision_pages", {}).items()},
            revision_numbers={str(k): int(v) for k, v in payload.get("revision_numbers", {}).items()},
            revision_statuses={str(k): str(v) for k, v in payload.get("revision_statuses", {}).items()},
            active_revision_key=str(payload.get("active_revision_key", "")),
            active_revision_page_id=str(payload.get("active_revision_page_id", "")),
            approved_plan_path=str(payload.get("approved_plan_path", "")),
            approved_plan_revision_key=str(payload.get("approved_plan_revision_key", "")),
            task_graph_path=str(payload.get("task_graph_path", "")),
            review_path=str(payload.get("review_path", "")),
            handoff_path=str(payload.get("handoff_path", "")),
            current_state_path=str(payload.get("current_state_path", "")),
            recovery_plan_path=str(payload.get("recovery_plan_path", "")),
            detailed_scan_path=str(payload.get("detailed_scan_path", "")),
            active_handoff_id=str(payload.get("active_handoff_id", "")),
            active_review_status=str(payload.get("active_review_status", "")),
            phase_pages_by_key={str(k): str(v) for k, v in payload.get("phase_pages_by_key", {}).items()},
            task_pages_by_key={str(k): str(v) for k, v in payload.get("task_pages_by_key", {}).items()},
            titles_by_key={str(k): str(v) for k, v in payload.get("titles_by_key", {}).items()},
            dependencies={
                str(k): [str(item) for item in value]
                for k, value in payload.get("dependencies", {}).items()
            },
            snapshot={str(k): dict(v) for k, v in payload.get("snapshot", {}).items()},
            artifacts={str(k): str(v) for k, v in payload.get("artifacts", {}).items()},
        )

    @classmethod
    def load(cls, path: Path) -> "BridgeState":
        if not path.exists():
            return cls()
        import json

        return cls.from_dict(json.loads(path.read_text()))

    def save(self, path: Path) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
