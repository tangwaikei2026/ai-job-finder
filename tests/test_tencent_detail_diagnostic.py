from __future__ import annotations

import json

import httpx
import pytest

from src.collectors.tencent import TencentRawCollector
from tools import tencent_detail_diagnostic as diagnostic


POST_ID = "2093528517592662016"
CONFIG = {
    "cities": ["深圳"],
    "include_unknown_location": False,
    "max_retries": 3,
    "timeout_seconds": 30,
    "platforms": {
        "tencent": {
            "enabled": True,
            "name": "腾讯",
            "list_api": "https://example.test/tencent/list",
            "detail_api": "https://example.test/tencent/detail",
            "detail_url": "https://example.test/jobs/{job_id}",
            "detail_delay_seconds": 0,
            "detail_timeout_seconds": 8,
            "detail_max_retries": 1,
        }
    },
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_single_post_uses_only_existing_tencent_detail_parser(monkeypatch):
    requests: list[httpx.Request] = []
    parser_calls: list[str] = []
    original = TencentRawCollector._fetch_detail

    def tracked_parser(self, job):
        parser_calls.append(job.job_id)
        return original(self, job)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={
                "Code": 200,
                "Data": {
                    "Responsibility": "负责支付合作对接。",
                    "Requirement": "具备项目管理经验。",
                },
            },
        )

    monkeypatch.setattr(TencentRawCollector, "_fetch_detail", tracked_parser)
    with _client(handler) as client:
        evidence = diagnostic.diagnose_detail(CONFIG, POST_ID, client=client)

    assert parser_calls == [POST_ID]
    assert len(requests) == 1
    assert requests[0].url.path == "/tencent/detail"
    assert dict(requests[0].url.params) == {
        "timestamp": "careers",
        "postId": POST_ID,
        "language": "zh-cn",
    }
    assert evidence == {
        "diagnostic_contract_version": 1,
        "platform": "tencent",
        "post_id": POST_ID,
        "endpoint": "https://example.test/tencent/detail",
        "bounded": {"max_attempts": 1, "timeout_seconds": 8.0},
        "request_count": 1,
        "response_count": 1,
        "http_status": 200,
        "content_type": "application/json; charset=utf-8",
        "json_parse_result": "SUCCESS",
        "payload_code": 200,
        "payload_data_type": "object",
        "responsibility_present": True,
        "requirement_present": True,
        "collector_parse_result": "SUCCESS",
        "exception_class": None,
        "exception_message": None,
    }


@pytest.mark.parametrize(
    ("response", "json_result", "payload_code", "data_type", "exception_class"),
    [
        (
            httpx.Response(503, headers={"Content-Type": "application/json"}, json={"Code": 503}),
            "SUCCESS",
            503,
            "missing",
            "httpx.HTTPStatusError",
        ),
        (
            httpx.Response(200, headers={"Content-Type": "text/html"}, text="not json"),
            "ERROR",
            None,
            "not_observed",
            "json.decoder.JSONDecodeError",
        ),
        (
            httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                json={"Code": 200, "Data": []},
            ),
            "SUCCESS",
            200,
            "array",
            "builtins.RuntimeError",
        ),
    ],
)
def test_failure_evidence_is_structured(
    response,
    json_result,
    payload_code,
    data_type,
    exception_class,
):
    with _client(lambda _: response) as client:
        evidence = diagnostic.diagnose_detail(CONFIG, POST_ID, client=client)

    assert evidence["request_count"] == 1
    assert evidence["response_count"] == 1
    assert evidence["http_status"] == response.status_code
    assert evidence["json_parse_result"] == json_result
    assert evidence["payload_code"] == payload_code
    assert evidence["payload_data_type"] == data_type
    assert evidence["collector_parse_result"] == "ERROR"
    assert evidence["exception_class"] == exception_class
    assert evidence["exception_message"]


def test_connect_error_records_request_without_claiming_a_response():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("TLS EOF", request=request)

    with _client(handler) as client:
        evidence = diagnostic.diagnose_detail(CONFIG, POST_ID, client=client)

    assert evidence["request_count"] == 1
    assert evidence["response_count"] == 0
    assert evidence["http_status"] is None
    assert evidence["content_type"] is None
    assert evidence["json_parse_result"] == "NOT_OBSERVED"
    assert evidence["payload_code"] is None
    assert evidence["payload_data_type"] == "not_observed"
    assert evidence["collector_parse_result"] == "ERROR"
    assert evidence["exception_class"] == "httpx.ConnectError"
    assert evidence["exception_message"] == "TLS EOF"


def test_diagnostic_does_not_write_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = list(tmp_path.rglob("*"))

    with _client(
        lambda _: httpx.Response(
            200,
            json={"Code": 200, "Data": {"Responsibility": "职责"}},
        )
    ) as client:
        evidence = diagnostic.diagnose_detail(CONFIG, POST_ID, client=client)

    assert evidence["collector_parse_result"] == "SUCCESS"
    assert list(tmp_path.rglob("*")) == before


def test_cli_accepts_exactly_one_post_id(monkeypatch, capsys):
    monkeypatch.setattr(diagnostic, "load_config", lambda _: CONFIG)
    monkeypatch.setattr(
        diagnostic,
        "diagnose_detail",
        lambda config, post_id: {
            "post_id": post_id,
            "collector_parse_result": "SUCCESS",
        },
    )

    assert diagnostic.main(["--post-id", POST_ID]) == 0
    assert json.loads(capsys.readouterr().out)["post_id"] == POST_ID

    with pytest.raises(SystemExit):
        diagnostic.main(["--post-id", POST_ID, "unexpected-second-id"])
