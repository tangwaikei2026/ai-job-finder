from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from src.collectors.didi import DidiRawCollector


COLLECTION_CONFIG = {
    "cities": ["北京"],
    "include_unknown_location": False,
    "max_retries": 1,
}


def _items(start: int, end: int, *, location: str = "成都") -> list[dict[str, Any]]:
    return [
        {
            "jdId": str(job_id),
            "jdNo": f"job-{job_id}",
            "jobName": f"Job {job_id}",
            "workArea": location,
        }
        for job_id in range(start, end + 1)
    ]


def _payload(total: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"meta": {"code": 0}, "data": {"total": total, "items": items}}


def _collect(
    pages: dict[int, dict[str, Any]],
    *,
    reread_page1: dict[str, Any] | None = None,
    detail_handler: Callable[[httpx.Request], httpx.Response] | None = None,
    max_pages: int = 10,
) -> tuple[Any, list[int]]:
    requested_pages: list[int] = []
    page1_reads = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal page1_reads
        if request.url.path == "/social/list/1":
            return httpx.Response(200, text="<html></html>")
        if request.url.path == "/front/list":
            page = int(request.url.params["page"])
            requested_pages.append(page)
            if page == 1:
                page1_reads += 1
                if page1_reads > 1 and reread_page1 is not None:
                    return httpx.Response(200, json=reread_page1)
            response = pages.get(page)
            if isinstance(response, dict) and "http_status" in response:
                return httpx.Response(int(response["http_status"]))
            assert response is not None, f"unexpected list page {page}"
            return httpx.Response(200, json=response)
        if detail_handler is not None:
            return detail_handler(request)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collector = DidiRawCollector(
            {
                "name": "滴滴",
                "list_url": "https://example.test/social/list/1",
                "list_api": "https://example.test/front/list",
                "detail_api": "https://example.test/front/view/{job_id}",
                "detail_url": "https://example.test/social/p/{job_id}",
                "page_size": 16,
                "detail_workers": 1,
                "max_pages": max_pages,
            },
            COLLECTION_CONFIG,
            client,
        )
        return collector.collect(), requested_pages


def test_didi_stable_observation_is_complete_under_available_source_contract():
    page1 = _payload(32, _items(1, 16))
    result, requested_pages = _collect(
        {
            1: page1,
            2: _payload(32, _items(17, 32)),
            3: _payload(32, []),
        }
    )

    manifest = result.manifest
    metadata = manifest.metadata
    assert requested_pages == [1, 2, 3, 1]
    assert manifest.status == "success"
    assert manifest.complete is True
    assert manifest.stopped_by == "source_total_reached"
    assert metadata["list_complete"] is True
    assert metadata["completeness_reasons"] == []
    assert metadata["first_total"] == metadata["last_total"] == 32
    assert metadata["min_total"] == metadata["max_total"] == 32
    assert metadata["records_fetched"] == 32
    assert metadata["unique_job_ids"] == 32
    assert metadata["duplicate_records"] == 0
    assert metadata["page1_changed"] is False
    assert metadata["terminal_page"] == 3
    assert metadata["terminal_page_count"] == 0
    assert metadata["terminal_condition"] == "next_page_empty"
    assert metadata["terminal_condition_proven"] is True
    assert metadata["source_total_semantics"] == "final_valid_api_reported_total"
    assert metadata["stable_snapshot_mechanism"] is False
    assert metadata["completeness_scope"] == (
        "observation_complete_under_available_source_contract"
    )
    assert len(metadata["page_ledger"]) == 3
    assert "job-1" not in str(metadata["page_ledger"])


def test_didi_total_change_is_partial_even_when_rows_look_sufficient():
    page1 = _payload(32, _items(1, 16))
    result, _ = _collect(
        {
            1: page1,
            2: _payload(33, _items(17, 32)),
            3: _payload(33, []),
        },
        reread_page1=_payload(33, _items(1, 16)),
    )

    manifest = result.manifest
    assert manifest.source_total == 33
    assert manifest.status == "partial"
    assert manifest.complete is False
    assert manifest.stopped_by == "dynamic_total"
    assert manifest.metadata["total_changed"] is True
    assert manifest.metadata["completeness_reasons"] == [
        "dynamic_total",
        "unique_deficit",
    ]


def test_didi_reason_precedence_retains_every_observed_failure():
    page1 = _payload(32, _items(1, 16))
    result, _ = _collect(
        {
            1: page1,
            2: _payload(33, _items(16, 31)),
            3: _payload(33, []),
        },
        reread_page1=_payload(33, _items(1, 16)),
    )

    assert result.manifest.stopped_by == "dynamic_total"
    assert result.manifest.metadata["completeness_reasons"] == [
        "dynamic_total",
        "duplicate_pagination",
        "unique_deficit",
    ]


def test_didi_page1_change_is_partial_even_when_total_is_stable():
    page1 = _payload(32, _items(1, 16))
    result, _ = _collect(
        {
            1: page1,
            2: _payload(32, _items(17, 32)),
            3: _payload(32, []),
        },
        reread_page1=_payload(32, _items(2, 17)),
    )

    assert result.manifest.stopped_by == "dynamic_page1"
    assert result.manifest.metadata["page1_changed"] is True
    assert result.manifest.metadata["completeness_reasons"] == ["dynamic_page1"]
    assert result.manifest.metadata["start_page1_ids_hash"] != (
        result.manifest.metadata["end_page1_ids_hash"]
    )


def test_didi_duplicate_rows_cannot_create_false_success():
    page1 = _payload(32, _items(1, 16))
    result, _ = _collect(
        {
            1: page1,
            2: _payload(32, _items(16, 31)),
            3: _payload(32, []),
        }
    )

    metadata = result.manifest.metadata
    assert metadata["records_fetched"] == 32
    assert metadata["unique_job_ids"] == 31
    assert metadata["duplicate_records"] == 1
    assert metadata["list_complete"] is False
    assert metadata["completeness_reasons"] == [
        "duplicate_pagination",
        "unique_deficit",
    ]
    assert result.manifest.stopped_by == "duplicate_pagination"
    assert result.manifest.complete is False


def test_didi_rows_above_total_with_duplicates_remain_partial():
    page1 = _payload(32, _items(1, 16))
    result, _ = _collect(
        {
            1: page1,
            2: _payload(32, _items(16, 31)),
            3: _payload(32, _items(1, 2)),
            4: _payload(32, []),
        }
    )

    metadata = result.manifest.metadata
    assert metadata["records_fetched"] == 34
    assert metadata["unique_job_ids"] == 31
    assert metadata["duplicate_records"] == 3
    assert metadata["list_complete"] is False
    assert result.manifest.complete is False


def test_didi_unique_deficit_without_duplicates_is_partial():
    page1 = _payload(32, _items(1, 16))
    result, _ = _collect(
        {
            1: page1,
            2: _payload(32, _items(17, 30)),
            3: _payload(32, []),
        }
    )

    metadata = result.manifest.metadata
    assert metadata["records_fetched"] == 30
    assert metadata["unique_job_ids"] == 30
    assert metadata["duplicate_records"] == 0
    assert metadata["completeness_reasons"] == ["unique_deficit"]
    assert result.manifest.stopped_by == "unique_deficit"


def test_didi_normal_short_final_page_and_empty_terminal_are_complete():
    page1 = _payload(19, _items(1, 16))
    result, requested_pages = _collect(
        {
            1: page1,
            2: _payload(19, _items(17, 19)),
            3: _payload(19, []),
        }
    )

    assert requested_pages == [1, 2, 3, 1]
    assert result.manifest.records_fetched == 19
    assert result.manifest.pages_fetched == 2
    assert result.manifest.metadata["unique_job_ids"] == 19
    assert result.manifest.complete is True


def test_didi_stable_zero_total_is_a_complete_empty_observation():
    page1 = _payload(0, [])
    result, requested_pages = _collect({1: page1})

    assert requested_pages == [1, 1]
    assert result.jobs == []
    assert result.manifest.source_total == 0
    assert result.manifest.pages_fetched == 0
    assert result.manifest.complete is True
    assert result.manifest.metadata["terminal_page"] == 1


@pytest.mark.parametrize(
    "bad_response",
    [
        {"http_status": 503},
        {"meta": {"code": 1, "message": "unavailable"}, "data": {}},
        {"meta": {"code": 0}, "data": {"total": 1, "items": {}}},
    ],
    ids=["http", "api", "schema"],
)
def test_didi_list_errors_use_existing_error_status_and_request_reason(bad_response):
    result, _ = _collect({1: bad_response})

    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == "request_error"
    assert result.manifest.metadata["list_complete"] is False
    assert result.manifest.metadata["completeness_reasons"] == [
        "request_error",
        "incomplete_list",
    ]


def test_didi_list_complete_with_detail_failure_is_platform_partial():
    page1 = _payload(1, _items(1, 1, location="北京"))

    def fail_detail(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"meta": {"code": 1, "message": "detail unavailable"}},
        )

    result, _ = _collect(
        {1: page1, 2: _payload(1, [])}, detail_handler=fail_detail
    )

    assert result.manifest.metadata["list_complete"] is True
    assert result.manifest.detail_failed == 1
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == "detail_errors"
    assert result.manifest.metadata["completeness_reasons"] == ["detail_errors"]


def test_didi_without_empty_terminal_page_is_incomplete():
    page1 = _payload(2, _items(1, 1))
    result, requested_pages = _collect(
        {1: page1, 2: _payload(2, _items(2, 2))}, max_pages=2
    )

    assert requested_pages == [1, 2, 1]
    assert result.manifest.metadata["terminal_page"] is None
    assert result.manifest.metadata["completeness_reasons"] == ["incomplete_list"]
    assert result.manifest.complete is False
