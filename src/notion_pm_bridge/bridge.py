from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable

from .config import BridgeConfig
from .exceptions import APIError, BridgeError, StateError
from .models import BridgeState, DocSpec, PlanSpec, ProjectSpec, TaskSnapshot, TaskSpec
from .notion_client import NotionClient, extract_title, rich_text

MANAGED_START = "<!-- pm-bridge-managed:start -->"
MANAGED_END = "<!-- pm-bridge-managed:end -->"
ESCAPED_MANAGED_START = r"\<!-- pm-bridge-managed:start --\>"
ESCAPED_MANAGED_END = r"\<!-- pm-bridge-managed:end --\>"


def _title_property(value: str) -> dict[str, Any]:
    return {"title": rich_text(value)}


def _rich_text_property(value: str) -> dict[str, Any]:
    return {"rich_text": rich_text(value)}


def _select_property(value: str) -> dict[str, Any]:
    return {"select": {"name": value}}


def _date_property(value: str) -> dict[str, Any]:
    return {"date": {"start": value}}


def _checkbox_property(value: bool) -> dict[str, Any]:
    return {"checkbox": value}


def _number_property(value: int) -> dict[str, Any]:
    return {"number": value}


def _url_property(value: str) -> dict[str, Any]:
    return {"url": value}


def _relation_property(page_ids: list[str]) -> dict[str, Any]:
    return {"relation": [{"id": page_id} for page_id in page_ids]}


class BridgeService:
    def __init__(
        self,
        client: NotionClient,
        config: BridgeConfig,
        *,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.client = client
        self.config = config
        self.progress_callback = progress_callback

    def _load_state(self) -> BridgeState:
        return BridgeState.load(self.config.state_path)

    def _save_state(self, state: BridgeState) -> None:
        state.save(self.config.state_path)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _emit_progress(self, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(message)

    def _slugify(self, value: str) -> str:
        slug = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
        slug = "-".join(part for part in slug.split("-") if part)
        return slug or "item"

    def _status_title(self, state_name: str) -> str:
        return self.config.status_map[state_name]

    def _status_matches(self, title: str | None, state_name: str) -> bool:
        if not title:
            return False
        return title.lower() == self._status_title(state_name).lower()

    def _is_done(self, status_title: str | None, progress: int | None = None) -> bool:
        if progress is not None and progress >= 100:
            return True
        return self._status_matches(status_title, "done")

    def _is_active(self, status_title: str | None) -> bool:
        return self._status_matches(status_title, "in_progress") or self._status_matches(status_title, "review")

    def _normalize_delivery_state(self, delivery_state: str | None) -> str | None:
        if not delivery_state:
            return None
        normalized = delivery_state.strip().lower()
        if normalized in {"completed", "complete", "done"}:
            return "Completed"
        if normalized in {"in progress", "in-progress", "active"}:
            return "In progress"
        if normalized in {"not started", "not-started", "todo", "to do"}:
            return "Not started"
        return delivery_state.strip()

    def _delivery_state_from_progress(self, progress: int | None) -> str:
        if progress is not None and progress >= 100:
            return "Completed"
        if progress is not None and progress > 0:
            return "In progress"
        return "Not started"

    def _sync_progress_and_delivery_state(self, progress: int | None, delivery_state: str | None) -> tuple[int, str]:
        normalized_state = self._normalize_delivery_state(delivery_state)
        if normalized_state == "Completed":
            return 100, "Completed"
        if normalized_state == "In progress":
            if progress is None or progress <= 0 or progress >= 100:
                return 50, "In progress"
            return progress, "In progress"
        if normalized_state == "Not started":
            if progress is not None and progress >= 100:
                return 100, "Completed"
            if progress is not None and progress > 0:
                return progress, "In progress"
            return 0, "Not started"

        inferred = self._delivery_state_from_progress(progress)
        synced_progress = progress if progress is not None else 0
        if inferred == "Completed":
            synced_progress = 100
        elif inferred == "In progress" and synced_progress <= 0:
            synced_progress = 50
        elif inferred == "Not started":
            synced_progress = 0
        return synced_progress, inferred

    def _project_spec_or_default(self, spec: PlanSpec | None) -> ProjectSpec:
        if spec:
            return spec.project
        identifier = self.config.project_identifier
        return ProjectSpec(
            identifier=identifier,
            name=identifier.replace("-", " ").title(),
            description="Agent-managed Notion workspace.",
        )

    def _reset_state_for_project_switch(self, state: BridgeState, project_identifier: str) -> BridgeState:
        if not state.project_identifier or state.project_identifier == project_identifier:
            return state
        return BridgeState(
            project_identifier=project_identifier,
            artifacts=dict(state.artifacts),
        )

    def _clear_workspace_state(self, state: BridgeState) -> None:
        state.project_page_id = ""
        state.project_page_url = ""
        state.phases_database_id = ""
        state.phases_data_source_id = ""
        state.tasks_database_id = ""
        state.tasks_data_source_id = ""
        state.docs_database_id = ""
        state.docs_data_source_id = ""
        state.docs_pages = {}
        state.phase_pages_by_key = {}
        state.task_pages_by_key = {}
        state.titles_by_key = {}
        state.dependencies = {}
        state.snapshot = {}

    def _artifact_belongs_to_project(self, path: str, project_identifier: str) -> bool:
        if not path or not project_identifier:
            return False
        expected_root = (Path.cwd() / self.config.plans_dir / self._slugify(project_identifier)).resolve()
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        else:
            candidate = candidate.resolve()
        try:
            candidate.relative_to(expected_root)
            return True
        except ValueError:
            return False

    def _scoped_artifact_path(self, state: BridgeState, path: str) -> str:
        return path if self._artifact_belongs_to_project(path, state.project_identifier) else ""

    def _require_parent_page_id(self) -> str:
        if not self.config.parent_page_id:
            raise BridgeError("NOTION_PARENT_PAGE_ID is required for bootstrap and sync-plan")
        return self.config.parent_page_id

    def _safe_retrieve_page(self, page_id: str) -> dict[str, Any] | None:
        if not page_id:
            return None
        try:
            return self.client.retrieve_page(page_id)
        except KeyError:
            return None
        except APIError as exc:
            if exc.status == 404:
                return None
            raise

    def _safe_retrieve_database(self, database_id: str) -> dict[str, Any] | None:
        if not database_id:
            return None
        try:
            return self.client.retrieve_database(database_id)
        except KeyError:
            return None
        except APIError as exc:
            if exc.status == 404:
                return None
            raise

    def _safe_retrieve_data_source(self, data_source_id: str) -> dict[str, Any] | None:
        if not data_source_id:
            return None
        try:
            return self.client.retrieve_data_source(data_source_id)
        except KeyError:
            return None
        except APIError as exc:
            if exc.status == 404:
                return None
            raise

    def _page_title(self, page: dict[str, Any]) -> str:
        return extract_title(page)

    def _page_parent_page_id(self, page: dict[str, Any]) -> str | None:
        parent = page.get("parent", {})
        if parent.get("type") == "page_id":
            return parent.get("page_id")
        return None

    def _page_parent_data_source_id(self, page: dict[str, Any]) -> str | None:
        parent = page.get("parent", {})
        if parent.get("type") == "data_source_id":
            return parent.get("data_source_id")
        return None

    def _database_parent_page_id(self, database: dict[str, Any]) -> str | None:
        parent = database.get("parent", {})
        if parent.get("type") == "page_id":
            return parent.get("page_id")
        return None

    def _first_data_source_id(self, database: dict[str, Any]) -> str:
        data_sources = database.get("data_sources", [])
        if not data_sources:
            raise StateError("Notion database does not expose any data sources")
        return str(data_sources[0]["id"])

    def _page_property(self, page: dict[str, Any], name: str) -> dict[str, Any]:
        properties = page.get("properties", {})
        value = properties.get(name, {})
        return value if isinstance(value, dict) else {}

    def _property_text(self, page: dict[str, Any], name: str) -> str:
        prop = self._page_property(page, name)
        if prop.get("type") == "rich_text":
            return "".join(
                item.get("plain_text") or item.get("text", {}).get("content", "")
                for item in prop.get("rich_text", [])
            )
        if prop.get("type") == "title":
            return "".join(
                item.get("plain_text") or item.get("text", {}).get("content", "")
                for item in prop.get("title", [])
            )
        return ""

    def _property_select(self, page: dict[str, Any], name: str) -> str | None:
        prop = self._page_property(page, name)
        if prop.get("type") != "select":
            return None
        select = prop.get("select")
        if isinstance(select, dict):
            return select.get("name")
        return None

    def _property_checkbox(self, page: dict[str, Any], name: str) -> bool | None:
        prop = self._page_property(page, name)
        if prop.get("type") != "checkbox":
            return None
        return bool(prop.get("checkbox"))

    def _property_number(self, page: dict[str, Any], name: str) -> int | None:
        prop = self._page_property(page, name)
        if prop.get("type") != "number":
            return None
        value = prop.get("number")
        return None if value is None else int(value)

    def _property_date(self, page: dict[str, Any], name: str) -> str | None:
        prop = self._page_property(page, name)
        if prop.get("type") != "date":
            return None
        date = prop.get("date")
        if isinstance(date, dict):
            return date.get("start")
        return None

    def _property_relation_ids(self, page: dict[str, Any], name: str) -> list[str]:
        prop = self._page_property(page, name)
        if prop.get("type") != "relation":
            return []
        return [str(item["id"]) for item in prop.get("relation", []) if item.get("id")]

    def _search_project_page(self, project_name: str, parent_page_id: str) -> dict[str, Any] | None:
        for page in self.client.search_exact_title(project_name, filter_type="page"):
            if self._page_parent_page_id(page) == parent_page_id:
                return page
        return None

    def _search_doc_page(
        self,
        title: str,
        *,
        parent_page_id: str | None = None,
        parent_data_source_id: str | None = None,
    ) -> dict[str, Any] | None:
        for page in self.client.search_exact_title(title, filter_type="page"):
            if parent_page_id and self._page_parent_page_id(page) == parent_page_id:
                return page
            if parent_data_source_id and self._page_parent_data_source_id(page) == parent_data_source_id:
                return page
        return None

    def _search_database(self, title: str, project_page_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for data_source in self.client.search_exact_title(title, filter_type="data_source"):
            parent = data_source.get("parent", {})
            database_id = parent.get("database_id")
            if not database_id:
                continue
            database = self._safe_retrieve_database(str(database_id))
            if not database:
                continue
            if self._database_parent_page_id(database) == project_page_id:
                return database, data_source
        return None

    def _task_database_title(self, project: ProjectSpec) -> str:
        return "Tasks"

    def _docs_database_title(self, project: ProjectSpec) -> str:
        return "Docs"

    def _phases_database_title(self, project: ProjectSpec) -> str:
        return "Phases"

    def _phase_group_options(self, tasks: list[TaskSpec] | None = None) -> list[dict[str, str]]:
        palette = ["blue", "green", "orange", "purple", "red", "pink", "brown", "yellow", "default"]
        labels: list[str] = []
        seen: set[str] = set()
        ordered_tasks = sorted(
            tasks or [],
            key=lambda item: (
                item.sequence if item.sequence is not None else 10**9,
                item.title.lower(),
            ),
        )
        for task in ordered_tasks:
            label = ""
            if (task.type or "").lower() == "milestone":
                label = self._phase_group_label(task)
            elif task.phase_group:
                label = task.phase_group
            label = label.strip()
            if not label or label == "No Phase" or label in seen:
                continue
            labels.append(label)
            seen.add(label)
        if not labels:
            labels = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]
        options = [{"name": label, "color": palette[index % len(palette)]} for index, label in enumerate(labels)]
        options.append({"name": "No Phase", "color": "gray"})
        return options

    def _task_schema(self, tasks: list[TaskSpec] | None = None) -> dict[str, Any]:
        statuses = [
            {"name": self._status_title("ready"), "color": "blue"},
            {"name": self._status_title("in_progress"), "color": "yellow"},
            {"name": self._status_title("blocked"), "color": "red"},
            {"name": self._status_title("review"), "color": "orange"},
            {"name": self._status_title("done"), "color": "green"},
            {"name": "Superseded", "color": "gray"},
        ]
        return {
            "Name": {"title": {}},
            "Task ID": {"rich_text": {}},
            "Status": {"select": {"options": statuses}},
            "Delivery Status": {
                "select": {
                    "options": [
                        {"name": "Not started", "color": "gray"},
                        {"name": "In progress", "color": "yellow"},
                        {"name": "Completed", "color": "green"},
                    ]
                }
            },
            "Execution Slot": {"rich_text": {}},
            "Phase Group": {"select": {"options": self._phase_group_options(tasks)}},
            "Type": {
                "select": {
                    "options": [
                        {"name": "Task", "color": "default"},
                        {"name": "Epic", "color": "orange"},
                        {"name": "Feature", "color": "blue"},
                        {"name": "Bug", "color": "red"},
                        {"name": "Research", "color": "purple"},
                        {"name": "Milestone", "color": "green"},
                        {"name": "Subtask", "color": "gray"},
                    ]
                }
            },
            "Priority": {
                "select": {
                    "options": [
                        {"name": "Low", "color": "gray"},
                        {"name": "Normal", "color": "default"},
                        {"name": "High", "color": "orange"},
                        {"name": "Critical", "color": "red"},
                    ]
                }
            },
            "Start": {"date": {}},
            "Due": {"date": {}},
            "Human Estimate (hrs)": {"number": {"format": "number"}},
            "Agent Estimate (hrs)": {"number": {"format": "number"}},
            "Agent Owner": {"rich_text": {}},
            "Execution Mode": {
                "select": {
                    "options": [
                        {"name": "human", "color": "default"},
                        {"name": "agent", "color": "blue"},
                        {"name": "pair", "color": "green"},
                    ]
                }
            },
            "Parallelizable": {"checkbox": {}},
            "Parallel Wave": {
                "select": {
                    "options": [
                        {"name": "Serial", "color": "gray"},
                        {"name": "Solo", "color": "default"},
                        {"name": "Wave A", "color": "blue"},
                        {"name": "Wave B", "color": "green"},
                        {"name": "Wave C", "color": "orange"},
                        {"name": "Wave D", "color": "pink"},
                        {"name": "Wave E", "color": "purple"},
                        {"name": "Wave F", "color": "red"},
                        {"name": "Wave G", "color": "brown"},
                        {"name": "Wave H", "color": "yellow"},
                    ]
                }
            },
            "Agent Role": {
                "select": {
                    "options": [
                        {"name": "planner", "color": "purple"},
                        {"name": "pm", "color": "orange"},
                        {"name": "reviewer", "color": "yellow"},
                        {"name": "executor", "color": "blue"},
                    ]
                }
            },
            "Preferred Skill": {"rich_text": {}},
            "Repo Ref": {"rich_text": {}},
            "Branch Ref": {"rich_text": {}},
            "PR URL": {"url": {}},
            "Commit SHA": {"rich_text": {}},
            "Source Revision": {"rich_text": {}},
            "Plan Revision": {"rich_text": {}},
            "Decomposition Review": {"rich_text": {}},
            "Review Status": {
                "select": {
                    "options": [
                        {"name": "pending", "color": "yellow"},
                        {"name": "pass", "color": "green"},
                        {"name": "changes_required", "color": "red"},
                    ]
                }
            },
            "Sequence": {"number": {"format": "number"}},
            "Superseded By Revision": {"rich_text": {}},
            "Last Agent Sync At": {"rich_text": {}},
            "Progress": {"number": {"format": "number"}},
        }

    def _phase_schema(self) -> dict[str, Any]:
        return {
            "Name": {"title": {}},
            "Priority": {
                "select": {
                    "options": [
                        {"name": "P0", "color": "red"},
                        {"name": "P1", "color": "yellow"},
                        {"name": "P2", "color": "default"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "Not started", "color": "gray"},
                        {"name": "In progress", "color": "blue"},
                        {"name": "Done", "color": "green"},
                    ]
                }
            },
            "Agent Estimate (hrs)": {"number": {"format": "number"}},
            "Human Estimate (hrs)": {"number": {"format": "number"}},
            "Progress": {"number": {"format": "number"}},
            "Timeline": {"date": {}},
            "Plan Revision": {"rich_text": {}},
        }

    def _docs_schema(self) -> dict[str, Any]:
        return {
            "Name": {"title": {}},
            "Description": {"rich_text": {}},
            "Doc Type": {
                "select": {
                    "options": [
                        {"name": "Plan", "color": "blue"},
                        {"name": "Phase Plan", "color": "blue"},
                        {"name": "Task Sheet", "color": "orange"},
                        {"name": "Phase Tasks", "color": "orange"},
                        {"name": "Rescue", "color": "red"},
                        {"name": "Handoff", "color": "purple"},
                        {"name": "Runbook", "color": "green"},
                        {"name": "Dashboard", "color": "yellow"},
                        {"name": "Prompt", "color": "pink"},
                        {"name": "Reference", "color": "default"},
                    ]
                }
            },
            "Stage": {
                "select": {
                    "options": [
                        {"name": "Rescue", "color": "red"},
                        {"name": "Approved Plan", "color": "blue"},
                        {"name": "Execution", "color": "green"},
                        {"name": "Reference", "color": "default"},
                    ]
                }
            },
            "Repo Path": {"rich_text": {}},
            "Source Revision": {"rich_text": {}},
            "Doc Status": {
                "select": {
                    "options": [
                        {"name": "Active", "color": "green"},
                        {"name": "Reference", "color": "blue"},
                        {"name": "Superseded", "color": "gray"},
                    ]
                }
            },
            "Last Synced At": {"rich_text": {}},
        }

    def _merge_select_property_schema(self, current: dict[str, Any], desired: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
        current_options = current.get("select", {}).get("options", [])
        desired_options = desired.get("select", {}).get("options", [])
        if not current_options or not desired_options:
            return None, False

        current_by_name = {
            str(option.get("name")): option
            for option in current_options
            if isinstance(option, dict) and option.get("name")
        }
        desired_names: list[str] = []
        merged: list[dict[str, Any]] = []
        changed = False

        for option in desired_options:
            name = str(option.get("name", "")).strip()
            if not name:
                continue
            desired_names.append(name)
            existing = current_by_name.pop(name, None)
            if existing:
                merged.append(existing)
            else:
                merged.append(option)
                changed = True

        extras = [option for name, option in current_by_name.items() if name not in desired_names]
        if extras:
            merged.extend(extras)

        current_names = [
            str(option.get("name"))
            for option in current_options
            if isinstance(option, dict) and option.get("name")
        ]
        if current_names != [option["name"] for option in merged]:
            changed = True
        if not changed:
            return None, False
        return {"select": {"options": merged}}, True

    def _schema_updates(self, current_properties: dict[str, Any], desired_properties: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for name, schema in desired_properties.items():
            current = current_properties.get(name)
            if not current:
                updates[name] = schema
                continue
            if "select" in schema and current.get("type") == "select":
                merged, changed = self._merge_select_property_schema(current, schema)
                if changed and merged:
                    updates[name] = merged
        return updates

    def _ensure_task_schema(self, state: BridgeState, tasks: list[TaskSpec] | None = None) -> None:
        data_source = self.client.retrieve_data_source(state.tasks_data_source_id)
        current_properties = data_source.get("properties", {})
        updates = self._schema_updates(current_properties, self._task_schema(tasks))
        if "Parent" not in current_properties:
            updates["Parent"] = {"relation": {"data_source_id": state.tasks_data_source_id, "single_property": {}}}
        if "Blocked By" not in current_properties:
            updates["Blocked By"] = {"relation": {"data_source_id": state.tasks_data_source_id, "single_property": {}}}
        if "Parallel With" not in current_properties:
            updates["Parallel With"] = {"relation": {"data_source_id": state.tasks_data_source_id, "single_property": {}}}
        if state.phases_data_source_id and "Phase" not in current_properties:
            updates["Phase"] = {"relation": {"data_source_id": state.phases_data_source_id, "single_property": {}}}
        if updates:
            self.client.update_data_source(state.tasks_data_source_id, properties=updates)

    def _ensure_phase_schema(self, state: BridgeState) -> None:
        data_source = self.client.retrieve_data_source(state.phases_data_source_id)
        current_properties = data_source.get("properties", {})
        updates = self._schema_updates(current_properties, self._phase_schema())
        if "Tasks" not in current_properties and state.tasks_data_source_id:
            updates["Tasks"] = {"relation": {"data_source_id": state.tasks_data_source_id, "single_property": {}}}
        if "Blocked By" not in current_properties:
            updates["Blocked By"] = {"relation": {"data_source_id": state.phases_data_source_id, "single_property": {}}}
        if updates:
            self.client.update_data_source(state.phases_data_source_id, properties=updates)

    def _ensure_phases_database(self, project: ProjectSpec, state: BridgeState) -> dict[str, Any]:
        database = self._safe_retrieve_database(state.phases_database_id)
        if database:
            if self._database_parent_page_id(database) != state.project_page_id or extract_title(database) != self._phases_database_title(project):
                database = None
                state.phases_database_id = ""
                state.phases_data_source_id = ""
        if not database and state.project_page_id:
            match = self._search_database(self._phases_database_title(project), state.project_page_id)
            if match:
                database, data_source = match
                state.phases_database_id = str(database["id"])
                state.phases_data_source_id = str(data_source["id"])

        if not database:
            created = self.client.create_database(
                parent_page_id=state.project_page_id,
                title=self._phases_database_title(project),
                data_source_title=self._phases_database_title(project),
                properties=self._phase_schema(),
                is_inline=False,
            )
            database = created
            state.phases_database_id = str(created["id"])
            state.phases_data_source_id = self._first_data_source_id(created)
        elif not state.phases_data_source_id:
            state.phases_data_source_id = self._first_data_source_id(database)

        self._ensure_phase_schema(state)
        return database

    def _ensure_docs_database(self, project: ProjectSpec, state: BridgeState) -> dict[str, Any]:
        database = self._safe_retrieve_database(state.docs_database_id)
        if database:
            if self._database_parent_page_id(database) != state.project_page_id or extract_title(database) != self._docs_database_title(project):
                database = None
                state.docs_database_id = ""
                state.docs_data_source_id = ""
        if not database and state.project_page_id:
            match = self._search_database(self._docs_database_title(project), state.project_page_id)
            if match:
                database, data_source = match
                state.docs_database_id = str(database["id"])
                state.docs_data_source_id = str(data_source["id"])

        if not database:
            created = self.client.create_database(
                parent_page_id=state.project_page_id,
                title=self._docs_database_title(project),
                data_source_title=self._docs_database_title(project),
                properties=self._docs_schema(),
                is_inline=False,
            )
            database = created
            state.docs_database_id = str(created["id"])
            state.docs_data_source_id = self._first_data_source_id(created)
        elif not state.docs_data_source_id:
            state.docs_data_source_id = self._first_data_source_id(database)

        data_source = self.client.retrieve_data_source(state.docs_data_source_id)
        current_properties = data_source.get("properties", {})
        missing: dict[str, Any] = {}
        for name, schema in self._docs_schema().items():
            if name not in current_properties:
                missing[name] = schema
        if missing:
            self.client.update_data_source(state.docs_data_source_id, properties=missing)
        return database

    def _topological_parent_order(self, tasks: list[TaskSpec]) -> list[TaskSpec]:
        by_key = {item.key: item for item in tasks}
        pending = list(tasks)
        ordered: list[TaskSpec] = []
        while pending:
            progressed = False
            next_round: list[TaskSpec] = []
            for item in pending:
                if not item.parent_key or item.parent_key not in by_key or any(done.key == item.parent_key for done in ordered):
                    ordered.append(item)
                    progressed = True
                else:
                    next_round.append(item)
            if not progressed:
                raise StateError("Could not resolve parent task ordering")
            pending = next_round
        return ordered

    def _docs_in_parent_order(self, docs: list[DocSpec]) -> list[DocSpec]:
        by_title = {item.title: item for item in docs}
        pending = list(docs)
        ordered: list[DocSpec] = []
        while pending:
            progressed = False
            next_round: list[DocSpec] = []
            for item in pending:
                if not item.parent_title or item.parent_title not in by_title or any(done.title == item.parent_title for done in ordered):
                    ordered.append(item)
                    progressed = True
                else:
                    next_round.append(item)
            if not progressed:
                raise StateError("Could not resolve document parent ordering")
            pending = next_round
        return ordered

    def _render_managed_section(self, title: str, body: str, *, metadata: dict[str, Any] | None = None) -> str:
        lines = [MANAGED_START, f"# {title}"]
        if metadata:
            lines.append("")
            for key, value in metadata.items():
                if value in (None, "", []):
                    continue
                pretty_key = key.replace("_", " ").title()
                lines.append(f"- **{pretty_key}:** `{value}`")
        body = body.strip()
        if body:
            lines.extend(["", body])
        lines.extend(["", MANAGED_END])
        return "\n".join(lines).strip()

    def _split_h2_sections(self, markdown: str) -> tuple[str, list[tuple[str, str]]]:
        preamble_lines: list[str] = []
        sections: list[tuple[str, str]] = []
        current_title: str | None = None
        current_lines: list[str] = []
        for raw_line in markdown.splitlines():
            match = re.match(r"^##\s+(.+?)\s*$", raw_line.strip())
            if match:
                if current_title is None:
                    preamble_lines = current_lines
                else:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = match.group(1).strip()
                current_lines = []
                continue
            current_lines.append(raw_line)
        if current_title is None:
            preamble_lines = current_lines
        else:
            sections.append((current_title, "\n".join(current_lines).strip()))
        return "\n".join(preamble_lines).strip(), sections

    def _render_h2_sections(self, preamble: str, sections: list[tuple[str, str]]) -> str:
        blocks: list[str] = []
        if preamble.strip():
            blocks.append(preamble.strip())
        for title, body in sections:
            block = f"## {title.strip()}"
            if body.strip():
                block += f"\n{body.strip()}"
            blocks.append(block)
        return "\n\n".join(blocks).strip()

    def _project_index_line(self, project: ProjectSpec, state: BridgeState) -> str:
        project_url = state.project_page_url or f"https://www.notion.so/{state.project_page_id}"
        return f"- [{project.name}]({project_url})"

    def _line_matches_project_link(self, line: str, project: ProjectSpec, state: BridgeState) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        escaped_name = re.escape(project.name)
        if re.search(rf"\[{escaped_name}\]\(", stripped):
            return True
        if state.project_page_url and state.project_page_url in stripped:
            return True
        if state.project_page_id and state.project_page_id in stripped:
            return True
        return False

    def _ensure_parent_projects_index(self, project: ProjectSpec, state: BridgeState) -> None:
        parent_page_id = self._require_parent_page_id()
        parent_page = self._safe_retrieve_page(parent_page_id)
        if not parent_page:
            return
        current = self.client.retrieve_page_markdown(parent_page_id).get("markdown", "")
        link_line = self._project_index_line(project, state)
        preamble, sections = self._split_h2_sections(current)
        cleaned_sections: list[tuple[str, str]] = []
        projects_index: int | None = None

        for index, (title, body) in enumerate(sections):
            filtered_lines = [
                line
                for line in body.splitlines()
                if not self._line_matches_project_link(line, project, state)
            ]
            cleaned_sections.append((title, "\n".join(filtered_lines).strip()))
            if title.strip().lower() == "projects":
                projects_index = index

        if projects_index is None:
            cleaned_sections.append(("Projects", link_line))
        else:
            title, body = cleaned_sections[projects_index]
            body_lines = [line for line in body.splitlines() if line.strip()]
            if link_line not in body_lines:
                body_lines.append(link_line)
            cleaned_sections[projects_index] = (title, "\n".join(body_lines).strip())

        rendered = self._render_h2_sections(preamble, cleaned_sections)
        if rendered.strip() == current.strip():
            return
        self.client.update_page(parent_page_id, erase_content=True)
        self.client.update_page_markdown(parent_page_id, operation="insert_content", content=rendered)

    def _load_markdown_file(self, path_value: str | None) -> str:
        if not path_value:
            return ""
        path = Path(path_value)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            return ""
        return path.read_text().strip()

    def _extract_markdown_section(self, markdown: str, heading: str) -> str:
        if not markdown.strip():
            return ""
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(markdown)
        return match.group(1).strip() if match else ""

    def _extract_h3_section(self, markdown: str, heading: str) -> str:
        if not markdown.strip():
            return ""
        pattern = re.compile(
            rf"^###\s+{re.escape(heading)}\s*$\n(.*?)(?=^###\s+|^##\s+|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(markdown)
        return match.group(1).strip() if match else ""

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

    def _doc_descriptions(self) -> dict[str, str]:
        return {
            "Docs Library": "Database copy of planning, execution, and instruction markdown synced from the repo.",
            "Rescue Notebook": "Durable rescue context and PM notes before execution work begins.",
            "Rescue Current State": "What the project appears to be today, including current reality and rescue questions.",
            "Rescue Detailed Scan": "Deeper repo-level diagnosis of canonical files, work-in-progress, and legacy noise.",
            "Recovery Plan": "Human-readable bring-it-home plan that separates rescue understanding from executable work.",
            "Final Approved Plan": "The repo-approved plan that became the source of truth for decomposition.",
            "Shipping Tasks": "Companion task sheet that drives the structured release handoff and execution schedule.",
            "Handoff Summary": "Structured summary of the reviewed handoff, milestones, and task counts.",
            "Execution Runbook": "How Codex, reviewer agents, and execution agents are expected to operate.",
            "Dashboard Snapshot": "Current ready, active, blocked, and done status from the live execution workspace.",
            "Notion MCP Prompts": "Codex-facing prompts for rebuilding or refining Notion views when needed.",
            "Notion View Setup": "One-time instructions for building inline linked views and refining the Notion PM surface.",
            "Plan Index": "Revision tracking for plan-first workflows.",
            "Brief": "Short project framing and user/problem summary.",
            "PRD": "Product requirements and scope decisions.",
            "Architecture": "Implementation shape, constraints, and important technical decisions.",
        }

    def _doc_metadata(self, doc: DocSpec, state: BridgeState) -> dict[str, str]:
        title = doc.title
        metadata: dict[str, str] = {
            "doc_type": "Reference",
            "stage": "Reference",
            "status": "Active",
            "repo_path": "",
            "source_revision": state.approved_plan_revision_key or "",
        }
        explicit_paths = {
            "Rescue Current State": state.current_state_path,
            "Recovery Plan": state.recovery_plan_path,
            "Rescue Detailed Scan": state.detailed_scan_path,
            "Final Approved Plan": state.approved_plan_path,
            "Shipping Tasks": str(Path(state.approved_plan_path).with_name("approved-tasks.md")) if state.approved_plan_path else "",
            "Handoff Summary": state.handoff_path,
            "Dashboard Snapshot": state.artifacts.get("dashboard", ""),
            "Notion MCP Prompts": state.artifacts.get("mcp_prompts", ""),
            "Execution Runbook": "",
            "Rescue Notebook": "",
        }
        metadata["repo_path"] = explicit_paths.get(title, "")
        if title.startswith("Rescue") or title == "Recovery Plan":
            metadata["doc_type"] = "Rescue"
            metadata["stage"] = "Rescue"
        elif title in {"Final Approved Plan", "Brief", "PRD", "Architecture", "Plan Index"}:
            metadata["doc_type"] = "Plan"
            metadata["stage"] = "Approved Plan" if title == "Final Approved Plan" else "Reference"
        elif title == "Shipping Tasks":
            metadata["doc_type"] = "Task Sheet"
            metadata["stage"] = "Approved Plan"
        elif title in {"Handoff Summary"}:
            metadata["doc_type"] = "Handoff"
            metadata["stage"] = "Execution"
        elif title in {"Execution Runbook"}:
            metadata["doc_type"] = "Runbook"
            metadata["stage"] = "Execution"
        elif title in {"Dashboard Snapshot"}:
            metadata["doc_type"] = "Dashboard"
            metadata["stage"] = "Execution"
        elif title in {"Notion MCP Prompts"}:
            metadata["doc_type"] = "Prompt"
            metadata["stage"] = "Execution"
        if doc.doc_type:
            metadata["doc_type"] = doc.doc_type
        if doc.stage:
            metadata["stage"] = doc.stage
        if doc.status:
            metadata["status"] = doc.status
        if doc.repo_path:
            metadata["repo_path"] = doc.repo_path
        return metadata

    def _doc_properties(self, doc: DocSpec, state: BridgeState, *, create: bool) -> dict[str, Any]:
        metadata = self._doc_metadata(doc, state)
        properties: dict[str, Any] = {"Name": _title_property(doc.title)}
        description = doc.description if doc.description is not None else self._doc_descriptions().get(doc.title, "")
        if create or description:
            properties["Description"] = _rich_text_property(description)
        if create or metadata["doc_type"]:
            properties["Doc Type"] = _select_property(metadata["doc_type"])
        if create or metadata["stage"]:
            properties["Stage"] = _select_property(metadata["stage"])
        if create or metadata["status"]:
            properties["Doc Status"] = _select_property(metadata["status"])
        if create or metadata["repo_path"]:
            properties["Repo Path"] = _rich_text_property(metadata["repo_path"])
        if create or metadata["source_revision"]:
            properties["Source Revision"] = _rich_text_property(metadata["source_revision"])
        properties["Last Synced At"] = _rich_text_property(self._utc_now())
        return properties

    def _ordered_doc_titles(self, state: BridgeState) -> list[str]:
        preferred = [
            "Rescue Notebook",
            "Rescue Current State",
            "Rescue Detailed Scan",
            "Recovery Plan",
            "Final Approved Plan",
            "Shipping Tasks",
            "Handoff Summary",
            "Execution Runbook",
            "Dashboard Snapshot",
            "Notion MCP Prompts",
            "Brief",
            "PRD",
            "Architecture",
            "Plan Index",
        ]
        remaining = [title for title in state.docs_pages if title not in preferred]
        ordered = [title for title in preferred if title in state.docs_pages]
        ordered.extend(sorted(remaining))
        return ordered

    def _task_link(self, state: BridgeState, key: str) -> str:
        snapshot = state.snapshot.get(key, {})
        title = snapshot.get("title") or state.titles_by_key.get(key) or key
        url = snapshot.get("url")
        if not url:
            page_id = state.task_pages_by_key.get(key, "")
            page = self._safe_retrieve_page(page_id)
            if page:
                url = page.get("url")
        return f"[{title}]({url})" if url else f"`{title}`"

    def _child_task_keys(self, state: BridgeState, parent_key: str) -> list[str]:
        parent_page_id = state.task_pages_by_key.get(parent_key, "")
        if not parent_page_id:
            return []
        children: list[tuple[int, str]] = []
        for key, snapshot in state.snapshot.items():
            parent_ids = snapshot.get("parent_page_ids") or []
            if parent_page_id not in parent_ids:
                continue
            sequence = snapshot.get("sequence") or 0
            children.append((sequence, key))
        return [key for _sequence, key in sorted(children)]

    def _dependency_links(self, task: TaskSpec, state: BridgeState | None) -> list[str]:
        links: list[str] = []
        for dependency in task.dependencies:
            if state:
                links.append(self._task_link(state, dependency))
            else:
                links.append(f"`{dependency}`")
        return links

    def _project_context(self, state: BridgeState) -> dict[str, Any]:
        approved_plan = self._load_markdown_file(self._scoped_artifact_path(state, state.approved_plan_path))
        current_state = self._load_markdown_file(self._scoped_artifact_path(state, state.current_state_path))
        recovery_plan = self._load_markdown_file(self._scoped_artifact_path(state, state.recovery_plan_path))

        goal = (
            self._extract_markdown_section(approved_plan, "Project Goal")
            or self._extract_markdown_section(current_state, "Project Goal")
            or self._extract_markdown_section(recovery_plan, "Project Goal")
        ).strip()

        completion_items = self._markdown_list_items(self._extract_markdown_section(current_state, "What Completion Requires"))
        if not completion_items:
            completion_items = self._markdown_list_items(self._extract_markdown_section(approved_plan, "Definition of Completion"))
        if not completion_items:
            completion_items = self._markdown_list_items(self._extract_h3_section(recovery_plan, "Finish the shippable core"))

        maintenance_items = self._markdown_list_items(self._extract_markdown_section(current_state, "What Maintenance Requires"))
        if not maintenance_items:
            maintenance_items = self._markdown_list_items(self._extract_markdown_section(approved_plan, "Maintenance Baseline"))
        if not maintenance_items:
            maintenance_items = self._markdown_list_items(self._extract_h3_section(recovery_plan, "Keep the project maintainable"))

        return {
            "goal": goal,
            "completion_items": completion_items[:5],
            "maintenance_items": maintenance_items[:5],
        }

    def _parallel_wave_summary(self, state: BridgeState) -> list[tuple[str, list[dict[str, Any]]]]:
        waves: dict[str, list[dict[str, Any]]] = {}
        for snapshot in state.snapshot.values():
            if snapshot.get("type") in {"Milestone", "Epic"}:
                continue
            wave = snapshot.get("parallel_group") or ("Solo" if snapshot.get("parallelizable") else "Serial")
            waves.setdefault(wave, []).append(snapshot)
        ordered: list[tuple[str, list[dict[str, Any]]]] = []
        for wave, items in sorted(waves.items(), key=lambda item: item[0]):
            ordered.append(
                (
                    wave,
                    sorted(
                        items,
                        key=lambda row: (
                            row.get("sequence") if row.get("sequence") is not None else 10**9,
                            (row.get("title") or "").lower(),
                        ),
                    ),
                )
            )
        return ordered

    def _split_phase_tasks(self, tasks: list[TaskSpec]) -> tuple[list[TaskSpec], list[TaskSpec]]:
        phase_tasks = [task for task in tasks if (task.type or "").lower() == "milestone"]
        executable_tasks = [task for task in tasks if (task.type or "").lower() != "milestone"]
        return phase_tasks, executable_tasks

    def _tracking_code(self, task: TaskSpec | None) -> str:
        if not task:
            return ""
        match = re.match(r"^(P\d+\.\d+)", task.title.strip())
        if match:
            return match.group(1)
        return task.key

    def _phase_group_label(self, task: TaskSpec) -> str:
        if task.phase_group:
            return task.phase_group
        title = task.title.strip()
        if (task.type or "").lower() == "milestone" and title:
            return title
        match = re.match(r"^(Phase\s+.+)$", title)
        if match:
            return match.group(1)
        return "No Phase"

    def _derive_execution_slots(self, phase_tasks: list[TaskSpec], executable_tasks: list[TaskSpec]) -> None:
        phase_labels = {task.key: self._phase_group_label(task) for task in phase_tasks}
        ordered = sorted(executable_tasks, key=lambda item: ((item.sequence or 10**9), item.title.lower()))
        tasks_by_key = {task.key: task for task in executable_tasks}
        wave_slots: dict[str, int] = {}
        slot = 0

        for task in ordered:
            task.phase_group = phase_labels.get(task.parent_key or "", "No Phase")
            wave = task.parallel_group or ("Solo" if task.parallelizable else "Serial")
            if wave in {"Serial", "Solo"}:
                slot += 1
                slot_number = slot
            else:
                if wave not in wave_slots:
                    slot += 1
                    wave_slots[wave] = slot
                slot_number = wave_slots[wave]

            dependency_codes = [self._tracking_code(tasks_by_key.get(key)) for key in task.dependencies]
            dependency_codes = [code for code in dependency_codes if code]
            suffix = ""
            if dependency_codes:
                shown = dependency_codes[:2]
                if len(dependency_codes) > 2:
                    shown.append(f"+{len(dependency_codes) - 2} more")
                suffix = f" · after {' + '.join(shown)}"
            task.execution_slot = f"{slot_number:02d} · {wave}{suffix}"

    def _phase_priority(self, task: TaskSpec) -> str:
        if task.sequence is not None and task.sequence <= 10:
            return "P0"
        if task.sequence is not None and task.sequence <= 20:
            return "P1"
        return "P2"

    def _phase_properties(self, task: TaskSpec, *, create: bool) -> dict[str, Any]:
        synced_progress, _ = self._sync_progress_and_delivery_state(task.progress, task.completion_state)
        if synced_progress >= 100:
            phase_status = "Done"
        elif synced_progress > 0:
            phase_status = "In progress"
        else:
            phase_status = "Not started"
        properties: dict[str, Any] = {
            "Name": _title_property(task.title),
            "Priority": _select_property(self._phase_priority(task)),
            "Status": _select_property(phase_status),
            "Progress": _number_property(synced_progress),
            "Plan Revision": _rich_text_property(task.plan_revision or ""),
        }
        if create or task.agent_estimate_hours is not None:
            properties["Agent Estimate (hrs)"] = _number_property(task.agent_estimate_hours if task.agent_estimate_hours is not None else 0)
        if create or task.human_estimate_hours is not None:
            properties["Human Estimate (hrs)"] = _number_property(task.human_estimate_hours if task.human_estimate_hours is not None else 0)
        if create or task.start_date or task.due_date:
            properties["Timeline"] = {"date": {"start": task.start_date, "end": task.due_date or task.start_date}}
        return properties

    def _page_role_lines(self, *, include_manual_setup: bool) -> list[str]:
        lines = [
            "## How Pages Fit Together",
            "- This project home page: PM start page. Use it for the project goal, finish line, maintenance baseline, and the fast path into tasks, phases, and docs.",
            "- `Phases`: source database for the top-level roadmap, grouped workstreams, and cross-phase blockers.",
            "- `Tasks`: source database for the execution table. It should stay readable enough that a human can assign and track work from Notion alone.",
            "- `Docs`: source database for approved plans, task sheets, rescue notes, runbooks, prompts, and dashboards.",
        ]
        if include_manual_setup:
            lines.extend(
                [
                    "",
                    "## Inline View Setup",
                    "- If linked databases are not already embedded, stay on this project page, type `/linked`, choose `Tasks`, and embed the `All tasks` view near the top.",
                    "- Then embed `Phases -> Timeline` below that.",
                    "- Repeat for `Docs` so the document library is visible inline on the same page.",
                    "- After those linked views exist, agents can keep the underlying databases up to date.",
                ]
            )
        return lines

    def _render_team_project(self, spec: PlanSpec, state: BridgeState) -> str:
        context = self._project_context(state)
        summary = self._task_buckets_from_state(state) if state.snapshot else {"ready": [], "active": [], "blocked": [], "done": []}
        lines: list[str] = []
        if spec.project.description.strip():
            lines.append(spec.project.description.strip())
        if context["goal"]:
            lines.extend(["", "## Project Goal", context["goal"]])
        if context["completion_items"]:
            lines.extend(["", "## Finish Line"])
            lines.extend(f"- {item}" for item in context["completion_items"])
        if context["maintenance_items"]:
            lines.extend(["", "## Maintenance Baseline"])
            lines.extend(f"- {item}" for item in context["maintenance_items"])

        lines.extend(
            [
                "",
                "## How To Operate From This Page",
                "- Use `Phases` for roadmap and wave grouping, not as executable cards.",
                "- Use `Status` for workflow lane, and `Delivery Status` for PM-readable completion.",
                "- `Parallel Wave` groups work that can run in the same execution window.",
                "- `Parallel With` names the exact peer tasks that can run together.",
                "- Timeline dates are grounded in `Agent Estimate (hrs)` while `Human Estimate (hrs)` stays visible for planning comparison.",
            ]
        )
        lines.extend([""] + self._page_role_lines(include_manual_setup=True))

        if state.snapshot:
            executable = [row for row in state.snapshot.values() if row.get("type") not in {"Milestone", "Epic"}]
            lines.extend(
                [
                    "",
                    "## Control Panel",
                    f"- Active handoff: `{state.active_handoff_id or 'none'}`",
                    f"- Reviewed plan revision: `{state.approved_plan_revision_key or 'none'}`",
                    f"- Executor work items: `{len(executable)}`",
                    f"- Ready now: `{len(summary['ready'])}`",
                    f"- In progress: `{len(summary['active'])}`",
                    f"- Blocked or superseded: `{len(summary['blocked'])}`",
                    f"- Agent-grounded effort: `{sum((row.get('agent_estimate_hours') or 0) for row in executable)}` hours",
                    f"- Human-estimated effort: `{sum((row.get('human_estimate_hours') or 0) for row in executable)}` hours",
                ]
            )

        lines.extend(["", "## Operating Surfaces"])
        if state.phases_database_id:
            phases_database = self._safe_retrieve_database(state.phases_database_id)
            if phases_database and phases_database.get("url"):
                lines.append(f"- [Phases]({phases_database['url']}): use the saved views `Timeline`, `All phases`, and `By Priority` for the roadmap layer.")
        if state.tasks_database_id:
            database = self._safe_retrieve_database(state.tasks_database_id)
            if database and database.get("url"):
                lines.append(f"- [Tasks]({database['url']}): open `Kanban board`, `All tasks`, `By phase`, `Ready Now`, `Blocked`, `Task Timeline`, and `Done`.")
        if state.docs_database_id:
            docs_database = self._safe_retrieve_database(state.docs_database_id)
            if docs_database and docs_database.get("url"):
                lines.append(f"- [Docs Library]({docs_database['url']}): searchable copies of approved plans, task sheets, runbooks, rescue docs, and prompts.")
        lines.append("- Run the project from Notion alone: this page should be enough to understand the goal, the plan, the current status, and the next assignments.")

        if summary["ready"]:
            lines.extend(["", "## Ready To Assign"])
            for item in summary["ready"][:8]:
                label = f"[{item['title']}]({item['url']})" if item.get("url") else item["title"]
                wave = item.get("parallel_group") or ("Solo" if item.get("parallelizable") else "Serial")
                with_items = ", ".join(item.get("parallel_with") or []) or "none listed"
                lines.append(
                    f"- {label}: `{item.get('agent_estimate_hours') or 0}` agent hrs, `{item.get('human_estimate_hours') or 0}` human hrs, wave `{wave}`, runs with `{with_items}`"
                )

        if summary["blocked"]:
            lines.extend(["", "## Current Blockers"])
            for item in summary["blocked"][:6]:
                unmet = ", ".join(item.get("unmet_dependencies") or item.get("dependencies") or []) or "explicit blocker recorded in task"
                label = f"[{item['title']}]({item['url']})" if item.get("url") else item["title"]
                lines.append(f"- {label}: waiting on {unmet}")

        wave_summary = self._parallel_wave_summary(state)
        lines.extend(["", "## Parallel Waves"])
        if wave_summary:
            for wave, items in wave_summary:
                if not items:
                    continue
                rendered = []
                for row in items:
                    label = f"[{row.get('title')}]({row.get('url')})" if row.get("url") else row.get("title") or "Untitled"
                    rendered.append(label)
                lines.append(f"- `{wave}`: {', '.join(rendered)}")
        else:
            lines.append("- No executor concurrency has been defined yet.")

        lines.extend(
            [
                "",
                "## Key Docs",
                "- Use the `Docs` database views `Planning`, `Execution`, and `Rescue` for the full document set.",
            ]
        )
        for title in ("Final Approved Plan", "Shipping Tasks", "Handoff Summary", "Execution Runbook", "Dashboard Snapshot"):
            page_id = state.docs_pages.get(title)
            if not page_id:
                continue
            page = self._safe_retrieve_page(page_id)
            if page and page.get("url"):
                description = self._doc_descriptions().get(title, "")
                suffix = f": {description}" if description else ""
                lines.append(f"- [{title}]({page['url']}){suffix}")

        return "\n".join(lines).strip()

    def _task_done_guidance(self, task: TaskSpec) -> list[str]:
        normalized = f"{task.title} {task.description}".lower()
        if task.type == "Milestone":
            return [
                "all child work is complete or intentionally superseded",
                "the linked docs and task statuses tell the same story as the shipped state",
            ]
        if any(token in normalized for token in ("execution-state", "payload", "endpoint", "persistence")):
            return [
                "execution-state behavior is consistent across API, storage, and UI surfaces",
                "operators and agents can inspect or update this area without guessing which system is authoritative",
            ]
        if any(token in normalized for token in ("guide", "story", "docs", "operator")):
            return [
                "the user-facing docs and the actual runtime behavior agree",
                "a human PM can understand this area directly from Notion and the linked docs",
            ]
        if any(token in normalized for token in ("test", "review", "validate", "qa")):
            return [
                "automated or reviewer checks cover the real shipped workflow",
                "regressions in this area would be visible before release",
            ]
        return [
            "the task outcome is implemented and reflected in the linked docs or runtime surfaces",
            "blockers and dependencies for this area are explicit enough for another PM or agent to take over",
        ]

    def _task_page_body(self, task: TaskSpec, state: BridgeState | None = None) -> str:
        parts: list[str] = []
        if task.description.strip():
            if re.search(r"^###\s+", task.description, re.MULTILINE):
                parts.append(task.description.strip())
            else:
                parts.extend(["## Why This Matters", task.description.strip()])

        details: list[str] = []
        if task.parent_key:
            if state:
                details.append(f"- Parent workstream: {self._task_link(state, task.parent_key)}")
            else:
                details.append(f"- Parent workstream: `{task.parent_key}`")
        if task.human_estimate_hours is not None:
            details.append(f"- Human estimate: `{task.human_estimate_hours}` hours")
        if task.agent_estimate_hours is not None:
            details.append(f"- Agent-grounded estimate: `{task.agent_estimate_hours}` hours")
        if task.execution_slot:
            details.append(f"- Execution slot: `{task.execution_slot}`")
        if task.phase_group:
            details.append(f"- Phase group: `{task.phase_group}`")
        if task.completion_state:
            details.append(f"- Delivery status: `{task.completion_state}`")
        if task.parallelizable is not None:
            details.append(f"- Parallelizable: `{'yes' if task.parallelizable else 'no'}`")
        if task.parallel_group:
            details.append(f"- Parallel wave: `{task.parallel_group}`")
        if task.start_date:
            details.append(f"- Planned start: `{task.start_date}`")
        if task.due_date:
            details.append(f"- Planned finish: `{task.due_date}`")
        dependency_links = self._dependency_links(task, state)
        if dependency_links:
            details.append(f"- Depends on: {', '.join(dependency_links)}")
        if task.parallel_with:
            parallel_links = [self._task_link(state, key) for key in task.parallel_with] if state else [f"`{key}`" for key in task.parallel_with]
            details.append(f"- Runs with: {', '.join(parallel_links)}")
        if details:
            parts.extend(["## Execution Details", "\n".join(details)])

        child_lines: list[str] = []
        if state:
            for child_key in self._child_task_keys(state, task.key):
                child_snapshot = state.snapshot.get(child_key, {})
                estimate = child_snapshot.get("agent_estimate_hours")
                due = child_snapshot.get("due_date") or "TBD"
                status = child_snapshot.get("status") or "Unknown"
                suffix = f" - `{status}`"
                if estimate is not None:
                    suffix += f", `{estimate}` agent hrs"
                suffix += f", due `{due}`"
                child_lines.append(f"- {self._task_link(state, child_key)}{suffix}")
        if child_lines:
            parts.extend(["## Child Work", "\n".join(child_lines)])

        if "### done means" not in task.description.lower():
            done_lines = [f"- {bullet}" for bullet in self._task_done_guidance(task)]
            parts.extend(["## Done Means", "\n".join(done_lines)])

        if task.notes and task.notes.strip():
            parts.extend(["## Bridge Notes", task.notes.strip()])

        if state:
            reference_lines: list[str] = []
            if state.project_page_url:
                reference_lines.append(f"- [Project Home]({state.project_page_url})")
            for title in self._ordered_doc_titles(state):
                page_id = state.docs_pages.get(title)
                if not page_id:
                    continue
                page = self._safe_retrieve_page(page_id)
                if page and page.get("url"):
                    reference_lines.append(f"- [{title}]({page['url']})")
            if task.repo_ref:
                reference_lines.append(f"- Repo source: `{task.repo_ref}`")
            if reference_lines:
                parts.extend(["## References", "\n".join(reference_lines)])
        parts.extend(["## Activity Log"])
        return "\n\n".join(parts)

    def _render_task_page_markdown(self, task: TaskSpec, state: BridgeState | None = None) -> str:
        metadata = {
            "task_id": task.key,
            "type": task.type,
            "execution_mode": task.execution_mode,
            "parallelizable": task.parallelizable,
            "repo_ref": task.repo_ref,
            "parent_key": task.parent_key,
        }
        if task.completion_state:
            metadata["delivery_status"] = task.completion_state
        if task.parallel_group:
            metadata["parallel_wave"] = task.parallel_group
        if task.phase_group:
            metadata["phase_group"] = task.phase_group
        if task.execution_slot:
            metadata["execution_slot"] = task.execution_slot
        if task.human_estimate_hours is not None:
            metadata["human_estimate_hours"] = task.human_estimate_hours
        if task.agent_estimate_hours is not None:
            metadata["agent_estimate_hours"] = task.agent_estimate_hours
        if task.start_date:
            metadata["start_date"] = task.start_date
        if task.due_date:
            metadata["due_date"] = task.due_date
        return self._render_managed_section(task.title, self._task_page_body(task, state), metadata=metadata)

    def _replace_managed_markdown(self, page_id: str, markdown: str) -> None:
        try:
            current = self.client.retrieve_page_markdown(page_id).get("markdown", "")
        except APIError:
            current = ""

        content_range = None
        if MANAGED_START in current and MANAGED_END in current:
            content_range = f"{MANAGED_START}...{MANAGED_END}"
        elif ESCAPED_MANAGED_START in current and ESCAPED_MANAGED_END in current:
            content_range = f"{ESCAPED_MANAGED_START}...{ESCAPED_MANAGED_END}"

        if content_range:
            self.client.update_page_markdown(
                page_id,
                operation="replace_content_range",
                content=markdown,
                content_range=content_range,
            )
            return
        if current.strip():
            self.client.update_page_markdown(page_id, operation="insert_content", content=f"\n\n{markdown}")
            return
        self.client.update_page_markdown(page_id, operation="insert_content", content=markdown)

    def _append_activity(self, page_id: str, message: str) -> None:
        timestamp = self._utc_now()
        self.client.update_page_markdown(page_id, operation="insert_content", content=f"\n- {timestamp} {message}")

    def _default_docs(self) -> list[DocSpec]:
        return [
            DocSpec(
                title="Brief",
                content="Add the app brief here. Codex will keep this page in sync with the latest project request.",
            ),
            DocSpec(
                title="PRD",
                content="Product requirements draft goes here.",
            ),
            DocSpec(
                title="Architecture",
                content="Architecture notes and implementation constraints go here.",
            ),
            DocSpec(
                title="Plan Index",
                content="This page tracks implementation-plan revisions and the currently active approved plan.",
            ),
            DocSpec(
                title="Execution Runbook",
                content=(
                    "1. Keep the approved plan and task sheet in the repo first.\n"
                    "2. Ask Codex to decompose and review that approved plan before building Notion.\n"
                    "3. Use the project home page as the PM start page.\n"
                    "4. Use `Tasks -> All tasks` as the main execution table.\n"
                    "5. Use `Phases` for roadmap context and `Docs` for the document library."
                ),
            ),
        ]

    def _view_setup_content(self) -> str:
        return (
            "## Recommended Notion Views\n\n"
            "### Workspace Root\n"
            "- Add a short note near the top of the workspace root page explaining the linked-database limitation and the manual setup steps.\n"
            "- Use a notes callout or emoji so humans can quickly see how to finish the inline setup on the project page.\n\n"
            "### Manual Inline Database Workaround\n"
            "- Notion's connector currently rejects creating inline linked-database blocks programmatically.\n"
            "- As a one-time human step, stay on the project home page, type `/linked`, pick `Tasks`, and select the `All tasks` view.\n"
            "- Then embed `Phases -> Timeline`, followed by the `Docs` view you want.\n"
            "- Keep those linked views in place; Codex can keep the underlying databases updated afterward.\n\n"
            "### Phases\n"
            "- Create a separate `Phases` database for top-level workstreams.\n"
            "- Keep phases as grouping rows, not executable task cards.\n"
            "- Create `Timeline`, `All phases`, and `By Priority` views.\n\n"
            "### Tasks\n"
            "- Keep one primary view: `All tasks`.\n"
            "- Add `Phase Group` as the foldable grouping layer so phases stay in the intended order.\n"
            "- Add `Execution Slot` so a human can see sequence, concurrency, and blocker summary from one column.\n"
            "- Keep `Name`, `Execution Slot`, and `Delivery Status` as the first columns.\n\n"
            "### Docs Library\n"
            "- Create a searchable docs database for approved plans, shipping task sheets, rescue docs, runbooks, dashboards, and prompts.\n"
            "- Add views such as `All Docs`, `Planning`, `Execution`, and `Rescue`.\n"
            "- Show `Description`, `Doc Type`, `Stage`, `Repo Path`, `Source Revision`, and `Doc Status`.\n\n"
            "### Dependencies\n"
            "- Keep `Blocked By` visible in task rows.\n"
            "- Use `Phase` for workstream grouping and `Parent` only for real task-to-task nesting.\n"
            "- If Notion dependency visuals are enabled in the workspace, use `Blocked By` as the dependency relation.\n\n"
            "Notion's public API can create the database and properties, but saved views still need to be created in the Notion UI or through Notion MCP."
        )

    def _mcp_prompt_content(self, project: ProjectSpec) -> str:
        tasks_name = self._task_database_title(project)
        phases_name = self._phases_database_title(project)
        docs_name = self._docs_database_title(project)
        return (
            f"Use Notion MCP in the `{project.name}` workspace and configure the `{tasks_name}` database with these views:\n\n"
            "1. If a generic `Default view` already exists, rename and reconfigure it into `All tasks` instead of leaving both behind.\n"
            "2. `All tasks` should be a table grouped by `Phase Group`, sorted by `Sequence` ascending.\n"
            "3. Show columns in this order: `Name`, `Execution Slot`, `Delivery Status`, `Type`, `Agent Role`, `Parallelizable`, `Parent`, `Sequence`, `Blocked By`.\n"
            "4. Keep the `Plan Revision` filter pinned to the active handoff only.\n\n"
            f"Also configure the `{phases_name}` database with views `Timeline`, `All phases`, and `By Priority`. Use phases as top-level workstream rows rather than executable tasks.\n\n"
            f"Also configure the `{docs_name}` database with views `All Docs`, `Planning`, `Execution`, and `Rescue`, showing `Name`, `Description`, `Doc Type`, `Stage`, `Repo Path`, `Source Revision`, and `Doc Status`.\n\n"
            "Then refresh the project home page so it works as the PM start page: it should clearly explain the project goal, finish line, maintenance baseline, and the fast path into `Tasks`, `Phases`, and `Docs`.\n"
            "If inline linked-database blocks cannot be created programmatically, add explicit human setup instructions telling the user to create linked views for `Tasks`, `Phases`, and `Docs` manually with `/linked` on the project home page.\n"
        )

    def _merged_docs(self, spec: PlanSpec, *, merge_defaults: bool = True) -> list[DocSpec]:
        docs = list(spec.docs or ([] if not merge_defaults else self._default_docs()))
        titles = {doc.title for doc in docs}
        if merge_defaults:
            for required_doc in self._default_docs():
                if required_doc.title not in titles:
                    docs.append(required_doc)
            titles = {doc.title for doc in docs}
            if "Dashboard Snapshot" not in titles:
                docs.append(DocSpec(title="Dashboard Snapshot", content="Codex will update this page with the latest execution dashboard."))
            if "Notion MCP Prompts" not in titles:
                docs.append(DocSpec(title="Notion MCP Prompts", content=self._mcp_prompt_content(spec.project)))
        return docs

    def _ensure_project_page(self, project: ProjectSpec, state: BridgeState) -> dict[str, Any]:
        parent_page_id = self._require_parent_page_id()
        existing = self._safe_retrieve_page(state.project_page_id)
        if existing:
            same_parent = self._page_parent_page_id(existing) == parent_page_id
            title_matches = self._page_title(existing) == project.name
            if not same_parent or not title_matches:
                existing = None
        if not existing:
            existing = self._search_project_page(project.name, parent_page_id)
        if existing:
            state.project_page_id = str(existing["id"])
            state.project_page_url = str(existing.get("url", ""))
            self._ensure_parent_projects_index(project, state)
            return existing

        created = self.client.create_page(
            parent_page_id=parent_page_id,
            title=project.name,
            markdown=self._render_managed_section(project.name, project.description or "Agent-managed Notion project workspace."),
            icon_emoji="🗂️",
        )
        state.project_page_id = str(created["id"])
        state.project_page_url = str(created.get("url", ""))
        self._ensure_parent_projects_index(project, state)
        return created

    def _ensure_tasks_database(
        self,
        project: ProjectSpec,
        state: BridgeState,
        *,
        tasks: list[TaskSpec] | None = None,
    ) -> dict[str, Any]:
        database = self._safe_retrieve_database(state.tasks_database_id)
        if database:
            if self._database_parent_page_id(database) != state.project_page_id or extract_title(database) != self._task_database_title(project):
                database = None
                state.tasks_database_id = ""
                state.tasks_data_source_id = ""
        if not database and state.project_page_id:
            match = self._search_database(self._task_database_title(project), state.project_page_id)
            if match:
                database, data_source = match
                state.tasks_database_id = str(database["id"])
                state.tasks_data_source_id = str(data_source["id"])

        if not database:
            created = self.client.create_database(
                parent_page_id=state.project_page_id,
                title=self._task_database_title(project),
                data_source_title=self._task_database_title(project),
                properties=self._task_schema(tasks),
                is_inline=False,
            )
            database = created
            state.tasks_database_id = str(created["id"])
            state.tasks_data_source_id = self._first_data_source_id(created)
        elif not state.tasks_data_source_id:
            state.tasks_data_source_id = self._first_data_source_id(database)

        self._ensure_task_schema(state, tasks)
        return database

    def _ensure_doc_pages(self, spec: PlanSpec, state: BridgeState, *, merge_defaults: bool = True) -> dict[str, list[str]]:
        created: list[str] = []
        updated: list[str] = []
        for doc in self._docs_in_parent_order(self._merged_docs(spec, merge_defaults=merge_defaults)):
            parent_data_source_id = state.docs_data_source_id

            page = self._safe_retrieve_page(state.docs_pages.get(doc.title, ""))
            if page:
                title_matches = self._page_title(page) == doc.title
                same_parent = self._page_parent_data_source_id(page) == parent_data_source_id
                if not same_parent or not title_matches:
                    page = None
            if not page:
                page = self._search_doc_page(
                    doc.title,
                    parent_data_source_id=parent_data_source_id or None,
                )

            managed = self._render_managed_section(doc.title, doc.content)
            if page:
                properties = self._doc_properties(doc, state, create=False)
                self.client.update_page(str(page["id"]), properties=properties)
                self._replace_managed_markdown(str(page["id"]), managed)
                updated.append(doc.title)
            else:
                page = self.client.create_page(
                    parent_data_source_id=parent_data_source_id,
                    properties=self._doc_properties(doc, state, create=True),
                    markdown=managed,
                    icon_emoji="📄",
                )
                created.append(doc.title)
            state.docs_pages[doc.title] = str(page["id"])
        return {"created": created, "updated": updated}

    def _render_project_home(self, spec: PlanSpec, state: BridgeState) -> str:
        lines = []
        context = self._project_context(state)
        approved_plan_path = self._scoped_artifact_path(state, state.approved_plan_path)
        current_state_path = self._scoped_artifact_path(state, state.current_state_path)
        recovery_plan_path = self._scoped_artifact_path(state, state.recovery_plan_path)
        detailed_scan_path = self._scoped_artifact_path(state, state.detailed_scan_path)
        if spec.project.description.strip():
            lines.append(spec.project.description.strip())
        phases_database_url = ""
        if state.phases_database_id:
            phases_database = self._safe_retrieve_database(state.phases_database_id)
            if phases_database:
                phases_database_url = str(phases_database.get("url", ""))
        tasks_database_url = ""
        if state.tasks_database_id:
            database = self._safe_retrieve_database(state.tasks_database_id)
            if database:
                tasks_database_url = str(database.get("url", ""))
        docs_database_url = ""
        if state.docs_database_id:
            docs_database = self._safe_retrieve_database(state.docs_database_id)
            if docs_database:
                docs_database_url = str(docs_database.get("url", ""))

        lines.extend(["", "## Start Here"])
        if tasks_database_url:
            lines.append(f"- [Tasks]({tasks_database_url}): primary execution surface. Open `All tasks` first.")
        if phases_database_url:
            lines.append(f"- [Phases]({phases_database_url}): roadmap layer for workstreams, sequencing, and cross-phase blockers.")
        if docs_database_url:
            lines.append(f"- [Docs]({docs_database_url}): searchable Notion copies of plans, task sheets, runbooks, rescue docs, and prompts.")
        lines.extend([""] + self._page_role_lines(include_manual_setup=False))
        if context["goal"]:
            lines.extend(["", "## Project Goal", context["goal"]])
        if context["completion_items"]:
            lines.extend(["", "## Finish Line"])
            lines.extend(f"- {item}" for item in context["completion_items"])
        if context["maintenance_items"]:
            lines.extend(["", "## Maintenance Baseline"])
            lines.extend(f"- {item}" for item in context["maintenance_items"])
        lines.extend(
            [
                "",
                "## Workspace",
                f"- Project identifier: `{spec.project.identifier}`",
                f"- Phases database: `{self._phases_database_title(spec.project)}`" if state.phases_database_id else "- Phases database: not built yet",
                f"- Tasks database: `{self._task_database_title(spec.project)}`" if state.tasks_database_id else "- Tasks database: not built yet",
                f"- Docs database: `{self._docs_database_title(spec.project)}`" if state.docs_database_id else "- Docs database: not built yet",
            ]
        )
        if phases_database_url:
            lines.append(f"- Phases database link: [Open roadmap workspace]({phases_database_url})")
        if tasks_database_url:
            lines.append(f"- Tasks database link: [Open task workspace]({tasks_database_url})")
        if docs_database_url:
            lines.append(f"- Docs database link: [Open docs library]({docs_database_url})")
        if approved_plan_path:
            lines.append(f"- Approved plan: `{approved_plan_path}`")
        if state.approved_plan_revision_key:
            lines.append(f"- Approved plan revision: `{state.approved_plan_revision_key}`")
        if current_state_path:
            lines.append(f"- Rescue snapshot: `{current_state_path}`")
        if recovery_plan_path:
            lines.append(f"- Recovery plan: `{recovery_plan_path}`")
        if detailed_scan_path:
            lines.append(f"- Detailed rescue scan: `{detailed_scan_path}`")
        if state.active_handoff_id:
            status_suffix = f" ({state.active_review_status})" if state.active_review_status else ""
            lines.append(f"- Active handoff: `{state.active_handoff_id}`{status_suffix}")
        if state.active_revision_key:
            active_page_id = state.active_revision_page_id or state.revision_pages.get(state.active_revision_key, "")
            active_url = ""
            if active_page_id:
                active_page = self._safe_retrieve_page(active_page_id)
                if active_page:
                    active_url = str(active_page.get("url", ""))
            if active_url:
                lines.append(f"- Active plan: [{state.active_revision_key}]({active_url})")
            else:
                lines.append(f"- Active plan: `{state.active_revision_key}`")
        else:
            final_plan_page_id = state.docs_pages.get("Final Approved Plan", "")
            final_plan_url = ""
            if final_plan_page_id:
                final_plan_page = self._safe_retrieve_page(final_plan_page_id)
                if final_plan_page:
                    final_plan_url = str(final_plan_page.get("url", ""))
            if final_plan_url:
                lines.append(f"- Active plan: [Final Approved Plan]({final_plan_url})")
            elif state.approved_plan_revision_key:
                lines.append(f"- Active plan: `{state.approved_plan_revision_key}`")
            else:
                lines.append("- Active plan: none approved yet")
        lines.extend(
            [
                "",
                "## Manual Inline View Setup",
                "- Notion's connector currently rejects creating inline linked-database blocks programmatically.",
                "- On this page, add linked `Tasks -> All tasks` first.",
                "- Then add linked `Phases -> Timeline` below it.",
                "- Then add a linked `Docs` view such as `Planning` or `Execution`.",
                "- Once those inline linked views exist, Codex can keep the underlying databases updated.",
            ]
        )
        return "\n".join(lines).strip()

    def _write_support_artifacts(self, spec: PlanSpec, state: BridgeState) -> dict[str, str]:
        artifacts_dir = self.config.artifacts_dir
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        view_setup_path = artifacts_dir / "notion_view_setup.md"
        view_setup_path.write_text(self._view_setup_content().strip() + "\n")

        mcp_prompt_path = artifacts_dir / "notion_mcp_prompts.md"
        mcp_prompt_path.write_text(self._mcp_prompt_content(spec.project).strip() + "\n")

        state.artifacts["view_setup"] = str(view_setup_path)
        state.artifacts["mcp_prompts"] = str(mcp_prompt_path)
        return {"view_setup": str(view_setup_path), "mcp_prompts": str(mcp_prompt_path)}

    def _ensure_workspace(self, spec: PlanSpec, state: BridgeState, *, merge_defaults: bool = True) -> None:
        self._ensure_project_page(spec.project, state)
        self._ensure_tasks_database(spec.project, state, tasks=spec.tasks)
        self._ensure_phases_database(spec.project, state)
        self._ensure_task_schema(state, spec.tasks)
        self._ensure_docs_database(spec.project, state)
        self._ensure_doc_pages(spec, state, merge_defaults=merge_defaults)
        self._replace_managed_markdown(
            state.project_page_id,
            self._render_managed_section(spec.project.name, self._render_project_home(spec, state)),
        )
        self._write_support_artifacts(spec, state)

    def ensure_project_docs(self, spec: PlanSpec, *, merge_defaults: bool = True) -> dict[str, Any]:
        state = self._load_state()
        state = self._reset_state_for_project_switch(state, spec.project.identifier)
        state.project_identifier = spec.project.identifier
        self._ensure_project_page(spec.project, state)
        self._ensure_docs_database(spec.project, state)
        doc_results = self._ensure_doc_pages(spec, state, merge_defaults=merge_defaults)
        self._replace_managed_markdown(
            state.project_page_id,
            self._render_managed_section(spec.project.name, self._render_project_home(spec, state)),
        )
        self._write_support_artifacts(spec, state)
        self._save_state(state)
        return {
            "project_identifier": spec.project.identifier,
            "project_page_id": state.project_page_id,
            "project_page_url": state.project_page_url,
            "docs_database_id": state.docs_database_id,
            "docs_data_source_id": state.docs_data_source_id,
            "docs_pages": state.docs_pages,
            "doc_results": doc_results,
            "artifacts": state.artifacts,
        }

    def ensure_task_workspace(self, project: ProjectSpec) -> dict[str, Any]:
        state = self._load_state()
        state = self._reset_state_for_project_switch(state, project.identifier)
        state.project_identifier = project.identifier
        self._ensure_project_page(project, state)
        self._ensure_tasks_database(project, state)
        self._ensure_phases_database(project, state)
        self._ensure_task_schema(state)
        self._ensure_docs_database(project, state)
        self._save_state(state)
        return {
            "project_identifier": project.identifier,
            "project_page_id": state.project_page_id,
            "phases_database_id": state.phases_database_id,
            "phases_data_source_id": state.phases_data_source_id,
            "tasks_database_id": state.tasks_database_id,
            "tasks_data_source_id": state.tasks_data_source_id,
            "docs_database_id": state.docs_database_id,
            "docs_data_source_id": state.docs_data_source_id,
        }

    def _resolve_existing_task(self, state: BridgeState, task: TaskSpec, current_pages: list[dict[str, Any]]) -> dict[str, Any] | None:
        known_page_id = state.task_pages_by_key.get(task.key)
        if known_page_id:
            for page in current_pages:
                if str(page["id"]) == known_page_id:
                    return page
        for page in current_pages:
            if self._property_text(page, "Task ID") == task.key:
                return page
        for page in current_pages:
            if self._page_title(page) == task.title:
                return page
        return None

    def _resolve_existing_phase(self, state: BridgeState, task: TaskSpec, current_pages: list[dict[str, Any]]) -> dict[str, Any] | None:
        known_page_id = state.phase_pages_by_key.get(task.key)
        if known_page_id:
            for page in current_pages:
                if str(page["id"]) == known_page_id:
                    return page
        for page in current_pages:
            if self._page_title(page) == task.title:
                return page
        return None

    def _task_properties(self, task: TaskSpec, *, create: bool) -> dict[str, Any]:
        synced_progress, synced_delivery_state = self._sync_progress_and_delivery_state(task.progress, task.completion_state)
        properties: dict[str, Any] = {
            "Name": _title_property(task.title),
            "Task ID": _rich_text_property(task.key),
            "Type": _select_property(task.type or "Task"),
        }
        status = task.status or self._status_title("ready")
        if create or task.status is not None:
            properties["Status"] = _select_property(status)
        if create or task.completion_state is not None or task.progress is not None:
            properties["Delivery Status"] = _select_property(synced_delivery_state)
        if create or task.execution_slot is not None:
            properties["Execution Slot"] = _rich_text_property(task.execution_slot or "")
        if create or task.phase_group is not None:
            properties["Phase Group"] = _select_property(task.phase_group or "No Phase")
        if create or task.priority is not None:
            properties["Priority"] = _select_property(task.priority or "Normal")
        if create or task.start_date is not None:
            properties["Start"] = _date_property(task.start_date) if task.start_date else {"date": None}
        if create or task.due_date is not None:
            properties["Due"] = _date_property(task.due_date) if task.due_date else {"date": None}
        if create or task.human_estimate_hours is not None:
            properties["Human Estimate (hrs)"] = _number_property(task.human_estimate_hours if task.human_estimate_hours is not None else 0)
        if create or task.agent_estimate_hours is not None:
            properties["Agent Estimate (hrs)"] = _number_property(task.agent_estimate_hours if task.agent_estimate_hours is not None else 0)
        if create or task.assignee is not None:
            properties["Agent Owner"] = _rich_text_property(task.assignee or "")
        if create or task.execution_mode is not None:
            properties["Execution Mode"] = _select_property(task.execution_mode or "agent")
        if create or task.parallelizable is not None:
            properties["Parallelizable"] = _checkbox_property(bool(task.parallelizable))
        if create or task.parallel_group is not None:
            properties["Parallel Wave"] = _select_property(task.parallel_group or "Serial")
        if create or task.agent_role is not None:
            properties["Agent Role"] = _select_property(task.agent_role or "executor")
        if create or task.preferred_skill is not None:
            properties["Preferred Skill"] = _rich_text_property(task.preferred_skill or "")
        if create or task.repo_ref is not None:
            properties["Repo Ref"] = _rich_text_property(task.repo_ref or "")
        if create or task.branch_ref is not None:
            properties["Branch Ref"] = _rich_text_property(task.branch_ref or "")
        if create or task.pr_url is not None:
            properties["PR URL"] = _url_property(task.pr_url or "") if task.pr_url else {"url": None}
        if create or task.commit_sha is not None:
            properties["Commit SHA"] = _rich_text_property(task.commit_sha or "")
        if create or task.source_revision is not None:
            properties["Source Revision"] = _rich_text_property(task.source_revision or "")
        if create or task.plan_revision is not None:
            properties["Plan Revision"] = _rich_text_property(task.plan_revision or "")
        if create or task.decomposition_review is not None:
            properties["Decomposition Review"] = _rich_text_property(task.decomposition_review or "")
        if create or task.review_status is not None:
            properties["Review Status"] = _select_property(task.review_status or "pending")
        if create or task.sequence is not None:
            properties["Sequence"] = _number_property(task.sequence if task.sequence is not None else 0)
        if create or task.superseded_by_revision is not None:
            properties["Superseded By Revision"] = _rich_text_property(task.superseded_by_revision or "")
        if create or task.progress is not None:
            properties["Progress"] = _number_property(synced_progress)
        elif create:
            properties["Progress"] = _number_property(synced_progress)
        properties["Last Agent Sync At"] = _rich_text_property(self._utc_now())
        return properties

    def _normalize_snapshot(self, key: str, page: dict[str, Any]) -> TaskSnapshot:
        return TaskSnapshot(
            key=key,
            page_id=str(page["id"]),
            title=self._page_title(page),
            status=self._property_select(page, "Status") or "Unknown",
            type=self._property_select(page, "Type"),
            priority=self._property_select(page, "Priority"),
            assignee=self._property_text(page, "Agent Owner") or None,
            parent_page_ids=self._property_relation_ids(page, "Parent"),
            dependency_page_ids=self._property_relation_ids(page, "Blocked By"),
            start_date=self._property_date(page, "Start"),
            due_date=self._property_date(page, "Due"),
            human_estimate_hours=self._property_number(page, "Human Estimate (hrs)"),
            agent_estimate_hours=self._property_number(page, "Agent Estimate (hrs)"),
            progress=self._property_number(page, "Progress"),
            parallelizable=self._property_checkbox(page, "Parallelizable"),
            completion_state=self._property_select(page, "Delivery Status"),
            phase_group=self._property_select(page, "Phase Group"),
            execution_slot=self._property_text(page, "Execution Slot") or None,
            parallel_group=self._property_select(page, "Parallel Wave"),
            agent_role=self._property_select(page, "Agent Role"),
            preferred_skill=self._property_text(page, "Preferred Skill") or None,
            sequence=self._property_number(page, "Sequence"),
            source_revision=self._property_text(page, "Source Revision") or None,
            plan_revision=self._property_text(page, "Plan Revision") or None,
            decomposition_review=self._property_text(page, "Decomposition Review") or None,
            review_status=self._property_select(page, "Review Status"),
            superseded_by_revision=self._property_text(page, "Superseded By Revision") or None,
            parallel_with=self._property_relation_ids(page, "Parallel With"),
            updated_at=page.get("last_edited_time"),
            url=page.get("url"),
            raw=page,
        )

    def _refresh_from_remote(self, state: BridgeState) -> dict[str, Any]:
        if not state.tasks_data_source_id:
            raise StateError("No Notion task data source is configured yet. Build the execution workspace from an approved handoff first.")
        pages = self.client.query_data_source(state.tasks_data_source_id)
        page_id_to_key: dict[str, str] = {}
        snapshots: dict[str, dict[str, Any]] = {}
        titles_by_key: dict[str, str] = {}
        task_pages_by_key: dict[str, str] = {}

        for page in pages:
            key = self._property_text(page, "Task ID") or self._slugify(self._page_title(page))
            page_id_to_key[str(page["id"])] = key

        dependencies: dict[str, list[str]] = {}
        for page in pages:
            key = page_id_to_key[str(page["id"])]
            normalized = self._normalize_snapshot(key, page)
            synced_progress, synced_delivery_state = self._sync_progress_and_delivery_state(
                normalized.progress,
                normalized.completion_state,
            )
            if synced_progress != normalized.progress or synced_delivery_state != normalized.completion_state:
                self.client.update_page(
                    normalized.page_id,
                    properties={
                        "Progress": _number_property(synced_progress),
                        "Delivery Status": _select_property(synced_delivery_state),
                        "Last Agent Sync At": _rich_text_property(self._utc_now()),
                    },
                )
                page = self.client.retrieve_page(normalized.page_id)
                normalized = self._normalize_snapshot(key, page)
            snapshot = normalized.to_dict()
            dependencies[key] = [
                page_id_to_key[page_id]
                for page_id in self._property_relation_ids(page, "Blocked By")
                if page_id in page_id_to_key
            ]
            snapshot["parallel_with"] = [
                page_id_to_key[page_id]
                for page_id in self._property_relation_ids(page, "Parallel With")
                if page_id in page_id_to_key
            ]
            snapshots[key] = snapshot
            titles_by_key[key] = snapshot["title"]
            task_pages_by_key[key] = snapshot["page_id"]

        state.snapshot = snapshots
        state.dependencies = dependencies
        state.titles_by_key = titles_by_key
        state.task_pages_by_key = task_pages_by_key
        self._save_state(state)
        return {
            "project_identifier": state.project_identifier,
            "project_page_id": state.project_page_id,
            "tasks": len(snapshots),
            "snapshot": snapshots,
        }

    def refresh(self) -> dict[str, Any]:
        state = self._load_state()
        return self._refresh_from_remote(state)

    def bootstrap(self, spec: PlanSpec | None = None) -> dict[str, Any]:
        project = self._project_spec_or_default(spec)
        full_spec = spec or PlanSpec(project=project, docs=self._default_docs(), tasks=[])
        state = self._load_state()
        state = self._reset_state_for_project_switch(state, full_spec.project.identifier)
        state.project_identifier = full_spec.project.identifier
        self._emit_progress(f"Ensuring Notion workspace scaffolding for `{project.name}`.")
        self._ensure_workspace(full_spec, state)
        self._save_state(state)
        self._emit_progress("Refreshing local state from Notion.")
        refresh_payload = self._refresh_from_remote(state)
        return {
            "project_identifier": full_spec.project.identifier,
            "project_page_id": state.project_page_id,
            "project_page_url": state.project_page_url,
            "phases_database_id": state.phases_database_id,
            "phases_data_source_id": state.phases_data_source_id,
            "tasks_database_id": state.tasks_database_id,
            "tasks_data_source_id": state.tasks_data_source_id,
            "docs_database_id": state.docs_database_id,
            "docs_data_source_id": state.docs_data_source_id,
            "docs_pages": state.docs_pages,
            "artifacts": state.artifacts,
            "tasks": refresh_payload["tasks"],
        }

    def _sync_tasks(
        self,
        spec: PlanSpec,
        *,
        reconcile_removed: bool = False,
        superseded_revision: str | None = None,
        merge_defaults: bool = True,
    ) -> dict[str, Any]:
        state = self._load_state()
        if state.tasks_data_source_id and not state.snapshot:
            self._refresh_from_remote(state)
            state = self._load_state()
        state = self._reset_state_for_project_switch(state, spec.project.identifier)
        state.project_identifier = spec.project.identifier
        self._emit_progress(f"Ensuring project page and databases for `{spec.project.name}`.")
        self._ensure_workspace(spec, state, merge_defaults=merge_defaults)
        phase_tasks, executable_tasks = self._split_phase_tasks(spec.tasks)
        self._derive_execution_slots(phase_tasks, executable_tasks)
        current_phase_pages = self.client.query_data_source(state.phases_data_source_id) if state.phases_data_source_id else []
        current_pages = self.client.query_data_source(state.tasks_data_source_id)
        created: list[str] = []
        updated: list[str] = []
        phase_created: list[str] = []
        phase_updated: list[str] = []

        self._emit_progress(f"Syncing {len(phase_tasks)} phases.")
        for phase in phase_tasks:
            existing_phase = self._resolve_existing_phase(state, phase, current_phase_pages)
            managed_markdown = self._render_task_page_markdown(phase, state)
            if existing_phase:
                page = self.client.update_page(str(existing_phase["id"]), properties=self._phase_properties(phase, create=False))
                self._replace_managed_markdown(str(existing_phase["id"]), managed_markdown)
                phase_updated.append(phase.key)
            else:
                page = self.client.create_page(
                    parent_data_source_id=state.phases_data_source_id,
                    properties=self._phase_properties(phase, create=True),
                    markdown=managed_markdown,
                    icon_emoji="🗂️",
                )
                phase_created.append(phase.key)
            state.phase_pages_by_key[phase.key] = str(page["id"])
            state.titles_by_key[phase.key] = phase.title

        self._emit_progress(f"Syncing {len(executable_tasks)} executable tasks.")
        for task in self._topological_parent_order(executable_tasks):
            existing = self._resolve_existing_task(state, task, current_pages)
            managed_markdown = self._render_task_page_markdown(task)
            if existing:
                page = self.client.update_page(str(existing["id"]), properties=self._task_properties(task, create=False))
                self._replace_managed_markdown(str(existing["id"]), managed_markdown)
                updated.append(task.key)
            else:
                page = self.client.create_page(
                    parent_data_source_id=state.tasks_data_source_id,
                    properties=self._task_properties(task, create=True),
                    markdown=managed_markdown,
                    icon_emoji="🧩",
                )
                created.append(task.key)
            state.task_pages_by_key[task.key] = str(page["id"])
            state.titles_by_key[task.key] = task.title

        self._emit_progress("Refreshing managed task page content.")
        for task in executable_tasks:
            page_id = state.task_pages_by_key[task.key]
            self._replace_managed_markdown(page_id, self._render_task_page_markdown(task, state))

        phase_keys = {task.key for task in phase_tasks}
        self._emit_progress("Linking task dependencies, phase relations, and execution metadata.")
        for task in executable_tasks:
            page_id = state.task_pages_by_key[task.key]
            parent_relations = []
            if task.parent_key and task.parent_key in state.task_pages_by_key:
                parent_relations = [state.task_pages_by_key[task.parent_key]]
            phase_relations = []
            if task.parent_key and task.parent_key in state.phase_pages_by_key:
                phase_relations = [state.phase_pages_by_key[task.parent_key]]
            properties = {
                "Parent": _relation_property(parent_relations),
                "Blocked By": _relation_property([state.task_pages_by_key[key] for key in task.dependencies]),
                "Parallel With": _relation_property([state.task_pages_by_key[key] for key in task.parallel_with if key in state.task_pages_by_key]),
                "Phase": _relation_property(phase_relations),
                "Last Agent Sync At": _rich_text_property(self._utc_now()),
            }
            self.client.update_page(page_id, properties=properties)
            state.dependencies[task.key] = list(task.dependencies)

        for phase in phase_tasks:
            phase_page_id = state.phase_pages_by_key[phase.key]
            child_ids = [
                state.task_pages_by_key[task.key]
                for task in executable_tasks
                if task.parent_key == phase.key and task.key in state.task_pages_by_key
            ]
            blocked_ids = [state.phase_pages_by_key[key] for key in phase.dependencies if key in state.phase_pages_by_key]
            self.client.update_page(
                phase_page_id,
                properties={
                    "Tasks": _relation_property(child_ids),
                    "Blocked By": _relation_property(blocked_ids),
                },
            )
            self._replace_managed_markdown(phase_page_id, self._render_task_page_markdown(phase, state))

        superseded: list[str] = []
        if reconcile_removed:
            self._emit_progress("Marking removed open tasks as superseded where needed.")
            desired_keys = {task.key for task in executable_tasks}
            for task_key, page_id in list(state.task_pages_by_key.items()):
                snapshot = state.snapshot.get(task_key)
                if task_key in desired_keys or not snapshot or task_key in phase_keys:
                    continue
                if self._is_done(snapshot.get("status"), snapshot.get("progress")):
                    continue
                self.client.update_page(
                    page_id,
                    properties={
                        "Status": _select_property("Superseded"),
                        "Superseded By Revision": _rich_text_property(superseded_revision or ""),
                        "Last Agent Sync At": _rich_text_property(self._utc_now()),
                    },
                )
                superseded.append(task_key)

        self._save_state(state)
        self._emit_progress("Refreshing local task snapshot from Notion.")
        refreshed = self._refresh_from_remote(state)
        refreshed_state = self._load_state()
        # Re-render only phase pages after refresh. Executable task pages were
        # already created with stable content, and rewriting every task again
        # adds a long post-build tail that makes successful builds feel hung.
        self._emit_progress("Updating phase pages, project home, and dashboard.")
        for phase in phase_tasks:
            phase_page_id = refreshed_state.phase_pages_by_key.get(phase.key)
            if not phase_page_id:
                continue
            self._replace_managed_markdown(phase_page_id, self._render_task_page_markdown(phase, refreshed_state))
        self._replace_managed_markdown(
            refreshed_state.project_page_id,
            self._render_managed_section(spec.project.name, self._render_project_home(spec, refreshed_state)),
        )
        dashboard_payload = self.dashboard()
        self._emit_progress("Workspace sync complete.")
        return {
            "phase_created": phase_created,
            "phase_updated": phase_updated,
            "created": created,
            "updated": updated,
            "superseded": superseded,
            "tasks": refreshed["tasks"],
            "dashboard": dashboard_payload["path"],
        }

    def sync_plan(self, spec: PlanSpec) -> dict[str, Any]:
        return self._sync_tasks(spec)

    def sync_plan_revision(
        self,
        project: ProjectSpec,
        tasks: list[TaskSpec],
        *,
        docs: list[DocSpec] | None = None,
        reconcile_removed: bool = True,
        superseded_revision: str | None = None,
        merge_defaults: bool = True,
    ) -> dict[str, Any]:
        spec = PlanSpec(project=project, docs=docs or [], tasks=tasks)
        return self._sync_tasks(
            spec,
            reconcile_removed=reconcile_removed,
            superseded_revision=superseded_revision,
            merge_defaults=merge_defaults,
        )

    def _resolve_task_key(self, state: BridgeState, task_ref: str) -> str:
        if task_ref in state.task_pages_by_key:
            return task_ref
        for key, page_id in state.task_pages_by_key.items():
            if page_id == task_ref:
                return key
        raise StateError(f"Unknown task reference '{task_ref}'")

    def _update_task(
        self,
        task_ref: str,
        *,
        properties: dict[str, Any] | None = None,
        activity_message: str | None = None,
    ) -> dict[str, Any]:
        state = self._load_state()
        if not state.snapshot:
            self._refresh_from_remote(state)
            state = self._load_state()
        task_key = self._resolve_task_key(state, task_ref)
        page_id = state.task_pages_by_key[task_key]
        payload = dict(properties or {})
        payload["Last Agent Sync At"] = _rich_text_property(self._utc_now())
        page = self.client.update_page(page_id, properties=payload) if payload else self.client.retrieve_page(page_id)
        if activity_message:
            self._append_activity(page_id, activity_message)
        refreshed = self._refresh_from_remote(state)
        return {
            "task_key": task_key,
            "page_id": page_id,
            "status": self._property_select(page, "Status"),
            "snapshot": refreshed["snapshot"].get(task_key),
        }

    def claim(self, task_ref: str, *, owner: str | None = None) -> dict[str, Any]:
        owner_value = owner or self.config.author
        return self._update_task(
            task_ref,
            properties={"Agent Owner": _rich_text_property(owner_value)},
            activity_message=f"`{owner_value}` claimed this task.",
        )

    def start(self, task_ref: str, *, owner: str | None = None, branch: str | None = None) -> dict[str, Any]:
        owner_value = owner or self.config.author
        properties: dict[str, Any] = {
            "Status": _select_property(self._status_title("in_progress")),
            "Agent Owner": _rich_text_property(owner_value),
            "Delivery Status": _select_property("In progress"),
            "Progress": _number_property(50),
        }
        if branch is not None:
            properties["Branch Ref"] = _rich_text_property(branch)
        return self._update_task(
            task_ref,
            properties=properties,
            activity_message=f"`{owner_value}` started this task{f' on `{branch}`' if branch else ''}.",
        )

    def block(self, task_ref: str, *, dependency_ref: str, note: str | None = None) -> dict[str, Any]:
        state = self._load_state()
        if not state.snapshot:
            self._refresh_from_remote(state)
            state = self._load_state()
        task_key = self._resolve_task_key(state, task_ref)
        dependency_key = self._resolve_task_key(state, dependency_ref)
        current_dependencies = list(state.dependencies.get(task_key, []))
        if dependency_key not in current_dependencies:
            current_dependencies.append(dependency_key)
        payload = {
            "Status": _select_property(self._status_title("blocked")),
            "Blocked By": _relation_property([state.task_pages_by_key[key] for key in current_dependencies]),
        }
        message = f"Blocked by `{dependency_key}`."
        if note:
            message = f"{message} {note}"
        return self._update_task(task_key, properties=payload, activity_message=message)

    def finish(
        self,
        task_ref: str,
        *,
        summary: str | None = None,
        branch: str | None = None,
        pr_url: str | None = None,
        commit_sha: str | None = None,
    ) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "Status": _select_property(self._status_title("done")),
            "Delivery Status": _select_property("Completed"),
            "Progress": _number_property(100),
        }
        if branch is not None:
            properties["Branch Ref"] = _rich_text_property(branch)
        if pr_url is not None:
            properties["PR URL"] = _url_property(pr_url) if pr_url else {"url": None}
        if commit_sha is not None:
            properties["Commit SHA"] = _rich_text_property(commit_sha)
        message = "Completed through pm bridge."
        if summary:
            message = f"{message} {summary}"
        return self._update_task(task_ref, properties=properties, activity_message=message)

    def next_tasks(self) -> dict[str, Any]:
        state = self._load_state()
        if not state.snapshot:
            self._refresh_from_remote(state)
            state = self._load_state()

        return self._task_buckets_from_state(state)

    def _task_buckets_from_state(self, state: BridgeState) -> dict[str, Any]:
        ready: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        active: list[dict[str, Any]] = []
        done: list[dict[str, Any]] = []

        for key, snapshot in state.snapshot.items():
            if snapshot.get("type") in {"Milestone", "Epic"}:
                continue
            status = snapshot.get("status")
            progress = snapshot.get("progress")
            dependencies = state.dependencies.get(key, [])
            unmet = [
                dependency
                for dependency in dependencies
                if dependency in state.snapshot
                and not self._is_done(state.snapshot[dependency].get("status"), state.snapshot[dependency].get("progress"))
            ]
            item = {
                "key": key,
                "title": snapshot.get("title"),
                "status": status,
                "type": snapshot.get("type"),
                "dependencies": dependencies,
                "unmet_dependencies": unmet,
                "page_id": snapshot.get("page_id"),
                "url": snapshot.get("url"),
                "priority": snapshot.get("priority"),
                "sequence": snapshot.get("sequence"),
                "human_estimate_hours": snapshot.get("human_estimate_hours"),
                "agent_estimate_hours": snapshot.get("agent_estimate_hours"),
                "due_date": snapshot.get("due_date"),
                "parallelizable": snapshot.get("parallelizable"),
                "completion_state": snapshot.get("completion_state"),
                "parallel_group": snapshot.get("parallel_group"),
                "parallel_with": snapshot.get("parallel_with") or [],
                "plan_revision": snapshot.get("plan_revision"),
            }
            if self._is_done(status, progress):
                done.append(item)
            elif status == "Superseded":
                blocked.append(item)
            elif self._is_active(status):
                active.append(item)
            elif unmet or self._status_matches(status, "blocked"):
                blocked.append(item)
            else:
                ready.append(item)

        ordering = lambda item: (
            item.get("sequence") if item.get("sequence") is not None else 10**9,
            (item.get("title") or item["key"]).lower(),
        )
        return {
            "ready": sorted(ready, key=ordering),
            "active": sorted(active, key=ordering),
            "blocked": sorted(blocked, key=ordering),
            "done": sorted(done, key=ordering),
        }

    def _dashboard_markdown(self, state: BridgeState) -> str:
        summary = self._task_buckets_from_state(state)
        lines = [f"# Dashboard: {state.project_identifier}", ""]
        if state.project_page_url:
            lines.append(f"- Project page: {state.project_page_url}")
        lines.append(f"- Tasks database ID: `{state.tasks_database_id}`")
        executable = [snapshot for snapshot in state.snapshot.values() if snapshot.get("type") not in {"Milestone", "Epic"}]
        if executable:
            lines.append(f"- Agent-grounded effort: `{sum((item.get('agent_estimate_hours') or 0) for item in executable)}` hours")
            lines.append(f"- Human-estimated effort: `{sum((item.get('human_estimate_hours') or 0) for item in executable)}` hours")
        lines.append("")
        milestone_rows = [
            snapshot
            for snapshot in state.snapshot.values()
            if snapshot.get("type") == "Milestone"
        ]
        if milestone_rows:
            lines.extend(["## Milestones"])
            for milestone in sorted(milestone_rows, key=lambda item: ((item.get("sequence") or 0), item.get("title") or "")):
                lines.append(
                    f"- {milestone.get('title')}: `{milestone.get('agent_estimate_hours') or 0}` agent hrs, "
                    f"`{milestone.get('human_estimate_hours') or 0}` human hrs, "
                    f"`{milestone.get('start_date') or 'TBD'}` -> `{milestone.get('due_date') or 'TBD'}`"
                )
            lines.append("")
        for label, key in (
            ("Ready Now", "ready"),
            ("Active", "active"),
            ("Blocked", "blocked"),
            ("Done", "done"),
        ):
            lines.append(f"## {label}")
            items = summary[key]
            if not items:
                lines.append("- None")
            else:
                for item in items:
                    dependency_suffix = ""
                    if item.get("unmet_dependencies"):
                        dependency_suffix = f" (waiting on {', '.join(item['unmet_dependencies'])})"
                    estimate_suffix = ""
                    if item.get("agent_estimate_hours") is not None:
                        estimate_suffix = f" - `{item['agent_estimate_hours']}` agent hrs"
                    due_suffix = f", due `{item['due_date']}`" if item.get("due_date") else ""
                    wave_suffix = ""
                    if item.get("parallel_group"):
                        companions = item.get("parallel_with") or []
                        if companions:
                            wave_suffix = f", {item['parallel_group']} with {', '.join(companions)}"
                        else:
                            wave_suffix = f", {item['parallel_group']}"
                    delivery_suffix = f", {item['completion_state']}" if item.get("completion_state") else ""
                    lines.append(f"- `{item['key']}` {item['title']}{estimate_suffix}{due_suffix}{delivery_suffix}{wave_suffix}{dependency_suffix}")
            lines.append("")

        lines.append("## Documents")
        if not state.docs_pages:
            lines.append("- None")
        else:
            for title in self._ordered_doc_titles(state):
                lines.append(f"- {title}")
        lines.append("")
        lines.append("## Suggested Views")
        lines.append("- Board grouped by `Status`")
        lines.append("- Timeline using `Start` and `Due`")
        lines.append("- Table filtered for `Blocked`")
        return "\n".join(lines).strip() + "\n"

    def dashboard(self, output_path: str | None = None) -> dict[str, Any]:
        state = self._load_state()
        if not state.snapshot and state.tasks_data_source_id:
            self._refresh_from_remote(state)
            state = self._load_state()

        markdown = self._dashboard_markdown(state)
        path = Path(output_path) if output_path else self.config.artifacts_dir / "dashboard.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown)
        state.artifacts["dashboard"] = str(path)
        dashboard_page_id = state.docs_pages.get("Dashboard Snapshot")
        if dashboard_page_id:
            self._replace_managed_markdown(
                dashboard_page_id,
                self._render_managed_section("Dashboard Snapshot", markdown.strip()),
            )
        self._save_state(state)
        return {"path": str(path), "page_id": dashboard_page_id}
