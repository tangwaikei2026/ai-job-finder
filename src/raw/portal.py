from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


SEARCH_API_MARKER = "/api/v1/search/job/posts"


@dataclass
class PortalBootstrap:
    request_url: str
    request_body: dict[str, Any]
    filter_data: dict[str, Any]


def bootstrap_portal(
    page: Any,
    list_url: str,
    *,
    filter_marker: str = "",
    attempts: int = 2,
    wait_ms: int = 9000,
) -> PortalBootstrap:
    captured: dict[str, Any] = {}
    filter_data: dict[str, Any] = {}

    def on_request(request: Any) -> None:
        if SEARCH_API_MARKER not in request.url or request.method != "POST":
            return
        try:
            body = json.loads(request.post_data or "{}")
        except json.JSONDecodeError:
            return
        captured["url"] = request.url
        captured["body"] = body

    def on_response(response: Any) -> None:
        if not filter_marker or filter_marker not in response.url or response.status != 200:
            return
        try:
            payload = response.json()
            data = payload.get("data")
            if isinstance(data, dict):
                filter_data.update(data)
        except Exception:
            return

    page.on("request", on_request)
    page.on("response", on_response)
    try:
        for _ in range(attempts):
            try:
                page.goto(list_url, wait_until="commit", timeout=30000)
            except Exception:
                pass
            waited_ms = 0
            while waited_ms < wait_ms:
                if captured and (not filter_marker or filter_data):
                    break
                page.wait_for_timeout(250)
                waited_ms += 250
            if captured and (not filter_marker or filter_data):
                break
    finally:
        page.remove_listener("request", on_request)
        page.remove_listener("response", on_response)

    if not captured:
        raise RuntimeError(f"portal list API was not observed while loading {list_url}")
    if filter_marker and not filter_data:
        raise RuntimeError(f"portal filters API was not observed while loading {list_url}")
    return PortalBootstrap(
        request_url=str(captured["url"]),
        request_body=dict(captured["body"]),
        filter_data=filter_data,
    )


def fetch_portal_page(
    page: Any,
    bootstrap: PortalBootstrap,
    *,
    offset: int,
    limit: int,
    body_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = dict(bootstrap.request_body)
    body["offset"] = offset
    body["limit"] = limit
    if body_updates:
        body.update(body_updates)

    result = page.evaluate(
        """
        async ({url, body}) => {
          const response = await fetch(url, {
            method: 'POST',
            credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
          });
          return {status: response.status, text: await response.text()};
        }
        """,
        {"url": bootstrap.request_url, "body": body},
    )
    if int(result["status"]) >= 400:
        raise RuntimeError(f"portal API returned HTTP {result['status']}")
    payload = json.loads(result["text"])
    if payload.get("code") != 0:
        raise RuntimeError(
            f"portal API returned code={payload.get('code')}: "
            f"{payload.get('message') or payload.get('error') or ''}"
        )
    return payload
