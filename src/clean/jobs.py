from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

CITY_SEPARATOR_PATTERN = re.compile(r"[、,，/]")


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


def summarize_city_companies(
    jobs: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Count normalized city occurrences by company."""
    companies_by_city: dict[str, Counter[str]] = defaultdict(Counter)
    for job in jobs:
        company = _normalized_text(job.get("company"))
        for city in clean_cities(
            job.get("location"),
            strip_province=job.get("platform") == "jd",
        ):
            companies_by_city[city][company] += 1

    return {
        city: dict(sorted(companies_by_city[city].items()))
        for city in sorted(companies_by_city)
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


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, path)


def run_clean_jobs(
    input_path: Path,
    *,
    output_path: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    jobs = load_jobs(input_path)
    company_city = summarize_city_companies(jobs)
    company_education = summarize_company_field_counts(jobs, "education")
    company_experience = summarize_company_field_counts(jobs, "experience")
    report = {
        "manifest": {
            "generated_at": generated_at
            or datetime.now().astimezone().isoformat(timespec="seconds"),
            "input_file": str(input_path),
            "output_file": str(output_path),
            "job_count": len(jobs),
            "city_count_before_dedup": sum(
                count
                for companies in company_city.values()
                for count in companies.values()
            ),
        },
        "company_city": company_city,
        "company_education": company_education,
        "company_experience": company_experience,
    }
    _write_json_atomic(output_path, report)
    return report
