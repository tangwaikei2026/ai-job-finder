from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.collectors.bytedance import ByteDanceRawCollector
from src.portal import PortalBootstrap


@dataclass
class _FakePage:
    pass


class _FakeBrowserContext:
    def __init__(self) -> None:
        self.page = _FakePage()

    def new_page(self) -> _FakePage:
        return self.page

    def close(self) -> None:
        pass


class _FakeBrowser:
    def new_context(self, **_kwargs: Any) -> _FakeBrowserContext:
        return _FakeBrowserContext()

    def close(self) -> None:
        pass


class _FakeChromium:
    def launch(self, **_kwargs: Any) -> _FakeBrowser:
        return _FakeBrowser()


class _FakePlaywright:
    chromium = _FakeChromium()


class _FakePlaywrightManager:
    def __enter__(self) -> _FakePlaywright:
        return _FakePlaywright()

    def __exit__(self, *_args: Any) -> None:
        pass


def _job(job_id: str, city: str) -> dict[str, Any]:
    return {
        "id": job_id,
        "title": f"岗位 {job_id}",
        "city_info": {"name": city},
    }


def _records(prefix: str, start: int, size: int, city: str) -> list[dict[str, Any]]:
    return [_job(f"{prefix}-{index}", city) for index in range(start, start + size)]


def _collect(
    monkeypatch,
    *,
    cities: list[str],
    responses: dict[str, dict[int, dict[str, Any] | Exception]],
    page_size: int = 100,
):
    city_codes = {city: f"code-{index}" for index, city in enumerate(cities)}
    filter_data = {
        "city_list": [
            {"name": city, "code": city_codes[city]}
            for city in cities
        ]
    }
    bootstrap = PortalBootstrap(
        request_url="https://example.test/api/v1/search/job/posts",
        request_body={},
        filter_data=filter_data,
    )

    def fake_fetch(
        _page,
        _bootstrap,
        *,
        offset: int,
        limit: int,
        body_updates: dict[str, Any],
    ) -> dict[str, Any]:
        assert limit == page_size
        city_code = body_updates["location_code_list"][0]
        response = responses[city_code][offset]
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(
        "playwright.sync_api.sync_playwright",
        lambda: _FakePlaywrightManager(),
    )
    monkeypatch.setattr(
        "src.collectors.bytedance.bootstrap_portal",
        lambda *_args, **_kwargs: bootstrap,
    )
    monkeypatch.setattr("src.collectors.bytedance.fetch_portal_page", fake_fetch)

    collector = ByteDanceRawCollector(
        {
            "name": "字节跳动",
            "list_url": "https://example.test/jobs",
            "detail_url": "https://example.test/jobs/{job_id}",
            "page_size": page_size,
        },
        {
            "cities": cities,
            "include_unknown_location": False,
            "max_retries": 1,
        },
    )
    try:
        return collector.collect()
    finally:
        collector.close()


def _response(count: int, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"code": 0, "data": {"count": count, "job_post_list": records}}


def test_bytedance_observes_exact_reported_total(monkeypatch) -> None:
    result = _collect(
        monkeypatch,
        cities=["北京"],
        responses={
            "code-0": {
                0: _response(200, _records("bj", 0, 100, "北京")),
                100: _response(200, _records("bj", 100, 100, "北京")),
            }
        },
    )

    evidence = result.manifest.metadata["cities"][0]
    assert result.manifest.status == "success"
    assert result.manifest.complete is True
    assert evidence["termination_reason"] == "reported_total_reached"
    assert evidence["records_fetched"] == 200
    assert evidence["pages_fetched"] == 2
    assert evidence["last_page_size"] == 100
    assert evidence["last_offset"] == 100


def test_bytedance_observes_partial_final_page(monkeypatch) -> None:
    result = _collect(
        monkeypatch,
        cities=["北京"],
        responses={
            "code-0": {
                0: _response(170, _records("bj", 0, 100, "北京")),
                100: _response(170, _records("bj", 100, 70, "北京")),
            }
        },
    )

    evidence = result.manifest.metadata["cities"][0]
    assert result.manifest.status == "success"
    assert result.manifest.complete is True
    assert result.manifest.records_fetched == 170
    assert evidence["records_fetched"] == 170
    assert evidence["last_page_size"] == 70
    assert evidence["termination_reason"] == "reported_total_reached"


def test_bytedance_observes_empty_page_before_reported_total(monkeypatch) -> None:
    pages = {
        offset: _response(
            5572,
            _records("bj", offset, 100 if offset < 5500 else 70, "北京"),
        )
        for offset in range(0, 5570, 100)
    }
    pages[5570] = _response(5572, [])

    result = _collect(
        monkeypatch,
        cities=["北京"],
        responses={"code-0": pages},
    )

    evidence = result.manifest.metadata["cities"][0]
    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert result.manifest.source_total == 5572
    assert result.manifest.records_fetched == 5570
    assert result.manifest.jobs_mapped == 5570
    assert result.manifest.jobs_in_scope == 5570
    assert evidence["reported_total_first"] == 5572
    assert evidence["reported_total_last_observed"] == 5572
    assert evidence["records_fetched"] == 5570
    assert evidence["pages_fetched"] == 56
    assert evidence["last_page_size"] == 70
    assert evidence["last_offset"] == 5570
    assert evidence["termination_reason"] == "empty_page_before_reported_total"


def test_bytedance_observes_downward_reported_total_drift(monkeypatch) -> None:
    pages = {
        0: _response(5572, _records("bj", 0, 100, "北京")),
        **{
            offset: _response(
                5570,
                _records("bj", offset, 100 if offset < 5500 else 70, "北京"),
            )
            for offset in range(100, 5570, 100)
        },
        5570: _response(5570, []),
    }

    result = _collect(
        monkeypatch,
        cities=["北京"],
        responses={"code-0": pages},
    )

    evidence = result.manifest.metadata["cities"][0]
    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert evidence["reported_total_first"] == 5572
    assert evidence["reported_total_last_observed"] == 5570
    assert evidence["reported_total_min"] == 5570
    assert evidence["reported_total_max"] == 5572
    assert evidence["termination_reason"] == "empty_page_before_reported_total"


def test_bytedance_observes_upward_reported_total_drift_without_behavior_change(
    monkeypatch,
) -> None:
    result = _collect(
        monkeypatch,
        cities=["北京"],
        responses={
            "code-0": {
                0: _response(100, _records("bj", 0, 50, "北京")),
                50: _response(101, _records("bj", 50, 50, "北京")),
            }
        },
        page_size=50,
    )

    evidence = result.manifest.metadata["cities"][0]
    assert result.manifest.status == "success"
    assert result.manifest.complete is True
    assert result.manifest.source_total == 100
    assert result.manifest.records_fetched == 100
    assert evidence["reported_total_first"] == 100
    assert evidence["reported_total_last_observed"] == 101
    assert evidence["reported_total_min"] == 100
    assert evidence["reported_total_max"] == 101


def test_bytedance_keeps_per_city_evidence_isolated(monkeypatch) -> None:
    result = _collect(
        monkeypatch,
        cities=["北京", "上海"],
        responses={
            "code-0": {0: _response(1, [_job("bj-1", "北京")])},
            "code-1": {0: _response(2, [_job("sh-1", "上海"), _job("sh-2", "上海")])},
        },
    )

    beijing, shanghai = result.manifest.metadata["cities"]
    assert beijing["city"] == "北京"
    assert beijing["reported_total_first"] == 1
    assert beijing["records_fetched"] == 1
    assert shanghai["city"] == "上海"
    assert shanghai["reported_total_first"] == 2
    assert shanghai["records_fetched"] == 2
    assert result.manifest.source_total == 3
    assert result.manifest.records_fetched == 3
    assert result.manifest.jobs_mapped == 3
    assert result.manifest.jobs_in_scope == 3
    assert result.manifest.status == "success"
    assert result.manifest.complete is True


def test_bytedance_observes_request_error_termination(monkeypatch) -> None:
    result = _collect(
        monkeypatch,
        cities=["北京"],
        responses={"code-0": {0: RuntimeError("offline request failure")}},
    )

    evidence = result.manifest.metadata["cities"][0]
    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert evidence["records_fetched"] == 0
    assert evidence["last_offset"] == 0
    assert evidence["termination_reason"] == "request_error"


def test_bytedance_observes_repeated_page_termination(monkeypatch) -> None:
    repeated = [_job("bj-1", "北京"), _job("bj-2", "北京")]
    result = _collect(
        monkeypatch,
        cities=["北京"],
        responses={
            "code-0": {
                0: _response(3, repeated),
                2: _response(3, repeated),
            }
        },
        page_size=2,
    )

    evidence = result.manifest.metadata["cities"][0]
    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert result.manifest.records_fetched == 2
    assert evidence["records_fetched"] == 2
    assert evidence["last_offset"] == 2
    assert evidence["termination_reason"] == "repeated_page"
