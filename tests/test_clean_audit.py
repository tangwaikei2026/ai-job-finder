from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from src.clean.audit import (
    MAX_SAMPLES,
    SHORT_DESCRIPTION_MIN_LENGTH,
    audit_jobs,
    run_audit,
)


def _job(**overrides: object) -> dict[str, object]:
    job: dict[str, object] = {
        "job_id": "job-1",
        "platform": "example",
        "title": "AI Engineer",
        "company": "Example",
        "department": "AI",
        "location": "Shanghai",
        "experience": "3 years",
        "education": "Bachelor",
        "salary": "30k",
        "description": "D" * SHORT_DESCRIPTION_MIN_LENGTH,
        "requirements": "Python",
        "url": "https://example.com/jobs/1",
        "scraped_at": "2026-07-06 10:00:00",
    }
    job.update(overrides)
    return job


def _audit(jobs: list[dict[str, object]]) -> dict[str, object]:
    return audit_jobs(
        jobs,
        input_file="data/raw/2026-07-06.json",
        generated_at="2026-07-06T12:00:00+08:00",
    )


def test_audit_counts_missing_required_and_optional_fields() -> None:
    jobs = [
        _job(
            job_id="",
            description=None,
            location="",
            url=None,
            department=" ",
            salary=None,
        ),
        _job(job_id="job-2"),
    ]

    report = _audit(jobs)
    issues = report["issues"]

    assert issues["missing_required_fields"]["count"] == 4
    assert issues["missing_required_fields"]["by_field"]["job_id"]["count"] == 1
    assert (
        issues["missing_required_fields"]["by_field"]["description"]["count"]
        == 1
    )
    assert issues["missing_required_fields"]["by_field"]["location"]["count"] == 1
    assert issues["missing_required_fields"]["by_field"]["url"]["count"] == 1
    assert issues["missing_optional_fields"]["count"] == 2
    assert (
        issues["missing_optional_fields"]["by_field"]["department"]["count"]
        == 1
    )
    assert issues["missing_optional_fields"]["by_field"]["salary"]["count"] == 1
    assert issues["missing_optional_fields"]["missing_fields"] == {
        "department": 1,
        "experience": 0,
        "education": 0,
        "salary": 1,
        "requirements": 0,
    }
    optional_sample = issues["missing_optional_fields"]["samples"][0]
    assert optional_sample["missing_fields"] == ["department", "salary"]
    assert all(
        len(field_issue["samples"]) <= MAX_SAMPLES
        for field_issue in issues["missing_required_fields"]["by_field"].values()
    )


def test_optional_missing_samples_include_two_per_affected_platform() -> None:
    jobs = [
        _job(
            job_id=f"{platform}-{number}",
            platform=platform,
            department="",
            salary="",
            requirements="",
        )
        for platform in ("example", "other")
        for number in range(3)
    ]

    issue = _audit(jobs)["issues"]["missing_optional_fields"]
    samples = issue["samples"]

    assert Counter(
        sample["platform"]
        for sample in samples
    ) == {"example": 2, "other": 2}
    assert len(samples) == 4
    assert all(
        sample["missing_fields"] == ["department", "salary", "requirements"]
        for sample in samples
    )


def test_audit_counts_duplicate_keys_as_records_after_first() -> None:
    jobs = [
        _job(),
        _job(),
        _job(),
        _job(platform="other"),
    ]

    issues = _audit(jobs)["issues"]

    assert issues["duplicate_platform_job_id"]["count"] == 2
    assert issues["duplicate_platform_job_id"]["group_count"] == 1
    assert issues["suspected_duplicate_company_title_location"]["count"] == 3
    assert (
        issues["suspected_duplicate_company_title_location"]["group_count"]
        == 1
    )
    suspected_sample = issues[
        "suspected_duplicate_company_title_location"
    ]["samples"][0]
    assert [row["url"] for row in suspected_sample["rows"]] == [
        "https://example.com/jobs/1",
    ] * 4
    assert suspected_sample["platforms"] == ["example", "other"]


def test_suspected_duplicate_key_includes_description() -> None:
    jobs = [
        _job(job_id="job-1", description="Description A"),
        _job(job_id="job-2", description="Description B"),
    ]

    issue = _audit(jobs)["issues"][
        "suspected_duplicate_company_title_location"
    ]

    assert issue["count"] == 0
    assert issue["group_count"] == 0
    assert issue["samples"] == []


def test_suspected_duplicate_samples_cover_every_affected_platform() -> None:
    jobs = []
    for group_number in range(MAX_SAMPLES + 1):
        platform = "other" if group_number == MAX_SAMPLES else "example"
        for duplicate_number in range(2):
            jobs.append(
                _job(
                    job_id=f"{group_number}-{duplicate_number}",
                    platform=platform,
                    title=f"Title {group_number}",
                )
            )

    samples = _audit(jobs)["issues"][
        "suspected_duplicate_company_title_location"
    ]["samples"]

    sampled_platform_counts = Counter(
        row["platform"]
        for sample in samples
        for row in sample["rows"]
    )
    assert sampled_platform_counts == {"example": 2, "other": 2}
    assert len(samples) == 2


def test_audit_counts_short_and_empty_descriptions() -> None:
    short_description = "D" * (SHORT_DESCRIPTION_MIN_LENGTH - 1)
    jobs = [
        _job(description=short_description, requirements=""),
        _job(job_id="job-2", description=" ", requirements=""),
        _job(
            job_id="job-3",
            platform="other",
            description=short_description,
            requirements="",
        ),
        _job(
            job_id="job-4",
            platform="other",
            description=short_description,
            requirements="",
        ),
        _job(
            job_id="job-5",
            platform="other",
            description=short_description,
            requirements="",
        ),
        _job(job_id="job-6", description="D" * SHORT_DESCRIPTION_MIN_LENGTH),
    ]

    issues = _audit(jobs)["issues"]

    assert issues["description_too_short"]["count"] == 5
    assert issues["description_and_requirements_empty"]["count"] == 1
    short_sample = issues["description_too_short"]["samples"][0]
    assert short_sample["description"] == short_description
    assert short_sample["url"] == "https://example.com/jobs/1"
    assert "description_length" not in short_sample
    assert Counter(
        sample["platform"]
        for sample in issues["description_too_short"]["samples"]
    ) == {"example": 2, "other": 2}


def test_audit_counts_missing_and_invalid_urls() -> None:
    jobs = [
        _job(url=""),
        _job(job_id="job-2", url="ftp://example.com/job/2"),
        _job(job_id="job-3", url="https://example.com/job/3"),
        _job(job_id="job-4", url="http://example.com/job/4"),
    ]

    issue = _audit(jobs)["issues"]["invalid_or_missing_url"]

    assert issue["count"] == 2
    assert [sample["url"] for sample in issue["samples"]] == [
        "",
        "ftp://example.com/job/2",
    ]


def test_run_audit_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.json"
    input_path.write_text(
        json.dumps(
            [
                _job(department="", salary=""),
                _job(job_id="job-2", department="", requirements=""),
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    json_path, markdown_path, report = run_audit(
        input_path,
        audit_date="2026-07-06",
        output_dir=tmp_path / "audit",
    )

    assert json_path.exists()
    assert markdown_path.exists()
    stored = json.loads(json_path.read_text(encoding="utf-8"))
    assert stored["manifest"]["input_file"] == str(input_path)
    assert stored["manifest"]["job_count"] == 2
    assert stored["manifest"]["issue_counts"] == report["manifest"][
        "issue_counts"
    ]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# RawJobPosting 数据质量报告" in markdown
    assert "### 按平台岗位样例（每个平台 2 条，不足则全部）" in markdown
    assert "| 缺失字段 |" in markdown
    assert "department, salary" in markdown
    assert "department, requirements" in markdown
