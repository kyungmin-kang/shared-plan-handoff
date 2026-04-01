from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .bridge import BridgeService
from .config import BridgeConfig
from .coordinator import CodexNotionWorkflowCoordinator
from .exceptions import BridgeError
from .notion_client import NotionClient
from .spec_io import load_plan_spec
from .webhook_server import run_webhook_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pm", description="Notion PM bridge debug/admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="Ensure the Notion project page, task database, and doc pages exist")
    bootstrap.add_argument("spec", nargs="?", help="Optional path to a PlanSpec JSON file")

    sync_plan = subparsers.add_parser("sync-plan", help="Create or update Notion task pages from a PlanSpec")
    sync_plan.add_argument("spec", help="Path to a PlanSpec JSON file")

    register_plan = subparsers.add_parser("register-plan", help="Copy an approved Markdown plan into the canonical repo artifact layout")
    register_plan.add_argument("project_name", help="Human-readable project name")
    register_plan.add_argument("plan_path", help="Path to the approved Markdown plan")
    register_plan.add_argument("--tasks-path", help="Optional path to a companion approved task-input Markdown file")

    rescue = subparsers.add_parser("rescue", help="Create a rescue snapshot and recovery-plan draft for an in-flight project")
    rescue.add_argument("project_name", help="Human-readable project name")
    rescue.add_argument("--context-file", help="Optional path to extra rescue context markdown")
    rescue.add_argument("--goal", help="Optional explicit rescue goal statement")

    deepen_rescue = subparsers.add_parser("deepen-rescue", help="Write a detailed rescue scan and refresh the rescue artifacts")
    deepen_rescue.add_argument("project_ref", help="Project name or slug")
    deepen_rescue.add_argument("--scan-file", required=True, help="Path to the detailed rescue scan markdown")
    deepen_rescue.add_argument("--goal", required=True, help="Explicit project goal statement")
    deepen_rescue.add_argument("--current-reality-file", help="Optional path to markdown for the executive-summary current reality section")
    deepen_rescue.add_argument("--completion-file", help="Optional path to markdown describing what completion requires")
    deepen_rescue.add_argument("--maintenance-file", help="Optional path to markdown describing maintenance requirements")
    deepen_rescue.add_argument("--publish-to-notion", action="store_true", help="Also sync the rescue notebook docs to Notion")

    publish_rescue = subparsers.add_parser("publish-rescue-docs", help="Sync rescue docs to Notion without creating the execution database")
    publish_rescue.add_argument("project_ref", help="Project name or slug")

    decompose = subparsers.add_parser("decompose", help="Generate task-graph.json and handoff.json from the approved plan")
    decompose.add_argument("project_ref", help="Project name or slug")

    review = subparsers.add_parser("review-decomposition", help="Run reviewer checks and write decomposition-review.md")
    review.add_argument("project_ref", help="Project name or slug")

    build_handoff = subparsers.add_parser("build-from-handoff", help="Create the Notion execution workspace from a reviewed handoff")
    build_handoff.add_argument("project_ref", help="Project name or slug")

    reconcile_handoff = subparsers.add_parser("reconcile-from-handoff", help="Reconcile the Notion execution workspace from the latest reviewed handoff")
    reconcile_handoff.add_argument("project_ref", help="Project name or slug")

    subparsers.add_parser("refresh", help="Refresh the local cache from Notion")
    subparsers.add_parser("next", help="Show tasks that are ready to run")

    claim = subparsers.add_parser("claim", help="Claim a task for an agent")
    claim.add_argument("task_ref", help="Task key or Notion page ID")
    claim.add_argument("--owner", help="Agent owner label")

    start = subparsers.add_parser("start", help="Move a task to in progress")
    start.add_argument("task_ref", help="Task key or Notion page ID")
    start.add_argument("--owner", help="Agent owner label")
    start.add_argument("--branch", help="Branch reference to attach")

    block = subparsers.add_parser("block", help="Mark a task as blocked on another task")
    block.add_argument("task_ref", help="Task key or Notion page ID")
    block.add_argument("--on", dest="dependency_ref", required=True, help="Dependency task key or Notion page ID")
    block.add_argument("--note", help="Optional blocker note")

    finish = subparsers.add_parser("finish", help="Mark a task as done")
    finish.add_argument("task_ref", help="Task key or Notion page ID")
    finish.add_argument("--summary", help="Completion summary")
    finish.add_argument("--branch", help="Branch reference to attach")
    finish.add_argument("--pr-url", help="Pull request URL")
    finish.add_argument("--commit-sha", help="Commit SHA")

    dashboard = subparsers.add_parser("dashboard", help="Render a markdown dashboard artifact and update the Dashboard Snapshot page")
    dashboard.add_argument("--output", help="Optional output path for the markdown file")

    webhooks = subparsers.add_parser("serve-webhooks", help="Run the webhook receiver")
    webhooks.add_argument("--host", default="127.0.0.1", help="Host to bind")
    webhooks.add_argument("--port", type=int, default=8090, help="Port to bind")
    webhooks.add_argument("--auto-refresh", action="store_true", help="Refresh bridge state after accepted webhooks")

    return parser


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _require_api_token(config: BridgeConfig) -> None:
    if not config.api_token:
        raise BridgeError("NOTION_API_TOKEN is required for this command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = BridgeConfig.from_env()
    client = NotionClient(config.api_base_url, config.api_token, notion_version=config.notion_version)
    service = BridgeService(client, config)
    coordinator = CodexNotionWorkflowCoordinator(service)

    try:
        if args.command == "bootstrap":
            _require_api_token(config)
            spec = load_plan_spec(args.spec) if args.spec else None
            _print(service.bootstrap(spec))
            return 0
        if args.command == "sync-plan":
            _require_api_token(config)
            _print(service.sync_plan(load_plan_spec(args.spec)))
            return 0
        if args.command == "register-plan":
            _print(coordinator.register_approved_plan(args.project_name, args.plan_path, task_plan_path=args.tasks_path))
            return 0
        if args.command == "rescue":
            context = None
            if args.context_file:
                with open(args.context_file, "r", encoding="utf-8") as handle:
                    context = handle.read()
            _print(coordinator.rescue_project(args.project_name, context_markdown=context, goal_statement=args.goal))
            return 0
        if args.command == "deepen-rescue":
            with open(args.scan_file, "r", encoding="utf-8") as handle:
                detailed_scan = handle.read()
            completion = None
            current_reality = None
            if args.current_reality_file:
                with open(args.current_reality_file, "r", encoding="utf-8") as handle:
                    current_reality = handle.read()
            if args.completion_file:
                with open(args.completion_file, "r", encoding="utf-8") as handle:
                    completion = handle.read()
            maintenance = None
            if args.maintenance_file:
                with open(args.maintenance_file, "r", encoding="utf-8") as handle:
                    maintenance = handle.read()
            if args.publish_to_notion:
                _require_api_token(config)
            _print(
                coordinator.deepen_rescue_scan(
                    args.project_ref,
                    detailed_scan_markdown=detailed_scan,
                    goal_statement=args.goal,
                    current_reality_summary=current_reality,
                    completion_definition=completion,
                    maintenance_requirements=maintenance,
                    publish_to_notion=args.publish_to_notion,
                )
            )
            return 0
        if args.command == "publish-rescue-docs":
            _require_api_token(config)
            _print(coordinator.publish_rescue_docs(args.project_ref))
            return 0
        if args.command == "decompose":
            _print(coordinator.decompose_approved_plan(args.project_ref))
            return 0
        if args.command == "review-decomposition":
            _print(coordinator.review_decomposition(args.project_ref))
            return 0
        if args.command == "build-from-handoff":
            _require_api_token(config)
            _print(coordinator.build_workspace_from_handoff(args.project_ref))
            return 0
        if args.command == "reconcile-from-handoff":
            _require_api_token(config)
            _print(coordinator.reconcile_workspace_from_handoff(args.project_ref))
            return 0
        if args.command == "refresh":
            _require_api_token(config)
            _print(service.refresh())
            return 0
        if args.command == "next":
            _require_api_token(config)
            _print(service.next_tasks())
            return 0
        if args.command == "claim":
            _require_api_token(config)
            _print(service.claim(args.task_ref, owner=args.owner))
            return 0
        if args.command == "start":
            _require_api_token(config)
            _print(service.start(args.task_ref, owner=args.owner, branch=args.branch))
            return 0
        if args.command == "block":
            _require_api_token(config)
            _print(service.block(args.task_ref, dependency_ref=args.dependency_ref, note=args.note))
            return 0
        if args.command == "finish":
            _require_api_token(config)
            _print(
                service.finish(
                    args.task_ref,
                    summary=args.summary,
                    branch=args.branch,
                    pr_url=args.pr_url,
                    commit_sha=args.commit_sha,
                )
            )
            return 0
        if args.command == "dashboard":
            _require_api_token(config)
            _print(service.dashboard(output_path=args.output))
            return 0
        if args.command == "serve-webhooks":
            print(
                json.dumps(
                    {
                        "host": args.host,
                        "port": args.port,
                        "auto_refresh": args.auto_refresh,
                        "events_path": str(config.state_path.parent / "webhooks" / "events.jsonl"),
                    },
                    indent=2,
                )
            )
            run_webhook_server(service, host=args.host, port=args.port, auto_refresh=args.auto_refresh)
            return 0
    except BridgeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
