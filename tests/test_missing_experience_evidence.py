from __future__ import annotations

from src.audit.missing_evidence import extract_missing_evidence


def _job(**overrides: object) -> dict[str, object]:
    job: dict[str, object] = {
        "job_id": "job-1",
        "platform": "example",
        "title": "AI Engineer",
        "company": "Example",
        "education": "本科",
        "experience": "<missing>",
        "description": "",
        "requirements": "",
        "url": "https://example.com/jobs/1",
    }
    job.update(overrides)
    return job


def _experience_rows(job: dict[str, object]) -> list[dict[str, object]]:
    result = extract_missing_evidence(
        [job],
        input_file="data/clean/2026-07-08.json",
        generated_at="2026-07-08 12:00:00",
    )
    return result["experience_rows"]


def test_year_range_experience_evidence() -> None:
    rows = _experience_rows(_job(requirements="需要3-5年工作经验"))

    assert rows[0]["suggested_value"] == "3-5年"
    assert rows[0]["min_years"] == 3
    assert rows[0]["max_years"] == 5


def test_min_years_experience_evidence() -> None:
    rows = _experience_rows(_job(requirements="3年以上产品经验"))

    assert rows[0]["suggested_value"] == "3年以上"
    assert rows[0]["min_years"] == 3
    assert rows[0]["max_years"] == ""


def test_chinese_three_years_experience_evidence() -> None:
    rows = _experience_rows(_job(requirements="三年以上工作经验"))

    assert rows[0]["suggested_value"] == "3年以上"


def test_chinese_two_years_related_experience_evidence() -> None:
    rows = _experience_rows(_job(requirements="两年以上相关经验"))

    assert rows[0]["suggested_value"] == "2年以上"


def test_no_requirement_experience_evidence() -> None:
    rows = _experience_rows(_job(requirements="经验不限"))

    assert rows[0]["suggested_value"] == "no_requirement"


def test_fresh_graduate_experience_evidence() -> None:
    rows = _experience_rows(_job(requirements="应届毕业生"))

    assert rows[0]["suggested_value"] == "fresh_graduate"
    assert rows[0]["min_years"] == 0
    assert rows[0]["max_years"] == 1


def test_multiple_experience_mentions_are_preserved() -> None:
    rows = _experience_rows(_job(requirements="5年以上互联网经验，3年以上 AI 产品经验"))

    assert [row["suggested_value"] for row in rows] == ["5年以上", "3年以上"]


def test_project_count_is_not_experience_evidence() -> None:
    rows = _experience_rows(_job(requirements="负责 3 个项目"))

    assert rows == []


def test_team_size_is_not_experience_evidence() -> None:
    rows = _experience_rows(_job(requirements="管理 5 人团队"))

    assert rows == []


def test_existing_api_experience_is_skipped() -> None:
    rows = _experience_rows(_job(experience="3-5年", requirements="3年以上产品经验"))

    assert rows == []
