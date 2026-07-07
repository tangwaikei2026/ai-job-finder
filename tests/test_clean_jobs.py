from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.clean.jobs import (
    clean_cities,
    load_jobs,
    run_clean_jobs,
    summarize_company_field_counts,
    summarize_city_companies,
)


def test_clean_cities_supports_all_separators_and_city_suffix() -> None:
    assert clean_cities("北京市、上海市, 深圳市，广州市/杭州市") == [
        "北京",
        "上海",
        "深圳",
        "广州",
        "杭州",
    ]


def test_summarize_city_companies_counts_each_city_by_company() -> None:
    jobs = [
        {"company": "甲公司", "location": "北京市、上海市"},
        {"company": "甲公司", "location": "北京/深圳市"},
        {"company": "乙公司", "location": "杭州市，杭州市"},
    ]

    assert summarize_city_companies(jobs) == {
        "上海": {"甲公司": 1},
        "北京": {"甲公司": 2},
        "杭州": {"乙公司": 2},
        "深圳": {"甲公司": 1},
    }


def test_jd_strips_province_suffix_without_affecting_other_platforms() -> None:
    jobs = [
        {"platform": "jd", "company": "京东", "location": "广东省/浙江省"},
        {"platform": "other", "company": "其他", "location": "广东省/浙江省"},
    ]

    assert summarize_city_companies(jobs) == {
        "广东": {"京东": 1},
        "广东省": {"其他": 1},
        "浙江": {"京东": 1},
        "浙江省": {"其他": 1},
    }


def test_summarize_company_field_counts_deduplicates_and_counts() -> None:
    jobs = [
        {"company": "甲公司", "education": " 本科 "},
        {"company": "甲公司", "education": "本科"},
        {"company": "甲公司", "education": "硕士"},
        {"company": "乙公司", "education": ""},
    ]

    assert summarize_company_field_counts(jobs, "education") == {
        "乙公司": {"<missing>": 1},
        "甲公司": {"本科": 2, "硕士": 1},
    }


def test_run_clean_jobs_writes_output_without_changing_input(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "clean" / "jobs.json"
    raw_content = json.dumps(
        [
            {
                "company": "甲公司",
                "location": "北京市/上海市",
                "education": "本科",
                "experience": "三年以上",
            }
        ],
        ensure_ascii=False,
    )
    input_path.write_text(raw_content, encoding="utf-8")

    report = run_clean_jobs(
        input_path,
        output_path=output_path,
        generated_at="2026-07-06T12:00:00+08:00",
    )

    assert input_path.read_text(encoding="utf-8") == raw_content
    assert json.loads(output_path.read_text(encoding="utf-8")) == report
    assert report["manifest"] == {
        "generated_at": "2026-07-06T12:00:00+08:00",
        "input_file": str(input_path),
        "output_file": str(output_path),
        "job_count": 1,
        "city_count_before_dedup": 2,
    }
    assert report["company_city"] == {
        "上海": {"甲公司": 1},
        "北京": {"甲公司": 1},
    }
    assert report["company_education"] == {"甲公司": {"本科": 1}}
    assert report["company_experience"] == {"甲公司": {"三年以上": 1}}
    assert "company_cities" not in report
    assert "jobs" not in report


def test_load_jobs_rejects_structural_changes(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.json"
    input_path.write_text('{"not": "a list"}', encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON array"):
        load_jobs(input_path)
