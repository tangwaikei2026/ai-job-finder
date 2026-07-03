from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
import yaml

from src.raw.collectors import COLLECTOR_REGISTRY
from src.raw.collectors.jd import JDRawCollector
from src.raw.models import RawJobPosting


PLATFORM_CONFIG = {
    "name": "京东",
    "list_url": "https://example.test/jobs",
    "list_api": "https://example.test/job_list",
    "count_api": "https://example.test/job_count",
    "detail_url": "https://example.test/detail?requementId={job_id}",
    "page_size": 100,
}

COLLECTION_CONFIG = {
    "cities": ["北京", "上海", "杭州", "深圳", "广州"],
    "include_unknown_location": False,
    "max_retries": 1,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _record(
    job_id: int | str = 1001,
    *,
    location: str = "北京市",
    **overrides,
) -> dict:
    record = {
        "requirementId": job_id,
        "positionNameOpen": "AI测试开发工程师",
        "positionName": "AI测试开发工程师岗",
        "positionDeptName": "京东科技",
        "jobType": "研发类",
        "workCity": location,
        "workContent": "负责大模型测试平台建设",
        "qualification": "本科及以上，三年以内相关经验",
    }
    record.update(overrides)
    return record


def _collector(
    handler,
    *,
    platform_updates: dict | None = None,
    collection_updates: dict | None = None,
) -> JDRawCollector:
    platform_config = {**PLATFORM_CONFIG, **(platform_updates or {})}
    collection_config = {**COLLECTION_CONFIG, **(collection_updates or {})}
    return JDRawCollector(
        platform_config,
        collection_config,
        _client(handler),
    )


def _single_page_handler(records: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/job_count":
            return httpx.Response(200, text=str(len(records)))
        if request.url.path == "/job_list":
            return httpx.Response(
                200,
                content=json.dumps(records, ensure_ascii=False).encode(),
                headers={"Content-Type": "text/plain;charset=UTF-8"},
            )
        return httpx.Response(404)

    return handler


def test_jd_parses_normal_list_response():
    collector = _collector(_single_page_handler([_record()]))

    result = collector.collect()

    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.job_id == "1001"
    assert job.platform == "jd"
    assert job.title == "AI测试开发工程师"
    assert job.company == "京东"
    assert job.department == "京东科技"
    assert job.location == "北京市"
    assert job.description == "负责大模型测试平台建设"
    assert job.requirements == "本科及以上，三年以内相关经验"
    assert job.url.endswith("requementId=1001")
    assert result.manifest.complete is True


def test_jd_returns_raw_job_posting_fields():
    collector = _collector(_single_page_handler([_record()]))

    job = collector.collect().jobs[0]

    assert isinstance(job, RawJobPosting)
    assert set(job.to_dict()) == {
        "job_id",
        "platform",
        "title",
        "company",
        "department",
        "location",
        "experience",
        "education",
        "salary",
        "description",
        "requirements",
        "url",
        "scraped_at",
    }
    assert job.experience == ""
    assert job.education == ""
    assert job.salary == ""


def test_jd_collects_all_pages():
    pages = {
        1: [_record(1001), _record(1002, location="上海市")],
        2: [_record(1003, location="浙江省")],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/job_count":
            return httpx.Response(200, text="3")
        form = parse_qs(request.content.decode(), keep_blank_values=True)
        page = int(form["pageIndex"][0])
        assert form["pageSize"] == ["2"]
        return httpx.Response(200, json=pages[page])

    collector = _collector(handler, platform_updates={"page_size": 2})

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1001", "1002", "1003"]
    assert result.manifest.pages_fetched == 2
    assert result.manifest.records_fetched == 3
    assert result.manifest.expected_pages == 2
    assert result.manifest.stopped_by == "source_total_reached"
    assert result.manifest.complete is True


@pytest.mark.parametrize(
    ("configured_city", "source_location"),
    [("北京", "北京市"), ("上海", "上海市")],
)
def test_jd_includes_direct_municipalities(
    configured_city: str,
    source_location: str,
):
    collector = _collector(
        _single_page_handler([_record(location=source_location)]),
        collection_updates={"cities": [configured_city]},
    )

    result = collector.collect()

    assert len(result.jobs) == 1
    assert result.jobs[0].location == source_location


@pytest.mark.parametrize("configured_city", ["广州", "深圳"])
def test_jd_maps_guangdong_to_configured_cities(configured_city: str):
    collector = _collector(
        _single_page_handler([_record(location="广东省")]),
        collection_updates={"cities": [configured_city]},
    )

    result = collector.collect()

    assert len(result.jobs) == 1
    assert result.manifest.outside_city_scope == 0


def test_jd_maps_zhejiang_to_hangzhou():
    collector = _collector(
        _single_page_handler([_record(location="浙江省")]),
        collection_updates={"cities": ["杭州"]},
    )

    result = collector.collect()

    assert len(result.jobs) == 1
    assert result.manifest.outside_city_scope == 0


def test_jd_excludes_unconfigured_province():
    collector = _collector(
        _single_page_handler([_record(location="四川省")]),
    )

    result = collector.collect()

    assert result.jobs == []
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.complete is True


def test_jd_does_not_include_guangdong_without_mapped_city():
    collector = _collector(
        _single_page_handler([_record(location="广东省")]),
        collection_updates={"cities": ["北京", "上海"]},
    )

    result = collector.collect()

    assert result.jobs == []
    assert result.manifest.outside_city_scope == 1


def test_jd_handles_missing_fields_and_missing_job_id():
    records = [
        {
            "requirementId": 1001,
            "positionNameOpen": "",
            "positionName": "",
            "workCity": "",
            "workContent": "",
            "qualification": "",
        },
        {
            "positionNameOpen": "缺少ID的岗位",
            "workCity": "北京市",
        },
    ]
    collector = _collector(
        _single_page_handler(records),
        collection_updates={"include_unknown_location": True},
    )

    result = collector.collect()

    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.title == "京东职位-1001"
    assert job.location == "地点未披露"
    assert job.description == "岗位描述未披露"
    assert job.requirements == "任职要求未披露"
    assert job.url
    assert result.manifest.missing_job_id == 1
    assert result.manifest.unknown_location == 1


def test_jd_deduplicates_repeated_requirement_id():
    records = [
        _record(1001),
        _record(1001, positionNameOpen="重复岗位"),
    ]
    collector = _collector(_single_page_handler(records))

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1001"]
    assert result.manifest.duplicate_records == 1
    assert result.manifest.records_fetched == 2


@pytest.mark.parametrize("payload", [{"unexpected": "object"}, ["bad-record"]])
def test_jd_rejects_invalid_array_schema(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/job_count":
            return httpx.Response(200, text="1")
        return httpx.Response(200, json=payload)

    collector = _collector(handler)

    result = collector.collect()

    assert result.jobs == []
    assert result.manifest.complete is False
    assert result.manifest.status == "error"
    assert result.manifest.stopped_by == "error"
    assert result.manifest.error


def test_jd_preserves_first_page_when_later_page_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/job_count":
            return httpx.Response(200, text="2")
        form = parse_qs(request.content.decode())
        if form["pageIndex"] == ["1"]:
            return httpx.Response(200, json=[_record(1001)])
        return httpx.Response(500, json={"message": "temporary failure"})

    collector = _collector(handler, platform_updates={"page_size": 1})

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1001"]
    assert result.manifest.complete is False
    assert result.manifest.status == "partial"
    assert result.manifest.pages_fetched == 1
    assert result.manifest.stopped_by == "error"
    assert "500" in result.manifest.error


def test_jd_count_request_failure_returns_error_manifest():
    collector = _collector(lambda _: httpx.Response(500))

    result = collector.collect()

    assert result.jobs == []
    assert result.manifest.complete is False
    assert result.manifest.status == "error"
    assert result.manifest.stopped_by == "error"
    assert "500" in result.manifest.error


def test_jd_is_registered_and_enabled():
    config_path = Path(__file__).parents[2] / "raw_config.yaml"
    with open(config_path, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    assert COLLECTOR_REGISTRY["jd"] is JDRawCollector
    assert config["raw_collection"]["platforms"]["jd"]["enabled"] is True
