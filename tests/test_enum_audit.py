from __future__ import annotations

import csv
import json
from pathlib import Path

from src.audit.enum_audit import audit_api_enums, run_enum_audit


def _job(**overrides: object) -> dict[str, object]:
    job: dict[str, object] = {
        "job_id": "job-1",
        "platform": "example",
        "title": "AI Engineer",
        "company": "Example",
        "location": "上海",
        "experience": "1-3年",
        "education": "本科",
        "salary": "30k",
        "description": "Build AI systems",
        "requirements": "Python",
        "url": "https://example.com/jobs/1",
    }
    job.update(overrides)
    return job


def _write_jobs(path: Path, jobs: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")


def _audit(jobs: list[dict[str, object]]) -> dict[str, object]:
    _, health, _ = audit_api_enums(
        jobs,
        audit_date="2026-07-07",
        input_file="data/clean/2026-07-07.json",
        generated_at="2026-07-07 12:00:00",
    )
    return health


def test_default_outputs_health_and_exceptions_without_full_json(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "2026-07-07.json"
    output_dir = tmp_path / "audit"
    _write_jobs(input_path, [_job()])

    health_path, exceptions_path, full_path, health = run_enum_audit(
        input_path,
        audit_date="2026-07-07",
        output_dir=output_dir,
    )

    assert health_path == output_dir / "2026-07-07_enum_health.json"
    assert exceptions_path == output_dir / "2026-07-07_enum_exceptions.csv"
    assert full_path is None
    assert health_path.exists()
    assert exceptions_path.exists()
    assert not (output_dir / "2026-07-07_enum_audit_full.json").exists()
    assert health["status"] == "pass"


def test_debug_full_outputs_full_audit_json(tmp_path: Path) -> None:
    input_path = tmp_path / "2026-07-07.json"
    output_dir = tmp_path / "audit"
    _write_jobs(input_path, [_job()])

    _, _, full_path, _ = run_enum_audit(
        input_path,
        audit_date="2026-07-07",
        output_dir=output_dir,
        debug_full=True,
    )

    assert full_path == output_dir / "2026-07-07_enum_audit_full.json"
    assert full_path.exists()
    full_report = json.loads(full_path.read_text(encoding="utf-8"))
    assert full_report["by_platform"]["example"]["education"]["本科"][
        "samples"
    ][0]["url"] == "https://example.com/jobs/1"


def test_known_enums_are_counted_as_known() -> None:
    health = _audit([_job(education="本科", experience="三年以上工作经验")])

    assert health["education"]["known_count"] == 1
    assert health["experience"]["known_count"] == 1
    assert health["status"] == "pass"


def test_missing_marker_is_counted_as_missing() -> None:
    health = _audit([_job(education="<missing>", experience="<missing>")])

    assert health["education"]["missing_count"] == 1
    assert health["experience"]["missing_count"] == 1
    assert health["education"]["unknown_count"] == 0
    assert health["experience"]["unknown_count"] == 0
    assert health["status"] == "pass"


def test_configured_invalid_value_counts_invalid_but_does_not_fail() -> None:
    raw_value = "{'from': None, 'to': 0}"

    health = _audit([_job(experience=raw_value)])

    assert health["experience"]["invalid_count"] == 1
    assert health["experience"]["invalid_values"] == {
        raw_value: "https://example.com/jobs/1"
    }
    assert health["signals"]["invalid_enum_found"] is True
    assert health["status"] == "pass"
    assert health["blocking_reasons"] == []


def test_unknown_enum_is_written_to_exceptions_csv(tmp_path: Path) -> None:
    input_path = tmp_path / "2026-07-07.json"
    output_dir = tmp_path / "audit"
    _write_jobs(input_path, [_job(education="高中")])

    _, exceptions_path, _, health = run_enum_audit(
        input_path,
        audit_date="2026-07-07",
        output_dir=output_dir,
    )
    with exceptions_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert health["education"]["unknown_count"] == 1
    assert rows == [
        {
            "date": "2026-07-07",
            "platform": "example",
            "field": "education",
            "raw_value": "高中",
            "count": "1",
            "sample_url": "https://example.com/jobs/1",
        }
    ]


def test_unknown_enum_fails_health_status() -> None:
    health = _audit([_job(education="高中")])

    assert health["status"] == "fail"
    assert health["can_continue_to_batch_b"] is False
    assert health["can_continue_to_clean_v2"] is False
    assert health["signals"]["new_unknown_enum_found"] is True
    assert health["blocking_reasons"] == ["unknown API enum values found"]


def test_zero_jobs_fails_health_status() -> None:
    health = _audit([])

    assert health["status"] == "fail"
    assert health["can_continue_to_batch_b"] is False
    assert health["can_continue_to_clean_v2"] is False
    assert health["blocking_reasons"] == ["job_count is zero"]


def test_health_includes_batch_b_and_clean_v2_flags() -> None:
    health = _audit([_job()])

    assert health["can_continue_to_batch_b"] is True
    assert health["can_continue_to_clean_v2"] is True


def test_exceptions_csv_contains_only_exceptions(tmp_path: Path) -> None:
    input_path = tmp_path / "2026-07-07.json"
    output_dir = tmp_path / "audit"
    _write_jobs(
        input_path,
        [
            _job(job_id="job-known", education="本科", experience="1-3年"),
            _job(job_id="job-unknown", education="高中", experience="1-3年"),
        ],
    )

    _, exceptions_path, _, _ = run_enum_audit(
        input_path,
        audit_date="2026-07-07",
        output_dir=output_dir,
    )
    with exceptions_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert [row["raw_value"] for row in rows] == ["高中"]
