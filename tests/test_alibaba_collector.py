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
    "cities": ["北京"],
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
    region_config = {"region_codes": {"北京": "110100"}} if platform == "aliyun" else {}
    return AlibabaBaseCollector(
        {
            "name": name,
            "platform_key": platform,
            "list_url": f"https://example.test/{platform}/jobs",
            "list_api": f"https://example.test/{platform}/position/search",
            "detail_url": f"https://example.test/{platform}/detail/{{job_id}}",
            "page_size": 50,
            **region_config,
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
            "regions": "110100",
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
    assert manifest.source_total == 3
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
    assert manifest.stopped_by == "all_partitions_complete"
    assert manifest.metadata["source_total_semantics"] == (
        "observed_unique_union_job_ids"
    )
    assert manifest.metadata["sum_partition_records"] == 5
    assert manifest.metadata["unique_union_jobs"] == 3
    assert manifest.metadata["cross_partition_duplicates"] == 0


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
                        {"id": "same-2", "name": "岗位二", "workLocations": ["北京"]},
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
    assert result.manifest.stopped_by == "partition_incomplete"
    assert result.manifest.metadata["partitions"][0]["stopped_by"] == (
        "repeated_page"
    )


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
        (
            {"success": True, "content": {"datas": []}},
            "Alibaba API content.totalCount is required",
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
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == "partition_error"
    assert result.manifest.error == f"北京(110100): {error}"


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

    assert platforms["aliyun"]["region_codes"] == {
        "北京": "110100",
        "上海": "310100",
        "杭州": "330100",
        "深圳": "440300",
        "广州": "440100",
    }


def _partitioned_collector(
    handler,
    *,
    cities: list[str],
    region_codes: dict[str, str],
    page_size: int = 2,
) -> AlibabaBaseCollector:
    return AlibabaBaseCollector(
        {
            "name": "阿里云",
            "platform_key": "aliyun",
            "list_url": "https://example.test/aliyun/jobs",
            "list_api": "https://example.test/aliyun/position/search",
            "detail_url": "https://example.test/aliyun/detail/{job_id}",
            "page_size": page_size,
            "region_codes": region_codes,
        },
        {
            "cities": cities,
            "include_unknown_location": False,
            "max_retries": 1,
        },
        _client(handler),
    )


def _aliyun_response(
    *,
    total: int,
    job_ids: list[str],
    location: str | list[str],
) -> httpx.Response:
    locations = [location] if isinstance(location, str) else location
    return httpx.Response(
        200,
        json={
            "success": True,
            "content": {
                "totalCount": total,
                "datas": [
                    {
                        "id": job_id,
                        "name": f"岗位 {job_id}",
                        "workLocations": locations,
                    }
                    for job_id in job_ids
                ],
            },
        },
    )


def test_aliyun_resolves_all_required_regions_and_fails_closed_for_unknown_city():
    collector = _partitioned_collector(
        lambda _: pytest.fail("missing region mapping must fail before HTTP"),
        cities=["北京", "上海", "杭州", "深圳", "广州"],
        region_codes={
            "北京": "110100",
            "上海": "310100",
            "杭州": "330100",
            "深圳": "440300",
            "广州": "440100",
        },
    )
    assert collector._resolve_region_partitions() == [
        ("北京", "110100"),
        ("上海", "310100"),
        ("杭州", "330100"),
        ("深圳", "440300"),
        ("广州", "440100"),
    ]
    collector.close()

    unknown = _partitioned_collector(
        lambda _: pytest.fail("unknown city must fail before HTTP"),
        cities=["未知城市"],
        region_codes={"北京": "110100"},
    )
    result = unknown.collect()
    unknown.close()

    assert result.jobs == []
    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert "missing_region_mapping" in result.manifest.error


def test_aliyun_region_partitions_complete_across_multiple_pages():
    datasets = {
        ("110100", 1): (3, ["b1", "b2"], "北京"),
        ("110100", 2): (3, ["b3"], "北京"),
        ("310100", 1): (2, ["s1", "s2"], "上海"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )
        body = json.loads(request.content)
        total, ids, location = datasets[(body["regions"], body["pageIndex"])]
        return _aliyun_response(total=total, job_ids=ids, location=location)

    collector = _partitioned_collector(
        handler,
        cities=["北京", "上海"],
        region_codes={"北京": "110100", "上海": "310100"},
    )
    result = collector.collect()
    collector.close()

    assert {job.job_id for job in result.jobs} == {"b1", "b2", "b3", "s1", "s2"}
    assert result.manifest.status == "success"
    assert result.manifest.complete is True
    assert result.manifest.source_total == 5
    assert result.manifest.expected_pages == 3
    assert result.manifest.pages_fetched == 3
    assert result.manifest.records_fetched == 5
    assert result.manifest.stopped_by == "all_partitions_complete"
    assert result.manifest.metadata["all_required_partitions_complete"] is True
    assert result.manifest.metadata["cross_partition_duplicates"] == 0
    assert set(result.manifest.metadata["partitions"][0]) == {
        "region_name",
        "region_code",
        "source_total",
        "expected_pages",
        "pages_fetched",
        "records_fetched",
        "unique_job_ids",
        "duplicate_job_ids_within_partition",
        "stopped_by",
        "complete",
        "error",
    }


def test_aliyun_zero_total_partition_is_complete():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )
        return _aliyun_response(total=0, job_ids=[], location="北京")

    collector = _partitioned_collector(
        handler,
        cities=["北京"],
        region_codes={"北京": "110100"},
    )
    result = collector.collect()
    collector.close()

    partition = result.manifest.metadata["partitions"][0]
    assert result.manifest.status == "success"
    assert result.manifest.complete is True
    assert result.manifest.source_total == 0
    assert result.manifest.pages_fetched == 0
    assert partition["complete"] is True
    assert partition["stopped_by"] == "empty_source"


def test_aliyun_empty_page_before_partition_total_is_partial():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )
        page = json.loads(request.content)["pageIndex"]
        ids = ["b1", "b2"] if page == 1 else []
        return _aliyun_response(total=3, job_ids=ids, location="北京")

    collector = _partitioned_collector(
        handler,
        cities=["北京"],
        region_codes={"北京": "110100"},
    )
    result = collector.collect()
    collector.close()

    partition = result.manifest.metadata["partitions"][0]
    assert {job.job_id for job in result.jobs} == {"b1", "b2"}
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert partition["complete"] is False
    assert partition["stopped_by"] == "empty_page"


def test_aliyun_partition_over_500_stays_partial_when_page_11_is_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )
        page = json.loads(request.content)["pageIndex"]
        ids = [f"job-{page}-{index}" for index in range(50)] if page <= 10 else []
        return _aliyun_response(total=501, job_ids=ids, location="北京")

    collector = _partitioned_collector(
        handler,
        cities=["北京"],
        region_codes={"北京": "110100"},
        page_size=50,
    )
    result = collector.collect()
    collector.close()

    partition = result.manifest.metadata["partitions"][0]
    assert len(result.jobs) == 500
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == "partition_limit"
    assert partition["source_total"] == 501
    assert partition["expected_pages"] == 11
    assert partition["pages_fetched"] == 10
    assert partition["records_fetched"] == 500
    assert partition["stopped_by"] == "partition_limit"


def test_aliyun_union_deduplicates_cross_partition_jobs_without_partial():
    datasets = {
        "110100": (2, ["shared", "beijing"], ["北京", "上海"]),
        "310100": (2, ["shared", "shanghai"], ["北京", "上海"]),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )
        region = json.loads(request.content)["regions"]
        total, ids, location = datasets[region]
        return _aliyun_response(total=total, job_ids=ids, location=location)

    collector = _partitioned_collector(
        handler,
        cities=["北京", "上海"],
        region_codes={"北京": "110100", "上海": "310100"},
    )
    result = collector.collect()
    collector.close()

    assert {job.job_id for job in result.jobs} == {"shared", "beijing", "shanghai"}
    assert result.manifest.status == "success"
    assert result.manifest.complete is True
    assert result.manifest.records_fetched == 4
    assert result.manifest.source_total == 3
    assert result.manifest.jobs_mapped == 3
    assert result.manifest.duplicate_records == 1
    assert result.manifest.metadata["sum_partition_records"] == 4
    assert result.manifest.metadata["unique_union_jobs"] == 3
    assert result.manifest.metadata["cross_partition_duplicates"] == 1


def test_aliyun_region_error_keeps_other_partition_data_and_is_partial():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )
        region = json.loads(request.content)["regions"]
        if region == "310100":
            return httpx.Response(500, json={"message": "temporary failure"})
        return _aliyun_response(total=1, job_ids=["beijing"], location="北京")

    collector = _partitioned_collector(
        handler,
        cities=["北京", "上海"],
        region_codes={"北京": "110100", "上海": "310100"},
    )
    result = collector.collect()
    collector.close()

    partitions = result.manifest.metadata["partitions"]
    assert [job.job_id for job in result.jobs] == ["beijing"]
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == "partition_error"
    assert partitions[0]["complete"] is True
    assert partitions[1]["complete"] is False
    assert partitions[1]["stopped_by"] == "error"
