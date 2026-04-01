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


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()

        parsed[key] = value
    return parsed


def _merged_env() -> dict[str, str]:
    env_path = Path(os.environ.get("PM_BRIDGE_ENV_FILE", ".env"))
    merged = _parse_dotenv(env_path)
    merged.update(os.environ)
    return merged


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
        env = _merged_env()
        state_path = Path(env.get("PM_BRIDGE_STATE_PATH", ".pm-bridge/state.json"))
        artifacts_dir = state_path.parent / "artifacts"
        raw_transport = env.get("NOTION_TRANSPORT", "mcp").strip().lower() or "mcp"
        notion_transport = raw_transport if raw_transport in {"mcp", "rest", "auto"} else "mcp"
        raw_fallback = env.get("NOTION_REST_FALLBACK", "1").strip().lower()
        rest_fallback_enabled = raw_fallback not in {"0", "false", "no", "off"}
        return cls(
            api_base_url=env.get("NOTION_API_BASE_URL", "https://api.notion.com").rstrip("/"),
            api_token=env.get("NOTION_API_TOKEN") or env.get("NOTION_TOKEN", ""),
            parent_page_id=_normalize_notion_page_id(env.get("NOTION_PARENT_PAGE_ID", "")),
            project_identifier=env.get("NOTION_PROJECT_IDENTIFIER", "agent-pm"),
            notion_transport=notion_transport,
            rest_fallback_enabled=rest_fallback_enabled,
            notion_version=env.get("NOTION_VERSION", "2025-09-03"),
            author=env.get("PM_BRIDGE_AUTHOR", "codex"),
            state_path=state_path,
            artifacts_dir=artifacts_dir,
            plans_dir=Path(env.get("PM_BRIDGE_PLANS_DIR", "plans")),
            webhook_secret=env.get("NOTION_WEBHOOK_SECRET") or env.get("PM_BRIDGE_WEBHOOK_SECRET") or None,
            webhook_verification_token=env.get("NOTION_WEBHOOK_VERIFICATION_TOKEN") or None,
            status_map=_parse_status_map(env.get("PM_BRIDGE_STATUS_MAP")),
        )
