"""Offline diagnostics only: these tests do not authorize an early-stop policy."""
from __future__ import annotations

import json
import logging
import ssl
from collections import Counter

import httpx
import pytest

from src import base
from src.collectors.meituan import MeituanRawCollector
from src.analysis.source_health import SourceHealth
from src.models import CollectionManifest, CollectionResult

SECRET = "Cookie=session-secret&Token=private-token"


def collector(client, retries=1):
    return MeituanRawCollector(
        {"name": "美团", "list_api": "https://example.test/list",
         "list_url": "https://example.test/jobs", "detail_api": "https://example.test/detail",
         "detail_workers": 4},
        {"max_retries": retries, "cities": ["北京"]}, client,
    )


def list_response(request, count=4, *, total=None):
    return httpx.Response(200, request=request, json={"status": 1, "data": {
        "list": [{"jobUnionId": str(i), "name": "工程师", "cityList": [{"name": "北京"}],
                  "jobDuty": "list description"} for i in range(count)],
        "page": {"totalCount": count if total is None else total, "totalPage": 1 if total is None else 2},
    }})


def wrapped_tls():
    exc = httpx.ConnectError(SECRET)
    exc.__cause__ = ssl.SSLEOFError(8, SECRET)
    return exc


@pytest.mark.parametrize("factory,kind,category", [
    (lambda: httpx.ReadTimeout(""), "ReadTimeout", "Timeout"),
    (lambda: httpx.ConnectTimeout(""), "ConnectTimeout", "Timeout"),
    (lambda: TimeoutError("_ssl.c: handshake operation timed out " + SECRET), "TimeoutError", "Timeout"),
    (wrapped_tls, "ConnectError", "TLS"),
    (lambda: ssl.SSLEOFError(8, SECRET), "SSLEOFError", "TLS"),
    (lambda: httpx.ConnectError(SECRET), "ConnectError", "ConnectError"),
    (lambda: httpx.RemoteProtocolError(SECRET), "RemoteProtocolError", "RemoteProtocolError"),
    (lambda: Exception(""), "Exception", "Other"),
])
def test_redacted_types_and_exact_retry_bound(factory, kind, category, monkeypatch, caplog):
    calls = []
    sleeps = []
    monkeypatch.setattr(base.time, "sleep", sleeps.append)

    def handler(request):
        calls.append(request)
        raise factory()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Exception):
            collector(client, retries=3).request(
                "POST", "https://example.test/" + SECRET, request_stage="detail",
                headers={"Cookie": SECRET}, json={"Token": SECRET},
            )
    records = [r for r in caplog.records if hasattr(r, "request_stage")]
    assert len(calls) == 3 and len(sleeps) == 2
    assert [r.request_attempt for r in records] == [1, 2, 3]
    assert [r.request_final for r in records] == [False, False, True]
    assert all(r.error_type == kind and r.error_category == category for r in records)
    assert all(r.request_stage == "detail" for r in records)
    assert SECRET not in caplog.text and "example.test" not in caplog.text


def test_http_status_and_untrusted_diagnostic_labels_are_redacted(caplog):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503, request=r))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            collector(client).request("GET", "https://example.test/" + SECRET, request_stage=SECRET)
    assert caplog.records[-1].error_type == "HTTPStatusError"
    assert caplog.records[-1].request_stage == "unspecified"
    assert SECRET not in caplog.text
    evil = type(SECRET, (Exception,), {})()
    evil.__cause__ = evil
    assert base.request_error_fields(evil) == {"error_type": "Exception", "error_category": "Other"}


@pytest.mark.parametrize("failed", [0, 1, 4])
def test_progress_preserves_successes_and_strict_coverage(failed, caplog):
    calls = Counter()
    caplog.set_level(logging.INFO)

    def handler(request):
        if request.url.path == "/list":
            return list_response(request)
        job_id = json.loads(request.content)["jobUnionId"]
        calls[job_id] += 1
        if int(job_id) < failed:
            raise httpx.ReadTimeout("")
        return httpx.Response(200, json={"status": 1, "data": {"jobDuty": "reliable detail"}}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = collector(client).collect()
    m = result.manifest
    p = m.metadata["progress"]
    assert len(result.jobs) == 4 and calls == Counter({str(i): 1 for i in range(4)})
    assert m.details_fetched == p["detail_succeeded"] == 4 - failed
    assert m.detail_failed == p["detail_failed"] == failed
    assert p["detail_targets"] == p["detail_submitted"] == p["detail_started"] == 4
    assert p["detail_unfinished"] == p["detail_not_started"] == p["detail_in_flight"] == 0
    assert p["list_complete"] is True
    assert m.complete is (failed == 0)
    assert m.status == ("partial" if failed else "success")
    assert p["last_success_at"] and p["last_success_elapsed_seconds"] >= 0
    assert p["list_seconds"] >= 0 and p["detail_seconds"] >= 0
    assert [r.collection_event for r in caplog.records if hasattr(r, "collection_event")] == [
        "enter", "list_progress", "detail_enter", "exit"]
    health = SourceHealth({"platforms": [m.to_dict()], "job_count": 4}, [j.to_dict() for j in result.jobs])
    for job in result.jobs:
        expected = int(job.job_id) >= failed
        assert job.description == ("reliable detail" if expected else "list description")
        assert health.resolve("meituan", "美团", job.to_dict()).content_reliable is expected


def test_list_failure_records_unattempted_details_without_discarding_jobs(caplog):
    def handler(request):
        assert request.url.path == "/list"
        if json.loads(request.content)["page"]["pageNo"] == 1:
            return list_response(request, 2, total=4)
        return httpx.Response(200, json={"status": 0, "message": SECRET}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = collector(client).collect()
    p = result.manifest.metadata["progress"]
    assert len(result.jobs) == 2
    assert not result.manifest.complete and result.manifest.status == "error"
    assert p["detail_targets"] == p["detail_not_started"] == p["detail_unfinished"] == 2
    assert p["detail_started"] == p["detail_submitted"] == p["detail_failed"] == 0
    assert p["list_complete"] is False
    assert "RuntimeError" in result.manifest.error
    assert SECRET not in json.dumps(result.manifest.to_dict()) + caplog.text


def test_parse_failure_keeps_stage_and_type(caplog):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=SECRET, request=r))) as client:
        result = collector(client).collect()
    assert result.manifest.metadata["collection_error"] == {
        "stage": "list", "error_type": "ValueError", "error_category": "ParseError"}
    assert SECRET not in result.manifest.error + caplog.text


def test_platform_after_meituan_still_runs_when_requests_exhaust(monkeypatch):
    from src import main
    reached = []

    def handler(request):
        if request.url.path == "/list":
            return list_response(request)
        raise httpx.ConnectError(SECRET)

    class NextCollector:
        def __init__(self, *args):
            pass
        def collect(self):
            reached.append("next")
            return CollectionResult([], CollectionManifest(platform="next", name="next", status="success", complete=True))
        def close(self):
            pass

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        c = collector(client)
        monkeypatch.setattr(main, "COLLECTOR_REGISTRY", {"meituan": lambda *a: c, "next": NextCollector})
        jobs, manifests = main.collect_all({"platforms": {"meituan": {"enabled": True}, "next": {"enabled": True}}})
    assert reached == ["next"] and len(jobs) == 4
    assert manifests[0].status == "partial" and not manifests[0].complete
    assert manifests[1].complete
