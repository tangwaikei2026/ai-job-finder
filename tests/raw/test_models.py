from __future__ import annotations

import json

from src.raw.models import (
    CollectionManifest,
    CollectionResult,
    RawJobPosting,
    write_json_atomic,
)


def _job() -> RawJobPosting:
    return RawJobPosting(
        job_id="job-1",
        platform="example",
        title="AI 测试工程师",
        company="示例公司",
        location="上海",
        scraped_at="2026-07-03 12:00:00",
    )


def test_raw_job_posting_to_dict() -> None:
    job = _job()

    assert job.to_dict() == {
        "job_id": "job-1",
        "platform": "example",
        "title": "AI 测试工程师",
        "company": "示例公司",
        "department": "",
        "location": "上海",
        "experience": "",
        "education": "",
        "salary": "",
        "description": "",
        "requirements": "",
        "url": "",
        "scraped_at": "2026-07-03 12:00:00",
    }


def test_raw_job_posting_unique_key() -> None:
    assert _job().unique_key == "example:job-1"


def test_collection_manifest_to_dict() -> None:
    manifest = CollectionManifest(
        platform="example",
        name="示例平台",
        status="success",
        complete=True,
        source_total=2,
        jobs_in_scope=1,
        started_at="2026-07-03 12:00:00",
        finished_at="2026-07-03 12:00:01",
        duration_seconds=1.0,
    )

    serialized = manifest.to_dict()

    assert serialized["platform"] == "example"
    assert serialized["status"] == "success"
    assert serialized["complete"] is True
    assert serialized["source_total"] == 2
    assert serialized["jobs_in_scope"] == 1
    assert serialized["duration_seconds"] == 1.0


def test_collection_result_combines_jobs_and_manifest() -> None:
    job = _job()
    manifest = CollectionManifest(platform="example", name="示例平台")

    result = CollectionResult(jobs=[job], manifest=manifest)

    assert result.jobs == [job]
    assert result.manifest is manifest


def test_write_json_atomic_writes_valid_json(tmp_path) -> None:
    output_path = tmp_path / "nested" / "jobs.json"
    payload = {"jobs": [_job().to_dict()]}

    write_json_atomic(output_path, payload)

    with open(output_path, encoding="utf-8") as output_file:
        assert json.load(output_file) == payload
    assert not output_path.with_suffix(".json.tmp").exists()
