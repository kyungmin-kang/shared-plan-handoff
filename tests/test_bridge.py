from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from notion_pm_bridge.bridge import ESCAPED_MANAGED_END, ESCAPED_MANAGED_START, MANAGED_END, MANAGED_START, BridgeService
from notion_pm_bridge.config import BridgeConfig
from notion_pm_bridge.coordinator import CodexNotionWorkflowCoordinator
from notion_pm_bridge.exceptions import StateError
from notion_pm_bridge.models import DocSpec, PlanSpec, PlanningDraft, ProjectSpec, TaskGraphSpec, TaskSpec
from notion_pm_bridge.notion_client import NotionClient, rich_text


def _plain_text(value: list[dict]) -> str:
    return "".join(item.get("plain_text") or item.get("text", {}).get("content", "") for item in value)


class FakeNotionClient:
    def __init__(self) -> None:
        self.next_page_id = 1
        self.next_database_id = 1
        self.next_data_source_id = 1
        self.pages: dict[str, dict] = {}
        self.page_markdown: dict[str, str] = {}
        self.databases: dict[str, dict] = {}
        self.data_sources: dict[str, dict] = {}
        self.data_source_pages: dict[str, list[str]] = {}

    def _new_page_id(self) -> str:
        page_id = f"page-{self.next_page_id}"
        self.next_page_id += 1
        return page_id

    def _new_database_id(self) -> str:
        database_id = f"db-{self.next_database_id}"
        self.next_database_id += 1
        return database_id

    def _new_data_source_id(self) -> str:
        data_source_id = f"ds-{self.next_data_source_id}"
        self.next_data_source_id += 1
        return data_source_id

    def _now(self) -> str:
        return "2026-03-30T12:00:00+00:00"

    def _property_title(self, title: str) -> dict:
        return {"id": "title", "type": "title", "title": rich_text(title)}

    def _page_title(self, page: dict) -> str:
        for value in page.get("properties", {}).values():
            if value.get("type") == "title":
                return _plain_text(value.get("title", []))
        title = page.get("title")
        if isinstance(title, list):
            return _plain_text(title)
        return ""

    def _clone(self, payload: dict) -> dict:
        return json.loads(json.dumps(payload))

    def search(self, *, query: str, filter_type: str | None = None) -> list[dict]:
        results: list[dict] = []
        if filter_type in (None, "page"):
            for page in self.pages.values():
                if query.lower() in self._page_title(page).lower():
                    results.append(self._clone(page))
        if filter_type in (None, "data_source"):
            for data_source in self.data_sources.values():
                title = _plain_text(data_source.get("title", []))
                if query.lower() in title.lower():
                    results.append(self._clone(data_source))
        return results

    def search_exact_title(self, title: str, *, filter_type: str | None = None) -> list[dict]:
        matches = []
        for item in self.search(query=title, filter_type=filter_type):
            if filter_type == "data_source":
                item_title = _plain_text(item.get("title", []))
            else:
                item_title = self._page_title(item)
            if item_title == title:
                matches.append(item)
        return matches

    def retrieve_page(self, page_id: str, *, filter_properties: list[str] | None = None) -> dict:
        return self._clone(self.pages[page_id])

    def update_page(
        self,
        page_id: str,
        *,
        properties: dict | None = None,
        archived: bool | None = None,
        erase_content: bool | None = None,
        icon_emoji: str | None = None,
    ) -> dict:
        page = self.pages[page_id]
        if properties:
            for key, value in properties.items():
                if key not in page["properties"]:
                    page["properties"][key] = self._clone(value)
                    if "title" in value:
                        page["properties"][key]["type"] = "title"
                    elif "rich_text" in value:
                        page["properties"][key]["type"] = "rich_text"
                    elif "select" in value:
                        page["properties"][key]["type"] = "select"
                    elif "date" in value:
                        page["properties"][key]["type"] = "date"
                    elif "checkbox" in value:
                        page["properties"][key]["type"] = "checkbox"
                    elif "number" in value:
                        page["properties"][key]["type"] = "number"
                    elif "url" in value:
                        page["properties"][key]["type"] = "url"
                    elif "relation" in value:
                        page["properties"][key]["type"] = "relation"
                else:
                    page["properties"][key].update(self._clone(value))
        if erase_content:
            self.page_markdown[page_id] = ""
        if icon_emoji:
            page["icon"] = {"type": "emoji", "emoji": icon_emoji}
        if archived is not None:
            page["archived"] = archived
        page["last_edited_time"] = self._now()
        return self._clone(page)

    def create_page(
        self,
        *,
        parent_page_id: str | None = None,
        parent_data_source_id: str | None = None,
        title: str | None = None,
        properties: dict | None = None,
        markdown: str | None = None,
        icon_emoji: str | None = None,
    ) -> dict:
        page_id = self._new_page_id()
        page_properties = self._clone(properties or {})
        if parent_page_id:
            page_properties.setdefault("title", self._property_title(title or "Untitled"))
            parent = {"type": "page_id", "page_id": parent_page_id}
        else:
            parent = {"type": "data_source_id", "data_source_id": parent_data_source_id}
            self.data_source_pages.setdefault(parent_data_source_id, []).append(page_id)
        for key, value in list(page_properties.items()):
            if "title" in value:
                value["type"] = "title"
            elif "rich_text" in value:
                value["type"] = "rich_text"
            elif "select" in value:
                value["type"] = "select"
            elif "date" in value:
                value["type"] = "date"
            elif "checkbox" in value:
                value["type"] = "checkbox"
            elif "number" in value:
                value["type"] = "number"
            elif "url" in value:
                value["type"] = "url"
            elif "relation" in value:
                value["type"] = "relation"
        page = {
            "object": "page",
            "id": page_id,
            "url": f"https://www.notion.so/{page_id}",
            "parent": parent,
            "properties": page_properties,
            "last_edited_time": self._now(),
        }
        if icon_emoji:
            page["icon"] = {"type": "emoji", "emoji": icon_emoji}
        self.pages[page_id] = page
        self.page_markdown[page_id] = markdown or ""
        return self._clone(page)

    def retrieve_page_markdown(self, page_id: str) -> dict:
        return {"markdown": self.page_markdown.get(page_id, "")}

    def update_page_markdown(
        self,
        page_id: str,
        *,
        operation: str,
        content: str,
        content_range: str | None = None,
        after: str | None = None,
    ) -> dict:
        current = self.page_markdown.get(page_id, "")
        if operation == "insert_content":
            self.page_markdown[page_id] = current + content
        elif operation == "replace_content_range" and content_range:
            start, _, end = content_range.partition("...")
            if start in current and end in current:
                start_index = current.index(start)
                end_index = current.index(end, start_index) + len(end)
                self.page_markdown[page_id] = current[:start_index] + content + current[end_index:]
            else:
                self.page_markdown[page_id] = current + content
        else:
            self.page_markdown[page_id] = current + content
        self.pages[page_id]["last_edited_time"] = self._now()
        return {"page_id": page_id}

    def retrieve_database(self, database_id: str) -> dict:
        return self._clone(self.databases[database_id])

    def create_database(
        self,
        *,
        parent_page_id: str,
        title: str,
        data_source_title: str,
        properties: dict,
        is_inline: bool = False,
    ) -> dict:
        database_id = self._new_database_id()
        data_source_id = self._new_data_source_id()
        database = {
            "object": "database",
            "id": database_id,
            "url": f"https://www.notion.so/{database_id}",
            "title": rich_text(title),
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "is_inline": is_inline,
            "data_sources": [{"id": data_source_id}],
        }
        data_source = {
            "object": "data_source",
            "id": data_source_id,
            "title": rich_text(data_source_title),
            "parent": {"type": "database_id", "database_id": database_id},
            "properties": self._clone(properties),
        }
        self.databases[database_id] = database
        self.data_sources[data_source_id] = data_source
        self.data_source_pages[data_source_id] = []
        return self._clone(database)

    def retrieve_data_source(self, data_source_id: str) -> dict:
        return self._clone(self.data_sources[data_source_id])

    def update_data_source(
        self,
        data_source_id: str,
        *,
        title: str | None = None,
        properties: dict | None = None,
    ) -> dict:
        data_source = self.data_sources[data_source_id]
        if title is not None:
            data_source["title"] = rich_text(title)
        if properties:
            for key, value in properties.items():
                data_source["properties"][key] = self._clone(value)
        return self._clone(data_source)

    def query_data_source(
        self,
        data_source_id: str,
        *,
        filter_payload: dict | None = None,
        sorts: list[dict] | None = None,
    ) -> list[dict]:
        return [self._clone(self.pages[page_id]) for page_id in self.data_source_pages[data_source_id]]


class BridgeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        state_path = Path(self.temp_dir.name) / "state.json"
        config = BridgeConfig(
            api_base_url="https://api.notion.test",
            api_token="token",
            parent_page_id="workspace-root",
            project_identifier="agent-pm",
            notion_version="2025-09-03",
            state_path=state_path,
            artifacts_dir=state_path.parent / "artifacts",
            plans_dir=Path(self.temp_dir.name) / "plans",
            status_map={
                "ready": "Ready",
                "in_progress": "In Progress",
                "blocked": "Blocked",
                "review": "Review",
                "done": "Done",
            },
        )
        self.client = FakeNotionClient()
        self.service = BridgeService(self.client, config)
        self.coordinator = CodexNotionWorkflowCoordinator(self.service)
        self.spec = PlanSpec(
            project=ProjectSpec(identifier="agent-pm", name="Agent PM", description="desc"),
            docs=[DocSpec(title="Home", content="# Home")],
            tasks=[
                TaskSpec(
                    key="foundation",
                    title="Foundation",
                    description="Set up the stack",
                    execution_mode="agent",
                    parallelizable=True,
                    repo_ref="repo",
                    status="Ready",
                    priority="High",
                ),
                TaskSpec(
                    key="dashboard",
                    title="Dashboard",
                    description="Build the dashboard",
                    dependencies=["foundation"],
                    execution_mode="agent",
                    parallelizable=True,
                    repo_ref="repo",
                    status="Ready",
                    priority="Normal",
                ),
            ],
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_bootstrap_creates_project_scaffold(self) -> None:
        result = self.service.bootstrap(self.spec)
        self.assertTrue(result["project_page_id"])
        self.assertTrue(result["phases_database_id"])
        self.assertTrue(result["tasks_database_id"])
        self.assertTrue(result["docs_database_id"])
        self.assertIn("Dashboard Snapshot", result["docs_pages"])
        self.assertIn("view_setup", result["artifacts"])
        dashboard_page = self.client.retrieve_page(result["docs_pages"]["Dashboard Snapshot"])
        self.assertEqual(dashboard_page["parent"]["data_source_id"], result["docs_data_source_id"])

    def test_config_normalizes_parent_page_id_from_urlish_value(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NOTION_API_TOKEN": "token",
                "NOTION_PARENT_PAGE_ID": "Reasoned-NYC-33478c4ea06e80169f72d1dfc8b108fc?pvs=12",
                "PM_BRIDGE_STATUS_MAP": "ready:Ready,in_progress:In Progress,blocked:Blocked,review:Review,done:Done",
            },
            clear=False,
        ):
            config = BridgeConfig.from_env()
        self.assertEqual(config.parent_page_id, "33478c4e-a06e-8016-9f72-d1dfc8b108fc")

    def test_config_reads_dotenv_without_shell_sourcing(self) -> None:
        env_file = Path(self.temp_dir.name) / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "NOTION_API_TOKEN='token-with-$-chars'",
                    'NOTION_PARENT_PAGE_ID="33478c4ea06e80169f72d1dfc8b108fc"',
                    "PM_BRIDGE_STATUS_MAP=ready:Ready,in_progress:In Progress",
                ]
            ),
            encoding="utf-8",
        )

        with patch.dict(
            os.environ,
            {
                "PM_BRIDGE_ENV_FILE": str(env_file),
            },
            clear=True,
        ):
            config = BridgeConfig.from_env()

        self.assertEqual(config.api_token, "token-with-$-chars")
        self.assertEqual(config.parent_page_id, "33478c4e-a06e-8016-9f72-d1dfc8b108fc")
        self.assertEqual(config.status_map["ready"], "Ready")

    def test_sync_plan_is_idempotent(self) -> None:
        first = self.service.sync_plan(self.spec)
        second = self.service.sync_plan(self.spec)

        self.assertEqual(first["created"], ["foundation", "dashboard"])
        self.assertEqual(second["created"], [])
        self.assertEqual(len(self.client.data_source_pages["ds-1"]), 2)

    def test_next_tasks_respects_dependencies_and_done_state(self) -> None:
        self.service.sync_plan(self.spec)
        initial = self.service.next_tasks()
        self.assertEqual([item["key"] for item in initial["ready"]], ["foundation"])
        self.assertEqual([item["key"] for item in initial["blocked"]], ["dashboard"])

        self.service.finish("foundation", summary="Done")
        after_finish = self.service.next_tasks()
        self.assertEqual([item["key"] for item in after_finish["ready"]], ["dashboard"])

    def test_claim_start_block_and_finish_append_activity(self) -> None:
        self.service.sync_plan(self.spec)

        self.service.claim("foundation", owner="codex")
        self.service.start("foundation", owner="codex", branch="codex/foundation")
        self.service.block("dashboard", dependency_ref="foundation", note="Waiting on foundation")
        self.service.finish("foundation", summary="Completed foundation", branch="codex/foundation")

        foundation_page_id = self.service._load_state().task_pages_by_key["foundation"]
        dashboard_page_id = self.service._load_state().task_pages_by_key["dashboard"]
        combined_markdown = self.client.page_markdown[foundation_page_id] + "\n" + self.client.page_markdown[dashboard_page_id]
        self.assertIn("claimed this task", combined_markdown)
        self.assertIn("started this task", combined_markdown)
        self.assertIn("Blocked by `foundation`", combined_markdown)
        self.assertIn("Completed through pm bridge", combined_markdown)

    def test_refresh_pulls_human_edits_back_into_snapshot(self) -> None:
        self.service.sync_plan(self.spec)
        foundation_page_id = self.service._load_state().task_pages_by_key["foundation"]
        foundation_page = self.client.pages[foundation_page_id]
        foundation_page["properties"]["Status"] = {"type": "select", "select": {"name": "Done"}}
        foundation_page["properties"]["Progress"] = {"type": "number", "number": 100}

        refreshed = self.service.refresh()
        self.assertEqual(refreshed["snapshot"]["foundation"]["status"], "Done")
        self.assertEqual(refreshed["snapshot"]["foundation"]["progress"], 100)

    def test_delivery_state_stays_synced_with_progress(self) -> None:
        self.service.sync_plan(self.spec)
        foundation_page_id = self.service._load_state().task_pages_by_key["foundation"]
        foundation_page = self.client.pages[foundation_page_id]

        self.assertEqual(foundation_page["properties"]["Delivery Status"]["select"]["name"], "Not started")
        self.assertEqual(foundation_page["properties"]["Progress"]["number"], 0)

        foundation_page["properties"]["Delivery Status"] = {"type": "select", "select": {"name": "In progress"}}
        foundation_page["properties"]["Progress"] = {"type": "number", "number": 0}

        refreshed = self.service.refresh()
        self.assertEqual(refreshed["snapshot"]["foundation"]["completion_state"], "In progress")
        self.assertEqual(refreshed["snapshot"]["foundation"]["progress"], 50)

        self.service.finish("foundation", summary="Done")
        finished_page = self.client.pages[foundation_page_id]
        self.assertEqual(finished_page["properties"]["Delivery Status"]["select"]["name"], "Completed")
        self.assertEqual(finished_page["properties"]["Progress"]["number"], 100)


    def test_dashboard_writes_markdown_artifact_and_updates_page(self) -> None:
        self.service.sync_plan(self.spec)
        result = self.service.dashboard()
        dashboard_path = Path(result["path"])
        self.assertTrue(dashboard_path.exists())
        self.assertIn("# Dashboard: agent-pm", dashboard_path.read_text())
        dashboard_page_id = self.service._load_state().docs_pages["Dashboard Snapshot"]
        self.assertIn(MANAGED_START, self.client.page_markdown[dashboard_page_id])
        self.assertIn(MANAGED_END, self.client.page_markdown[dashboard_page_id])

    def test_replace_managed_markdown_handles_escaped_markers_from_notion(self) -> None:
        page = self.client.create_page(parent_page_id="workspace-root", title="Escaped Page")
        page_id = page["id"]
        self.client.page_markdown[page_id] = "\n".join(
            [
                ESCAPED_MANAGED_START,
                "# Old",
                ESCAPED_MANAGED_END,
            ]
        )

        self.service._replace_managed_markdown(page_id, self.service._render_managed_section("New", "Fresh content"))

        self.assertEqual(self.client.page_markdown[page_id], self.service._render_managed_section("New", "Fresh content"))

    def test_draft_revision_flow_creates_scaffold_and_revision_pages(self) -> None:
        result = self.coordinator.draft_from_brief("Build an app for collaborative planning.", "Planner App")
        state = self.service._load_state()

        self.assertEqual(result["revision_key"], "rev-001")
        self.assertIn("Brief", state.docs_pages)
        self.assertIn("PRD", state.docs_pages)
        self.assertIn("Architecture", state.docs_pages)
        self.assertIn("Plan Index", state.docs_pages)
        self.assertTrue(state.docs_database_id)
        self.assertIn("rev-001", state.revision_pages)

    def test_revise_and_approve_revision_updates_active_plan(self) -> None:
        self.coordinator.draft_from_brief("Build an app for collaborative planning.", "Planner App")
        revised = self.coordinator.revise_plan("planner-app", "Split the work into a thinner v1 and clearer milestones.")
        approved = self.coordinator.approve_revision("planner-app", revised["revision_key"])
        state = self.service._load_state()

        self.assertEqual(revised["revision_key"], "rev-002")
        self.assertEqual(approved["active_revision_key"], "rev-002")
        self.assertEqual(state.revision_statuses["rev-001"], "superseded")
        self.assertEqual(state.revision_statuses["rev-002"], "approved")

    def test_build_workspace_and_execute_next_use_approved_revision(self) -> None:
        self.coordinator.draft_from_brief("Build an app for collaborative planning.", "Planner App")
        self.coordinator.approve_revision("planner-app", "rev-001")
        built = self.coordinator.build_workspace("planner-app", "rev-001")
        executed = self.coordinator.execute_next("planner-app", "codex-main")
        foundation_page_id = self.service._load_state().task_pages_by_key["scope-prd"]

        self.assertTrue(built["tasks_database_id"])
        self.assertEqual(len(built["mcp_view_specs"]), 1)
        self.assertEqual(executed["selected_task"], "scope-prd")
        self.assertEqual(self.client.pages[foundation_page_id]["properties"]["Status"]["select"]["name"], "In Progress")

    def test_reconcile_after_replan_supersedes_removed_tasks_but_keeps_done(self) -> None:
        self.coordinator.draft_from_brief("Build an app for collaborative planning.", "Planner App")
        self.coordinator.approve_revision("planner-app", "rev-001")
        self.coordinator.build_workspace("planner-app", "rev-001")
        self.service.finish("scope-prd", summary="Completed")

        revised_draft = PlanningDraft(
            project=ProjectSpec(identifier="planner-app", name="Planner App", description="Build an app for collaborative planning."),
            brief="Build an app for collaborative planning.",
            prd_markdown="# PRD\nRefined scope",
            architecture_markdown="# Architecture\nRefined architecture",
            revision_markdown="# Revised Plan\nNarrow the scope and remove validation from v1.",
            tasks=[
                TaskSpec(
                    key="scope-prd",
                    title="Finalize scope and PRD",
                    description="Keep the completed scope work.",
                    type="Research",
                    status="Done",
                    priority="High",
                    execution_mode="pair",
                    parallelizable=False,
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
                ),
            ],
            summary="Remove the validation phase from the first release.",
        )
        revised = self.coordinator.revise_plan("planner-app", "Remove validation from v1.", draft=revised_draft)
        self.coordinator.approve_revision("planner-app", revised["revision_key"])
        reconciled = self.coordinator.reconcile_after_replan("planner-app", revised["revision_key"])
        state = self.service._load_state()

        self.assertIn("architecture-foundation", reconciled["sync"]["superseded"])
        self.assertIn("validate-release", reconciled["sync"]["superseded"])
        self.assertEqual(state.snapshot["scope-prd"]["status"], "Done")
        self.assertEqual(state.snapshot["architecture-foundation"]["status"], "Superseded")
        self.assertEqual(state.snapshot["validate-release"]["status"], "Superseded")

    def test_register_approved_plan_copies_to_repo_artifact_layout(self) -> None:
        source = Path(self.temp_dir.name) / "source-plan.md"
        source.write_text("# Planner App\n\n## Implementation\n- Build execution workspace\n")

        result = self.coordinator.register_approved_plan("Planner App", str(source))

        approved_path = Path(result["approved_plan_path"])
        self.assertTrue(approved_path.exists())
        self.assertEqual(approved_path.name, "approved-plan.md")
        self.assertIn("Planner App", approved_path.read_text())
        self.assertEqual(result["approved_plan_revision_key"], "r001")
        self.assertTrue(Path(result["approved_plan_versioned_path"]).exists())

    def test_register_approved_plan_with_companion_tasks_copies_both_artifacts(self) -> None:
        source = Path(self.temp_dir.name) / "shipping-plan.md"
        source.write_text("# Shipping Plan\n\n## Goal\nShip the planner app.\n")
        tasks = Path(self.temp_dir.name) / "shipping-tasks.md"
        tasks.write_text("# Shipping Tasks\n\n## Phase 1 — Dogfood\n- `P1.1 Docker smoke path stabilization` — Explanation: make Docker work; Goal: clean startup; Tests: smoke path; AI-assisted estimate: `0.5-1 day`; Parallelization: serial anchor.\n")

        result = self.coordinator.register_approved_plan("Planner App", str(source), task_plan_path=str(tasks))

        self.assertTrue(Path(result["approved_plan_path"]).exists())
        self.assertTrue(Path(result["approved_tasks_path"]).exists())
        self.assertTrue(Path(result["approved_tasks_versioned_path"]).exists())
        self.assertIn("Shipping Tasks", Path(result["approved_tasks_path"]).read_text())

    def test_register_approved_plan_clears_foreign_workspace_and_rescue_state(self) -> None:
        stale_page = self.client.create_page(parent_page_id="workspace-root", title="Example Workspace", markdown="# Old project")
        stale = self.service._load_state()
        stale.project_identifier = "notion-pm-bridge"
        stale.project_page_id = stale_page["id"]
        stale.project_page_url = stale_page["url"]
        stale.tasks_database_id = "db-old"
        stale.tasks_data_source_id = "ds-old"
        stale.docs_database_id = "db-docs-old"
        stale.docs_data_source_id = "ds-docs-old"
        stale.docs_pages = {"Recovery Plan": "page-old"}
        stale.current_state_path = "plans/data-workbench/current-state.md"
        stale.recovery_plan_path = "plans/data-workbench/recovery-plan.md"
        stale.detailed_scan_path = "plans/data-workbench/detailed-scan.md"
        stale.snapshot = {"old-task": {"title": "Old task"}}
        self.service._save_state(stale)

        source = Path(self.temp_dir.name) / "shipping-plan.md"
        source.write_text("# Notion PM Bridge\n\n## Goal\nShip the bridge.\n")

        self.coordinator.register_approved_plan("Notion PM Bridge", str(source))
        state = self.service._load_state()

        self.assertEqual(state.project_identifier, "notion-pm-bridge")
        self.assertEqual(state.project_page_id, "")
        self.assertEqual(state.tasks_database_id, "")
        self.assertEqual(state.docs_pages, {})
        self.assertEqual(state.current_state_path, "")
        self.assertEqual(state.recovery_plan_path, "")
        self.assertEqual(state.detailed_scan_path, "")

    def test_project_home_ignores_foreign_rescue_paths_even_if_state_is_stale(self) -> None:
        project_dir = self.service.config.plans_dir / "notion-pm-bridge"
        project_dir.mkdir(parents=True, exist_ok=True)
        approved_plan = project_dir / "approved-plan.md"
        approved_plan.write_text(
            "# Notion PM Bridge\n\n"
            "## Goal\n"
            "Ship the bridge.\n\n"
            "## Maintenance Baseline\n"
            "- Keep the repo-first workflow understandable.\n"
        )
        foreign_dir = self.service.config.plans_dir / "data-workbench"
        foreign_dir.mkdir(parents=True, exist_ok=True)
        (foreign_dir / "current-state.md").write_text(
            "# Current State Snapshot\n\n"
            "## Project Goal\n"
            "Ship the example workspace instead.\n\n"
            "## What Completion Requires\n"
            "- Wrong project content.\n"
        )

        state = self.service._load_state()
        state.project_identifier = "notion-pm-bridge"
        state.approved_plan_path = "plans/notion-pm-bridge/approved-plan.md"
        state.current_state_path = "plans/data-workbench/current-state.md"

        rendered = self.service._render_project_home(
            PlanSpec(project=ProjectSpec(identifier="notion-pm-bridge", name="Notion PM Bridge", description="Ship the bridge."), docs=[], tasks=[]),
            state,
        )

        self.assertIn("Ship the bridge.", rendered)
        self.assertNotIn("Ship the example workspace instead.", rendered)
        self.assertNotIn("plans/data-workbench/current-state.md", rendered)

    def test_decompose_approved_plan_writes_graph_and_handoff_without_notion_mutation(self) -> None:
        source = Path(self.temp_dir.name) / "source-plan.md"
        source.write_text("# Planner App\n\n## Phase One\n- Build execution workspace\n- Add dashboard\n")
        self.coordinator.register_approved_plan("Planner App", str(source))

        result = self.coordinator.decompose_approved_plan("planner-app")

        self.assertTrue(Path(result["task_graph_path"]).exists())
        self.assertTrue(Path(result["handoff_path"]).exists())
        self.assertTrue(Path(result["review_path"]).parent.name == "revisions")
        self.assertEqual(result["tasks_seeded"], 3)
        self.assertEqual(self.client.pages, {})

    def test_decompose_approved_plan_uses_companion_shipping_tasks_when_present(self) -> None:
        plan = Path(self.temp_dir.name) / "shipping-plan.md"
        plan.write_text(
            "# Shipping Plan: Contributor Share\n\n"
            "## Goal\n"
            "Ship a contributor-ready public repo.\n\n"
            "## Maintainability Before Ship\n"
            "- Keep the entrypoint thin.\n"
        )
        tasks = Path(self.temp_dir.name) / "shipping-tasks.md"
        tasks.write_text(
            "# Shipping Tasks: Contributor Share\n\n"
            "## Goal\n"
            "Ship the repo.\n\n"
            "## Phase 1 — Dogfood Baseline\n"
            "Phase estimate: `2-3 focused days`\n\n"
            "- `P1.1 Docker smoke path stabilization` — Explanation: make Docker the happy path; Goal: predictable startup; Tests: smoke, healthz; AI-assisted estimate: `0.5-1 day`; Parallelization: serial anchor for all other Docker work.\n"
            "- `P1.2 Environment contract cleanup` — Explanation: document env vars; Goal: reproducible setup; Tests: Docker run from docs; AI-assisted estimate: `0.25-0.5 day`; Parallelization: can run after `P1.1` defines the real config shape.\n\n"
            "## Assumptions and Defaults\n"
            "- Docker-first.\n"
        )

        self.coordinator.register_approved_plan("Planner App", str(plan), task_plan_path=str(tasks))
        result = self.coordinator.decompose_approved_plan("planner-app")
        payload = json.loads(Path(result["task_graph_path"]).read_text())
        tasks_by_title = {task["title"]: task for task in payload["tasks"]}

        self.assertIn("Phase 1 — Dogfood Baseline", tasks_by_title)
        self.assertIn("P1.1 Docker smoke path stabilization", tasks_by_title)
        self.assertIn("P1.2 Environment contract cleanup", tasks_by_title)
        self.assertEqual(tasks_by_title["P1.1 Docker smoke path stabilization"]["agent_estimate_hours"], 4)
        self.assertTrue(tasks_by_title["P1.2 Environment contract cleanup"]["dependencies"])

    def test_shipping_decomposition_assigns_parallel_waves_and_links(self) -> None:
        plan = Path(self.temp_dir.name) / "shipping-plan.md"
        plan.write_text(
            "# Shipping Plan: Contributor Share\n\n"
            "## Goal\n"
            "Ship a contributor-ready public repo.\n"
        )
        tasks = Path(self.temp_dir.name) / "shipping-tasks.md"
        tasks.write_text(
            "# Shipping Tasks: Contributor Share\n\n"
            "## Goal\n"
            "Ship the repo.\n\n"
            "## Phase 1 — Dogfood Baseline\n"
            "Phase estimate: `2-3 focused days`\n\n"
            "- `P1.1 Docker smoke path stabilization` — Explanation: make Docker the happy path; Goal: predictable startup; Tests: smoke, healthz; AI-assisted estimate: `0.5-1 day`; Parallelization: serial anchor for all other Docker work.\n"
            "- `P1.2 Environment contract cleanup` — Explanation: document env vars; Goal: reproducible setup; Tests: Docker run from docs; AI-assisted estimate: `0.25-0.5 day`; Parallelization: parallel after `P1.1`.\n"
            "- `P1.3 Docs pass for local startup` — Explanation: clean quickstart docs; Goal: lower setup confusion; Tests: docs walkthrough; AI-assisted estimate: `0.25-0.5 day`; Parallelization: parallel after `P1.1`.\n"
        )

        self.coordinator.register_approved_plan("Planner App", str(plan), task_plan_path=str(tasks))
        result = self.coordinator.decompose_approved_plan("planner-app")
        payload = json.loads(Path(result["task_graph_path"]).read_text())
        tasks_by_title = {task["title"]: task for task in payload["tasks"]}

        env_task = tasks_by_title["P1.2 Environment contract cleanup"]
        docs_task = tasks_by_title["P1.3 Docs pass for local startup"]
        self.assertEqual(env_task["parallel_group"], "Wave A")
        self.assertEqual(docs_task["parallel_group"], "Wave A")
        self.assertIn(docs_task["key"], env_task["parallel_with"])
        self.assertIn(env_task["key"], docs_task["parallel_with"])
        self.assertEqual(env_task["completion_state"], "Not started")

    def test_parallel_with_references_do_not_create_false_dependency_cycles(self) -> None:
        plan = Path(self.temp_dir.name) / "shipping-plan.md"
        plan.write_text(
            "# Shipping Plan: Contributor Share\n\n"
            "## Goal\n"
            "Ship a contributor-ready public repo.\n"
        )
        tasks = Path(self.temp_dir.name) / "shipping-tasks.md"
        tasks.write_text(
            "# Shipping Tasks: Contributor Share\n\n"
            "## Goal\n"
            "Ship the repo.\n\n"
            "## Phase 4 — Release Confidence\n"
            "Phase estimate: `1-2 focused days`\n\n"
            "- `P4.1 Serial anchor` — Explanation: lock the shared release baseline; Goal: create the phase anchor; Tests: release baseline check; AI-assisted estimate: `0.5-1 day`; Parallelization: serial anchor for this phase.\n"
            "- `P4.2 QA rehearsal` — Explanation: run the rehearsal path; Goal: validate the release flow; Tests: rehearsal walkthrough; AI-assisted estimate: `0.5-1 day`; Parallelization: parallel with `P4.3` after `P4.1`.\n"
            "- `P4.3 Docs polish` — Explanation: finalize the public docs; Goal: make the release legible; Tests: docs walkthrough; AI-assisted estimate: `0.25-0.5 day`; Parallelization: parallel with `P4.2` after `P4.1`.\n"
        )

        self.coordinator.register_approved_plan("Planner App", str(plan), task_plan_path=str(tasks))
        result = self.coordinator.decompose_approved_plan("planner-app")
        review = self.coordinator.review_decomposition("planner-app")
        payload = json.loads(Path(result["task_graph_path"]).read_text())
        tasks_by_title = {task["title"]: task for task in payload["tasks"]}

        qa_task = tasks_by_title["P4.2 QA rehearsal"]
        docs_task = tasks_by_title["P4.3 Docs polish"]

        self.assertEqual(review["review_status"], "pass")
        self.assertEqual(qa_task["dependencies"], ["p4-1-serial-anchor"])
        self.assertEqual(docs_task["dependencies"], ["p4-1-serial-anchor"])
        self.assertIn(docs_task["key"], qa_task["parallel_with"])
        self.assertIn(qa_task["key"], docs_task["parallel_with"])

    def test_registering_new_approved_plan_creates_new_revision_and_updates_current_alias(self) -> None:
        first = Path(self.temp_dir.name) / "first.md"
        second = Path(self.temp_dir.name) / "second.md"
        first.write_text("# Planner App\n\n## Phase One\n- Build execution workspace\n")
        second.write_text("# Planner App\n\n## Phase Two\n- Reconcile workspace\n")

        first_result = self.coordinator.register_approved_plan("Planner App", str(first))
        second_result = self.coordinator.register_approved_plan("Planner App", str(second))

        current_path = Path(second_result["approved_plan_path"])
        self.assertEqual(first_result["approved_plan_revision_key"], "r001")
        self.assertEqual(second_result["approved_plan_revision_key"], "r002")
        self.assertTrue(Path(first_result["approved_plan_versioned_path"]).exists())
        self.assertTrue(Path(second_result["approved_plan_versioned_path"]).exists())
        self.assertIn("Phase Two", current_path.read_text())

    def test_review_gate_blocks_build_when_decomposition_requires_changes(self) -> None:
        source = Path(self.temp_dir.name) / "source-plan.md"
        source.write_text("# Planner App\n\n## Phase One\n- Build execution workspace\n")
        self.coordinator.register_approved_plan("Planner App", str(source))
        bad_graph = TaskGraphSpec(
            project=ProjectSpec(identifier="planner-app", name="Planner App", description="Execution workspace"),
            source_plan_path=str(self.service.config.plans_dir / "planner-app" / "approved-plan.md"),
            handoff_id="handoff-test",
            tasks=[TaskSpec(key="orphan-task", title="Orphan Task", type="Task")],
        )
        self.coordinator.decompose_approved_plan("planner-app", task_graph=bad_graph)
        review = self.coordinator.review_decomposition("planner-app")

        self.assertEqual(review["review_status"], "changes_required")
        with self.assertRaises(StateError):
            self.coordinator.build_workspace_from_handoff("planner-app")

    def test_build_workspace_from_reviewed_handoff_creates_execution_docs_and_tasks(self) -> None:
        source = Path(self.temp_dir.name) / "source-plan.md"
        source.write_text("# Planner App\n\n## Phase One\n- Build execution workspace\n")
        self.coordinator.register_approved_plan("Planner App", str(source))
        good_graph = TaskGraphSpec(
            project=ProjectSpec(identifier="planner-app", name="Planner App", description="Execution workspace"),
            source_plan_path=str(self.service.config.plans_dir / "planner-app" / "approved-plan.md"),
            handoff_id="handoff-test",
            summary="Reviewed handoff",
            tasks=[
                TaskSpec(
                    key="phase-one",
                    title="Phase One",
                    type="Milestone",
                    status="Ready",
                    priority="High",
                    execution_mode="pair",
                    parallelizable=False,
                    agent_role="pm",
                    preferred_skill="pm-plan-translator",
                    sequence=1,
                ),
                TaskSpec(
                    key="workspace-epic",
                    title="Workspace",
                    type="Epic",
                    status="Ready",
                    priority="High",
                    parent_key="phase-one",
                    execution_mode="pair",
                    parallelizable=False,
                    agent_role="pm",
                    preferred_skill="pm-plan-translator",
                    sequence=2,
                ),
                TaskSpec(
                    key="build-workspace",
                    title="Build execution workspace",
                    type="Task",
                    status="Ready",
                    priority="High",
                    parent_key="workspace-epic",
                    execution_mode="agent",
                    parallelizable=True,
                    agent_role="executor",
                    preferred_skill="notion-pm-bridge",
                    sequence=3,
                ),
            ],
        )
        self.coordinator.decompose_approved_plan("planner-app", task_graph=good_graph)
        review = self.coordinator.review_decomposition("planner-app")
        built = self.coordinator.build_workspace_from_handoff("planner-app")
        executed = self.coordinator.execute_next("planner-app", "codex-main")
        state = self.service._load_state()

        self.assertEqual(review["review_status"], "pass")
        self.assertIn("Final Approved Plan", state.docs_pages)
        self.assertIn("Handoff Summary", state.docs_pages)
        self.assertTrue(built["phases_database_id"])
        self.assertTrue(built["tasks_database_id"])
        self.assertTrue(state.docs_database_id)
        self.assertEqual(len(built["mcp_view_specs"]), 4)
        self.assertEqual(executed["selected_task"], "build-workspace")

    def test_reconcile_from_new_plan_revision_supersedes_removed_open_tasks(self) -> None:
        first = Path(self.temp_dir.name) / "first.md"
        second = Path(self.temp_dir.name) / "second.md"
        first.write_text("# Planner App\n\n## Phase One\n- Build execution workspace\n- Add dashboard\n")
        second.write_text("# Planner App\n\n## Phase Two\n- Build execution workspace\n- Reconcile workspace\n")

        self.coordinator.register_approved_plan("Planner App", str(first))
        first_graph = TaskGraphSpec(
            project=ProjectSpec(identifier="planner-app", name="Planner App", description="Execution workspace"),
            source_plan_path=str(self.service.config.plans_dir / "planner-app" / "approved-plan.md"),
            handoff_id="r001",
            summary="First handoff",
            tasks=[
                TaskSpec(key="phase-one", title="Phase One", type="Milestone", status="Ready", priority="High", execution_mode="pair", parallelizable=False, agent_role="pm", preferred_skill="pm-plan-translator", sequence=1),
                TaskSpec(key="workspace-epic", title="Workspace", type="Epic", status="Ready", priority="High", parent_key="phase-one", execution_mode="pair", parallelizable=False, agent_role="pm", preferred_skill="pm-plan-translator", sequence=2),
                TaskSpec(key="build-workspace", title="Build execution workspace", type="Task", status="Ready", priority="High", parent_key="workspace-epic", execution_mode="agent", parallelizable=True, agent_role="executor", preferred_skill="notion-pm-bridge", sequence=3),
                TaskSpec(key="add-dashboard", title="Add dashboard", type="Task", status="Ready", priority="Normal", parent_key="workspace-epic", execution_mode="agent", parallelizable=True, agent_role="executor", preferred_skill="notion-pm-bridge", sequence=4),
            ],
        )
        self.coordinator.decompose_approved_plan("planner-app", task_graph=first_graph)
        self.coordinator.review_decomposition("planner-app")
        self.coordinator.build_workspace_from_handoff("planner-app")
        self.service.finish("build-workspace", summary="Done")

        self.coordinator.register_approved_plan("Planner App", str(second))
        second_graph = TaskGraphSpec(
            project=ProjectSpec(identifier="planner-app", name="Planner App", description="Execution workspace"),
            source_plan_path=str(self.service.config.plans_dir / "planner-app" / "approved-plan.md"),
            handoff_id="r002",
            summary="Second handoff",
            tasks=[
                TaskSpec(key="phase-two", title="Phase Two", type="Milestone", status="Ready", priority="High", execution_mode="pair", parallelizable=False, agent_role="pm", preferred_skill="pm-plan-translator", sequence=1),
                TaskSpec(key="workspace-epic", title="Workspace", type="Epic", status="Ready", priority="High", parent_key="phase-two", execution_mode="pair", parallelizable=False, agent_role="pm", preferred_skill="pm-plan-translator", sequence=2),
                TaskSpec(key="build-workspace", title="Build execution workspace", type="Task", status="Done", priority="High", parent_key="workspace-epic", execution_mode="agent", parallelizable=True, agent_role="executor", preferred_skill="notion-pm-bridge", sequence=3),
                TaskSpec(key="reconcile-workspace", title="Reconcile workspace", type="Task", status="Ready", priority="High", parent_key="workspace-epic", execution_mode="agent", parallelizable=True, agent_role="executor", preferred_skill="notion-pm-bridge", sequence=4),
            ],
        )
        self.coordinator.decompose_approved_plan("planner-app", task_graph=second_graph)
        self.coordinator.review_decomposition("planner-app")
        reconciled = self.coordinator.reconcile_workspace_from_handoff("planner-app")
        state = self.service._load_state()

        self.assertEqual(reconciled["approved_plan_revision_key"], "r002")
        self.assertIn("add-dashboard", reconciled["sync"]["superseded"])
        self.assertEqual(state.snapshot["build-workspace"]["status"], "Done")
        self.assertEqual(state.snapshot["add-dashboard"]["status"], "Superseded")

    def test_rescue_project_writes_current_state_and_recovery_plan(self) -> None:
        result = self.coordinator.rescue_project(
            "Planner App",
            context_markdown="The repo has drifted and the team lost track of what is in flight.",
            goal_statement="Finish the planner app with one explicit approved plan and a maintainable execution trail.",
        )

        current_state = Path(result["current_state_path"])
        recovery_plan = Path(result["recovery_plan_path"])
        self.assertTrue(current_state.exists())
        self.assertTrue(recovery_plan.exists())
        self.assertIn("Current State Snapshot", current_state.read_text())
        self.assertIn("## Project Goal", current_state.read_text())
        self.assertIn("# Recovery Plan", recovery_plan.read_text())
        self.assertIn("## Bring-It-Home Workstreams", recovery_plan.read_text())

    def test_rescue_project_ignores_stale_state_from_different_project(self) -> None:
        stale = self.service._load_state()
        stale.project_identifier = "other-project"
        stale.approved_plan_path = "plans/other-project/approved-plan.md"
        stale.approved_plan_revision_key = "r009"
        stale.handoff_path = "plans/other-project/handoff.json"
        stale.active_review_status = "pass"
        stale.tasks_database_id = "db-other"
        stale.tasks_data_source_id = "ds-other"
        stale.docs_pages = {"Brief": "page-123"}
        self.service._save_state(stale)

        result = self.coordinator.rescue_project("Planner App", context_markdown="Fresh rescue context.")

        current_state = Path(result["current_state_path"]).read_text()
        recovery_plan = Path(result["recovery_plan_path"]).read_text()
        self.assertNotIn("plans/other-project/approved-plan.md", current_state)
        self.assertNotIn("Latest handoff", current_state)
        self.assertNotIn("Existing Notion Docs", current_state)
        self.assertNotIn("Previous approved plan", recovery_plan)
        self.assertIn("Fresh rescue context.", current_state)

    def test_deepen_rescue_scan_writes_detailed_scan_and_updates_rescue_docs(self) -> None:
        self.coordinator.rescue_project(
            "Planner App",
            context_markdown="Quick scan context.",
            goal_statement="Ship the planner app with a clear finish line.",
        )

        result = self.coordinator.deepen_rescue_scan(
            "planner-app",
            detailed_scan_markdown=(
                "### Essential Files\n"
                "- `src/main.py`\n"
                "- `docs/`\n\n"
                "### Work In Progress\n"
                "- tighten the approved plan and execution model\n"
            ),
            goal_statement="Ship the planner app with a clear finish line.",
            completion_definition="- Publish one approved plan and execute it to completion.",
            maintenance_requirements="- Preserve one canonical runbook and one durable rescue notebook.",
        )

        detailed_scan = Path(result["detailed_scan_path"])
        current_state = Path(result["current_state_path"])
        recovery_plan = Path(result["recovery_plan_path"])
        self.assertTrue(detailed_scan.exists())
        self.assertIn("Detailed Rescue Scan", detailed_scan.read_text())
        self.assertIn("What Completion Requires", current_state.read_text())
        self.assertIn("## Bring-It-Home Workstreams", recovery_plan.read_text())
        self.assertIn("### Keep the project maintainable", recovery_plan.read_text())

    def test_publish_rescue_docs_creates_doc_only_notebook_and_ignores_stale_project_page(self) -> None:
        other_project = self.client.create_page(parent_page_id="workspace-root", title="Other Project", markdown="# Old project")
        stale = self.service._load_state()
        stale.project_identifier = "other-project"
        stale.project_page_id = other_project["id"]
        stale.docs_pages = {
            "Brief": "page-old-brief",
            "PRD": "page-old-prd",
        }
        self.service._save_state(stale)

        self.coordinator.rescue_project(
            "Planner App",
            context_markdown="Quick rescue context.",
            goal_statement="Ship the planner app with a clear finish line.",
        )
        self.coordinator.deepen_rescue_scan(
            "planner-app",
            detailed_scan_markdown="### Essential Files\n- `src/main.py`\n",
            goal_statement="Ship the planner app with a clear finish line.",
            completion_definition="- Finish the rescue and execute from one approved plan.",
            maintenance_requirements="- Keep rescue docs durable in Notion.",
        )

        published = self.coordinator.publish_rescue_docs("Planner App")
        state = self.service._load_state()

        self.assertTrue(published["project_page_id"])
        self.assertNotEqual(published["project_page_id"], other_project["id"])
        self.assertEqual(state.tasks_database_id, "")
        self.assertTrue(state.docs_database_id)
        self.assertIn("Rescue Notebook", published["docs_pages"])
        self.assertIn("Rescue Current State", published["docs_pages"])
        self.assertIn("Recovery Plan", published["docs_pages"])
        self.assertNotIn("Brief", published["docs_pages"])
        self.assertNotIn("PRD", published["docs_pages"])
        for doc_title in ("Rescue Notebook", "Recovery Plan", "Rescue Current State", "Rescue Detailed Scan"):
            page = self.client.retrieve_page(published["docs_pages"][doc_title])
            self.assertEqual(page["parent"]["data_source_id"], state.docs_data_source_id)
        self.assertEqual(_plain_text(self.client.retrieve_page(other_project["id"])["properties"]["title"]["title"]), "Other Project")

    def test_publish_rescue_docs_rebuilds_docs_mapping_for_same_project(self) -> None:
        self.coordinator.rescue_project(
            "Planner App",
            context_markdown="Quick rescue context.",
            goal_statement="Ship the planner app with a clear finish line.",
        )
        self.coordinator.deepen_rescue_scan(
            "planner-app",
            detailed_scan_markdown="### Essential Files\n- `src/main.py`\n",
            goal_statement="Ship the planner app with a clear finish line.",
            completion_definition="- Finish the rescue and execute from one approved plan.",
            maintenance_requirements="- Keep rescue docs durable in Notion.",
        )

        stale = self.service._load_state()
        stale.docs_pages["Brief"] = "page-old-brief"
        stale.docs_pages["PRD"] = "page-old-prd"
        self.service._save_state(stale)

        published = self.coordinator.publish_rescue_docs("Planner App")

        self.assertIn("Rescue Notebook", published["docs_pages"])
        self.assertIn("Recovery Plan", published["docs_pages"])
        self.assertNotIn("Brief", published["docs_pages"])
        self.assertNotIn("PRD", published["docs_pages"])

    def test_project_home_mentions_tasks_phases_docs_and_inline_setup(self) -> None:
        self.service.sync_plan(self.spec)
        state = self.service._load_state()
        markdown = self.client.retrieve_page_markdown(state.project_page_id)["markdown"]

        self.assertIn("## Start Here", markdown)
        self.assertIn("[Tasks]", markdown)
        self.assertIn("[Phases]", markdown)
        self.assertIn("[Docs]", markdown)
        self.assertIn("How Pages Fit Together", markdown)
        self.assertIn("Inline View Setup", markdown)
        self.assertNotIn("Team Project", markdown)

    def test_new_project_is_indexed_under_projects_not_shared_templates(self) -> None:
        root = self.client.create_page(
            parent_page_id="workspace-root-parent",
            title="Reasoned NYC",
            markdown=(
                "# Reasoned NYC\n\n"
                "## Projects\n"
                "- [Data Workbench](https://www.notion.so/page-existing)\n\n"
                "## Shared Templates\n"
                "- [Team Projects](https://www.notion.so/page-template)\n"
                "- [Agent PM](https://www.notion.so/page-stale)\n"
            ),
        )
        self.service.config.parent_page_id = root["id"]

        self.service.sync_plan(self.spec)

        root_markdown = self.client.retrieve_page_markdown(root["id"])["markdown"]
        projects_section = root_markdown.split("## Projects", 1)[1].split("## Shared Templates", 1)[0]
        shared_templates_section = root_markdown.split("## Shared Templates", 1)[1]

        self.assertIn("[Agent PM](", projects_section)
        self.assertNotIn("[Agent PM](", shared_templates_section)

    def test_milestones_sync_into_phase_database_not_task_database(self) -> None:
        phase_spec = PlanSpec(
            project=self.spec.project,
            docs=[],
            tasks=[
                TaskSpec(
                    key="phase-1",
                    title="Phase 1",
                    type="Milestone",
                    plan_revision="r001",
                    start_date="2026-04-01",
                    due_date="2026-04-03",
                    agent_estimate_hours=6,
                    human_estimate_hours=12,
                ),
                TaskSpec(
                    key="task-a",
                    title="Task A",
                    parent_key="phase-1",
                    plan_revision="r001",
                    status="Ready",
                    agent_role="executor",
                ),
            ],
        )

        result = self.service.sync_plan(phase_spec)
        state = self.service._load_state()

        self.assertEqual(result["phase_created"], ["phase-1"])
        self.assertEqual(result["created"], ["task-a"])
        self.assertIn("phase-1", state.phase_pages_by_key)
        self.assertNotIn("phase-1", state.task_pages_by_key)
        task_page = self.client.retrieve_page(state.task_pages_by_key["task-a"])
        self.assertEqual(task_page["properties"]["Phase"]["relation"][0]["id"], state.phase_pages_by_key["phase-1"])

    def test_recovery_plan_meta_sections_do_not_turn_into_orphan_milestones(self) -> None:
        approved = Path(self.temp_dir.name) / "recovery-approved.md"
        approved.write_text(
            "# Recovery Plan\n\n"
            "## Project Goal\n"
            "Ship the reviewed v1 with a maintainable operator workflow.\n\n"
            "## Rescue Understanding\n"
            "- Old notes that should not become tasks.\n\n"
            "## Bring-It-Home Workstreams\n"
            "### Finish the shippable core\n"
            "- Finish and stabilize the execution panel and persistence path.\n"
            "- Ensure the operator guide, runtime plan artifacts, and UI/API behavior all describe the same day-to-day workflow.\n\n"
            "### Keep the project maintainable\n"
            "- Keep docs and tests aligned.\n\n"
            "## Human Decisions Before Approval\n"
            "- Confirm the v1 boundary.\n"
        )

        self.coordinator.register_approved_plan("Planner App", str(approved))
        decomposed = self.coordinator.decompose_approved_plan("planner-app")
        reviewed = self.coordinator.review_decomposition("planner-app")
        graph_path = Path(decomposed["task_graph_path"])
        graph_payload = json.loads(graph_path.read_text())
        task_ids = {task["key"] for task in graph_payload["tasks"]}
        task_titles = {task["title"] for task in graph_payload["tasks"]}

        self.assertEqual(reviewed["review_status"], "pass")
        self.assertNotIn("rescue-understanding", task_ids)
        self.assertNotIn("human-decisions-before-approval", task_ids)
        self.assertIn("Finish the shippable core", task_titles)
        self.assertIn("Keep the project maintainable", task_titles)
        self.assertIn("Align operator guide", next(title for title in task_titles if title.startswith("Align operator guide")))

    def test_recovery_plan_decomposition_keeps_real_project_name(self) -> None:
        approved = Path(self.temp_dir.name) / "recovery-approved.md"
        approved.write_text(
            "# Recovery Plan\n\n"
            "## Project Goal\n"
            "Ship the planner app.\n\n"
            "## Bring-It-Home Workstreams\n"
            "### Finish the shippable core\n"
            "- Stabilize execution-state surface.\n"
        )

        self.coordinator.register_approved_plan("Planner App", str(approved))
        decomposed = self.coordinator.decompose_approved_plan("planner-app")
        graph_payload = json.loads(Path(decomposed["task_graph_path"]).read_text())

        self.assertEqual(graph_payload["project"]["name"], "Planner App")

    def test_recovery_plan_decomposition_adds_dual_estimates_and_dates(self) -> None:
        approved = Path(self.temp_dir.name) / "recovery-approved.md"
        approved.write_text(
            "# Recovery Plan\n\n"
            "## Project Goal\n"
            "Ship the planner app.\n\n"
            "## Bring-It-Home Workstreams\n"
            "### Finish the shippable core\n"
            "- Stabilize execution-state surface.\n"
            "- Keep v1 test coverage green.\n"
        )

        self.coordinator.register_approved_plan("Planner App", str(approved))
        decomposed = self.coordinator.decompose_approved_plan("planner-app")
        graph_payload = json.loads(Path(decomposed["task_graph_path"]).read_text())
        tasks = {task["title"]: task for task in graph_payload["tasks"]}

        self.assertIn("Finish the shippable core", tasks)
        self.assertIn("Stabilize execution-state surface", tasks)
        self.assertIsNotNone(tasks["Stabilize execution-state surface"]["human_estimate_hours"])
        self.assertIsNotNone(tasks["Stabilize execution-state surface"]["agent_estimate_hours"])
        self.assertTrue(tasks["Stabilize execution-state surface"]["start_date"])
        self.assertTrue(tasks["Stabilize execution-state surface"]["due_date"])


class PluginScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_local_plugin_manifest_and_marketplace_exist(self) -> None:
        plugin_root = self.repo_root / "plugins" / "shared-plan-handoff"
        manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        marketplace_path = self.repo_root / ".agents" / "plugins" / "marketplace.json"

        self.assertTrue(plugin_root.exists())
        self.assertTrue(manifest_path.exists())
        self.assertTrue(marketplace_path.exists())

        manifest = json.loads(manifest_path.read_text())
        marketplace = json.loads(marketplace_path.read_text())

        self.assertEqual(manifest["name"], "shared-plan-handoff")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["license"], "MIT")
        self.assertEqual(manifest["interface"]["displayName"], "Shared Plan Handoff")

        plugin_names = [entry["name"] for entry in marketplace["plugins"]]
        self.assertIn("shared-plan-handoff", plugin_names)

    def test_local_plugin_skills_and_docs_are_present(self) -> None:
        plugin_root = self.repo_root / "plugins" / "shared-plan-handoff"
        skill_paths = [
            plugin_root / "skills" / "notion-pm-bridge" / "SKILL.md",
            plugin_root / "skills" / "pm-plan-translator" / "SKILL.md",
            plugin_root / "skills" / "pm-rescue" / "SKILL.md",
        ]
        for path in skill_paths:
            self.assertTrue(path.exists(), msg=f"Missing plugin skill: {path}")

        self.assertTrue((plugin_root / "README.md").exists())
        self.assertTrue((plugin_root / "agents" / "openai.yaml").exists())
        self.assertTrue((plugin_root / "assets" / "shared-plan-handoff.svg").exists())
        self.assertTrue((self.repo_root / "docs" / "local_codex_plugin.md").exists())

    def test_release_confidence_docs_exist(self) -> None:
        self.assertTrue((self.repo_root / "docs" / "release_readiness.md").exists())
        self.assertTrue((self.repo_root / "docs" / "dogfood_retrospective.md").exists())
        self.assertTrue((self.repo_root / "docs" / "qa_report.md").exists())


class PublicationHygieneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_env_example_is_public_and_not_suppressed_by_gitignore(self) -> None:
        self.assertTrue((self.repo_root / ".env.example").exists())
        gitignore = (self.repo_root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("!.env.example", gitignore)

    def test_public_facing_docs_do_not_embed_local_absolute_paths(self) -> None:
        files = [
            self.repo_root / "README.md",
            self.repo_root / "examples" / "README.md",
            self.repo_root / ".codex" / "skills" / "notion-pm-bridge" / "SKILL.md",
            self.repo_root / "docs" / "local_codex_plugin.md",
        ]
        for path in files:
            self.assertNotIn("/Users/", path.read_text(encoding="utf-8"), msg=f"Local path leaked in {path}")

    def test_public_repo_only_keeps_intended_plan_history(self) -> None:
        plan_dirs = sorted(path.name for path in (self.repo_root / "plans").iterdir() if path.is_dir())
        self.assertEqual(plan_dirs, ["shared-plan-handoff"])


class BootstrapRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_setup_py_carries_fallback_metadata_and_console_script(self) -> None:
        setup_text = (self.repo_root / "setup.py").read_text(encoding="utf-8")
        self.assertIn('name="notion-pm-bridge"', setup_text)
        self.assertIn("console_scripts", setup_text)
        self.assertIn("pm=notion_pm_bridge.cli:main", setup_text)

    def test_bootstrap_prefers_python_311_plus_and_validates_pm_entrypoint(self) -> None:
        script = (self.repo_root / "scripts" / "bootstrap_venv.sh").read_text(encoding="utf-8")
        self.assertIn("python3.11", script)
        self.assertIn("SHARED_PLAN_HANDOFF_PYTHON", script)
        self.assertIn("pip install -e .", script)
        self.assertIn('[[ ! -x ./.venv/bin/pm ]]', script)


class DynamicPhaseGroupSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        state_path = Path(self.temp_dir.name) / "state.json"
        config = BridgeConfig(
            api_base_url="https://api.notion.test",
            api_token="token",
            parent_page_id="workspace-root",
            project_identifier="agent-pm",
            state_path=state_path,
            artifacts_dir=state_path.parent / "artifacts",
            plans_dir=state_path.parent / "plans",
            status_map={
                "ready": "Ready",
                "in_progress": "In Progress",
                "blocked": "Blocked",
                "review": "Review",
                "done": "Done",
            },
        )
        self.client = FakeNotionClient()
        self.service = BridgeService(self.client, config)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_task_schema_uses_current_plan_phase_labels(self) -> None:
        spec = PlanSpec(
            project=ProjectSpec(identifier="shipping-demo", name="Shipping Demo", description="Demo"),
            docs=[],
            tasks=[
                TaskSpec(
                    key="phase-alpha",
                    title="Phase Alpha — Foundation",
                    type="Milestone",
                    sequence=1,
                    plan_revision="r001",
                ),
                TaskSpec(
                    key="task-alpha",
                    title="Do foundation work",
                    parent_key="phase-alpha",
                    type="Task",
                    sequence=2,
                    status="Ready",
                    plan_revision="r001",
                ),
                TaskSpec(
                    key="phase-beta",
                    title="Phase Beta — Release",
                    type="Milestone",
                    sequence=3,
                    plan_revision="r001",
                ),
                TaskSpec(
                    key="task-beta",
                    title="Do release work",
                    parent_key="phase-beta",
                    type="Task",
                    sequence=4,
                    status="Ready",
                    plan_revision="r001",
                ),
            ],
        )

        self.service.sync_plan(spec)

        data_source = self.client.retrieve_data_source(self.service._load_state().tasks_data_source_id)
        options = data_source["properties"]["Phase Group"]["select"]["options"]
        option_names = [option["name"] for option in options]

        self.assertEqual(
            option_names[:3],
            ["Phase Alpha — Foundation", "Phase Beta — Release", "No Phase"],
        )


class NotionClientTests(unittest.TestCase):
    def test_update_page_markdown_uses_current_discriminated_payload(self) -> None:
        client = NotionClient("https://api.notion.test", "token")
        with patch.object(client, "_request", return_value={"ok": True}) as request_mock:
            client.update_page_markdown(
                "page-123",
                operation="insert_content",
                content="# Title",
            )

        request_mock.assert_called_once_with(
            "PATCH",
            "/v1/pages/page-123/markdown",
            payload={
                "type": "insert_content",
                "insert_content": {
                    "content": "# Title",
                },
            },
            expected_statuses=(200,),
        )


if __name__ == "__main__":
    unittest.main()
