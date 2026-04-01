from __future__ import annotations

import json
import re
from pathlib import Path

from .exceptions import StateError
from .models import DecompositionReviewSpec, HandoffSpec, ProjectSpec, TaskGraphSpec

APPROVED_PLAN_FILENAME = "approved-plan.md"
APPROVED_TASKS_FILENAME = "approved-tasks.md"
TASK_GRAPH_FILENAME = "task-graph.json"
DECOMPOSITION_REVIEW_FILENAME = "decomposition-review.md"
HANDOFF_FILENAME = "handoff.json"
CURRENT_STATE_FILENAME = "current-state.md"
RECOVERY_PLAN_FILENAME = "recovery-plan.md"
DETAILED_SCAN_FILENAME = "detailed-scan.md"

REVIEW_JSON_START = "<!-- pm-bridge-review-json:start -->"
REVIEW_JSON_END = "<!-- pm-bridge-review-json:end -->"


class RepoArtifactStore:
    def __init__(self, plans_dir: Path) -> None:
        self.plans_dir = plans_dir

    def _relative(self, path: Path) -> str:
        try:
            return path.relative_to(Path.cwd()).as_posix()
        except ValueError:
            return path.as_posix()

    def project_slug(self, project_name: str) -> str:
        slug = "".join(char.lower() if char.isalnum() else "-" for char in project_name.strip())
        slug = "-".join(part for part in slug.split("-") if part)
        return slug or "project"

    def project_dir(self, project_ref: str) -> Path:
        return self.plans_dir / self.project_slug(project_ref)

    def revisions_dir(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / "revisions"

    def revision_key(self, number: int) -> str:
        return f"r{number:03d}"

    def _revision_filename(self, revision_key: str, filename: str) -> str:
        return f"{revision_key}-{filename}"

    def revision_artifact_path(self, project_ref: str, revision_key: str, filename: str) -> Path:
        return self.revisions_dir(project_ref) / self._revision_filename(revision_key, filename)

    def approved_plan_path(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / APPROVED_PLAN_FILENAME

    def task_graph_path(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / TASK_GRAPH_FILENAME

    def approved_tasks_path(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / APPROVED_TASKS_FILENAME

    def review_path(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / DECOMPOSITION_REVIEW_FILENAME

    def handoff_path(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / HANDOFF_FILENAME

    def current_state_path(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / CURRENT_STATE_FILENAME

    def recovery_plan_path(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / RECOVERY_PLAN_FILENAME

    def detailed_scan_path(self, project_ref: str) -> Path:
        return self.project_dir(project_ref) / DETAILED_SCAN_FILENAME

    def ensure_project_dir(self, project_ref: str) -> Path:
        directory = self.project_dir(project_ref)
        directory.mkdir(parents=True, exist_ok=True)
        self.revisions_dir(project_ref).mkdir(parents=True, exist_ok=True)
        return directory

    def latest_revision_number(self, project_ref: str) -> int:
        revisions = self.revisions_dir(project_ref)
        if not revisions.exists():
            return 0
        latest = 0
        pattern = re.compile(r"^r(\d{3})-approved-plan\.md$")
        for path in revisions.iterdir():
            match = pattern.match(path.name)
            if match:
                latest = max(latest, int(match.group(1)))
        return latest

    def latest_revision_key(self, project_ref: str) -> str:
        latest = self.latest_revision_number(project_ref)
        if not latest:
            raise StateError(f"No approved plan revisions exist for {self.project_slug(project_ref)}")
        return self.revision_key(latest)

    def register_approved_plan(self, project: ProjectSpec, source_path: str | Path, *, revision_key: str | None = None) -> tuple[str, str, str]:
        source = Path(source_path)
        if not source.exists():
            raise StateError(f"Approved plan file does not exist: {source}")
        content = source.read_text().strip()
        if not content:
            raise StateError("Approved plan file is empty")
        self.ensure_project_dir(project.identifier)
        if not revision_key:
            revision_key = self.revision_key(self.latest_revision_number(project.identifier) + 1)
        destination = self.approved_plan_path(project.identifier)
        destination.write_text(content + "\n")
        versioned = self.revision_artifact_path(project.identifier, revision_key, APPROVED_PLAN_FILENAME)
        versioned.write_text(content + "\n")
        return revision_key, self._relative(destination), self._relative(versioned)

    def register_approved_plan_bundle(
        self,
        project: ProjectSpec,
        source_path: str | Path,
        *,
        task_source_path: str | Path | None = None,
        revision_key: str | None = None,
    ) -> dict[str, str]:
        revision_key, approved_path, approved_versioned_path = self.register_approved_plan(
            project,
            source_path,
            revision_key=revision_key,
        )
        result = {
            "revision_key": revision_key,
            "approved_plan_path": approved_path,
            "approved_plan_versioned_path": approved_versioned_path,
            "approved_tasks_path": "",
            "approved_tasks_versioned_path": "",
        }
        if not task_source_path:
            return result
        task_source = Path(task_source_path)
        if not task_source.exists():
            raise StateError(f"Approved task input file does not exist: {task_source}")
        content = task_source.read_text().strip()
        if not content:
            raise StateError("Approved task input file is empty")
        destination = self.approved_tasks_path(project.identifier)
        destination.write_text(content + "\n")
        versioned = self.revision_artifact_path(project.identifier, revision_key, APPROVED_TASKS_FILENAME)
        versioned.write_text(content + "\n")
        result["approved_tasks_path"] = self._relative(destination)
        result["approved_tasks_versioned_path"] = self._relative(versioned)
        return result

    def load_approved_plan(self, project_ref: str) -> tuple[str, str]:
        path = self.approved_plan_path(project_ref)
        if not path.exists():
            raise StateError(f"Approved plan is missing: {self._relative(path)}")
        content = path.read_text().strip()
        if not content:
            raise StateError(f"Approved plan is empty: {self._relative(path)}")
        return self._relative(path), content

    def load_approved_plan_revision(self, project_ref: str, revision_key: str | None = None) -> tuple[str, str, str]:
        resolved_revision = revision_key or self.latest_revision_key(project_ref)
        path = self.revision_artifact_path(project_ref, resolved_revision, APPROVED_PLAN_FILENAME)
        if not path.exists():
            raise StateError(f"Approved plan revision is missing: {self._relative(path)}")
        content = path.read_text().strip()
        if not content:
            raise StateError(f"Approved plan revision is empty: {self._relative(path)}")
        return resolved_revision, self._relative(path), content

    def load_optional_approved_tasks_revision(self, project_ref: str, revision_key: str | None = None) -> tuple[str, str] | tuple[None, None]:
        resolved_revision = revision_key or self.latest_revision_key(project_ref)
        versioned = self.revision_artifact_path(project_ref, resolved_revision, APPROVED_TASKS_FILENAME)
        path = versioned if versioned.exists() else self.approved_tasks_path(project_ref)
        if not path.exists():
            return None, None
        content = path.read_text().strip()
        if not content:
            return None, None
        return self._relative(path), content

    def write_task_graph(self, project_ref: str, graph: TaskGraphSpec, *, revision_key: str | None = None) -> str:
        path = self.task_graph_path(project_ref)
        self.ensure_project_dir(project_ref)
        payload = json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n"
        path.write_text(payload)
        if revision_key:
            versioned = self.revision_artifact_path(project_ref, revision_key, TASK_GRAPH_FILENAME)
            versioned.write_text(payload)
            return self._relative(versioned)
        return self._relative(path)

    def load_task_graph(self, project_ref: str, revision_key: str | None = None) -> tuple[str, TaskGraphSpec]:
        path = self.revision_artifact_path(project_ref, revision_key, TASK_GRAPH_FILENAME) if revision_key else self.task_graph_path(project_ref)
        if not path.exists():
            raise StateError(f"Task graph is missing: {self._relative(path)}")
        return self._relative(path), TaskGraphSpec.from_dict(json.loads(path.read_text()))

    def render_review_markdown(self, review: DecompositionReviewSpec) -> str:
        lines = [
            "# Decomposition Review",
            "",
            f"- Source plan: `{review.source_plan_path}`",
            f"- Task graph: `{review.task_graph_path}`",
            f"- Review status: `{review.review_status}`",
            f"- Reviewed at: `{review.reviewed_at or ''}`",
            f"- Reviewer: `{review.reviewer}`",
            "",
            "## Findings",
        ]
        if review.findings:
            for finding in review.findings:
                lines.append(f"- {finding}")
        else:
            lines.append("- None")
        lines.extend(["", "## Required Fixes"])
        if review.required_fixes:
            for item in review.required_fixes:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        lines.extend(
            [
                "",
                "## Machine Metadata",
                REVIEW_JSON_START,
                json.dumps(review.to_dict(), indent=2, sort_keys=True),
                REVIEW_JSON_END,
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def write_review(self, project_ref: str, review: DecompositionReviewSpec, *, revision_key: str | None = None) -> str:
        path = self.review_path(project_ref)
        self.ensure_project_dir(project_ref)
        payload = self.render_review_markdown(review)
        path.write_text(payload)
        if revision_key:
            versioned = self.revision_artifact_path(project_ref, revision_key, DECOMPOSITION_REVIEW_FILENAME)
            versioned.write_text(payload)
            return self._relative(versioned)
        return self._relative(path)

    def load_review(self, project_ref: str, revision_key: str | None = None) -> tuple[str, DecompositionReviewSpec]:
        path = self.revision_artifact_path(project_ref, revision_key, DECOMPOSITION_REVIEW_FILENAME) if revision_key else self.review_path(project_ref)
        if not path.exists():
            raise StateError(f"Decomposition review is missing: {self._relative(path)}")
        markdown = path.read_text()
        if REVIEW_JSON_START not in markdown or REVIEW_JSON_END not in markdown:
            raise StateError(f"Decomposition review metadata is missing: {self._relative(path)}")
        pattern = re.compile(
            rf"{re.escape(REVIEW_JSON_START)}\s*(.*?)\s*{re.escape(REVIEW_JSON_END)}",
            re.DOTALL,
        )
        match = pattern.search(markdown)
        if not match:
            raise StateError(f"Could not parse decomposition review metadata: {self._relative(path)}")
        return self._relative(path), DecompositionReviewSpec.from_dict(json.loads(match.group(1)))

    def write_handoff(self, project_ref: str, handoff: HandoffSpec, *, revision_key: str | None = None) -> str:
        path = self.handoff_path(project_ref)
        self.ensure_project_dir(project_ref)
        payload = json.dumps(handoff.to_dict(), indent=2, sort_keys=True) + "\n"
        path.write_text(payload)
        if revision_key:
            versioned = self.revision_artifact_path(project_ref, revision_key, HANDOFF_FILENAME)
            versioned.write_text(payload)
            return self._relative(versioned)
        return self._relative(path)

    def load_handoff(self, project_ref: str, revision_key: str | None = None) -> tuple[str, HandoffSpec]:
        path = self.revision_artifact_path(project_ref, revision_key, HANDOFF_FILENAME) if revision_key else self.handoff_path(project_ref)
        if not path.exists():
            raise StateError(f"Handoff payload is missing: {self._relative(path)}")
        return self._relative(path), HandoffSpec.from_dict(json.loads(path.read_text()))

    def write_current_state(self, project_ref: str, markdown: str) -> str:
        path = self.current_state_path(project_ref)
        self.ensure_project_dir(project_ref)
        path.write_text(markdown.strip() + "\n")
        return self._relative(path)

    def load_current_state(self, project_ref: str) -> tuple[str, str]:
        path = self.current_state_path(project_ref)
        if not path.exists():
            raise StateError(f"Current-state snapshot is missing: {self._relative(path)}")
        return self._relative(path), path.read_text().strip()

    def write_recovery_plan(self, project_ref: str, markdown: str) -> str:
        path = self.recovery_plan_path(project_ref)
        self.ensure_project_dir(project_ref)
        path.write_text(markdown.strip() + "\n")
        return self._relative(path)

    def load_recovery_plan(self, project_ref: str) -> tuple[str, str]:
        path = self.recovery_plan_path(project_ref)
        if not path.exists():
            raise StateError(f"Recovery plan draft is missing: {self._relative(path)}")
        return self._relative(path), path.read_text().strip()

    def write_detailed_scan(self, project_ref: str, markdown: str) -> str:
        path = self.detailed_scan_path(project_ref)
        self.ensure_project_dir(project_ref)
        path.write_text(markdown.strip() + "\n")
        return self._relative(path)

    def load_detailed_scan(self, project_ref: str) -> tuple[str, str]:
        path = self.detailed_scan_path(project_ref)
        if not path.exists():
            raise StateError(f"Detailed rescue scan is missing: {self._relative(path)}")
        return self._relative(path), path.read_text().strip()
