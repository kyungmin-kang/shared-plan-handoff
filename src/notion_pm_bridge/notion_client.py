from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .exceptions import APIError


def rich_text(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    return [{"type": "text", "text": {"content": text}}]


class NotionClient:
    def __init__(
        self,
        api_base_url: str,
        api_token: str,
        *,
        notion_version: str = "2025-09-03",
        timeout: float = 30.0,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.api_token = api_token
        self.notion_version = notion_version
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Notion-Version": self.notion_version,
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        expected_statuses: Iterable[int] = (200,),
    ) -> Any:
        query = ""
        if params:
            query = f"?{urlencode(params, doseq=True)}"
        url = f"{self.api_base_url}{path}{query}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, method=method, headers=self._headers())
        try:
            with urlopen(request, timeout=self.timeout) as response:
                content = response.read()
                if response.status not in tuple(expected_statuses):
                    raise APIError(f"Unexpected status {response.status} for {method} {path}", status=response.status)
                if not content:
                    return None
                return json.loads(content.decode("utf-8"))
        except HTTPError as exc:
            payload_text = exc.read().decode("utf-8", errors="replace")
            try:
                parsed_payload = json.loads(payload_text)
            except json.JSONDecodeError:
                parsed_payload = payload_text
            message = (
                parsed_payload.get("message")
                if isinstance(parsed_payload, dict) and parsed_payload.get("message")
                else f"Notion API error for {method} {path}"
            )
            raise APIError(message, status=exc.code, payload=parsed_payload) from exc
        except URLError as exc:
            raise APIError(f"Could not reach Notion at {self.api_base_url}: {exc.reason}") from exc

    def _paginate_post(self, path: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        body = dict(payload or {})
        while True:
            response = self._request("POST", path, payload=body, expected_statuses=(200,))
            results.extend(response.get("results", []))
            if not response.get("has_more") or not response.get("next_cursor"):
                break
            body["start_cursor"] = response["next_cursor"]
        return results

    def search(self, *, query: str, filter_type: str | None = None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"query": query, "page_size": 100}
        if filter_type:
            payload["filter"] = {"property": "object", "value": filter_type}
        return self._paginate_post("/v1/search", payload)

    def search_exact_title(self, title: str, *, filter_type: str | None = None) -> list[dict[str, Any]]:
        matches = []
        for item in self.search(query=title, filter_type=filter_type):
            item_title = extract_title(item)
            if item_title == title:
                matches.append(item)
        return matches

    def retrieve_page(self, page_id: str, *, filter_properties: list[str] | None = None) -> dict[str, Any]:
        params: dict[str, Any] | None = None
        if filter_properties:
            params = {"filter_properties": filter_properties}
        return self._request("GET", f"/v1/pages/{page_id}", params=params, expected_statuses=(200,))

    def update_page(
        self,
        page_id: str,
        *,
        properties: dict[str, Any] | None = None,
        archived: bool | None = None,
        erase_content: bool | None = None,
        icon_emoji: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if properties:
            payload["properties"] = properties
        if archived is not None:
            payload["archived"] = archived
        if erase_content is not None:
            payload["erase_content"] = erase_content
        if icon_emoji:
            payload["icon"] = {"type": "emoji", "emoji": icon_emoji}
        return self._request("PATCH", f"/v1/pages/{page_id}", payload=payload, expected_statuses=(200,))

    def create_page(
        self,
        *,
        parent_page_id: str | None = None,
        parent_data_source_id: str | None = None,
        title: str | None = None,
        properties: dict[str, Any] | None = None,
        markdown: str | None = None,
        icon_emoji: str | None = None,
    ) -> dict[str, Any]:
        if bool(parent_page_id) == bool(parent_data_source_id):
            raise APIError("Exactly one of parent_page_id or parent_data_source_id is required")
        if parent_page_id:
            parent = {"type": "page_id", "page_id": parent_page_id}
            payload_properties = dict(properties or {})
            if title:
                payload_properties.setdefault("title", {"title": rich_text(title)})
        else:
            parent = {"type": "data_source_id", "data_source_id": parent_data_source_id}
            payload_properties = dict(properties or {})
        payload: dict[str, Any] = {"parent": parent, "properties": payload_properties}
        if markdown:
            payload["markdown"] = markdown
        if icon_emoji:
            payload["icon"] = {"type": "emoji", "emoji": icon_emoji}
        return self._request("POST", "/v1/pages", payload=payload, expected_statuses=(200,))

    def retrieve_page_markdown(self, page_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/pages/{page_id}/markdown", expected_statuses=(200,))

    def update_page_markdown(
        self,
        page_id: str,
        *,
        operation: str,
        content: str,
        content_range: str | None = None,
        after: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": operation}
        command_payload: dict[str, Any] = {"content": content}
        if content_range:
            command_payload["content_range"] = content_range
        if after:
            command_payload["after"] = after
        payload[operation] = command_payload
        return self._request("PATCH", f"/v1/pages/{page_id}/markdown", payload=payload, expected_statuses=(200,))

    def retrieve_database(self, database_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/databases/{database_id}", expected_statuses=(200,))

    def create_database(
        self,
        *,
        parent_page_id: str,
        title: str,
        data_source_title: str,
        properties: dict[str, Any],
        is_inline: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": rich_text(title),
            "is_inline": is_inline,
            "initial_data_source": {
                "title": rich_text(data_source_title),
                "properties": properties,
            },
        }
        return self._request("POST", "/v1/databases", payload=payload, expected_statuses=(200,))

    def retrieve_data_source(self, data_source_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/data_sources/{data_source_id}", expected_statuses=(200,))

    def update_data_source(
        self,
        data_source_id: str,
        *,
        title: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = rich_text(title)
        if properties:
            payload["properties"] = properties
        return self._request("PATCH", f"/v1/data_sources/{data_source_id}", payload=payload, expected_statuses=(200,))

    def query_data_source(
        self,
        data_source_id: str,
        *,
        filter_payload: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"page_size": 100}
        if filter_payload:
            payload["filter"] = filter_payload
        if sorts:
            payload["sorts"] = sorts
        return self._paginate_post(f"/v1/data_sources/{data_source_id}/query", payload)

    @staticmethod
    def verify_webhook_signature(body: bytes, *, signature: str, secret: str) -> bool:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)


def extract_title(entity: dict[str, Any]) -> str:
    title = entity.get("title")
    if isinstance(title, list):
        return plain_text(title)
    properties = entity.get("properties", {})
    for value in properties.values():
        if value.get("type") == "title":
            return plain_text(value.get("title", []))
    return ""


def plain_text(value: list[dict[str, Any]] | None) -> str:
    if not value:
        return ""
    return "".join(item.get("plain_text") or item.get("text", {}).get("content", "") for item in value)
