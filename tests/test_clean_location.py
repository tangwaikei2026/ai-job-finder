from __future__ import annotations

import json
from pathlib import Path

from src.clean.jobs import normalize_locations, run_clean_jobs


def test_guangdong_aliases_normalize_to_province_not_city() -> None:
    assert normalize_locations("广东/广东省") == {
        "locations_norm": ["广东省"],
        "location_level": ["province"],
        "province_norm": ["广东省"],
        "city_norm": [],
    }


def test_hong_kong_aliases_normalize_to_region() -> None:
    assert normalize_locations("中国香港/香港特别行政区") == {
        "locations_norm": ["香港"],
        "location_level": ["region"],
        "province_norm": [],
        "city_norm": [],
    }


def test_unknown_location_is_preserved_as_unknown_level() -> None:
    assert normalize_locations("") == {
        "locations_norm": ["unknown"],
        "location_level": ["unknown"],
        "province_norm": [],
        "city_norm": [],
    }
    assert normalize_locations("火星基地") == {
        "locations_norm": ["unknown"],
        "location_level": ["unknown"],
        "province_norm": [],
        "city_norm": [],
    }


def test_clean_report_counts_city_and_province_only_jobs(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "clean" / "2026-07-07.clean.json"
    jobs = [
        {"company": "甲公司", "location": "深圳市"},
        {"company": "乙公司", "location": "广东/广东省"},
        {"company": "丙公司", "location": "中国香港/香港特别行政区"},
        {"company": "丁公司", "location": "unknown"},
    ]
    input_path.write_text(
        json.dumps(jobs, ensure_ascii=False),
        encoding="utf-8",
    )

    report = run_clean_jobs(
        input_path,
        output_path=output_path,
        generated_at="2026-07-07T12:00:00+08:00",
    )
    clean_jobs = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(clean_jobs) == 4
    assert report["manifest"]["job_count"] == 4
    assert report["manifest"]["city_count"] == 1
    assert report["manifest"]["province_only_count"] == 1
    assert report["company_city"] == {"深圳": {"甲公司": 1}}
    assert report["company_province"] == {"广东省": {"乙公司": 1}}
