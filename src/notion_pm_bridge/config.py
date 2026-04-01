from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


def _parse_status_map(raw: str | None) -> dict[str, str]:
    defaults = {
        "ready": "Ready",
        "in_progress": "In Progress",
        "blocked": "Blocked",
        "review": "Review",
        "done": "Done",
    }
    if not raw:
        return defaults
    parsed = defaults.copy()
    for item in raw.split(","):
        if not item.strip():
            continue
        key, _, value = item.partition(":")
        if key and value:
            parsed[key.strip()] = value.strip()
    return parsed


def _normalize_notion_page_id(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.strip()
    matches = re.findall(r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}|[0-9a-fA-F]{32}", value)
    if not matches:
        return value
    page_id = matches[-1].replace("-", "").lower()
    if len(page_id) != 32:
        return value
    return (
        f"{page_id[0:8]}-"
        f"{page_id[8:12]}-"
        f"{page_id[12:16]}-"
        f"{page_id[16:20]}-"
        f"{page_id[20:32]}"
    )


@dataclass(slots=True)
class BridgeConfig:
    api_base_url: str
    api_token: str
    parent_page_id: str
    project_identifier: str
    notion_transport: str = "mcp"
    rest_fallback_enabled: bool = True
    notion_version: str = "2025-09-03"
    author: str = "codex"
    state_path: Path = Path(".pm-bridge/state.json")
    artifacts_dir: Path = Path(".pm-bridge/artifacts")
    plans_dir: Path = Path("plans")
    webhook_secret: str | None = None
    webhook_verification_token: str | None = None
    status_map: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        state_path = Path(os.environ.get("PM_BRIDGE_STATE_PATH", ".pm-bridge/state.json"))
        artifacts_dir = state_path.parent / "artifacts"
        raw_transport = os.environ.get("NOTION_TRANSPORT", "mcp").strip().lower() or "mcp"
        notion_transport = raw_transport if raw_transport in {"mcp", "rest", "auto"} else "mcp"
        raw_fallback = os.environ.get("NOTION_REST_FALLBACK", "1").strip().lower()
        rest_fallback_enabled = raw_fallback not in {"0", "false", "no", "off"}
        return cls(
            api_base_url=os.environ.get("NOTION_API_BASE_URL", "https://api.notion.com").rstrip("/"),
            api_token=os.environ.get("NOTION_API_TOKEN") or os.environ.get("NOTION_TOKEN", ""),
            parent_page_id=_normalize_notion_page_id(os.environ.get("NOTION_PARENT_PAGE_ID", "")),
            project_identifier=os.environ.get("NOTION_PROJECT_IDENTIFIER", "agent-pm"),
            notion_transport=notion_transport,
            rest_fallback_enabled=rest_fallback_enabled,
            notion_version=os.environ.get("NOTION_VERSION", "2025-09-03"),
            author=os.environ.get("PM_BRIDGE_AUTHOR", "codex"),
            state_path=state_path,
            artifacts_dir=artifacts_dir,
            plans_dir=Path(os.environ.get("PM_BRIDGE_PLANS_DIR", "plans")),
            webhook_secret=os.environ.get("NOTION_WEBHOOK_SECRET") or os.environ.get("PM_BRIDGE_WEBHOOK_SECRET") or None,
            webhook_verification_token=os.environ.get("NOTION_WEBHOOK_VERIFICATION_TOKEN") or None,
            status_map=_parse_status_map(os.environ.get("PM_BRIDGE_STATUS_MAP")),
        )
