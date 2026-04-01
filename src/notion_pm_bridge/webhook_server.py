from __future__ import annotations

import hashlib
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .bridge import BridgeService
from .notion_client import NotionClient


class WebhookEventStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_id = payload.get("event_id")
                if event_id:
                    self._seen.add(str(event_id))

    def record(self, event_id: str, payload: dict[str, Any]) -> bool:
        if event_id in self._seen:
            return False
        self._seen.add(event_id)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return True


def run_webhook_server(
    service: BridgeService,
    *,
    host: str = "127.0.0.1",
    port: int = 8090,
    auto_refresh: bool = False,
) -> None:
    store = WebhookEventStore(service.config.state_path.parent / "webhooks" / "events.jsonl")
    secret = service.config.webhook_secret
    verification_token = service.config.webhook_verification_token

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)

            if verification_token and self.headers.get("X-Notion-Verification-Token") != verification_token:
                self._reply(HTTPStatus.FORBIDDEN, {"error": "invalid verification token"})
                return

            signature = self.headers.get("X-Notion-Signature")
            if secret and signature and not NotionClient.verify_webhook_signature(body, signature=signature, secret=secret):
                self._reply(HTTPStatus.FORBIDDEN, {"error": "invalid webhook signature"})
                return

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self._reply(HTTPStatus.BAD_REQUEST, {"error": "body must be valid JSON"})
                return

            event_id = (
                self.headers.get("X-Request-Id")
                or payload.get("id")
                or payload.get("event_id")
                or hashlib.sha256(body).hexdigest()
            )
            recorded = store.record(
                event_id,
                {
                    "event_id": event_id,
                    "received_at": service._utc_now(),
                    "headers": dict(self.headers.items()),
                    "payload": payload,
                },
            )
            refresh_error = None
            if recorded and auto_refresh and service.config.api_token:
                try:
                    service.refresh()
                except Exception as exc:  # pragma: no cover
                    refresh_error = str(exc)

            self._reply(
                HTTPStatus.OK,
                {
                    "event_id": event_id,
                    "recorded": recorded,
                    "auto_refresh": auto_refresh,
                    "refresh_error": refresh_error,
                },
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _reply(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
