from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.clean.cli import main as clean_cli_main
from src.clean.jobs import (
    clean_cities,
    load_jobs,
    run_clean_jobs,
    summarize_company_field_counts,
    summarize_city_companies,
    summarize_province_companies,
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
        "杭州": {"乙公司": 1},
        "深圳": {"甲公司": 1},
    }


def test_province_locations_are_not_counted_as_cities() -> None:
    jobs = [
        {
            "company": "甲公司",
            "location": "广东省/深圳市",
            "city_norm": ["深圳"],
            "province_norm": ["广东省"],
        },
        {
            "company": "乙公司",
            "location": "广东",
            "city_norm": [],
            "province_norm": ["广东省"],
        },
    ]

    assert summarize_city_companies(jobs) == {
        "深圳": {"甲公司": 1},
    }
    assert summarize_province_companies(jobs) == {
        "广东省": {"乙公司": 1, "甲公司": 1},
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
    output_path = tmp_path / "clean" / "2026-07-07.clean.json"
    report_path = tmp_path / "clean" / "2026-07-07.clean_report.json"
    raw_content = json.dumps(
        [
            {
                "company": "甲公司",
                "location": "北京市/上海市/广东",
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
        report_path=report_path,
        generated_at="2026-07-06T12:00:00+08:00",
    )

    assert input_path.read_text(encoding="utf-8") == raw_content
    clean_jobs = json.loads(output_path.read_text(encoding="utf-8"))
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert len(clean_jobs) == 1
    assert clean_jobs[0]["locations_norm"] == ["北京", "上海", "广东省"]
    assert clean_jobs[0]["location_level"] == ["city", "city", "province"]
    assert clean_jobs[0]["city_norm"] == ["北京", "上海"]
    assert clean_jobs[0]["province_norm"] == ["广东省"]
    assert report["manifest"] == {
        "generated_at": "2026-07-06T12:00:00+08:00",
        "input_file": str(input_path),
        "output_file": str(output_path),
        "report_file": str(report_path),
        "job_count": 1,
        "city_count": 2,
        "province_only_count": 0,
    }
    assert report["company_city"] == {
        "上海": {"甲公司": 1},
        "北京": {"甲公司": 1},
    }
    assert report["company_province"] == {"广东省": {"甲公司": 1}}
    assert report["company_education"] == {"甲公司": {"本科": 1}}
    assert report["company_experience"] == {"甲公司": {"三年以上": 1}}
    assert "company_cities" not in report
    assert "jobs" not in report


def test_load_jobs_rejects_structural_changes(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.json"
    input_path.write_text('{"not": "a list"}', encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON array"):
        load_jobs(input_path)


def test_clean_cli_date_uses_analysis_compatible_filenames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "raw.json"
    output_dir = tmp_path / "clean"
    input_path.write_text(
        json.dumps(
            [{"company": "甲公司", "location": "北京"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "src.clean.cli",
            "clean-jobs",
            "--input",
            str(input_path),
            "--date",
            "2026-09-01",
            "--output-dir",
            str(output_dir),
        ],
    )

    clean_cli_main()

    assert (output_dir / "2026-09-01.json").exists()
    assert (output_dir / "2026-09-01_report.json").exists()
