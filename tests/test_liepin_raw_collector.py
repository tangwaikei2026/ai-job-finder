from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml

from src.raw.collectors import COLLECTOR_REGISTRY
from src.raw.collectors.jd import JDRawCollector
from src.raw.collectors.liepin import LiepinRawCollector
from src.raw.models import RawJobPosting


PLATFORM_CONFIG = {
    "name": "猎聘",
    "list_url": "https://example.test/zhaopin/",
    "list_api_marker": "/api/pc-search-job",
    "detail_url": "https://example.test/job/{job_id}.shtml",
    "page_size": 40,
    "list_max_retries": 1,
    "fetch_details": False,
    "detail_delay_min_seconds": 0,
    "detail_delay_max_seconds": 0,
    "detail_max_retries": 1,
    "detail_retry_backoff_seconds": [0],
    "detail_block_backoff_seconds": [0],
    "exclude_hunter_titles": ["猎头顾问", "寻访员"],
}

COLLECTION_CONFIG = {
    "cities": ["北京", "上海", "杭州", "深圳", "广州"],
    "include_unknown_location": False,
    "max_retries": 1,
}


def _record(
    job_id: str = "1980000001",
    *,
    title: str = "AI评测工程师",
    company: str = "示例科技",
    location: str = "深圳",
    **job_overrides: Any,
) -> dict[str, Any]:
    job = {
        "jobId": job_id,
        "title": title,
        "dq": location,
        "requireWorkYears": "1-3年",
        "requireEduLevel": "本科",
        "salary": "20-35k",
        "labels": ["大模型", "模型评测"],
    }
    job.update(job_overrides)
    return {"job": job, "comp": {"compName": company}}


def _payload(
    records: list[dict[str, Any]],
    *,
    total: int | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"jobCardList": records}
    if total is not None:
        data["totalCount"] = total
    return {"code": 0, "data": {"data": data}}


def _collector(
    page_fetcher: Callable[[int, int], dict[str, Any]],
    *,
    platform_updates: dict[str, Any] | None = None,
    collection_updates: dict[str, Any] | None = None,
    detail_handler: Callable[[httpx.Request], httpx.Response] | None = None,
) -> LiepinRawCollector:
    platform_config = {**PLATFORM_CONFIG, **(platform_updates or {})}
    collection_config = {**COLLECTION_CONFIG, **(collection_updates or {})}
    handler = detail_handler or (lambda _: httpx.Response(404))
    collector = LiepinRawCollector(
        platform_config,
        collection_config,
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    # 单元测试替换浏览器边界，只验证 adapter 自己的分页和解析行为。
    collector._browser_page = lambda: nullcontext(object())  # type: ignore[method-assign]
    collector._fetch_list_page = (  # type: ignore[method-assign]
        lambda _page, current_page, page_size: page_fetcher(
            current_page,
            page_size,
        )
    )
    return collector


def _single_page(records: list[dict[str, Any]]):
    return lambda _page, _size: _payload(records, total=len(records))


def test_liepin_parses_normal_list_response():
    collector = _collector(_single_page([_record()]))

    result = collector.collect()

    assert len(result.jobs) == 1
    job = result.jobs[0]
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
    assert job.job_id == "1980000001"
    assert job.platform == "liepin"
    assert job.title == "AI评测工程师"
    assert job.company == "示例科技"
    assert job.location == "深圳"
    assert job.experience == "1-3年"
    assert job.education == "本科"
    assert job.salary == "20-35k"
    assert job.description == "大模型, 模型评测"
    assert job.url.endswith("/1980000001.shtml")
    assert result.manifest.complete is True


def test_liepin_protects_missing_fields_and_missing_job_id():
    records = [
        {
            "job": {"jobId": "1980000002"},
            "comp": {},
        },
        {
            "job": {"title": "缺少ID的岗位", "dq": "深圳"},
            "comp": {"compName": "示例科技"},
        },
    ]
    collector = _collector(
        _single_page(records),
        collection_updates={"include_unknown_location": True},
    )

    result = collector.collect()

    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.title == "猎聘职位-1980000002"
    assert job.company == "公司未披露"
    assert job.location == "地点未披露"
    assert job.description == "岗位描述待详情补全"
    assert job.requirements == "任职要求待详情补全"
    assert job.url.endswith("/1980000002.shtml")
    assert result.manifest.missing_job_id == 1
    assert result.manifest.unknown_location == 1


def test_liepin_collects_all_pages():
    pages = {
        0: _payload([_record("1")], total=2),
        1: _payload([_record("2", location="上海")], total=2),
    }
    calls: list[int] = []

    def fetch(current_page: int, page_size: int) -> dict[str, Any]:
        calls.append(current_page)
        assert page_size == 1
        return pages[current_page]

    collector = _collector(fetch, platform_updates={"page_size": 1})

    result = collector.collect()

    assert calls == [0, 1]
    assert [job.job_id for job in result.jobs] == ["1", "2"]
    assert result.manifest.pages_fetched == 2
    assert result.manifest.expected_pages == 2
    assert result.manifest.records_fetched == 2
    assert result.manifest.complete is True


def test_liepin_prefers_total_pages_when_has_next_is_inconsistent():
    pages = {
        0: {
            "code": 0,
            "data": {
                "data": {"jobCardList": [_record("1")]},
                "pagination": {
                    "totalCounts": 2,
                    "totalPage": 2,
                    "hasNext": False,
                },
            },
        },
        1: {
            "code": 0,
            "data": {
                "data": {"jobCardList": [_record("2")]},
                "pagination": {
                    "totalCounts": 2,
                    "totalPage": 2,
                    "hasNext": False,
                },
            },
        },
    }
    calls: list[int] = []

    def fetch(current_page: int, _page_size: int) -> dict[str, Any]:
        calls.append(current_page)
        return pages[current_page]

    collector = _collector(fetch, platform_updates={"page_size": 1})

    result = collector.collect()

    assert calls == [0, 1]
    assert [job.job_id for job in result.jobs] == ["1", "2"]
    assert result.manifest.expected_pages == 2
    assert result.manifest.complete is True


def test_liepin_preserves_first_page_when_later_page_fails():
    def fetch(current_page: int, _page_size: int) -> dict[str, Any]:
        if current_page == 0:
            return _payload([_record("1")], total=2)
        raise RuntimeError("temporary page failure")

    collector = _collector(fetch, platform_updates={"page_size": 1})

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1"]
    assert result.manifest.pages_fetched == 1
    assert result.manifest.complete is False
    assert result.manifest.status == "partial"
    assert result.manifest.stopped_by == "list_error"
    assert "temporary page failure" in result.manifest.error


def test_liepin_retries_a_temporary_list_page_failure():
    attempts = 0

    def fetch(_current_page: int, _page_size: int) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary page failure")
        return _payload([_record("1")], total=1)

    collector = _collector(
        fetch,
        platform_updates={
            "list_max_retries": 2,
            "list_retry_backoff_seconds": [0],
        },
    )

    result = collector.collect()

    assert attempts == 2
    assert [job.job_id for job in result.jobs] == ["1"]
    assert result.manifest.complete is True


def test_liepin_deduplicates_repeated_job_id():
    records = [
        _record("1"),
        _record("1", title="重复岗位"),
    ]
    collector = _collector(_single_page(records))

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1"]
    assert result.manifest.records_fetched == 2
    assert result.manifest.duplicate_records == 1


def test_liepin_detail_failure_keeps_list_job():
    collector = _collector(
        _single_page([_record("1")]),
        platform_updates={"fetch_details": True},
        detail_handler=lambda _: httpx.Response(500, text="temporary failure"),
    )

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1"]
    assert result.jobs[0].description == "大模型, 模型评测"
    assert result.jobs[0].requirements == "任职要求待详情补全"
    assert result.manifest.details_fetched == 0
    assert result.manifest.detail_failed == 1
    assert result.manifest.status == "partial"
    assert result.manifest.stopped_by == "detail_errors"
    assert "detail failures" in result.manifest.error


def test_liepin_detail_success_fills_description_and_requirements():
    detail = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "高级AI评测工程师",
        "hiringOrganization": {"@type": "Organization", "name": "详情科技"},
        "description": (
            "<p>岗位职责：</p><p>负责大模型质量评测</p>"
            "<p>任职要求：</p><p>本科及以上，三年以内经验</p>"
        ),
        "experienceRequirements": "1-3年",
        "educationRequirements": "本科",
    }
    html = (
        '<html><script type="application/ld+json">'
        f"{json.dumps(detail, ensure_ascii=False)}"
        "</script></html>"
    )
    collector = _collector(
        _single_page([_record("1")]),
        platform_updates={"fetch_details": True},
        detail_handler=lambda _: httpx.Response(200, text=html),
    )

    result = collector.collect()

    job = result.jobs[0]
    assert job.title == "高级AI评测工程师"
    assert job.company == "详情科技"
    assert job.description == "岗位职责：\n负责大模型质量评测"
    assert job.requirements == "本科及以上，三年以内经验"
    assert result.manifest.details_fetched == 1
    assert result.manifest.detail_failed == 0
    assert result.manifest.complete is True


def test_liepin_detail_tolerates_unescaped_newlines_in_json_ld():
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "AI评测工程师",
      "description": "岗位职责：
负责模型评测
任职要求：
本科及以上"
    }
    </script>
    """
    collector = _collector(
        _single_page([_record("1")]),
        platform_updates={"fetch_details": True},
        detail_handler=lambda _: httpx.Response(200, text=html),
    )

    result = collector.collect()

    assert result.jobs[0].description == "岗位职责：\n负责模型评测"
    assert result.jobs[0].requirements == "本科及以上"
    assert result.manifest.details_fetched == 1


def test_liepin_recognizes_wow_redirect_as_detail_rate_limit():
    response = httpx.Response(
        200,
        request=httpx.Request(
            "GET",
            "https://wow.liepin.com/security-check",
        ),
        text="<html></html>",
    )

    assert LiepinRawCollector._is_blocked_detail_response(response) is True


def test_liepin_rejects_changed_platform_response_schema_without_crashing():
    changed_payload = {
        "code": 0,
        "data": {
            "data": {
                "jobs": [_record()],
                "totalCount": 1,
            }
        },
    }
    collector = _collector(lambda _page, _size: changed_payload)

    result = collector.collect()

    assert result.jobs == []
    assert result.manifest.complete is False
    assert result.manifest.status == "error"
    assert result.manifest.stopped_by == "list_error"
    assert "jobCardList" in result.manifest.error


def test_liepin_filters_outside_city_scope():
    records = [
        _record("1", location="深圳"),
        _record("2", location="北京"),
    ]
    collector = _collector(
        _single_page(records),
        collection_updates={"cities": ["深圳"]},
    )

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1"]
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.complete is True


def test_liepin_filters_hunter_job_titles():
    records = [
        _record("1", title="AI评测工程师"),
        _record("2", title="猎头顾问"),
    ]
    collector = _collector(_single_page(records))

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1"]


def test_liepin_is_registered_enabled_and_existing_registry_is_unchanged():
    config_path = Path(__file__).parent.parent / "raw_config.yaml"
    with open(config_path, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    assert COLLECTOR_REGISTRY["liepin"] is LiepinRawCollector
    assert COLLECTOR_REGISTRY["jd"] is JDRawCollector
    assert config["raw_collection"]["platforms"]["liepin"]["enabled"] is True
