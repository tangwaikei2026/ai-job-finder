from __future__ import annotations

import httpx
import pytest

from src import base as raw_base
from src.base import RawCollector
from src.models import CollectionManifest, CollectionResult


class DummyCollector(RawCollector):
    platform = "dummy"

    def collect(self) -> CollectionResult:
        return CollectionResult(
            jobs=[],
            manifest=CollectionManifest(platform=self.platform, name="Dummy"),
        )


def _collector(
    *,
    cities: list[str] | None = None,
    include_unknown_location: bool = False,
    max_retries: int = 3,
    client: httpx.Client | None = None,
) -> DummyCollector:
    return DummyCollector(
        platform_config={"name": "Dummy"},
        collection_config={
            "cities": cities or [],
            "include_unknown_location": include_unknown_location,
            "max_retries": max_retries,
        },
        client=client,
    )


def test_location_in_scope_matches_configured_city() -> None:
    collector = _collector(cities=["上海市"])

    assert collector.location_in_scope("上海-浦东新区") is True


def test_location_in_scope_rejects_unconfigured_city() -> None:
    collector = _collector(cities=["上海"])

    assert collector.location_in_scope("北京") is False


def test_empty_location_is_rejected_by_default() -> None:
    collector = _collector(include_unknown_location=False)

    assert collector.location_in_scope("") is False


def test_empty_location_can_be_included_explicitly() -> None:
    collector = _collector(include_unknown_location=True)

    assert collector.location_in_scope("  ") is True


def test_finish_manifest_sets_finished_at_and_duration(monkeypatch) -> None:
    manifest = CollectionManifest(platform="dummy", name="Dummy")
    monkeypatch.setattr(raw_base.time, "monotonic", lambda: 12.345)

    DummyCollector.finish_manifest(manifest, started_monotonic=10.0)

    assert manifest.finished_at
    assert manifest.duration_seconds == 2.345


def test_close_safely_closes_owned_client() -> None:
    collector = _collector()

    collector.close()
    collector.close()

    assert collector.client.is_closed is True


def test_request_returns_successful_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True}, request=request)
    )

    with httpx.Client(transport=transport) as client:
        collector = _collector(client=client)
        response = collector.request("GET", "https://example.test/jobs")

    assert response.json() == {"ok": True}


def test_request_retries_then_raises_visible_error(monkeypatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, request=request)

    monkeypatch.setattr(raw_base.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(raw_base.random, "uniform", lambda _start, _end: 0.0)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collector = _collector(max_retries=3, client=client)
        with pytest.raises(httpx.HTTPStatusError):
            collector.request("GET", "https://example.test/jobs")

    assert attempts == 3


def test_request_json_raises_for_invalid_json() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="not-json", request=request)
    )

    with httpx.Client(transport=transport) as client:
        collector = _collector(client=client)
        with pytest.raises(ValueError):
            collector.request_json("GET", "https://example.test/jobs")


def test_request_json_rejects_non_object_payload() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=[], request=request)
    )

    with httpx.Client(transport=transport) as client:
        collector = _collector(client=client)
        with pytest.raises(ValueError, match="expected JSON object, got list"):
            collector.request_json("GET", "https://example.test/jobs")
