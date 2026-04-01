from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from pathlib import Path
from typing import Any

from .bridge import BridgeService
from .exceptions import BridgeError, StateError
from .models import (
    BridgeState,
    DecompositionReviewSpec,
    DocSpec,
    HandoffSpec,
    PlanRevisionSpec,
    PlanSpec,
    PlanningDraft,
    ProjectSpec,
    TaskGraphSpec,
    TaskSpec,
)
from .repo_artifacts import RepoArtifactStore

REVISION_JSON_START = "<!-- pm-bridge-revision-json:start -->"
REVISION_JSON_END = "<!-- pm-bridge-revision-json:end -->"
DECOMPOSITION_REVIEW_FILENAME = "decomposition-review.md"


class CodexNotionWorkflowCoordinator:
    def __init__(self, bridge: BridgeService) -> None:
        self.bridge = bridge
        self.client = bridge.client
        self.config = bridge.config
        self.artifacts = RepoArtifactStore(self.config.plans_dir)

    def _emit_progress(self, message: str) -> None:
        self.bridge._emit_progress(message)

    def _load_state(self) -> BridgeState:
        return self.bridge._load_state()

    def _save_state(self, state: BridgeState) -> None:
        self.bridge._save_state(state)

    def _utc_now(self) -> str:
        return self.bridge._utc_now()

    def _slugify(self, value: str) -> str:
        return self.bridge._slugify(value)

    def _project_spec(self, project_name: str, brief_text: str = "") -> ProjectSpec:
        return ProjectSpec(
            identifier=self._slugify(project_name),
            name=project_name.strip(),
            description=brief_text.strip() or f"{project_name.strip()} project workspace managed by Codex in Notion.",
        )

    def _base_docs(self, draft: PlanningDraft) -> list[DocSpec]:
        return [
            DocSpec(title="Brief", content=draft.brief.strip()),
            DocSpec(title="PRD", content=draft.prd_markdown.strip()),
            DocSpec(title="Architecture", content=draft.architecture_markdown.strip()),
            DocSpec(title="Plan Index", content="Implementation-plan revisions will be tracked here."),
            DocSpec(
                title="Execution Runbook",
                content=(
                    "Ask Codex to draft or revise implementation plans in Notion.\n\n"
                    "Approve a revision before asking Codex to build or reconcile the execution workspace.\n\n"
                    "After approval, ask Codex to execute the next ready tasks while keeping Notion updated."
                ),
            ),
            DocSpec(title="Dashboard Snapshot", content="Codex will publish the latest task dashboard here."),
        ]

    def _default_draft(self, brief_text: str, project_name: str) -> PlanningDraft:
        project = self._project_spec(project_name, brief_text)
        project_label = project.name
        prd = (
            f"# Product Requirements Draft\n\n"
            f"## Product Brief\n{brief_text.strip()}\n\n"
            "## Goals\n"
            "- Clarify the end-user outcome and success criteria.\n"
            "- Identify the minimum lovable v1.\n"
            "- Preserve room for iteration after the first release.\n\n"
            "## Scope Notes\n"
            "- Confirm must-have capabilities.\n"
            "- Capture what is intentionally out of scope for v1.\n"
        )
        architecture = (
            f"# Architecture Draft\n\n"
            f"## Context\nThis architecture supports `{project_label}`.\n\n"
            "## Initial Design\n"
            "- Define the primary application surfaces and core data model.\n"
            "- Break the implementation into foundation, product surface, and operations concerns.\n"
            "- Highlight integration points, risk areas, and rollout constraints.\n"
        )
        revision = (
            f"# Draft Implementation Plan\n\n"
            f"## Objective\nBuild `{project_label}` based on the brief below.\n\n"
            f"## Brief\n{brief_text.strip()}\n\n"
            "## Proposed Workstreams\n"
            "1. Product framing and UX definition.\n"
            "2. Architecture and technical foundation.\n"
            "3. Core feature implementation.\n"
            "4. Validation, polish, and release readiness.\n\n"
            "## Open Questions\n"
            "- Final scope and milestones to confirm during review.\n"
            "- Any external integrations, compliance, or deployment constraints.\n"
        )
        tasks = [
            TaskSpec(
                key="scope-prd",
                title="Finalize scope and PRD",
                description="Turn the brief into an approved product scope and clarified requirements.",
                type="Research",
                status="Ready",
                priority="High",
                execution_mode="pair",
                parallelizable=False,
            ),
            TaskSpec(
                key="architecture-foundation",
                title="Design architecture and foundation",
                description="Define the technical approach, core modules, and implementation foundation.",
                type="Task",
                status="Ready",
                priority="High",
                execution_mode="agent",
                parallelizable=False,
                dependencies=["scope-prd"],
            ),
            TaskSpec(
                key="build-v1",
                title="Implement v1 feature set",
                description="Build the approved v1 scope on top of the agreed architecture.",
                type="Feature",
                status="Ready",
                priority="Normal",
                execution_mode="agent",
                parallelizable=True,
                dependencies=["architecture-foundation"],
            ),
            TaskSpec(
                key="validate-release",
                title="Validate and prepare release",
                description="Run validation, polish, and release-readiness work for the first delivery.",
                type="Task",
                status="Ready",
                priority="Normal",
                execution_mode="agent",
                parallelizable=True,
                dependencies=["build-v1"],
            ),
        ]
        return PlanningDraft(
            project=project,
            brief=brief_text.strip(),
            prd_markdown=prd,
            architecture_markdown=architecture,
            revision_markdown=revision,
            tasks=tasks,
            summary=f"Initial implementation draft for {project_label}.",
        )

    def _revision_key(self, number: int) -> str:
        return f"rev-{number:03d}"

    def _next_revision_number(self, state: BridgeState) -> int:
        if not state.revision_numbers:
            return 1
        return max(state.revision_numbers.values()) + 1

    def _revision_title(self, revision: PlanRevisionSpec) -> str:
        return f"Implementation Plan R{revision.revision_number:02d} ({revision.status.title()})"

    def _display_project_name(self, project_ref: str | None, project_slug: str) -> str:
        if project_ref and self._slugify(project_ref) != project_slug:
            return project_ref.strip()
        return project_slug.replace("-", " ").title()

    def _render_revision_markdown(self, revision: PlanRevisionSpec) -> str:
        metadata = {
            "revision_key": revision.revision_key,
            "revision_number": revision.revision_number,
            "status": revision.status,
            "source_revision_key": revision.source_revision_key,
            "change_request": revision.change_request,
            "created_at": revision.created_at,
            "approved_at": revision.approved_at,
            "summary": revision.summary,
        }
        visible = revision.markdown.strip()
        hidden = json.dumps(revision.to_dict(), indent=2, sort_keys=True)
        body = "\n\n".join(
            part
            for part in [
                visible,
                "## Machine Metadata\nThis section is managed by Codex for stable task reconciliation across plan revisions.",
                f"{REVISION_JSON_START}\n{hidden}\n{REVISION_JSON_END}",
            ]
            if part
        )
        return self.bridge._render_managed_section(self._revision_title(revision), body, metadata=metadata)

    def _extract_revision_json(self, markdown: str) -> dict[str, Any]:
        if REVISION_JSON_START not in markdown or REVISION_JSON_END not in markdown:
            raise StateError("Revision page does not contain managed task-graph metadata")
        pattern = re.compile(
            rf"{re.escape(REVISION_JSON_START)}\s*(.*?)\s*{re.escape(REVISION_JSON_END)}",
            re.DOTALL,
        )
        match = pattern.search(markdown)
        if not match:
            raise StateError("Could not parse revision metadata block")
        return json.loads(match.group(1))

    def _revision_from_page(self, page_id: str) -> PlanRevisionSpec:
        markdown = self.client.retrieve_page_markdown(page_id).get("markdown", "")
        payload = self._extract_revision_json(markdown)
        tasks = [TaskSpec(**task_payload) for task_payload in payload.get("tasks", [])]
        return PlanRevisionSpec(
            revision_key=payload["revision_key"],
            revision_number=int(payload["revision_number"]),
            status=payload.get("status", "draft"),
            title=payload.get("title", ""),
            summary=payload.get("summary", ""),
            brief=payload.get("brief", ""),
            markdown=payload.get("markdown", ""),
            tasks=tasks,
            source_revision_key=payload.get("source_revision_key"),
            change_request=payload.get("change_request"),
            created_at=payload.get("created_at"),
            approved_at=payload.get("approved_at"),
        )

    def _resolve_project_state(self, project_ref: str | None = None) -> BridgeState:
        state = self._load_state()
        if state.project_page_id and (project_ref is None or project_ref in {state.project_identifier, state.project_page_id}):
            return state
        if project_ref and state.project_page_id:
            page = self.bridge._safe_retrieve_page(state.project_page_id)
            if page and project_ref in {page.get("id"), self.bridge._page_title(page), state.project_identifier}:
                return state
        if not state.project_page_id:
            raise StateError("No project workspace is configured yet. Draft a project brief first.")
        raise StateError(f"Could not resolve project '{project_ref}' from current state")

    def _resolve_revision_key(self, state: BridgeState, revision_ref: str | None) -> str:
        if not revision_ref:
            if state.active_revision_key:
                return state.active_revision_key
            if state.revision_numbers:
                return max(state.revision_numbers, key=lambda key: state.revision_numbers[key])
            raise StateError("No plan revisions exist yet")
        if revision_ref in state.revision_pages:
            return revision_ref
        for key, page_id in state.revision_pages.items():
            if revision_ref == page_id:
                return key
        raise StateError(f"Unknown revision reference '{revision_ref}'")

    def _set_revision_status(self, state: BridgeState, revision_key: str, status: str, *, approved_at: str | None = None) -> PlanRevisionSpec:
        page_id = state.revision_pages[revision_key]
        revision = self._revision_from_page(page_id)
        revision.status = status
        if approved_at is not None:
            revision.approved_at = approved_at
        self.client.update_page(page_id, properties={"title": {"title": [{"type": "text", "text": {"content": self._revision_title(revision)}}]}})
        self.bridge._replace_managed_markdown(page_id, self._render_revision_markdown(revision))
        state.revision_statuses[revision_key] = status
        if status == "approved":
            state.active_revision_key = revision_key
            state.active_revision_page_id = page_id
        elif state.active_revision_key == revision_key and status != "approved":
            state.active_revision_key = ""
            state.active_revision_page_id = ""
        return revision

    def _update_plan_index(self, project: ProjectSpec, state: BridgeState) -> None:
        plan_index_page_id = state.docs_pages.get("Plan Index")
        if not plan_index_page_id:
            return
        lines = ["# Plan Index", ""]
        if state.active_revision_key:
            active_page = self.bridge._safe_retrieve_page(state.active_revision_page_id)
            active_url = active_page.get("url") if active_page else ""
            if active_url:
                lines.append(f"- Active plan: [{state.active_revision_key}]({active_url})")
            else:
                lines.append(f"- Active plan: `{state.active_revision_key}`")
        else:
            lines.append("- Active plan: none approved yet")
        lines.extend(["", "## Revisions"])

        ordered = sorted(state.revision_numbers.items(), key=lambda item: item[1], reverse=True)
        if not ordered:
            lines.append("- No revisions yet.")
        else:
            for revision_key, revision_number in ordered:
                page = self.bridge._safe_retrieve_page(state.revision_pages.get(revision_key, ""))
                url = page.get("url") if page else ""
                status = state.revision_statuses.get(revision_key, "draft")
                label = f"R{revision_number:02d}"
                if url:
                    lines.append(f"- [{label}]({url}) `{revision_key}` - {status}")
                else:
                    lines.append(f"- {label} `{revision_key}` - {status}")

        self.bridge._replace_managed_markdown(plan_index_page_id, self.bridge._render_managed_section("Plan Index", "\n".join(lines)))
        self.bridge._replace_managed_markdown(
            state.project_page_id,
            self.bridge._render_managed_section(project.name, self.bridge._render_project_home(PlanSpec(project=project, docs=[], tasks=[]), state)),
        )

    def _ensure_revision_page(self, project: ProjectSpec, revision: PlanRevisionSpec, state: BridgeState) -> dict[str, Any]:
        plan_index_page_id = state.docs_pages.get("Plan Index")
        if not plan_index_page_id:
            raise StateError("Plan Index page is missing from project docs")
        page = self.client.create_page(
            parent_page_id=plan_index_page_id,
            title=self._revision_title(revision),
            markdown=self._render_revision_markdown(revision),
            icon_emoji="📝",
        )
        state.revision_pages[revision.revision_key] = str(page["id"])
        state.revision_numbers[revision.revision_key] = revision.revision_number
        state.revision_statuses[revision.revision_key] = revision.status
        self._update_plan_index(project, state)
        self._save_state(state)
        return page

    def _revision_view_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "database": "tasks",
                "type": "table",
                "name": "All tasks",
                "configure": 'GROUP BY "Phase Group"; SORT BY "Sequence" ASC; SHOW "Name", "Execution Slot", "Delivery Status", "Type", "Agent Role", "Parallelizable", "Parent", "Sequence", "Blocked By"',
            },
        ]

    def _handoff_view_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "database": "phases",
                "type": "timeline",
                "name": "Timeline",
                "configure": 'TIMELINE BY "Start" TO "Due"; SHOW "Name", "Priority", "Agent Estimate (hrs)", "Human Estimate (hrs)", "Blocked By", "Tasks"',
            },
            {
                "database": "phases",
                "type": "table",
                "name": "All phases",
                "configure": 'SHOW "Name", "Priority", "Agent Estimate (hrs)", "Human Estimate (hrs)", "Progress", "Status", "Tasks", "Blocked By", "Timeline"',
            },
            {
                "database": "phases",
                "type": "table",
                "name": "By Priority",
                "configure": 'SORT BY "Priority" ASC; SHOW "Name", "Priority", "Agent Estimate (hrs)", "Human Estimate (hrs)", "Progress", "Status", "Tasks", "Blocked By", "Timeline"',
            },
            {
                "database": "tasks",
                "type": "table",
                "name": "All tasks",
                "configure": 'GROUP BY "Phase Group"; SORT BY "Sequence" ASC; SHOW "Name", "Execution Slot", "Delivery Status", "Type", "Agent Role", "Parallelizable", "Parent", "Sequence", "Blocked By"',
            },
        ]

    def _resolve_project_slug(self, project_ref: str | None = None) -> str:
        state = self._load_state()
        candidates: list[str] = []
        if project_ref:
            candidates.extend([project_ref, self._slugify(project_ref)])
        if state.project_identifier:
            candidates.extend([state.project_identifier, self._slugify(state.project_identifier)])
        if self.config.project_identifier:
            candidates.extend([self.config.project_identifier, self._slugify(self.config.project_identifier)])

        seen: set[str] = set()
        for candidate in candidates:
            slug = self._slugify(candidate)
            if slug in seen:
                continue
            seen.add(slug)
            if self.artifacts.project_dir(slug).exists():
                return slug

        if project_ref:
            return self._slugify(project_ref)
        if state.project_identifier:
            return state.project_identifier
        return self._slugify(self.config.project_identifier)

    def _resolve_plan_revision_key(self, project_ref: str | None = None) -> str:
        state = self._load_state()
        project_slug = self._resolve_project_slug(project_ref)
        if state.approved_plan_revision_key and project_slug in {state.project_identifier, self._slugify(state.project_identifier)}:
            return state.approved_plan_revision_key
        return self.artifacts.latest_revision_key(project_slug)

    def _plan_title_from_markdown(self, markdown: str, fallback: str) -> str:
        for line in markdown.splitlines():
            match = re.match(r"^#\s+(.+?)\s*$", line.strip())
            if match:
                return match.group(1).strip()
        return fallback.strip()

    def _task_type_from_title(self, title: str, *, fallback: str = "Task") -> str:
        normalized = title.lower()
        if any(token in normalized for token in ("bug", "fix", "defect")):
            return "Bug"
        if any(token in normalized for token in ("research", "spike", "investigate", "discovery")):
            return "Research"
        return fallback

    def _markdown_list_items(self, markdown: str) -> list[str]:
        items: list[str] = []
        in_code_block = False
        for raw_line in markdown.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            match = re.match(r"^(?:[-*+]|\d+\.)\s+(.*)$", stripped)
            if not match:
                continue
            content = re.sub(r"^\[[ xX]\]\s*", "", match.group(1).strip()).strip()
            if content:
                items.append(content)
        return items

    def _extract_h3_sections(self, markdown: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_title = ""
        current_lines: list[str] = []
        for raw_line in markdown.splitlines():
            match = re.match(r"^###\s+(.+?)\s*$", raw_line.strip())
            if match:
                if current_title:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = match.group(1).strip()
                current_lines = []
                continue
            if current_title:
                current_lines.append(raw_line)
        if current_title:
            sections.append((current_title, "\n".join(current_lines).strip()))
        return sections

    def _extract_h2_sections(self, markdown: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_title = ""
        current_lines: list[str] = []
        for raw_line in markdown.splitlines():
            match = re.match(r"^##\s+(.+?)\s*$", raw_line.strip())
            if match:
                if current_title:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = match.group(1).strip()
                current_lines = []
                continue
            if current_title:
                current_lines.append(raw_line)
        if current_title:
            sections.append((current_title, "\n".join(current_lines).strip()))
        return sections

    def _humanize_task_title(self, content: str) -> str:
        title = re.sub(r"`([^`]+)`", r"\1", content).strip().rstrip(".")
        lowered = title.lower()
        special_cases = (
            (
                ("graph as structural source of truth" in lowered and "plan_state" in lowered),
                "Keep graph, reviews, and plan_state roles clear",
            ),
            (
                ("execution-state surface" in lowered or "source-of-truth payloads" in lowered),
                "Stabilize execution-state surface",
            ),
            (
                ("canonical local run path" in lowered and "docker compose path" in lowered),
                "Preserve canonical run paths",
            ),
            (
                ("operator guide" in lowered and "ui/api behavior" in lowered),
                "Align operator guide, runtime plans, and UI/API behavior",
            ),
            (
                ("coverage" in lowered and "green" in lowered),
                "Keep v1 test coverage green",
            ),
            (
                ("ambiguity between" in lowered or "prototype or in-progress changes" in lowered),
                "Separate prototype work from the shipped v1 surface",
            ),
            (
                ("canonical product story" in lowered),
                "Keep one canonical product story",
            ),
            (
                ("coupling inside large files" in lowered),
                "Reduce coupling in large application files",
            ),
            (
                ("runtime artifacts" in lowered and "inspectable" in lowered),
                "Preserve inspectable runtime artifacts",
            ),
            (
                ("test coverage aligned" in lowered and "operator and agent workflows" in lowered),
                "Keep tests aligned with operator and agent workflows",
            ),
            (
                ("committed source-of-truth artifacts" in lowered and "local noise" in lowered),
                "Separate source-of-truth artifacts from local noise",
            ),
        )
        for applies, replacement in special_cases:
            if applies:
                return replacement
        replacements = (
            (r"^finish and stabilize the\s+", "Stabilize "),
            (r"^finish and\s+", ""),
            (r"^ensure the\s+", "Align "),
            (r"^ensure\s+", ""),
            (r"^keep one\s+", "Keep one "),
            (r"^keep\s+", "Keep "),
            (r"^preserve\s+", "Preserve "),
            (r"^reduce\s+", "Reduce "),
            (r"^distinguish clearly between\s+", "Separate "),
            (r"^turn the\s+", "Turn the "),
            (r"^review the\s+", "Review the "),
            (r"^identify the\s+", "Identify the "),
            (r"^confirm the\s+", "Confirm the "),
        )
        for pattern, replacement in replacements:
            title = re.sub(pattern, replacement, title, flags=re.IGNORECASE)
        for separator in (":", ";"):
            if separator in title:
                prefix = title.split(separator, 1)[0].strip()
                if len(prefix.split()) >= 3:
                    title = prefix
                    break
        if len(title.split()) > 10:
            for separator in (",", " so that ", " while ", " with ", " and the "):
                if separator in title:
                    prefix = title.split(separator, 1)[0].strip()
                    if len(prefix.split()) >= 3:
                        title = prefix
                        break
        title = re.sub(r"\s+", " ", title).strip()
        if len(title.split()) > 10:
            title = " ".join(title.split()[:10])
        if title:
            title = title[0].upper() + title[1:]
        return title or "Execute scoped work"

    def _estimate_human_hours_for_task(self, title: str, description: str, task_type: str) -> int:
        normalized = f"{title} {description}".lower()
        if task_type in {"Milestone", "Epic"}:
            return 0
        if "canonical product story" in normalized or "one canonical product story" in normalized:
            return 12
        if "execution-state surface" in normalized:
            return 24
        if "test coverage" in normalized or "tests aligned" in normalized:
            return 14
        if "align operator guide" in normalized or "canonical product story" in normalized:
            return 10
        if "reduce coupling" in normalized:
            return 16
        if "preserve canonical run paths" in normalized or "preserve inspectable runtime artifacts" in normalized:
            return 8
        if "separate prototype" in normalized or "separate source-of-truth artifacts" in normalized:
            return 6
        if "plan_state roles" in normalized or "source of truth" in normalized:
            return 6
        if task_type == "Research":
            return 6
        if task_type == "Bug":
            return 8
        return 8

    def _agent_effort_multiplier(self, title: str, description: str, role: str) -> float:
        normalized = f"{title} {description}".lower()
        multiplier = 0.4 if role == "executor" else 0.6
        if any(token in normalized for token in ("review", "validate", "qa", "test", "story", "guide", "align", "docs")):
            multiplier = 0.55 if role == "executor" else 0.7
        elif any(token in normalized for token in ("persistence", "api", "execution-state", "runtime", "refactor", "coupling")):
            multiplier = 0.45 if role == "executor" else 0.65
        if any(token in normalized for token in ("handoff", "approval", "signoff")):
            multiplier = max(multiplier, 0.8)
        return multiplier

    def _estimate_agent_hours_for_task(self, title: str, description: str, task_type: str, human_hours: int, role: str) -> int:
        if task_type in {"Milestone", "Epic"}:
            return 0
        multiplier = self._agent_effort_multiplier(title, description, role)
        return max(1, int(round(human_hours * multiplier)))

    def _estimate_human_hours_from_agent_hours(self, title: str, description: str, role: str, agent_hours: int) -> int:
        multiplier = self._agent_effort_multiplier(title, description, role)
        return max(agent_hours, int(round(agent_hours / max(0.2, multiplier))))

    def _parse_day_range_to_hours(self, estimate_text: str) -> int | None:
        normalized = estimate_text.strip().lower()
        match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*day", normalized)
        if match:
            low = float(match.group(1))
            high = float(match.group(2))
            return max(1, int(round(((low + high) / 2.0) * 6)))
        match = re.search(r"(\d+(?:\.\d+)?)\s*day", normalized)
        if match:
            return max(1, int(round(float(match.group(1)) * 6)))
        return None

    def _looks_like_shipping_task_plan(self, markdown: str) -> bool:
        lowered = markdown.lower()
        return lowered.startswith("# shipping tasks") or "## phase 1" in lowered

    def _parse_shipping_task_entry(self, item: str) -> dict[str, str]:
        match = re.match(r"^`([^`]+)`\s+[—-]\s+(.*)$", item.strip())
        if match:
            label = match.group(1).strip()
            remainder = match.group(2).strip()
        else:
            label = item.strip()
            remainder = ""
        code = ""
        title = label
        if re.match(r"^[A-Za-z]\d+(?:\.\d+)+\s+", label):
            code, title = label.split(" ", 1)
        fields: dict[str, str] = {}
        if remainder:
            for segment in [part.strip() for part in remainder.split(";") if part.strip()]:
                if ":" in segment:
                    key, value = segment.split(":", 1)
                    fields[key.strip().lower()] = value.strip()
        return {
            "code": code,
            "title": title.strip(),
            "label": label.strip(),
            "explanation": fields.get("explanation", ""),
            "goal": fields.get("goal", ""),
            "tests": fields.get("tests", ""),
            "ai_estimate": fields.get("ai-assisted estimate", ""),
            "parallelization": fields.get("parallelization", ""),
            "non_blocking": fields.get("non-blocking", ""),
        }

    def _shipping_parallelization_links(self, parallelization_text: str) -> tuple[list[str], list[str]]:
        normalized = re.sub(r"\s+", " ", parallelization_text.strip())
        if not normalized:
            return [], []

        def extract_codes(segment: str) -> list[str]:
            seen: set[str] = set()
            ordered: list[str] = []
            for code in re.findall(r"`([^`]+)`", segment):
                if code not in seen:
                    ordered.append(code)
                    seen.add(code)
            return ordered

        parallel_codes: list[str] = []
        dependency_codes: list[str] = []
        parallel_patterns = [
            r"(?:parallel with|in parallel with|alongside|same wave as)\s+(.+?)(?=(?:\s+(?:after|once|while|but|then|so that)|[.;]|$))",
        ]
        dependency_patterns = [
            r"(?:starts after|run after|after|once|depends on|blocked by|serial with)\s+(.+?)(?=(?:\s+(?:while|but|then|so that)|[.;]|$))",
        ]

        for pattern in parallel_patterns:
            for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                parallel_codes.extend(extract_codes(match.group(1)))
        for pattern in dependency_patterns:
            for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                dependency_codes.extend(extract_codes(match.group(1)))

        deduped_dependencies: list[str] = []
        seen_dependencies: set[str] = set()
        for code in dependency_codes:
            if code not in seen_dependencies:
                deduped_dependencies.append(code)
                seen_dependencies.add(code)

        deduped_parallel: list[str] = []
        seen_parallel: set[str] = set()
        for code in parallel_codes:
            if code in seen_dependencies or code in seen_parallel:
                continue
            deduped_parallel.append(code)
            seen_parallel.add(code)

        return deduped_dependencies, deduped_parallel

    def _shipping_task_description(
        self,
        *,
        phase_title: str,
        project_goal: str,
        task_code: str,
        explanation: str,
        goal: str,
        tests: str,
        parallelization: str,
        non_blocking: str,
    ) -> str:
        lines = [
            f"This shipping task belongs to `{phase_title}`.",
            "",
            "### Why this matters",
            explanation.strip() or goal.strip() or "This task supports the current shipping plan.",
            "",
            "### Release goal alignment",
            project_goal.strip(),
        ]
        if goal.strip():
            lines.extend(["", "### Task goal", goal.strip()])
        if tests.strip():
            lines.extend(["", "### Validation", f"- {tests.strip()}"])
        if parallelization.strip():
            lines.extend(["", "### Parallelization", parallelization.strip()])
        if non_blocking.strip():
            lines.extend(["", "### Release note", non_blocking.strip()])
        lines.extend(
            [
                "",
                "### Done means",
                "- the shipped behavior and public docs both reflect the task outcome",
                "- the release plan can advance without hidden repo-only assumptions",
            ]
        )
        if task_code:
            lines.extend(["", f"### Tracking code\n- `{task_code}`"])
        return "\n".join(lines).strip()

    def _shipping_milestone_description(self, *, phase_title: str, phase_estimate: str, project_goal: str) -> str:
        lines = [
            f"This milestone covers `{phase_title}` in the shipping track.",
            "",
            "### Why this milestone exists",
            project_goal.strip(),
        ]
        if phase_estimate.strip():
            lines.extend(["", f"### Phase estimate\n- `{phase_estimate.strip()}`"])
        lines.extend(
            [
                "",
                "### PM expectation",
                "- use this phase to track release readiness, not only code output",
                "- child tasks should make the public-share path understandable from Notion alone",
            ]
        )
        return "\n".join(lines).strip()

    def _build_shipping_task_graph_from_markdown(
        self,
        project: ProjectSpec,
        source_plan_path: str,
        plan_markdown: str,
        task_input_path: str,
        task_input_markdown: str,
        *,
        handoff_id: str,
    ) -> TaskGraphSpec:
        tasks: list[TaskSpec] = []
        seen_keys: set[str] = set()
        sequence = 1
        code_to_key: dict[str, str] = {}
        project_goal = (
            self._extract_markdown_section(plan_markdown, "Project Goal")
            or self._extract_markdown_section(plan_markdown, "Goal")
            or project.description
        ).strip()
        anchor_by_milestone: dict[str, str] = {}
        task_meta_by_key: dict[str, dict[str, Any]] = {}

        def add_task(
            title: str,
            description: str,
            task_type: str,
            *,
            parent_key: str | None = None,
            priority: str | None = None,
            parallelizable: bool | None = None,
            agent_role: str | None = None,
            human_hours: int | None = None,
            agent_hours: int | None = None,
        ) -> TaskSpec:
            nonlocal sequence
            role = agent_role or self._agent_role_for_task(task_type, title)
            human_estimate = human_hours
            agent_estimate = agent_hours
            if task_type not in {"Milestone", "Epic"}:
                if human_estimate is None:
                    human_estimate = self._estimate_human_hours_for_task(title, description, task_type)
                if agent_estimate is None:
                    agent_estimate = self._estimate_agent_hours_for_task(title, description, task_type, human_estimate, role)
            task = TaskSpec(
                key=self._unique_task_key(title, seen_keys),
                title=title.strip(),
                description=description.strip(),
                type=task_type,
                status="Ready",
                priority=priority or ("High" if task_type == "Milestone" else "Normal"),
                parent_key=parent_key,
                execution_mode=self._execution_mode_for_role(role, title),
                parallelizable=self._parallelizable_for_task(task_type, title) if parallelizable is None else parallelizable,
                repo_ref=source_plan_path,
                plan_revision=handoff_id,
                agent_role=role,
                preferred_skill=self._preferred_skill_for_role(role),
                sequence=sequence,
                human_estimate_hours=human_estimate if human_estimate else None,
                agent_estimate_hours=agent_estimate if agent_estimate else None,
                source_revision=source_plan_path,
                review_status="pending",
            )
            sequence += 1
            tasks.append(task)
            return task

        meta_sections = {
            "goal",
            "scope",
            "summary",
            "public apis, interfaces, and types",
            "test scenarios that must appear in both planning and validation",
            "assumptions and defaults",
        }
        milestones: list[TaskSpec] = []
        for phase_title, body in self._extract_h2_sections(task_input_markdown):
            if phase_title.lower() in meta_sections:
                continue
            phase_estimate = ""
            match = re.search(r"^Phase estimate:\s*(.+)$", body, re.MULTILINE)
            if match:
                phase_estimate = match.group(1).strip()
            milestone = add_task(
                phase_title.strip(),
                self._shipping_milestone_description(
                    phase_title=phase_title.strip(),
                    phase_estimate=phase_estimate,
                    project_goal=project_goal,
                ),
                "Milestone",
                priority="High",
                parallelizable=False,
                agent_role="pm",
            )
            milestones.append(milestone)
            for item in self._markdown_list_items(body):
                entry = self._parse_shipping_task_entry(item)
                title = f"{entry['code']} {entry['title']}".strip() if entry["code"] else entry["title"]
                task_type = self._task_type_from_title(title)
                explanation = entry["explanation"] or entry["goal"] or item
                role = self._agent_role_for_task(task_type, title)
                agent_hours = self._parse_day_range_to_hours(entry["ai_estimate"]) if entry["ai_estimate"] else None
                human_hours = (
                    self._estimate_human_hours_from_agent_hours(title, explanation, role, agent_hours)
                    if agent_hours is not None
                    else None
                )
                parallelization = entry["parallelization"].lower()
                parallelizable = not any(token in parallelization for token in ("serial gate", "serial anchor", "serial with"))
                task = add_task(
                    title,
                    self._shipping_task_description(
                        phase_title=phase_title.strip(),
                        project_goal=project_goal,
                        task_code=entry["code"],
                        explanation=entry["explanation"],
                        goal=entry["goal"],
                        tests=entry["tests"],
                        parallelization=entry["parallelization"],
                        non_blocking=entry["non_blocking"],
                    ),
                    task_type,
                    parent_key=milestone.key,
                    parallelizable=parallelizable,
                    agent_role=role,
                    human_hours=human_hours,
                    agent_hours=agent_hours,
                )
                if entry["code"]:
                    code_to_key[entry["code"]] = task.key
                task_meta_by_key[task.key] = entry
                if "serial anchor" in parallelization:
                    anchor_by_milestone[milestone.key] = task.key

        by_key = {task.key: task for task in tasks}
        previous_by_parent: dict[str, str] = {}
        for task in sorted(tasks, key=lambda item: item.sequence or 0):
            if task.type == "Milestone":
                continue
            parent_key = task.parent_key or ""
            previous_key = previous_by_parent.get(parent_key)
            meta = task_meta_by_key.get(task.key, {})
            parallelization = meta.get("parallelization", "").lower()
            dependency_codes, _parallel_codes = self._shipping_parallelization_links(meta.get("parallelization", ""))
            explicit_dependencies = [
                code_to_key[code]
                for code in dependency_codes
                if code in code_to_key and code_to_key[code] != task.key
            ]
            if explicit_dependencies:
                for dependency_key in explicit_dependencies:
                    if dependency_key not in task.dependencies:
                        task.dependencies.append(dependency_key)
            if not task.dependencies:
                anchor_key = anchor_by_milestone.get(parent_key)
                if anchor_key and anchor_key != task.key:
                    task.dependencies.append(anchor_key)
            if not task.parallelizable and previous_key and previous_key not in task.dependencies:
                task.dependencies.append(previous_key)
            previous_by_parent[parent_key] = task.key

        self._apply_recovery_schedule(tasks)
        self._apply_parallel_metadata(tasks)
        self._apply_completion_defaults(tasks)
        summary = (
            f"Generated {len(tasks)} work items from `{source_plan_path}` "
            f"using companion task input `{task_input_path}`."
        )
        return TaskGraphSpec(
            project=project,
            source_plan_path=source_plan_path,
            handoff_id=handoff_id,
            created_at=self._utc_now(),
            summary=summary,
            tasks=tasks,
        )

    def _recovery_done_means(self, title: str, source_item: str) -> list[str]:
        normalized = f"{title} {source_item}".lower()
        bullets = [
            "the task outcome is reflected consistently in the code, docs, and operator-facing workflow",
            "the live Notion task status and linked project docs tell the same story as the implementation",
        ]
        if "execution-state" in normalized:
            bullets = [
                "payloads, endpoints, briefs, UI state, and persistence behavior all agree on the same execution-state contract",
                "operators and agents can inspect or update execution state without guessing which surface is authoritative",
            ]
        elif any(token in normalized for token in ("guide", "story", "docs", "operator")):
            bullets = [
                "README, operator guide, runtime plans, and UI/API behavior describe the same day-to-day workflow",
                "a human PM can understand what this area does without opening the repo first",
            ]
        elif any(token in normalized for token in ("test", "coverage", "validate", "qa")):
            bullets = [
                "automated coverage exists for the real shipped workflow, not only prototype behavior",
                "regressions in this area fail loudly enough that future maintenance stays safe",
            ]
        elif any(token in normalized for token in ("run path", "docker", "runtime artifact", "inspectable")):
            bullets = [
                "the canonical commands and persisted artifacts are documented, reproducible, and easy to inspect locally",
                "future contributors can tell which runtime outputs are source-of-truth, generated evidence, or disposable local noise",
            ]
        elif any(token in normalized for token in ("coupling", "prototype", "source-of-truth")):
            bullets = [
                "the boundary for this work is explicit enough that future changes remain reviewable",
                "old or prototype surfaces no longer compete with the maintained v1 path",
            ]
        return bullets

    def _recovery_task_description(
        self,
        *,
        workstream_title: str,
        goal_statement: str,
        task_title: str,
        source_item: str,
        task_type: str,
    ) -> str:
        lines = [
            f"This `{task_type}` belongs to the `{workstream_title}` workstream.",
            "",
            "### Why this matters",
            source_item.strip(),
            "",
            "### Project goal alignment",
            goal_statement.strip(),
            "",
            "### Done means",
        ]
        lines.extend(f"- {bullet}" for bullet in self._recovery_done_means(task_title, source_item))
        return "\n".join(lines).strip()

    def _recovery_milestone_description(self, *, workstream_title: str, goal_statement: str) -> str:
        return "\n".join(
            [
                f"This milestone groups the work needed to `{workstream_title.lower()}`.",
                "",
                "### Why this milestone exists",
                goal_statement.strip(),
                "",
                "### PM expectation",
                "- use this milestone to track the health of the whole workstream, not just one engineering change",
                "- child tasks should make the milestone understandable even for someone reading Notion without the repo open",
            ]
        ).strip()

    def _apply_recovery_dependencies(self, tasks: list[TaskSpec]) -> None:
        by_title = {task.title: task for task in tasks}

        def link(task_title: str, dependency_title: str) -> None:
            task = by_title.get(task_title)
            dependency = by_title.get(dependency_title)
            if not task or not dependency:
                return
            if dependency.key not in task.dependencies:
                task.dependencies.append(dependency.key)

        link("Stabilize execution-state surface", "Keep graph, reviews, and plan_state roles clear")
        link("Preserve canonical run paths", "Stabilize execution-state surface")
        link("Align operator guide, runtime plans, and UI/API behavior", "Stabilize execution-state surface")
        link("Keep v1 test coverage green", "Align operator guide, runtime plans, and UI/API behavior")
        link("Separate prototype work from the shipped v1 surface", "Align operator guide, runtime plans, and UI/API behavior")
        link("Reduce coupling in large application files", "Keep one canonical product story")
        link("Preserve inspectable runtime artifacts", "Keep one canonical product story")
        link("Keep tests aligned with operator and agent workflows", "Keep one canonical product story")
        link("Separate source-of-truth artifacts from local noise", "Preserve inspectable runtime artifacts")

    def _apply_recovery_schedule(self, tasks: list[TaskSpec]) -> None:
        task_by_key = {task.key: task for task in tasks}
        milestone_children: dict[str, list[TaskSpec]] = {}
        for task in tasks:
            if task.parent_key:
                milestone_children.setdefault(task.parent_key, []).append(task)

        base_date = datetime.now(timezone.utc).date() + timedelta(days=1)
        milestone_offset_days = 0

        def days_for(agent_hours: int) -> int:
            return max(1, (agent_hours + 5) // 6)

        def iso(day) -> str:
            return day.isoformat()

        for milestone in [task for task in tasks if task.type == "Milestone"]:
            children = sorted(milestone_children.get(milestone.key, []), key=lambda item: item.sequence or 0)
            milestone_start = base_date + timedelta(days=milestone_offset_days)
            milestone_end = milestone_start
            sequential_cursor = milestone_start
            child_starts: list[Any] = []
            child_ends: list[Any] = []
            for child in children:
                earliest = milestone_start
                for dependency_key in child.dependencies:
                    dependency = task_by_key.get(dependency_key)
                    if dependency and dependency.due_date:
                        dependency_day = datetime.fromisoformat(dependency.due_date).date() + timedelta(days=1)
                        if dependency_day > earliest:
                            earliest = dependency_day
                if not child.parallelizable and sequential_cursor > earliest:
                    earliest = sequential_cursor
                duration_days = days_for(child.agent_estimate_hours or 1)
                due_day = earliest + timedelta(days=duration_days - 1)
                child.start_date = iso(earliest)
                child.due_date = iso(due_day)
                if not child.parallelizable:
                    sequential_cursor = due_day + timedelta(days=1)
                child_starts.append(earliest)
                child_ends.append(due_day)
                if due_day > milestone_end:
                    milestone_end = due_day
            milestone.start_date = iso(min(child_starts) if child_starts else milestone_start)
            milestone.due_date = iso(max(child_ends) if child_ends else milestone_end)
            milestone.human_estimate_hours = sum(child.human_estimate_hours or 0 for child in children)
            milestone.agent_estimate_hours = sum(child.agent_estimate_hours or 0 for child in children)
            milestone_offset_days += 2

    def _apply_completion_defaults(self, tasks: list[TaskSpec]) -> None:
        for task in tasks:
            if task.progress is None:
                task.progress = 0
            if task.completion_state:
                continue
            if task.progress >= 100:
                task.completion_state = "Completed"
            elif task.progress > 0:
                task.completion_state = "In progress"
            else:
                task.completion_state = "Not started"

    def _apply_parallel_metadata(self, tasks: list[TaskSpec]) -> None:
        executable = [task for task in tasks if task.type not in {"Milestone", "Epic"}]
        task_by_key = {task.key: task for task in tasks}
        grouped: dict[tuple[str, str], list[TaskSpec]] = {}

        for task in executable:
            if not task.parallelizable or not task.start_date:
                task.parallel_group = "Serial"
                task.parallel_with = []
                continue
            group_key = (task.parent_key or "", task.start_date)
            grouped.setdefault(group_key, []).append(task)

        wave_index = 0
        for group_key in sorted(grouped, key=lambda item: (item[1], item[0])):
            wave_tasks = sorted(grouped[group_key], key=lambda item: item.sequence or 0)
            valid_wave = len(wave_tasks) > 1
            if valid_wave:
                parallel_label = f"Wave {chr(ord('A') + wave_index)}"
                wave_index += 1
            else:
                parallel_label = "Solo"

            for task in wave_tasks:
                task.parallel_group = parallel_label
                if not valid_wave:
                    task.parallel_with = []
                    continue
                related: list[str] = []
                for candidate in wave_tasks:
                    if candidate.key == task.key:
                        continue
                    if candidate.key in task.dependencies:
                        continue
                    if task.key in candidate.dependencies:
                        continue
                    if task_by_key.get(candidate.key) is None:
                        continue
                    related.append(candidate.key)
                task.parallel_with = related

    def _looks_like_recovery_plan(self, markdown: str) -> bool:
        lowered = markdown.lower()
        return (
            lowered.startswith("# recovery plan")
            or "## rescue understanding" in lowered
            or "## bring-it-home workstreams" in lowered
            or "## definition of completion" in lowered
            or "## maintenance baseline" in lowered
        )

    def _build_recovery_task_graph_from_markdown(
        self,
        project: ProjectSpec,
        source_plan_path: str,
        markdown: str,
        *,
        handoff_id: str,
    ) -> TaskGraphSpec:
        tasks: list[TaskSpec] = []
        seen_keys: set[str] = set()
        sequence = 1
        workstreams: list[tuple[str, list[str]]] = []
        goal_statement = self._extract_markdown_section(markdown, "Project Goal") or project.description

        def add_task(title: str, description: str, task_type: str, *, parent_key: str | None = None, priority: str | None = None) -> TaskSpec:
            nonlocal sequence
            role = self._agent_role_for_task(task_type, title)
            human_hours = self._estimate_human_hours_for_task(title, description, task_type)
            agent_hours = self._estimate_agent_hours_for_task(title, description, task_type, human_hours, role)
            task = TaskSpec(
                key=self._unique_task_key(title, seen_keys),
                title=title.strip(),
                description=description.strip(),
                type=task_type,
                status="Ready",
                priority=priority or ("High" if task_type == "Milestone" else "Normal"),
                parent_key=parent_key,
                execution_mode=self._execution_mode_for_role(role, title),
                parallelizable=self._parallelizable_for_task(task_type, title),
                repo_ref=source_plan_path,
                plan_revision=handoff_id,
                agent_role=role,
                preferred_skill=self._preferred_skill_for_role(role),
                sequence=sequence,
                human_estimate_hours=human_hours if human_hours else None,
                agent_estimate_hours=agent_hours if agent_hours else None,
                source_revision=source_plan_path,
                review_status="pending",
            )
            sequence += 1
            tasks.append(task)
            return task

        bring_it_home = self._extract_markdown_section(markdown, "Bring-It-Home Workstreams")
        for section_title, body in self._extract_h3_sections(bring_it_home):
            items = self._markdown_list_items(body)
            if items:
                workstreams.append((section_title, items))

        if not workstreams:
            completion_items = self._markdown_list_items(
                self._extract_markdown_section(markdown, "Definition Of Completion")
                or self._extract_markdown_section(markdown, "What Completion Requires")
            )
            if completion_items:
                workstreams.append(("Finish the shippable core", completion_items))
            maintenance_items = self._markdown_list_items(
                self._extract_markdown_section(markdown, "Maintenance Baseline")
                or self._extract_markdown_section(markdown, "What Maintenance Requires")
            )
            if maintenance_items:
                workstreams.append(("Keep the project maintainable", maintenance_items))

        if not workstreams:
            fallback_items = self._markdown_list_items(self._extract_markdown_section(markdown, "Immediate Actions"))
            if fallback_items:
                workstreams.append(("Clarify the rescue plan", fallback_items))

        previous_task_by_parent: dict[str, str] = {}
        for workstream_title, items in workstreams:
            milestone = add_task(
                workstream_title.strip(),
                self._recovery_milestone_description(
                    workstream_title=workstream_title.strip(),
                    goal_statement=goal_statement,
                ),
                "Milestone",
                priority="High",
            )
            for item in items:
                task_title = self._humanize_task_title(item)
                task_type = self._task_type_from_title(task_title)
                task = add_task(
                    task_title,
                    self._recovery_task_description(
                        workstream_title=workstream_title.strip(),
                        goal_statement=goal_statement,
                        task_title=task_title,
                        source_item=item,
                        task_type=task_type,
                    ),
                    task_type,
                    parent_key=milestone.key,
                )
                previous_key = previous_task_by_parent.get(milestone.key)
                if previous_key and not task.parallelizable:
                    task.dependencies = [previous_key]
                previous_task_by_parent[milestone.key] = task.key

        if not tasks:
            milestone = add_task(
                "Bring the project home",
                f"Fallback rescue milestone generated from `{source_plan_path}`.",
                "Milestone",
                priority="High",
            )
            add_task(
                "Clarify the finish line",
                "No structured bring-it-home workstreams were found, so start by clarifying the final scope.",
                "Task",
                parent_key=milestone.key,
            )

        self._apply_recovery_dependencies(tasks)
        self._apply_recovery_schedule(tasks)
        self._apply_parallel_metadata(tasks)
        self._apply_completion_defaults(tasks)

        summary = (
            f"Generated {len(tasks)} recovery work items from `{source_plan_path}` "
            "using the bring-it-home workstreams."
        )
        return TaskGraphSpec(
            project=project,
            source_plan_path=source_plan_path,
            handoff_id=handoff_id,
            created_at=self._utc_now(),
            summary=summary,
            tasks=tasks,
        )

    def _agent_role_for_task(self, task_type: str, title: str) -> str:
        normalized = title.lower()
        if task_type in {"Milestone", "Epic"}:
            return "pm"
        if any(token in normalized for token in ("review", "validate", "qa", "test")):
            return "reviewer"
        if any(token in normalized for token in ("scope", "spec", "plan", "handoff")):
            return "planner"
        return "executor"

    def _preferred_skill_for_role(self, role: str) -> str:
        if role in {"planner", "pm", "reviewer"}:
            return "pm-plan-translator"
        return "notion-pm-bridge"

    def _execution_mode_for_role(self, role: str, title: str) -> str:
        normalized = title.lower()
        if any(token in normalized for token in ("signoff", "approval", "launch")):
            return "human"
        if role in {"planner", "pm", "reviewer"}:
            return "pair"
        return "agent"

    def _parallelizable_for_task(self, task_type: str, title: str) -> bool:
        normalized = title.lower()
        if task_type in {"Milestone", "Epic", "Research"}:
            return False
        if any(token in normalized for token in ("foundation", "architecture", "migration", "review", "validate", "release", "deploy")):
            return False
        return task_type in {"Task", "Subtask", "Bug", "Feature"}

    def _unique_task_key(self, title: str, seen: set[str]) -> str:
        base = self._slugify(title)
        key = base
        suffix = 2
        while key in seen:
            key = f"{base}-{suffix}"
            suffix += 1
        seen.add(key)
        return key

    def _build_task_graph_from_markdown(
        self,
        project: ProjectSpec,
        source_plan_path: str,
        markdown: str,
        *,
        handoff_id: str,
        task_input_path: str | None = None,
        task_input_markdown: str | None = None,
    ) -> TaskGraphSpec:
        if self._looks_like_recovery_plan(markdown):
            return self._build_recovery_task_graph_from_markdown(
                project,
                source_plan_path,
                markdown,
                handoff_id=handoff_id,
            )
        if task_input_markdown and task_input_path and self._looks_like_shipping_task_plan(task_input_markdown):
            return self._build_shipping_task_graph_from_markdown(
                project,
                source_plan_path,
                markdown,
                task_input_path,
                task_input_markdown,
                handoff_id=handoff_id,
            )
        meta_sections = {
            "goal",
            "inputs",
            "summary",
            "objective",
            "brief",
            "goals",
            "non goals",
            "scope",
            "scope notes",
            "constraints",
            "open questions",
            "risks",
            "testing",
            "acceptance criteria",
            "definition of completion",
            "maintenance baseline",
            "rollout",
            "monitoring",
            "additional rescue context",
            "rescue understanding",
            "bring it home workstreams",
            "human decisions before approval",
            "notion handoff gate",
            "how to read this plan",
            "project goal",
        }
        tasks: list[TaskSpec] = []
        seen_keys: set[str] = set()
        sequence = 1
        default_milestone_key = ""
        current_milestone_key = ""
        current_epic_key = ""
        current_task_key = ""
        in_code_block = False

        def add_task(title: str, task_type: str, *, parent_key: str | None = None, priority: str | None = None) -> TaskSpec:
            nonlocal sequence
            role = self._agent_role_for_task(task_type, title)
            task = TaskSpec(
                key=self._unique_task_key(title, seen_keys),
                title=title.strip(),
                description=title.strip(),
                type=task_type,
                status="Ready",
                priority=priority or ("High" if task_type in {"Milestone", "Epic"} else "Normal"),
                parent_key=parent_key,
                execution_mode=self._execution_mode_for_role(role, title),
                parallelizable=self._parallelizable_for_task(task_type, title),
                repo_ref=source_plan_path,
                plan_revision=handoff_id,
                agent_role=role,
                preferred_skill=self._preferred_skill_for_role(role),
                sequence=sequence,
                source_revision=source_plan_path,
                review_status="pending",
            )
            sequence += 1
            tasks.append(task)
            return task

        def ensure_default_milestone() -> str:
            nonlocal default_milestone_key, current_milestone_key
            if not default_milestone_key:
                default_milestone_key = add_task("Implementation Handoff", "Milestone", priority="High").key
            current_milestone_key = default_milestone_key
            return current_milestone_key

        for raw_line in markdown.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block or not stripped:
                continue

            heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                normalized_heading = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
                actionable = normalized_heading not in meta_sections
                current_task_key = ""

                if level == 1:
                    continue
                if level == 2:
                    current_epic_key = ""
                    if actionable:
                        current_milestone_key = add_task(title, "Milestone", priority="High").key
                    else:
                        current_milestone_key = ""
                    continue
                if level >= 3:
                    if not actionable:
                        if level == 3:
                            current_epic_key = ""
                        continue
                    milestone_key = current_milestone_key or ensure_default_milestone()
                    current_epic_key = add_task(title, "Epic", parent_key=milestone_key, priority="High").key
                    continue

            bullet_match = re.match(r"^(\s*)(?:[-*+]|\d+\.)\s+(.*)$", raw_line)
            if not bullet_match:
                continue
            content = re.sub(r"^\[[ xX]\]\s*", "", bullet_match.group(2).strip())
            if not content:
                continue
            indent = len(bullet_match.group(1))
            if not current_milestone_key:
                ensure_default_milestone()
            if current_epic_key:
                if indent >= 2 and current_task_key:
                    parent_key = current_task_key
                    task_type = "Subtask"
                else:
                    parent_key = current_epic_key
                    task_type = self._task_type_from_title(content)
            else:
                if indent >= 2 and current_task_key:
                    parent_key = current_task_key
                    task_type = "Subtask"
                else:
                    parent_key = current_milestone_key
                    task_type = self._task_type_from_title(content)
            created = add_task(content, task_type, parent_key=parent_key)
            if task_type != "Subtask":
                current_task_key = created.key

        if not tasks:
            milestone = add_task("Implementation Handoff", "Milestone", priority="High")
            add_task("Execute approved plan", "Task", parent_key=milestone.key)

        children_by_parent: dict[str | None, list[TaskSpec]] = {}
        for task in tasks:
            children_by_parent.setdefault(task.parent_key, []).append(task)

        for siblings in children_by_parent.values():
            ordered = sorted(siblings, key=lambda item: item.sequence or 0)
            previous_key = ""
            for item in ordered:
                if previous_key and (item.type in {"Milestone", "Epic"} or not item.parallelizable):
                    dependencies = [dependency for dependency in item.dependencies if dependency != previous_key]
                    dependencies.append(previous_key)
                    item.dependencies = dependencies
                previous_key = item.key

        self._apply_parallel_metadata(tasks)
        self._apply_completion_defaults(tasks)

        summary = f"Generated {len(tasks)} work items from `{source_plan_path}`."
        return TaskGraphSpec(
            project=project,
            source_plan_path=source_plan_path,
            handoff_id=handoff_id,
            created_at=self._utc_now(),
            summary=summary,
            tasks=tasks,
        )

    def _review_task_graph(self, graph_path: str, graph: TaskGraphSpec) -> DecompositionReviewSpec:
        by_key = {task.key: task for task in graph.tasks}
        children_by_parent: dict[str, list[TaskSpec]] = {}
        findings: list[str] = []
        required_fixes: list[str] = []

        for task in graph.tasks:
            if task.parent_key:
                children_by_parent.setdefault(task.parent_key, []).append(task)
                if task.parent_key not in by_key:
                    required_fixes.append(f"`{task.key}` references missing parent `{task.parent_key}`.")
            if task.type == "Subtask" and not task.parent_key:
                required_fixes.append(f"`{task.key}` is a subtask without a parent.")
            if task.type == "Milestone" and task.parent_key:
                required_fixes.append(f"`{task.key}` is a milestone but has parent `{task.parent_key}`.")
            if not task.agent_role:
                required_fixes.append(f"`{task.key}` is missing `Agent Role`.")
            if not task.preferred_skill:
                required_fixes.append(f"`{task.key}` is missing `Preferred Skill`.")
            for dependency in task.dependencies:
                if dependency not in by_key:
                    required_fixes.append(f"`{task.key}` references missing dependency `{dependency}`.")

        if not any(task.type == "Milestone" for task in graph.tasks):
            required_fixes.append("Task graph must contain at least one `Milestone`.")
        if not any(task.type in {"Task", "Subtask", "Bug", "Research", "Feature"} for task in graph.tasks):
            required_fixes.append("Task graph must contain at least one executable work item.")

        for task in graph.tasks:
            if task.type in {"Milestone", "Epic"} and not children_by_parent.get(task.key):
                required_fixes.append(f"`{task.key}` is a `{task.type}` without child work items.")
            if task.type not in {"Milestone", "Epic"} and not task.parent_key:
                findings.append(f"`{task.key}` is a root-level executable item; confirm it should not be nested under a milestone or epic.")
            if task.type == "Subtask" and any(child.parent_key == task.key for child in graph.tasks):
                required_fixes.append(f"`{task.key}` is a subtask with nested children.")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_key: str) -> None:
            if task_key in visited:
                return
            if task_key in visiting:
                required_fixes.append(f"Dependency cycle detected at `{task_key}`.")
                return
            visiting.add(task_key)
            for dependency in by_key[task_key].dependencies:
                if dependency in by_key:
                    visit(dependency)
            visiting.remove(task_key)
            visited.add(task_key)

        for task in graph.tasks:
            visit(task.key)

        if not required_fixes:
            findings.append(f"Validated `{len(graph.tasks)}` work items with reviewer checks.")

        return DecompositionReviewSpec(
            project_identifier=graph.project.identifier,
            source_plan_path=graph.source_plan_path,
            task_graph_path=graph_path,
            review_status="pass" if not required_fixes else "changes_required",
            findings=findings,
            required_fixes=required_fixes,
            reviewed_at=self._utc_now(),
        )

    def _phase_section_map(self, markdown: str) -> dict[str, str]:
        return {
            title.strip(): body.strip()
            for title, body in self._extract_h2_sections(markdown)
            if title.strip()
        }

    def _phase_plan_notes(self, approved_plan: str, phase_title: str) -> str:
        sections = self._phase_section_map(approved_plan)
        if phase_title in sections:
            return sections[phase_title]
        phase_prefix = phase_title.split("—", 1)[0].strip()
        for title, body in sections.items():
            if title.strip() == phase_prefix or title.startswith(phase_prefix):
                return body
        return ""

    def _render_phase_plan_doc(
        self,
        milestone: TaskSpec,
        phase_tasks: list[TaskSpec],
        *,
        approved_plan: str,
        task_section_markdown: str,
    ) -> str:
        plan_notes = self._phase_plan_notes(approved_plan, milestone.title)
        lines = [
            f"# {milestone.title} Plan",
            "",
            "## Why this phase exists",
            milestone.description.strip() or "This phase captures one major delivery segment of the approved plan.",
            "",
            "## Schedule",
            f"- Agent-grounded estimate: `{milestone.agent_estimate_hours or 0}` hours",
            f"- Human estimate: `{milestone.human_estimate_hours or 0}` hours",
            f"- Timeline: `{milestone.start_date or 'TBD'}` -> `{milestone.due_date or 'TBD'}`",
        ]
        if milestone.dependencies:
            lines.append(f"- Blocked by phases: `{', '.join(milestone.dependencies)}`")
        if plan_notes:
            lines.extend(["", "## Approved plan notes", plan_notes.strip()])
        if task_section_markdown.strip():
            lines.extend(["", "## Task-sheet notes", task_section_markdown.strip()])
        lines.extend(["", "## Phase outcomes"])
        for task in phase_tasks:
            lines.append(
                f"- `{task.title}`: `{task.agent_estimate_hours or 0}` agent hrs, "
                f"`{task.human_estimate_hours or 0}` human hrs, "
                f"`{task.execution_slot or 'order pending'}`"
            )
        return "\n".join(lines).strip() + "\n"

    def _render_phase_tasks_doc(self, milestone: TaskSpec, phase_tasks: list[TaskSpec]) -> str:
        lines = [
            f"# {milestone.title} Tasks",
            "",
            "## Execution order",
        ]
        for task in sorted(phase_tasks, key=lambda item: (item.sequence or 0, item.title)):
            dependency_text = ", ".join(task.dependencies) if task.dependencies else "none"
            parallel_text = ", ".join(task.parallel_with) if task.parallel_with else "none"
            lines.extend(
                [
                    f"### {task.title}",
                    f"- Implementation slot: `{task.execution_slot or 'order pending'}`",
                    f"- Type: `{task.type}`",
                    f"- Agent role: `{task.agent_role or 'executor'}`",
                    f"- Dependencies: `{dependency_text}`",
                    f"- Parallel with: `{parallel_text}`",
                    f"- Agent estimate: `{task.agent_estimate_hours or 0}` hours",
                    f"- Human estimate: `{task.human_estimate_hours or 0}` hours",
                    f"- Delivery status default: `{task.completion_state or 'Not started'}`",
                    "",
                    task.description.strip(),
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    def _phase_doc_specs(
        self,
        project_slug: str,
        revision_key: str,
        approved_plan: str,
        handoff: HandoffSpec,
        *,
        task_input_markdown: str | None = None,
    ) -> list[DocSpec]:
        task_sections = self._phase_section_map(task_input_markdown or "")
        phase_docs: list[DocSpec] = []
        for milestone in [task for task in handoff.tasks if task.type == "Milestone"]:
            phase_tasks = [
                task
                for task in handoff.tasks
                if task.parent_key == milestone.key and task.type != "Milestone"
            ]
            plan_markdown = self._render_phase_plan_doc(
                milestone,
                phase_tasks,
                approved_plan=approved_plan,
                task_section_markdown=task_sections.get(milestone.title, ""),
            )
            tasks_markdown = self._render_phase_tasks_doc(milestone, phase_tasks)
            plan_path = self.artifacts.write_phase_doc(project_slug, milestone.title, "plan", plan_markdown, revision_key=revision_key)
            tasks_path = self.artifacts.write_phase_doc(project_slug, milestone.title, "tasks", tasks_markdown, revision_key=revision_key)
            phase_docs.extend(
                [
                    DocSpec(
                        title=f"{milestone.title} Plan",
                        content=plan_markdown.strip(),
                        description="Phase-level planning copy for this workstream.",
                        repo_path=plan_path,
                        doc_type="Phase Plan",
                        stage="Approved Plan",
                        status="Active",
                    ),
                    DocSpec(
                        title=f"{milestone.title} Tasks",
                        content=tasks_markdown.strip(),
                        description="Phase-level task sheet for this workstream.",
                        repo_path=tasks_path,
                        doc_type="Phase Tasks",
                        stage="Execution",
                        status="Active",
                    ),
                ]
            )
        return phase_docs

    def _handoff_docs(
        self,
        project_slug: str,
        revision_key: str,
        project: ProjectSpec,
        approved_plan: str,
        handoff: HandoffSpec,
        *,
        task_input_path: str | None = None,
        task_input_markdown: str | None = None,
    ) -> list[DocSpec]:
        type_counts: dict[str, int] = {}
        total_human_hours = 0
        total_agent_hours = 0
        next_executor_tasks = [
            task
            for task in handoff.tasks
            if task.type not in {"Milestone", "Epic"}
        ]
        for task in handoff.tasks:
            type_counts[task.type] = type_counts.get(task.type, 0) + 1
            if task.type not in {"Milestone", "Epic"}:
                total_human_hours += task.human_estimate_hours or 0
                total_agent_hours += task.agent_estimate_hours or 0
        project_goal = (
            self._extract_markdown_section(approved_plan, "Project Goal")
            or self._extract_markdown_section(approved_plan, "Goal")
            or project.description
        ).strip()
        lines = [
            "# Handoff Summary",
            "",
            f"- Handoff ID: `{handoff.handoff_id}`",
            f"- Source plan: `{handoff.source_plan_path}`",
            f"- Task input: `{task_input_path or 'embedded in approved plan'}`",
            f"- Task graph: `{handoff.task_graph_path}`",
            f"- Decomposition review: `{handoff.review_path}`",
            f"- Review status: `{handoff.review_status}`",
            f"- Human-estimated effort: `{total_human_hours}` hours",
            f"- Agent-grounded effort: `{total_agent_hours}` hours",
            "",
            "## Project Goal",
            project_goal,
            "",
            "## Work Item Counts",
        ]
        for task_type in sorted(type_counts):
            lines.append(f"- {task_type}: {type_counts[task_type]}")
        lines.extend(["", "## Phases"])
        for milestone in [task for task in handoff.tasks if task.type == "Milestone"]:
            lines.append(
                f"- {milestone.title}: `{milestone.agent_estimate_hours or 0}` agent hrs, "
                f"`{milestone.human_estimate_hours or 0}` human hrs, "
                f"`{milestone.start_date or 'TBD'}` -> `{milestone.due_date or 'TBD'}`"
            )
        if next_executor_tasks:
            lines.extend(["", "## First Execution Queue"])
            for task in sorted(next_executor_tasks, key=lambda item: (item.sequence or 0, item.title))[:8]:
                lines.append(
                    f"- {task.title}: `{task.agent_estimate_hours or 0}` agent hrs, "
                    f"`{task.human_estimate_hours or 0}` human hrs, "
                    f"depends on `{', '.join(task.dependencies) or 'none'}`"
                )
        docs = [
            DocSpec(title="Final Approved Plan", content=approved_plan.strip()),
            DocSpec(
                title="Execution Runbook",
                content=(
                    "1. Finalize and approve the implementation plan in `plans/<project_slug>/approved-plan.md`.\n"
                    "2. Ask Codex to decompose that approved plan and run reviewer checks.\n"
                    "3. Ask Codex to build or reconcile the Notion execution workspace only after reviewer pass.\n"
                    "4. Let execution agents claim, update, block, and finish tasks directly in Notion.\n"
                    "5. Re-run decomposition and review whenever the approved plan changes."
                ),
            ),
            DocSpec(title="Dashboard Snapshot", content="Codex will publish the latest execution dashboard here."),
            DocSpec(title="Handoff Summary", content="\n".join(lines).strip()),
            DocSpec(title="Notion MCP Prompts", content=self.bridge._mcp_prompt_content(project)),
        ]
        if task_input_markdown and task_input_markdown.strip():
            docs.insert(1, DocSpec(title="Shipping Tasks", content=task_input_markdown.strip()))
        docs.extend(
            self._phase_doc_specs(
                project_slug,
                revision_key,
                approved_plan,
                handoff,
                task_input_markdown=task_input_markdown,
            )
        )
        return docs

    def _project_from_artifacts(self, project_slug: str, approved_plan: str, explicit_name: str | None = None) -> ProjectSpec:
        project_name = explicit_name or project_slug.replace("-", " ").title()
        description = (
            self._extract_markdown_section(approved_plan, "Project Goal")
            or self._extract_markdown_section(approved_plan, "Goal")
            or self._extract_markdown_section(approved_plan, "Objective")
            or project_name
        )
        description = description.strip().splitlines()[0] if description.strip() else project_name
        return ProjectSpec(identifier=project_slug, name=project_name.strip(), description=description.strip())

    def register_approved_plan(self, project_name: str, plan_path: str, task_plan_path: str | None = None) -> dict[str, Any]:
        project = self._project_spec(project_name)
        bundle = self.artifacts.register_approved_plan_bundle(project, plan_path, task_source_path=task_plan_path)
        revision_key = bundle["revision_key"]
        canonical_path = bundle["approved_plan_path"]
        versioned_path = bundle["approved_plan_versioned_path"]
        state = self.bridge._reset_state_for_project_switch(self._load_state(), project.identifier)
        potentially_foreign_paths = [
            state.approved_plan_path,
            state.task_graph_path,
            state.review_path,
            state.handoff_path,
            state.current_state_path,
            state.recovery_plan_path,
            state.detailed_scan_path,
        ]
        if any(
            path and not self.bridge._artifact_belongs_to_project(path, project.identifier)
            for path in potentially_foreign_paths
        ):
            self.bridge._clear_workspace_state(state)
        state.project_identifier = project.identifier
        state.approved_plan_path = canonical_path
        state.approved_plan_revision_key = revision_key
        state.task_graph_path = ""
        state.review_path = ""
        state.handoff_path = ""
        state.current_state_path = ""
        state.recovery_plan_path = ""
        state.detailed_scan_path = ""
        state.active_handoff_id = ""
        state.active_review_status = ""
        self._save_state(state)
        return {
            "project_identifier": project.identifier,
            "approved_plan_path": canonical_path,
            "approved_plan_revision_key": revision_key,
            "approved_plan_versioned_path": versioned_path,
            "approved_tasks_path": bundle["approved_tasks_path"],
            "approved_tasks_versioned_path": bundle["approved_tasks_versioned_path"],
        }

    def decompose_approved_plan(
        self,
        project_ref: str,
        *,
        task_graph: TaskGraphSpec | None = None,
    ) -> dict[str, Any]:
        project_slug = self._resolve_project_slug(project_ref)
        revision_key = self._resolve_plan_revision_key(project_slug)
        revision_key, approved_plan_path, approved_plan = self.artifacts.load_approved_plan_revision(project_slug, revision_key)
        task_input_path, task_input_markdown = self.artifacts.load_optional_approved_tasks_revision(project_slug, revision_key)
        display_name = self._display_project_name(project_ref, project_slug)
        project = task_graph.project if task_graph else self._project_from_artifacts(project_slug, approved_plan, explicit_name=display_name)
        handoff_id = task_graph.handoff_id if task_graph and task_graph.handoff_id else revision_key
        graph = task_graph or self._build_task_graph_from_markdown(
            project,
            approved_plan_path,
            approved_plan,
            handoff_id=handoff_id,
            task_input_path=task_input_path,
            task_input_markdown=task_input_markdown,
        )
        graph.handoff_id = handoff_id
        graph.created_at = graph.created_at or self._utc_now()
        graph.source_plan_path = approved_plan_path
        graph_path = self.artifacts.write_task_graph(project_slug, graph, revision_key=revision_key)
        review_path = self.artifacts._relative(self.artifacts.revision_artifact_path(project_slug, revision_key, DECOMPOSITION_REVIEW_FILENAME))

        handoff = HandoffSpec(
            handoff_id=handoff_id,
            project=project,
            source_plan_path=approved_plan_path,
            task_graph_path=graph_path,
            review_path=review_path,
            review_status="pending",
            created_at=self._utc_now(),
            summary=graph.summary,
            docs=self._handoff_docs(
                project_slug,
                revision_key,
                project,
                approved_plan,
                HandoffSpec(
                    handoff_id=handoff_id,
                    project=project,
                    source_plan_path=approved_plan_path,
                    task_graph_path=graph_path,
                    review_path=review_path,
                    review_status="pending",
                    created_at=self._utc_now(),
                    summary=graph.summary,
                    tasks=graph.tasks,
                ),
                task_input_path=task_input_path,
                task_input_markdown=task_input_markdown,
            ),
            tasks=[
                replace(
                    task,
                    plan_revision=revision_key,
                    source_revision=approved_plan_path,
                    decomposition_review=review_path,
                    review_status="pending",
                )
                for task in graph.tasks
            ],
        )
        handoff_path = self.artifacts.write_handoff(project_slug, handoff, revision_key=revision_key)

        state = self._load_state()
        state.project_identifier = project.identifier
        state.approved_plan_path = approved_plan_path
        state.approved_plan_revision_key = revision_key
        state.task_graph_path = graph_path
        state.review_path = review_path
        state.handoff_path = handoff_path
        state.active_handoff_id = handoff_id
        state.active_review_status = "pending"
        self._save_state(state)

        return {
            "project_identifier": project.identifier,
            "approved_plan_path": approved_plan_path,
            "approved_plan_revision_key": revision_key,
            "task_graph_path": graph_path,
            "handoff_path": handoff_path,
            "review_path": review_path,
            "handoff_id": handoff_id,
            "tasks_seeded": len(graph.tasks),
        }

    def review_decomposition(
        self,
        project_ref: str,
        *,
        review: DecompositionReviewSpec | None = None,
    ) -> dict[str, Any]:
        project_slug = self._resolve_project_slug(project_ref)
        revision_key = self._resolve_plan_revision_key(project_slug)
        graph_path, graph = self.artifacts.load_task_graph(project_slug, revision_key)
        generated_review = review or self._review_task_graph(graph_path, graph)
        review_path = self.artifacts.write_review(project_slug, generated_review, revision_key=revision_key)
        handoff_path, handoff = self.artifacts.load_handoff(project_slug, revision_key)
        handoff.review_path = review_path
        handoff.review_status = generated_review.review_status
        handoff.tasks = [
            replace(
                task,
                decomposition_review=review_path,
                review_status=generated_review.review_status,
            )
            for task in handoff.tasks
        ]
        handoff_path = self.artifacts.write_handoff(project_slug, handoff, revision_key=revision_key)

        state = self._load_state()
        state.project_identifier = graph.project.identifier
        state.approved_plan_revision_key = revision_key
        state.task_graph_path = graph_path
        state.review_path = review_path
        state.handoff_path = handoff_path
        state.active_handoff_id = handoff.handoff_id
        state.active_review_status = generated_review.review_status
        self._save_state(state)

        return {
            "project_identifier": graph.project.identifier,
            "approved_plan_revision_key": revision_key,
            "task_graph_path": graph_path,
            "review_path": review_path,
            "review_status": generated_review.review_status,
            "required_fixes": generated_review.required_fixes,
        }

    def _require_handoff_ready(self, project_ref: str) -> tuple[str, str, str, str, HandoffSpec]:
        project_slug = self._resolve_project_slug(project_ref)
        revision_key = self._resolve_plan_revision_key(project_slug)
        _resolved_revision, approved_plan_path, _approved_plan = self.artifacts.load_approved_plan_revision(project_slug, revision_key)
        graph_path, _graph = self.artifacts.load_task_graph(project_slug, revision_key)
        review_path, review = self.artifacts.load_review(project_slug, revision_key)
        handoff_path, handoff = self.artifacts.load_handoff(project_slug, revision_key)
        if review.review_status != "pass" or handoff.review_status != "pass":
            raise StateError("Reviewer gate has not passed. Fix the decomposition review before building the Notion workspace.")
        return approved_plan_path, graph_path, review_path, handoff_path, handoff

    def _sync_workspace_from_handoff(self, project_ref: str, *, reconcile_removed: bool) -> dict[str, Any]:
        self._emit_progress(f"Loading reviewed handoff for `{project_ref}`.")
        approved_plan_path, graph_path, review_path, handoff_path, handoff = self._require_handoff_ready(project_ref)
        revision_key = self._resolve_plan_revision_key(project_ref)
        _resolved_revision, _approved_plan_path, approved_plan = self.artifacts.load_approved_plan_revision(project_ref, revision_key)
        task_input_path, task_input_markdown = self.artifacts.load_optional_approved_tasks_revision(project_ref, revision_key)
        self._emit_progress("Preparing docs and task payload for Notion sync.")
        docs = handoff.docs
        if not docs or not any(doc.doc_type == "Phase Plan" for doc in docs):
            docs = self._handoff_docs(
                self._resolve_project_slug(project_ref),
                revision_key,
                handoff.project,
                approved_plan,
                handoff,
                task_input_path=task_input_path,
                task_input_markdown=task_input_markdown,
            )
        self._emit_progress("Syncing project workspace to Notion.")
        sync_result = self.bridge.sync_plan_revision(
            handoff.project,
            handoff.tasks,
            docs=docs,
            reconcile_removed=reconcile_removed,
            superseded_revision=handoff.handoff_id,
            merge_defaults=False,
        )
        state = self._load_state()
        state.project_identifier = handoff.project.identifier
        state.approved_plan_path = approved_plan_path
        state.approved_plan_revision_key = revision_key
        state.task_graph_path = graph_path
        state.review_path = review_path
        state.handoff_path = handoff_path
        state.active_handoff_id = handoff.handoff_id
        state.active_review_status = handoff.review_status
        self._save_state(state)
        self._emit_progress("Reviewed handoff synced successfully.")
        return {
            "project_identifier": handoff.project.identifier,
            "approved_plan_path": approved_plan_path,
            "approved_plan_revision_key": revision_key,
            "task_graph_path": graph_path,
            "review_path": review_path,
            "handoff_path": handoff_path,
            "handoff_id": handoff.handoff_id,
            "phases_database_id": state.phases_database_id,
            "phases_data_source_id": state.phases_data_source_id,
            "tasks_database_id": state.tasks_database_id,
            "tasks_data_source_id": state.tasks_data_source_id,
            "sync": sync_result,
            "mcp_view_specs": self._handoff_view_specs(),
        }

    def build_workspace_from_handoff(self, project_ref: str) -> dict[str, Any]:
        return self._sync_workspace_from_handoff(project_ref, reconcile_removed=False)

    def reconcile_workspace_from_handoff(self, project_ref: str) -> dict[str, Any]:
        return self._sync_workspace_from_handoff(project_ref, reconcile_removed=True)

    def _fallback_rescue_goal(self, project: ProjectSpec) -> str:
        return (
            f"Recover a clear, auditable path to completion for `{project.name}` and turn the repo into a maintainable "
            "project with one explicit approved plan, durable evidence, and low-ambiguity execution tracking."
        )

    def _extract_markdown_section(self, markdown: str, heading: str) -> str:
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(markdown)
        return match.group(1).strip() if match else ""

    def _render_rescue_current_state(
        self,
        project: ProjectSpec,
        *,
        goal_statement: str,
        reality_markdown: str,
        rescue_stage: str,
        completion_definition: str | None = None,
        maintenance_requirements: str | None = None,
        detailed_scan_path: str | None = None,
    ) -> str:
        lines = [
            "# Current State Snapshot",
            "",
            f"- Project identifier: `{project.identifier}`",
            f"- Rescue stage: `{rescue_stage}`",
            f"- Generated at: `{self._utc_now()}`",
        ]
        if detailed_scan_path:
            lines.append(f"- Detailed scan: `{detailed_scan_path}`")
        lines.extend(
            [
                "",
                "## Project Goal",
                goal_statement.strip(),
                "",
                "## Current Reality",
                (reality_markdown or "- Initial rescue scan still needs more concrete findings.").strip(),
            ]
        )
        if completion_definition and completion_definition.strip():
            lines.extend(["", "## What Completion Requires", completion_definition.strip()])
        if maintenance_requirements and maintenance_requirements.strip():
            lines.extend(["", "## What Maintenance Requires", maintenance_requirements.strip()])
        lines.extend(
            [
                "",
                "## Recovery Questions",
                "- What is already built and should be preserved?",
                "- Which in-flight tasks are still valid?",
                "- What should be explicitly superseded or dropped?",
                "- What new milestones are needed after the rethink?",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _render_recovery_plan(
        self,
        project: ProjectSpec,
        *,
        goal_statement: str,
        current_state_path: str,
        completion_definition: str | None = None,
        maintenance_requirements: str | None = None,
        detailed_scan_path: str | None = None,
        previous_plan_path: str | None = None,
        context_markdown: str | None = None,
    ) -> str:
        completion_items = self._markdown_list_items(completion_definition or "")
        if not completion_items:
            completion_items = [
                "Freeze one finishable v1 boundary and remove ambiguity about what operators and agents should trust.",
                "Stabilize the active execution-state surface, including payloads, endpoints, briefs, UI, and persistence.",
                "Keep the canonical run paths, evidence artifacts, and validation coverage aligned with the shipped workflow.",
            ]
        maintenance_items = self._markdown_list_items(maintenance_requirements or "")
        if not maintenance_items:
            maintenance_items = [
                "Keep one canonical product story across docs, runtime plans, and operator guidance.",
                "Reduce coupling in the biggest files so future changes stay reviewable.",
                "Keep tests and runtime artifacts aligned with the real workflow and easy to inspect.",
            ]
        context_notes = (context_markdown or "").strip()
        lines = [
            "# Recovery Plan",
            "",
            "## Objective",
            f"Stabilize `{project.name}` and convert the repo into one explicit, approved execution plan that can re-enter the normal handoff pipeline.",
            "",
            "## Project Goal",
            goal_statement.strip(),
            "",
            "## How To Read This Plan",
            "- `Rescue Understanding` is for humans. It explains the project boundary, current context, and what should survive the rescue.",
            "- `Bring-It-Home Workstreams` is the only section that should turn into execution work in Notion.",
            "- `Human Decisions Before Approval` and `Notion Handoff Gate` are planning guardrails, not execution tasks.",
            "",
            "## Rescue Understanding",
            f"- Current state snapshot: `{current_state_path}`",
        ]
        if detailed_scan_path:
            lines.append(f"- Detailed rescue scan: `{detailed_scan_path}`")
        if previous_plan_path:
            lines.append(f"- Previous approved plan: `{previous_plan_path}`")
        lines.append("- This document separates rescue diagnosis from the actual work needed to bring the project home.")
        if context_notes:
            lines.extend(["", "### Context Notes", context_notes])
        lines.extend(
            [
                "",
                "## Bring-It-Home Workstreams",
                "### Finish the shippable core",
            ]
        )
        lines.extend(f"- {item}" for item in completion_items)
        lines.extend(["", "### Keep the project maintainable"])
        lines.extend(f"- {item}" for item in maintenance_items)
        lines.extend(
            [
                "",
                "## Human Decisions Before Approval",
                "- Confirm the true project goal and the finishable v1 boundary.",
                "- Confirm which files, commands, artifacts, and evidence are canonical.",
                "- Confirm which old work should be preserved, deferred, or explicitly superseded.",
                "",
                "## Notion Handoff Gate",
                "- Do not build or reconcile the execution workspace until this plan is approved, decomposed, and reviewed.",
                "- When the approved plan changes, create a new revision and reconcile instead of editing live tasks ad hoc.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _render_detailed_scan(
        self,
        project: ProjectSpec,
        *,
        current_state_path: str,
        goal_statement: str,
        detailed_scan_markdown: str,
        completion_definition: str | None = None,
        maintenance_requirements: str | None = None,
    ) -> str:
        lines = [
            "# Detailed Rescue Scan",
            "",
            f"- Project identifier: `{project.identifier}`",
            f"- Generated at: `{self._utc_now()}`",
            f"- Quick scan reference: `{current_state_path}`",
            "",
            "## Project Goal",
            goal_statement.strip(),
        ]
        if completion_definition and completion_definition.strip():
            lines.extend(["", "## What Completion Requires", completion_definition.strip()])
        if maintenance_requirements and maintenance_requirements.strip():
            lines.extend(["", "## What Maintenance Requires", maintenance_requirements.strip()])
        lines.extend(["", "## Detailed Findings", detailed_scan_markdown.strip()])
        return "\n".join(lines).strip() + "\n"

    def _rescue_doc_specs(
        self,
        project: ProjectSpec,
        *,
        current_state_path: str,
        current_state_markdown: str,
        recovery_plan_path: str,
        recovery_plan_markdown: str,
        detailed_scan_path: str = "",
        detailed_scan_markdown: str = "",
    ) -> list[DocSpec]:
        goal_statement = self._extract_markdown_section(current_state_markdown, "Project Goal") or self._fallback_rescue_goal(project)
        notebook_lines = [
            "# Rescue Notebook",
            "",
            "This notebook keeps a durable shared understanding of the rescue effort before the execution workspace exists.",
            "",
            f"- Goal: {goal_statement}",
            f"- Current state: `{current_state_path}`",
            f"- Recovery plan: `{recovery_plan_path}`",
        ]
        if detailed_scan_path:
            notebook_lines.append(f"- Detailed scan: `{detailed_scan_path}`")
        notebook_lines.extend(
            [
                "",
                "## Usage",
                "Use this notebook to preserve context, align on the real project goal, and decide when the repo is ready for an approved handoff.",
                "Keep the core rescue docs as direct pages under the project so they stay easy to scan during recovery.",
            ]
        )
        docs = [
            DocSpec(title="Rescue Notebook", content="\n".join(notebook_lines).strip()),
            DocSpec(title="Recovery Plan", content=recovery_plan_markdown.strip()),
            DocSpec(title="Rescue Current State", content=current_state_markdown.strip()),
        ]
        if detailed_scan_path and detailed_scan_markdown.strip():
            docs.append(DocSpec(title="Rescue Detailed Scan", content=detailed_scan_markdown.strip()))
        return docs

    def rescue_project(
        self,
        project_name: str,
        *,
        context_markdown: str | None = None,
        goal_statement: str | None = None,
    ) -> dict[str, Any]:
        project = self._project_spec(project_name)
        state = self._load_state()
        state_matches_project = self._slugify(state.project_identifier) == project.identifier if state.project_identifier else False
        rescue_state = state if state_matches_project else BridgeState()
        if not state_matches_project:
            state = BridgeState(artifacts=dict(state.artifacts))
        resolved_goal = (goal_statement or self._fallback_rescue_goal(project)).strip()

        reality_sections: list[str] = []
        carryover_lines: list[str] = []
        if rescue_state.approved_plan_path:
            carryover_lines.append(f"- Current approved plan: `{rescue_state.approved_plan_path}`")
        if rescue_state.approved_plan_revision_key:
            carryover_lines.append(f"- Current approved plan revision: `{rescue_state.approved_plan_revision_key}`")
        if rescue_state.handoff_path:
            carryover_lines.append(f"- Latest handoff: `{rescue_state.handoff_path}`")
        if rescue_state.active_review_status:
            carryover_lines.append(f"- Latest review status: `{rescue_state.active_review_status}`")
        if rescue_state.tasks_database_id:
            carryover_lines.append(f"- Notion tasks database: `{rescue_state.tasks_database_id}`")
        if carryover_lines:
            reality_sections.append("### Prior Bridge State\n" + "\n".join(carryover_lines))

        task_summary: dict[str, Any] | None = None
        try:
            if rescue_state.tasks_data_source_id:
                task_summary = self.bridge.next_tasks()
        except BridgeError:
            task_summary = None
        if task_summary:
            reality_sections.append(
                "\n".join(
                    [
                        "### Existing Execution Snapshot",
                        f"- Ready: {len(task_summary['ready'])}",
                        f"- Active: {len(task_summary['active'])}",
                        f"- Blocked: {len(task_summary['blocked'])}",
                        f"- Done: {len(task_summary['done'])}",
                    ]
                )
            )
        if rescue_state.docs_pages:
            docs_lines = ["### Existing Notion Docs"]
            for title in sorted(rescue_state.docs_pages):
                docs_lines.append(f"- {title}")
            reality_sections.append("\n".join(docs_lines))
        if context_markdown and context_markdown.strip():
            reality_sections.append("### Repo Scan Notes\n" + context_markdown.strip())

        reality_markdown = "\n\n".join(section.strip() for section in reality_sections if section.strip())
        current_state_markdown = self._render_rescue_current_state(
            project,
            goal_statement=resolved_goal,
            reality_markdown=reality_markdown,
            rescue_stage="quick-scan",
        )
        current_state_path = self.artifacts.write_current_state(project.identifier, current_state_markdown)

        recovery_plan_markdown = self._render_recovery_plan(
            project,
            goal_statement=resolved_goal,
            current_state_path=current_state_path,
            previous_plan_path=rescue_state.approved_plan_path or None,
            context_markdown=context_markdown,
        )
        recovery_plan_path = self.artifacts.write_recovery_plan(project.identifier, recovery_plan_markdown)

        state.project_identifier = project.identifier
        state.current_state_path = current_state_path
        state.recovery_plan_path = recovery_plan_path
        state.detailed_scan_path = ""
        self._save_state(state)
        return {
            "project_identifier": project.identifier,
            "goal_statement": resolved_goal,
            "current_state_path": current_state_path,
            "recovery_plan_path": recovery_plan_path,
        }

    def deepen_rescue_scan(
        self,
        project_ref: str,
        *,
        detailed_scan_markdown: str,
        goal_statement: str,
        current_reality_summary: str | None = None,
        completion_definition: str | None = None,
        maintenance_requirements: str | None = None,
        publish_to_notion: bool = False,
    ) -> dict[str, Any]:
        project_slug = self._resolve_project_slug(project_ref)
        project_name = project_ref.strip() if project_ref and self._slugify(project_ref) == project_slug else project_slug.replace("-", " ").title()
        project = ProjectSpec(identifier=project_slug, name=project_name, description=goal_statement.strip())

        try:
            current_state_path, _current_state = self.artifacts.load_current_state(project_slug)
        except StateError:
            rescue_result = self.rescue_project(project_name, goal_statement=goal_statement, context_markdown=detailed_scan_markdown)
            current_state_path = str(rescue_result["current_state_path"])

        detailed_scan_markdown = self._render_detailed_scan(
            project,
            current_state_path=current_state_path,
            goal_statement=goal_statement,
            detailed_scan_markdown=detailed_scan_markdown,
            completion_definition=completion_definition,
            maintenance_requirements=maintenance_requirements,
        )
        detailed_scan_path = self.artifacts.write_detailed_scan(project_slug, detailed_scan_markdown)

        current_state_markdown = self._render_rescue_current_state(
            project,
            goal_statement=goal_statement,
            reality_markdown=(
                current_reality_summary.strip()
                if current_reality_summary and current_reality_summary.strip()
                else (
                    f"- Quick rescue scan: `{current_state_path}`\n"
                    f"- Detailed rescue scan: `{detailed_scan_path}`\n"
                    "- The detailed scan should now be treated as the canonical rescue diagnosis until a new approved plan exists."
                )
            ),
            rescue_stage="detailed-scan",
            completion_definition=completion_definition,
            maintenance_requirements=maintenance_requirements,
            detailed_scan_path=detailed_scan_path,
        )
        current_state_path = self.artifacts.write_current_state(project_slug, current_state_markdown)

        recovery_plan_markdown = self._render_recovery_plan(
            project,
            goal_statement=goal_statement,
            current_state_path=current_state_path,
            completion_definition=completion_definition,
            maintenance_requirements=maintenance_requirements,
            detailed_scan_path=detailed_scan_path,
            context_markdown="Use the detailed rescue scan as the basis for the next approved plan revision.",
        )
        recovery_plan_path = self.artifacts.write_recovery_plan(project_slug, recovery_plan_markdown)

        state = self._load_state()
        state_matches_project = self._slugify(state.project_identifier) == project_slug if state.project_identifier else False
        if not state_matches_project:
            state = BridgeState(artifacts=dict(state.artifacts))
        state.project_identifier = project_slug
        state.current_state_path = current_state_path
        state.recovery_plan_path = recovery_plan_path
        state.detailed_scan_path = detailed_scan_path
        self._save_state(state)

        result = {
            "project_identifier": project_slug,
            "goal_statement": goal_statement.strip(),
            "current_state_path": current_state_path,
            "detailed_scan_path": detailed_scan_path,
            "recovery_plan_path": recovery_plan_path,
        }
        if publish_to_notion:
            result["notion"] = self.publish_rescue_docs(project_ref)
        return result

    def publish_rescue_docs(self, project_ref: str) -> dict[str, Any]:
        project_slug = self._resolve_project_slug(project_ref)
        project_name = project_ref.strip() if project_ref and self._slugify(project_ref) == project_slug else project_slug.replace("-", " ").title()
        current_state_path, current_state_markdown = self.artifacts.load_current_state(project_slug)
        recovery_plan_path, recovery_plan_markdown = self.artifacts.load_recovery_plan(project_slug)
        try:
            detailed_scan_path, detailed_scan_markdown = self.artifacts.load_detailed_scan(project_slug)
        except StateError:
            detailed_scan_path, detailed_scan_markdown = "", ""

        goal_statement = self._extract_markdown_section(current_state_markdown, "Project Goal") or self._fallback_rescue_goal(
            ProjectSpec(identifier=project_slug, name=project_name)
        )
        project = ProjectSpec(identifier=project_slug, name=project_name, description=goal_statement)
        state = self._load_state()
        state_matches_project = self._slugify(state.project_identifier) == project_slug if state.project_identifier else False
        if not state_matches_project:
            state = BridgeState(artifacts=dict(state.artifacts))
        state.project_identifier = project_slug
        state.docs_pages = {}
        self._save_state(state)
        docs = self._rescue_doc_specs(
            project,
            current_state_path=current_state_path,
            current_state_markdown=current_state_markdown,
            recovery_plan_path=recovery_plan_path,
            recovery_plan_markdown=recovery_plan_markdown,
            detailed_scan_path=detailed_scan_path,
            detailed_scan_markdown=detailed_scan_markdown,
        )
        result = self.bridge.ensure_project_docs(PlanSpec(project=project, docs=docs), merge_defaults=False)

        state = self._load_state()
        state.project_identifier = project_slug
        state.current_state_path = current_state_path
        state.recovery_plan_path = recovery_plan_path
        state.detailed_scan_path = detailed_scan_path
        self._save_state(state)
        return {
            "project_identifier": project_slug,
            "project_page_id": result["project_page_id"],
            "project_page_url": result["project_page_url"],
            "docs_pages": result["docs_pages"],
            "doc_results": result["doc_results"],
        }

    def draft_from_brief(self, brief_text: str, project_name: str, *, draft: PlanningDraft | None = None) -> dict[str, Any]:
        planning_draft = draft or self._default_draft(brief_text, project_name)
        spec = PlanSpec(project=planning_draft.project, docs=self._base_docs(planning_draft), tasks=[])
        self.bridge.ensure_project_docs(spec)
        state = self._load_state()
        next_revision_number = self._next_revision_number(state)
        revision_key = self._revision_key(next_revision_number)
        revision = planning_draft.to_revision(
            revision_key=revision_key,
            revision_number=next_revision_number,
            status="draft",
            created_at=self._utc_now(),
        )

        self._ensure_revision_page(planning_draft.project, revision, state)
        self._update_plan_index(planning_draft.project, state)
        self._save_state(state)
        return {
            "project_identifier": planning_draft.project.identifier,
            "project_page_id": state.project_page_id,
            "docs_pages": state.docs_pages,
            "revision_key": revision_key,
            "revision_page_id": state.revision_pages[revision_key],
            "revision_status": revision.status,
            "tasks_seeded": len(revision.tasks),
        }

    def revise_plan(self, project_ref: str, change_request: str, *, draft: PlanningDraft | None = None) -> dict[str, Any]:
        state = self._resolve_project_state(project_ref)
        base_revision_key = self._resolve_revision_key(state, None)
        base_revision = self._revision_from_page(state.revision_pages[base_revision_key])
        project_page = self.bridge._safe_retrieve_page(state.project_page_id)
        project = ProjectSpec(
            identifier=state.project_identifier,
            name=self.bridge._page_title(project_page) if project_page else state.project_identifier.replace("-", " ").title(),
            description=base_revision.brief or change_request,
        )
        if draft:
            planning_draft = draft
        else:
            revision_markdown = "\n\n".join(
                [
                    base_revision.markdown.strip(),
                    "## Revision Request",
                    change_request.strip(),
                ]
            ).strip()
            planning_draft = PlanningDraft(
                project=project,
                brief=base_revision.brief or change_request,
                prd_markdown=self.client.retrieve_page_markdown(state.docs_pages["PRD"]).get("markdown", ""),
                architecture_markdown=self.client.retrieve_page_markdown(state.docs_pages["Architecture"]).get("markdown", ""),
                revision_markdown=revision_markdown,
                tasks=list(base_revision.tasks),
                summary=change_request.strip(),
            )

        next_revision_number = self._next_revision_number(state)
        revision_key = self._revision_key(next_revision_number)
        revision = planning_draft.to_revision(
            revision_key=revision_key,
            revision_number=next_revision_number,
            status="draft",
            created_at=self._utc_now(),
        )
        revision.source_revision_key = base_revision_key
        revision.change_request = change_request

        for existing_key, status in list(state.revision_statuses.items()):
            if status == "draft":
                self._set_revision_status(state, existing_key, "superseded")

        self._ensure_revision_page(planning_draft.project, revision, state)
        self._update_plan_index(planning_draft.project, state)
        self._save_state(state)
        return {
            "project_identifier": planning_draft.project.identifier,
            "base_revision_key": base_revision_key,
            "revision_key": revision_key,
            "revision_page_id": state.revision_pages[revision_key],
            "revision_status": revision.status,
        }

    def approve_revision(self, project_ref: str, revision_ref: str) -> dict[str, Any]:
        state = self._resolve_project_state(project_ref)
        revision_key = self._resolve_revision_key(state, revision_ref)
        approved_at = self._utc_now()
        for existing_key, status in list(state.revision_statuses.items()):
            if existing_key == revision_key:
                continue
            if status in {"approved", "draft"}:
                self._set_revision_status(state, existing_key, "superseded")
        revision = self._set_revision_status(state, revision_key, "approved", approved_at=approved_at)
        project_page = self.bridge._safe_retrieve_page(state.project_page_id)
        project = ProjectSpec(
            identifier=state.project_identifier,
            name=self.bridge._page_title(project_page) if project_page else state.project_identifier.replace("-", " ").title(),
            description=revision.brief or "",
        )
        self._update_plan_index(project, state)
        self._save_state(state)
        return {
            "project_identifier": state.project_identifier,
            "revision_key": revision_key,
            "revision_page_id": state.revision_pages[revision_key],
            "revision_status": revision.status,
            "active_revision_key": state.active_revision_key,
        }

    def build_workspace(self, project_ref: str, approved_revision_ref: str) -> dict[str, Any]:
        state = self._resolve_project_state(project_ref)
        revision_key = self._resolve_revision_key(state, approved_revision_ref)
        revision = self._revision_from_page(state.revision_pages[revision_key])
        if revision.status != "approved":
            raise StateError("Only approved revisions can build the task workspace")
        project_page = self.bridge._safe_retrieve_page(state.project_page_id)
        project = self._project_spec(self.bridge._page_title(project_page) if project_page else state.project_identifier.replace("-", " ").title(), revision.brief)
        self.bridge.ensure_task_workspace(project)
        tasks = [
            replace(task, plan_revision=revision.revision_key, superseded_by_revision=None)
            for task in revision.tasks
        ]
        sync_result = self.bridge.sync_plan_revision(
            project,
            tasks,
            reconcile_removed=True,
            superseded_revision=revision.revision_key,
        )
        state = self._load_state()
        self._update_plan_index(project, state)
        self._save_state(state)
        return {
            "project_identifier": project.identifier,
            "revision_key": revision.revision_key,
            "tasks_database_id": state.tasks_database_id,
            "tasks_data_source_id": state.tasks_data_source_id,
            "sync": sync_result,
            "mcp_view_specs": self._revision_view_specs(),
        }

    def reconcile_after_replan(self, project_ref: str, approved_revision_ref: str) -> dict[str, Any]:
        return self.build_workspace(project_ref, approved_revision_ref)

    def _priority_rank(self, value: str | None) -> int:
        ordering = {"Critical": 0, "High": 1, "Normal": 2, "Low": 3}
        return ordering.get(value or "Normal", 2)

    def execute_next(self, project_ref: str, agent_name: str) -> dict[str, Any]:
        state = self._resolve_project_state(project_ref)
        summary = self.bridge.next_tasks()
        ready = [item for item in summary["ready"] if item.get("type") not in {"Milestone", "Epic"}]
        if not ready:
            return {
                "project_identifier": state.project_identifier,
                "selected_task": None,
                "ready": ready,
                "active": summary["active"],
                "blocked": summary["blocked"],
            }

        ready_sorted = sorted(
            ready,
            key=lambda item: (
                item.get("sequence") if item.get("sequence") is not None else 10**9,
                self._priority_rank(item.get("priority")),
                item.get("due_date") or "9999-12-31",
                (item.get("title") or item.get("key") or "").lower(),
            ),
        )
        selected = ready_sorted[0]
        self.bridge.claim(selected["key"], owner=agent_name)
        started = self.bridge.start(selected["key"], owner=agent_name, branch=f"codex/{selected['key']}")
        return {
            "project_identifier": state.project_identifier,
            "selected_task": selected["key"],
            "page_id": started["page_id"],
            "snapshot": started["snapshot"],
            "remaining_ready": [item["key"] for item in ready_sorted[1:]],
        }
