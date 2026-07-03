from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable

from src.raw.collectors.liepin import LiepinRawCollector
from src.raw.models import RawJobPosting


COLLECTION_CONFIG = {
    "cities": ["深圳"],
    "include_unknown_location": False,
    "max_retries": 1,
}


def _record(
    job_id: str,
    *,
    title: str = "AI测试工程师",
    company: str = "示例科技",
) -> dict[str, Any]:
    return {
        "job": {
            "jobId": job_id,
            "title": title,
            "dq": "深圳",
            "salary": "20-35k",
            "requireWorkYears": "1-3年",
            "requireEduLevel": "本科",
            "labels": ["大模型", "模型评测"],
        },
        "comp": {"compName": company},
    }


def _payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "code": 0,
        "data": {
            "data": {
                "jobCardList": records,
                "totalCount": len(records),
            }
        },
    }


def _collector(
    tmp_path: Path,
    keywords: list[str],
    fetcher: Callable[[str, int, int], dict[str, Any]],
) -> LiepinRawCollector:
    collector = LiepinRawCollector(
        {
            "name": "猎聘",
            "list_url": "https://example.test/zhaopin/",
            "list_api_marker": "/api/pc-search-job",
            "detail_url": "https://example.test/job/{job_id}.shtml",
            "output_file": str(tmp_path / "liepin" / "raw_job.json"),
            "keywords": keywords,
            "industry": "H01$H01",
            "job_kind": "2",
            "page_size": 40,
            "max_pages": 1,
            "list_max_retries": 1,
            "fetch_details": False,
            "exclude_hunter_titles": [],
        },
        COLLECTION_CONFIG,
    )
    # 单元测试替换浏览器边界，避免依赖实时网站和本机 Chromium。
    collector._browser_page = lambda: nullcontext(object())  # type: ignore[method-assign]
    collector._fetch_list_page = (  # type: ignore[method-assign]
        lambda _page, keyword, current_page, page_size: fetcher(
            keyword,
            current_page,
            page_size,
        )
    )
    return collector


def test_liepin_parses_each_keyword_list_and_writes_raw_jobs(tmp_path: Path):
    calls: list[tuple[str, int, int]] = []

    def fetch(keyword: str, current_page: int, page_size: int):
        calls.append((keyword, current_page, page_size))
        return _payload([_record(str(len(calls)), title=keyword)])

    collector = _collector(
        tmp_path,
        ["大模型评测", "AI测试工程师"],
        fetch,
    )
    try:
        result = collector.collect()
    finally:
        collector.close()

    assert calls == [
        ("大模型评测", 0, 40),
        ("AI测试工程师", 0, 40),
    ]
    assert len(result.jobs) == 2
    assert result.manifest.status == "success"
    assert result.manifest.pages_fetched == 2
    assert all(isinstance(job, RawJobPosting) for job in result.jobs)

    first = result.jobs[0]
    assert first.job_id == "1"
    assert first.platform == "liepin"
    assert first.title == "大模型评测"
    assert first.company == "示例科技"
    assert first.location == "深圳"
    assert first.salary == "20-35k"
    assert first.experience == "1-3年"
    assert first.education == "本科"
    assert first.description == "大模型, 模型评测"
    assert first.requirements == ""
    assert first.url.endswith("/1.shtml")
    assert first.scraped_at

    output_path = tmp_path / "liepin" / "raw_job.json"
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == [job.to_dict() for job in result.jobs]


def test_liepin_deduplicates_job_id_across_keywords(tmp_path: Path):
    collector = _collector(
        tmp_path,
        ["大模型评测", "Agent评测"],
        lambda _keyword, _page, _size: _payload([_record("same-job")]),
    )
    try:
        result = collector.collect()
    finally:
        collector.close()

    assert [job.job_id for job in result.jobs] == ["same-job"]
    assert result.manifest.records_fetched == 2
    assert result.manifest.duplicate_records == 1


def test_liepin_schema_change_is_reported_without_crashing(tmp_path: Path):
    changed_payload = {
        "code": 0,
        "data": {
            "data": {
                "jobs": [_record("1")],
                "totalCount": 1,
            }
        },
    }
    collector = _collector(
        tmp_path,
        ["大模型评测"],
        lambda _keyword, _page, _size: changed_payload,
    )
    try:
        result = collector.collect()
    finally:
        collector.close()

    assert result.jobs == []
    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == "list_error"
    assert "jobCardList" in result.manifest.error
    assert not (tmp_path / "liepin" / "raw_job.json").exists()
