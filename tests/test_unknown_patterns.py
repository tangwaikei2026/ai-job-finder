from __future__ import annotations

from src.audit.missing_evidence import extract_missing_evidence


def _job(**overrides: object) -> dict[str, object]:
    job: dict[str, object] = {
        "job_id": "job-1",
        "platform": "example",
        "title": "AI Engineer",
        "company": "Example",
        "education": "<missing>",
        "experience": "<missing>",
        "description": "",
        "requirements": "",
        "url": "https://example.com/jobs/1",
    }
    job.update(overrides)
    return job


def _result(job: dict[str, object]) -> dict[str, object]:
    return extract_missing_evidence(
        [job],
        input_file="data/clean/2026-07-08.json",
        generated_at="2026-07-08 12:00:00",
    )


def _unknown_rows(job: dict[str, object]) -> list[dict[str, object]]:
    return _result(job)["unknown_rows"]


def test_degree_keyword_without_supported_pattern_goes_to_unknown() -> None:
    rows = _unknown_rows(_job(requirements="学历背景优秀"))

    assert rows[0]["field"] == "education"
    assert rows[0]["reason"] == "contains_degree_keyword_but_no_hard_requirement"


def test_major_background_without_supported_pattern_goes_to_unknown() -> None:
    rows = _unknown_rows(_job(requirements="具备专业背景"))

    assert rows[0]["field"] == "education"
    assert rows[0]["reason"] == "contains_major_keyword_but_unsupported_pattern"


def test_experience_keyword_without_year_goes_to_unknown() -> None:
    rows = _unknown_rows(_job(requirements="具备丰富经验"))

    assert rows[0]["field"] == "experience"
    assert rows[0]["reason"] == "contains_experience_keyword_but_no_year"


def test_unrelated_sentence_does_not_go_to_unknown() -> None:
    rows = _unknown_rows(_job(requirements="具备良好的沟通能力"))

    assert rows == []


def test_recognized_education_evidence_is_not_unknown() -> None:
    result = _result(_job(requirements="本科及以上学历"))

    assert result["education_rows"][0]["pattern_name"] == "bachelor_plus"
    assert result["unknown_rows"] == []


def test_recognized_experience_evidence_is_not_unknown() -> None:
    result = _result(_job(requirements="3年以上工作经验", education="本科"))

    assert result["experience_rows"][0]["suggested_value"] == "3年以上"
    assert result["unknown_rows"] == []


def test_preferred_only_education_evidence_is_not_unknown() -> None:
    result = _result(_job(requirements="硕士优先"))

    assert result["education_rows"][0]["preferred"] == "硕士"
    assert result["unknown_rows"] == []


def test_major_preferred_evidence_is_not_unknown() -> None:
    result = _result(_job(requirements="人工智能专业优先"))

    assert result["education_rows"][0]["preferred"] == "人工智能专业"
    assert result["unknown_rows"] == []
