"""Highest-priority resilience contracts for the legacy business pipeline.

These tests intentionally describe the desired behavior at external-data
boundaries.  They may expose gaps in the current implementation; business code
must not be changed merely to make the test setup more permissive.
"""
from __future__ import annotations

from src.models import JobPosting
from src.legacy.pipeline import filter as filter_module
from src.legacy.pipeline.dedup import deduplicate
from src.legacy.pipeline.detail_fetcher import enrich_with_details
from src.legacy.pipeline.filter import classify_strict, reload_filter_rules


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

    from src.legacy.pipeline import detail_fetcher

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
