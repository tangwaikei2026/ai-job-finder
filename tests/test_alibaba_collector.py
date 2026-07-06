from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import yaml

from src.collectors import AlibabaBaseCollector, COLLECTOR_REGISTRY
from src.collectors.quark import QuarkRawCollector


PLATFORMS = ("aliyun", "tongyi", "dingtalk")
COLLECTION_CONFIG = {
    "cities": ["北京", "上海"],
    "include_unknown_location": False,
    "max_retries": 1,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _collector(
    handler,
    platform: str = "aliyun",
    name: str = "阿里云",
) -> AlibabaBaseCollector:
    return AlibabaBaseCollector(
        {
            "name": name,
            "platform_key": platform,
            "list_url": f"https://example.test/{platform}/jobs",
            "list_api": f"https://example.test/{platform}/position/search",
            "detail_url": f"https://example.test/{platform}/detail/{{job_id}}",
            "page_size": 50,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )


def test_alibaba_platforms_share_one_registered_collector():
    assert all(
        COLLECTOR_REGISTRY[platform] is AlibabaBaseCollector
        for platform in PLATFORMS
    )
    assert COLLECTOR_REGISTRY["quark"] is QuarkRawCollector


def test_alibaba_collects_maps_deduplicates_and_filters_by_city():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                text="<html></html>",
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )

        body = json.loads(request.content)
        assert body == {
            "channel": "group_official_site",
            "language": "zh",
            "batchId": "",
            "categories": "",
            "deptCodes": [],
            "key": "",
            "pageIndex": 1,
            "pageSize": 50,
            "regions": "",
            "subCategories": "",
            "shareType": "",
            "shareId": "",
            "myReferralShareCode": "",
        }
        assert request.headers["referer"] == "https://example.test/aliyun/jobs"
        assert request.headers["x-xsrf-token"] == "test-token"
        return httpx.Response(
            200,
            json={
                "success": True,
                "content": {
                    "totalCount": 5,
                    "datas": [
                        {
                            "id": 1001,
                            "name": "云平台工程师",
                            "departmentName": "云计算",
                            "workLocations": ["北京", "上海"],
                            "experience": {"from": 3, "to": 5},
                            "degree": "bachelor",
                            "description": "职责原文",
                            "requirement": "要求原文",
                        },
                        {
                            "id": 1001,
                            "name": "重复岗位",
                            "workLocations": ["北京"],
                        },
                        {
                            "id": "",
                            "name": "缺少 ID",
                            "workLocations": ["北京"],
                        },
                        {
                            "id": 1002,
                            "name": "未知地点",
                            "workLocations": [],
                        },
                        {
                            "id": 1003,
                            "name": "范围外岗位",
                            "workLocations": ["杭州"],
                        },
                    ],
                },
            },
        )

    collector = _collector(handler)
    result = collector.collect()
    collector.close()

    assert [job.job_id for job in result.jobs] == ["1001"]
    job = result.jobs[0]
    assert job.platform == "aliyun"
    assert job.company == "阿里云"
    assert job.title == "云平台工程师"
    assert job.department == "云计算"
    assert job.location == "北京, 上海"
    assert job.experience == "3-5年"
    assert job.education == "本科"
    assert job.salary == ""
    assert job.description == "职责原文"
    assert job.requirements == "要求原文"
    assert job.url == "https://example.test/aliyun/detail/1001"

    manifest = result.manifest
    assert manifest.status == "success"
    assert manifest.complete is True
    assert manifest.source_total == 5
    assert manifest.expected_pages == 1
    assert manifest.pages_fetched == 1
    assert manifest.records_fetched == 5
    assert manifest.jobs_mapped == 3
    assert manifest.jobs_in_scope == 1
    assert manifest.outside_city_scope == 2
    assert manifest.unknown_location == 1
    assert manifest.duplicate_records == 1
    assert manifest.missing_job_id == 1
    assert manifest.details_fetched == 0
    assert manifest.detail_failed == 0
    assert manifest.stopped_by == "source_total_reached"


def test_alibaba_stops_on_repeated_page():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "content": {
                    "totalCount": 10,
                    "datas": [
                        {"id": "same-1", "name": "岗位一", "workLocations": ["北京"]},
                        {"id": "same-2", "name": "岗位二", "workLocations": ["上海"]},
                    ],
                },
            },
        )

    collector = _collector(handler)
    result = collector.collect()
    collector.close()

    assert [job.job_id for job in result.jobs] == ["same-1", "same-2"]
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert result.manifest.pages_fetched == 1
    assert result.manifest.records_fetched == 2
    assert result.manifest.stopped_by == "repeated_page"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (
            {"success": True, "content": []},
            "Alibaba API content must be an object",
        ),
        (
            {"success": True, "content": {"datas": {}}},
            "Alibaba API content.datas must be a list of objects",
        ),
    ],
)
def test_alibaba_structure_changes_return_error_manifest(response, error):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )
        return httpx.Response(200, json=response)

    collector = _collector(handler)
    result = collector.collect()
    collector.close()

    assert result.jobs == []
    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == "error"
    assert result.manifest.error == error


def test_alibaba_missing_csrf_returns_platform_error_manifest():
    collector = _collector(lambda _: httpx.Response(200))
    result = collector.collect()
    collector.close()

    assert result.jobs == []
    assert result.manifest.platform == "aliyun"
    assert result.manifest.status == "error"
    assert result.manifest.error == (
        "aliyun list page did not set XSRF-TOKEN"
    )


def test_alibaba_helpers_keep_quark_formatting_contract():
    assert AlibabaBaseCollector._format_experience({"from": 3, "to": 5}) == "3-5年"
    assert AlibabaBaseCollector._format_experience({"from": 3}) == "3年以上"
    assert AlibabaBaseCollector._format_degree("bachelor") == "本科"
    assert AlibabaBaseCollector._format_degree("不限") == "不限"


def test_alibaba_platforms_are_enabled_in_config():
    config_path = Path(__file__).parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    platforms = config["platforms"]

    for platform in PLATFORMS:
        assert platforms[platform]["enabled"] is True
        assert platforms[platform]["platform_key"] == platform
