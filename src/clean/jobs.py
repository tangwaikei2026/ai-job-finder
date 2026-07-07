from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

CITY_SEPARATOR_PATTERN = re.compile(r"[、,，/]")

CITY_ALIASES = {
    "北京": "北京",
    "北京市": "北京",
    "上海": "上海",
    "上海市": "上海",
    "深圳": "深圳",
    "深圳市": "深圳",
    "广州": "广州",
    "广州市": "广州",
}
PROVINCE_ALIASES = {
    "广东": "广东省",
    "广东省": "广东省",
}
REGION_ALIASES = {
    "中国香港": "香港",
    "香港特别行政区": "香港",
    "香港": "香港",
}
COUNTRY_ALIASES = {
    "中国": "中国",
}
KNOWN_LOCATION_NAMES = {
    *CITY_ALIASES.values(),
    *PROVINCE_ALIASES.values(),
    *REGION_ALIASES.values(),
    *COUNTRY_ALIASES.values(),
}


def _normalized_text(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "<missing>"


def clean_cities(value: Any, *, strip_province: bool = False) -> list[str]:
    """Split and normalize cities while preserving their input order."""
    if not isinstance(value, str):
        return []

    cities = []
    for part in CITY_SEPARATOR_PATTERN.split(value):
        city = part.strip()
        if city.endswith("市"):
            city = city[:-1].strip()
        if strip_province and city.endswith("省"):
            city = city[:-1].strip()
        if city:
            cities.append(city)
    return cities


def _split_locations(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [
        part.strip()
        for part in CITY_SEPARATOR_PATTERN.split(value)
        if part.strip()
    ]


def normalize_location_part(value: str) -> tuple[str, str]:
    """Return normalized location name and level for one raw token."""
    location = value.strip()
    if not location:
        return "unknown", "unknown"
    if location in CITY_ALIASES:
        return CITY_ALIASES[location], "city"
    if location in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[location], "province"
    if location in REGION_ALIASES:
        return REGION_ALIASES[location], "region"
    if location in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[location], "country"
    if location.endswith("市"):
        return location[:-1].strip(), "city"
    if location.endswith("省"):
        return location, "province"
    if location in KNOWN_LOCATION_NAMES:
        if location in CITY_ALIASES.values():
            return location, "city"
        if location in PROVINCE_ALIASES.values():
            return location, "province"
        if location in REGION_ALIASES.values():
            return location, "region"
        if location in COUNTRY_ALIASES.values():
            return location, "country"
    return "unknown", "unknown"


def normalize_locations(value: Any) -> dict[str, list[str]]:
    """Normalize a raw location field without dropping any job row."""
    names: list[str] = []
    levels: list[str] = []
    for part in _split_locations(value):
        name, level = normalize_location_part(part)
        if name == "unknown" and "unknown" in names:
            continue
        names.append(name)
        levels.append(level)

    if not names:
        names = ["unknown"]
        levels = ["unknown"]

    deduped_names: list[str] = []
    deduped_levels: list[str] = []
    seen_names = set()
    for name, level in zip(names, levels, strict=True):
        if name in seen_names:
            continue
        seen_names.add(name)
        deduped_names.append(name)
        deduped_levels.append(level)

    return {
        "locations_norm": deduped_names,
        "location_level": deduped_levels,
        "province_norm": [
            name
            for name, level in zip(deduped_names, deduped_levels, strict=True)
            if level == "province"
        ],
        "city_norm": [
            name
            for name, level in zip(deduped_names, deduped_levels, strict=True)
            if level == "city"
        ],
    }


def clean_job_locations(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_jobs = []
    for job in jobs:
        clean_job = dict(job)
        clean_job.update(normalize_locations(job.get("location")))
        clean_jobs.append(clean_job)
    return clean_jobs


def summarize_city_companies(
    jobs: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Count normalized city occurrences by company."""
    companies_by_city: dict[str, Counter[str]] = defaultdict(Counter)
    for job in jobs:
        company = _normalized_text(job.get("company"))
        cities = job.get("city_norm")
        if not isinstance(cities, list):
            cities = normalize_locations(job.get("location"))["city_norm"]
        for city in cities:
            companies_by_city[city][company] += 1

    return {
        city: dict(sorted(companies_by_city[city].items()))
        for city in sorted(companies_by_city)
    }


def summarize_province_companies(
    jobs: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Count normalized province occurrences by company."""
    companies_by_province: dict[str, Counter[str]] = defaultdict(Counter)
    for job in jobs:
        company = _normalized_text(job.get("company"))
        provinces = job.get("province_norm")
        if not isinstance(provinces, list):
            provinces = normalize_locations(job.get("location"))["province_norm"]
        for province in provinces:
            companies_by_province[province][company] += 1

    return {
        province: dict(sorted(companies_by_province[province].items()))
        for province in sorted(companies_by_province)
    }


def summarize_company_field_counts(
    jobs: list[dict[str, Any]],
    field_name: str,
) -> dict[str, dict[str, int]]:
    """Count unique normalized field values by company."""
    values_by_company: dict[str, Counter[str]] = defaultdict(Counter)
    for job in jobs:
        company = _normalized_text(job.get("company"))
        value = _normalized_text(job.get(field_name))
        values_by_company[company][value] += 1

    return {
        company: dict(sorted(values_by_company[company].items()))
        for company in sorted(values_by_company)
    }


def load_jobs(input_path: Path) -> list[dict[str, Any]]:
    with input_path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{input_path} must contain a JSON array")
    for row_number, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"{input_path} row {row_number} must be a JSON object"
            )
    return data


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, path)


def _default_report_path(output_path: Path) -> Path:
    if output_path.name.endswith(".clean.json"):
        return output_path.with_name(
            output_path.name.removesuffix(".clean.json") + ".clean_report.json"
        )
    return output_path.with_name(output_path.stem + "_report.json")


def _build_report(
    clean_jobs: list[dict[str, Any]],
    *,
    input_path: Path,
    output_path: Path,
    report_path: Path,
    generated_at: str | None,
) -> dict[str, Any]:
    company_city = summarize_city_companies(clean_jobs)
    company_province = summarize_province_companies(clean_jobs)
    company_education = summarize_company_field_counts(clean_jobs, "education")
    company_experience = summarize_company_field_counts(clean_jobs, "experience")
    return {
        "manifest": {
            "generated_at": generated_at
            or datetime.now().astimezone().isoformat(timespec="seconds"),
            "input_file": str(input_path),
            "output_file": str(output_path),
            "report_file": str(report_path),
            "job_count": len(clean_jobs),
            "city_count": sum(len(job["city_norm"]) for job in clean_jobs),
            "province_only_count": sum(
                1
                for job in clean_jobs
                if job["province_norm"]
                and all(level == "province" for level in job["location_level"])
            ),
        },
        "company_city": company_city,
        "company_province": company_province,
        "company_education": company_education,
        "company_experience": company_experience,
    }


def run_clean_jobs(
    input_path: Path,
    *,
    output_path: Path,
    report_path: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    jobs = load_jobs(input_path)
    clean_jobs = clean_job_locations(jobs)
    report_path = report_path or _default_report_path(output_path)
    report = _build_report(
        clean_jobs,
        input_path=input_path,
        output_path=output_path,
        report_path=report_path,
        generated_at=generated_at,
    )
    _write_json_atomic(output_path, clean_jobs)
    _write_json_atomic(report_path, report)
    return report
