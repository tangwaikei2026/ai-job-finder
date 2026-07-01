"""Highest-priority resilience contracts for the job collection pipeline.

These tests intentionally describe the desired behavior at external-data
boundaries.  They may expose gaps in the current implementation; business code
must not be changed merely to make the test setup more permissive.
"""
from __future__ import annotations

from urllib.parse import parse_qs

import httpx

from src.models import JobPosting
from src.pipeline import filter as filter_module
from src.pipeline.dedup import deduplicate
from src.pipeline.detail_fetcher import enrich_with_details
from src.pipeline.filter import classify_strict, reload_filter_rules
from src.raw.collectors.baidu import BaiduRawCollector
from src.raw.collectors.tencent import TencentRawCollector


COLLECTION_CONFIG = {
    "cities": ["北京", "上海"],
    "include_unknown_location": False,
    "max_retries": 1,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _job(
    job_id: str,
    *,
    platform: str = "test",
    title: str | None = "AI测试工程师",
    description: str | None = "",
    requirements: str | None = "",
    education: str | None = "",
    experience: str | None = "",
) -> JobPosting:
    return JobPosting(
        job_id=job_id,
        platform=platform,
        company="测试公司",
        title=title,  # type: ignore[arg-type]
        description=description,  # type: ignore[arg-type]
        requirements=requirements,  # type: ignore[arg-type]
        education=education,  # type: ignore[arg-type]
        experience=experience,  # type: ignore[arg-type]
    )


def test_filter_handles_missing_jd_fields_without_crashing():
    """Missing optional JD fields are empty values; a missing title is rejected."""
    job = _job(
        "missing-optional",
        description=None,
        requirements=None,
        education=None,
        experience=None,
    )
    assert classify_strict(job) == "大模型/AI测试"
    assert classify_strict(_job("missing-title", title=None)) is None


def test_detail_failure_keeps_list_job_and_continues(monkeypatch):
    """One failed detail request must not remove or mutate another list record."""
    calls: list[str] = []

    def fetch(job: JobPosting) -> str | None:
        calls.append(job.job_id)
        if job.job_id == "failed":
            raise TimeoutError("detail page timed out")
        return "完整职位描述" * 20

    from src.pipeline import detail_fetcher

    monkeypatch.setitem(detail_fetcher._REGISTRY, "contract-platform", fetch)
    failed = _job(
        "failed",
        platform="contract-platform",
        description="列表页摘要",
    )
    succeeded = _job("succeeded", platform="contract-platform")

    result = enrich_with_details(
        [failed, succeeded],
        http_max_workers=1,
        min_desc_len=50,
    )

    assert result == [failed, succeeded]
    assert calls == ["failed", "succeeded"]
    assert failed.description == "列表页摘要"
    assert len(succeeded.description) >= 50


def test_tencent_schema_change_is_reported_in_manifest():
    """HTTP 200 with an incompatible Posts type must never look complete."""
    collector = TencentRawCollector(
        {
            "name": "腾讯",
            "list_api": "https://example.test/tencent",
            "page_size": 20,
        },
        COLLECTION_CONFIG,
        _client(
            lambda _: httpx.Response(
                200,
                json={
                    "Code": 200,
                    "Data": {
                        "Count": 1,
                        "Posts": {"unexpected": "object-not-list"},
                    },
                },
            )
        ),
    )

    result = collector.collect()

    assert result.jobs == []
    assert result.manifest.complete is False
    assert result.manifest.status in {"error", "partial"}
    assert result.manifest.stopped_by == "error"
    assert result.manifest.error


def test_filter_config_reload_replaces_and_resets_injected_rules():
    """Rule changes must take effect immediately and reset must discard injection."""
    job = _job("config-change", requirements="要求5年以上工作经验")
    try:
        reload_filter_rules({"filter_rules": {"max_experience_years": 5}})
        assert classify_strict(job) == "大模型/AI测试"

        reload_filter_rules({"filter_rules": {"max_experience_years": 3}})
        assert classify_strict(job) is None

        reload_filter_rules({"filter_rules": {"max_experience_years": 5}})
        assert classify_strict(job) == "大模型/AI测试"

        reload_filter_rules()
        assert classify_strict(job) is None
    finally:
        # Keep this contract test isolated even when the reset assertion exposes
        # stale injected state in the production implementation.
        filter_module._INJECTED_RULES.clear()
        filter_module._load_rules_from_config.cache_clear()


def test_dedup_keeps_richest_duplicate_without_merging_missing_ids():
    """Real duplicate IDs collapse; unrelated missing-ID jobs remain distinct."""
    short = _job("same-id", description="短")
    rich = _job("same-id", description="完整职位描述" * 20)
    missing_a = _job("", title="AI测试工程师")
    missing_b = _job("", title="Agent评测工程师")

    result = deduplicate([short, rich, missing_a, missing_b])

    assert len(result) == 3
    assert {job.title for job in result if not job.job_id} == {
        "AI测试工程师",
        "Agent评测工程师",
    }
    kept = next(job for job in result if job.job_id == "same-id")
    assert kept.description == rich.description


def test_baidu_second_page_failure_is_partial_and_keeps_first_page():
    """A mid-pagination failure preserves fetched data but cannot claim success."""
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(parse_qs(request.content.decode())["curPage"][0])
        if page == 2:
            return httpx.Response(500, json={"message": "temporary failure"})
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "total": "2",
                    "pages": 2,
                    "list": [
                        {
                            "name": "AI测试工程师",
                            "postId": "post-1",
                            "workPlace": "北京市",
                        }
                    ],
                },
            },
        )

    collector = BaiduRawCollector(
        {
            "name": "百度",
            "list_url": "https://example.test/social-list",
            "list_api": "https://example.test/getPostListNew",
            "detail_url": "https://example.test/detail/{job_id}",
            "page_size": 1,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )

    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["post-1"]
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert result.manifest.pages_fetched == 1
    assert result.manifest.records_fetched == 1
    assert result.manifest.stopped_by == "error"
    assert "500" in result.manifest.error
