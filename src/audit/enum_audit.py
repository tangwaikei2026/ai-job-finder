from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_DIR = Path("configs/normalization")
FIELD_CONFIG_FILES = {
    "education": "education_api_enums.yaml",
    "experience": "experience_api_enums.yaml",
}
EXCEPTION_CSV_FIELDS = (
    "date",
    "platform",
    "field",
    "raw_value",
    "count",
    "sample_url",
)
MAX_SAMPLES_PER_RAW_VALUE = 5
MAX_SAMPLES_PER_PLATFORM = 2


@dataclass(frozen=True)
class EnumConfig:
    missing_values: frozenset[str]
    invalid_values: frozenset[str]
    values: frozenset[str]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _load_config(path: Path) -> EnumConfig:
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    values = data.get("values") or {}
    if not isinstance(values, dict):
        raise ValueError(f"{path} values must be a mapping")
    return EnumConfig(
        missing_values=frozenset(
            _stringify(value) for value in data.get("missing_values", [])
        ),
        invalid_values=frozenset(
            _stringify(value) for value in data.get("invalid_values", [])
        ),
        values=frozenset(_stringify(value) for value in values),
    )


def load_enum_configs(config_dir: Path = DEFAULT_CONFIG_DIR) -> dict[str, EnumConfig]:
    return {
        field_name: _load_config(config_dir / file_name)
        for field_name, file_name in FIELD_CONFIG_FILES.items()
    }


def load_jobs(input_path: Path) -> list[dict[str, Any]]:
    with input_path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{input_path} must contain a JSON array")
    for row_number, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{input_path} row {row_number} must be an object")
    return data


def _looks_invalid_format(raw_value: str) -> bool:
    return (
        (raw_value.startswith("{") and raw_value.endswith("}"))
        or (raw_value.startswith("[") and raw_value.endswith("]"))
    )


def _status(raw_value: str, enum_config: EnumConfig) -> tuple[str, str]:
    if raw_value in enum_config.missing_values:
        return "missing", "raw_value is configured as missing"
    if raw_value in enum_config.values:
        return "known", "raw_value is configured API enum"
    if raw_value in enum_config.invalid_values:
        return "invalid_format", "raw_value is configured as invalid API format"
    if _looks_invalid_format(raw_value):
        return "invalid_unconfigured", "raw_value looks like an invalid API format"
    return "unknown", "raw_value is not configured"


def _sample(job: dict[str, Any]) -> dict[str, str]:
    return {
        "job_id": _stringify(job.get("job_id")),
        "title": _stringify(job.get("title")),
        "company": _stringify(job.get("company")),
        "url": _stringify(job.get("url")),
        "description": _stringify(job.get("description")),
        "requirements": _stringify(job.get("requirements")),
        "education": _stringify(job.get("education")),
        "experience": _stringify(job.get("experience")),
    }


def _append_sample(
    samples: list[dict[str, str]],
    platform_counts: dict[str, int],
    platform: str,
    sample: dict[str, str],
) -> None:
    if len(samples) >= MAX_SAMPLES_PER_RAW_VALUE:
        return
    if platform_counts.get(platform, 0) >= MAX_SAMPLES_PER_PLATFORM:
        return
    samples.append(sample)
    platform_counts[platform] = platform_counts.get(platform, 0) + 1


def _sample_url(samples: list[dict[str, str]]) -> str:
    for sample in samples:
        if sample["url"]:
            return sample["url"]
    return ""


def audit_api_enums(
    jobs: list[dict[str, Any]],
    *,
    audit_date: str,
    input_file: str,
    generated_at: str,
    configs: dict[str, EnumConfig] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    enum_configs = configs or load_enum_configs()
    summary = {
        "education_known_count": 0,
        "education_unknown_count": 0,
        "education_missing_count": 0,
        "education_invalid_count": 0,
        "experience_known_count": 0,
        "experience_unknown_count": 0,
        "experience_missing_count": 0,
        "experience_invalid_count": 0,
    }
    by_platform: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    sample_counts: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)

    for job in jobs:
        platform = _stringify(job.get("platform")) or "<missing>"
        for field_name in FIELD_CONFIG_FILES:
            raw_value = _stringify(job.get(field_name))
            status, reason = _status(raw_value, enum_configs[field_name])
            if status == "known":
                summary[f"{field_name}_known_count"] += 1
            elif status == "missing":
                summary[f"{field_name}_missing_count"] += 1
            elif status in {"invalid_format", "invalid_unconfigured"}:
                summary[f"{field_name}_invalid_count"] += 1
            else:
                summary[f"{field_name}_unknown_count"] += 1

            field_values = by_platform[platform][field_name]
            value_entry = field_values.setdefault(
                raw_value,
                {
                    "count": 0,
                    "status": status,
                    "reason": reason,
                    "samples": [],
                },
            )
            value_entry["count"] += 1
            _append_sample(
                value_entry["samples"],
                sample_counts[(platform, field_name, raw_value)],
                platform,
                _sample(job),
            )

    full_report = {
        "manifest": {
            "date": audit_date,
            "input_file": input_file,
            "generated_at": generated_at,
            "job_count": len(jobs),
        },
        "summary": summary,
        "by_platform": {
            platform: {
                field_name: dict(sorted(values.items()))
                for field_name, values in sorted(fields.items())
            }
            for platform, fields in sorted(by_platform.items())
        },
    }
    exception_rows = _exception_csv_rows(
        full_report["by_platform"],
        audit_date=audit_date,
    )
    health = _health_report(full_report, exception_rows)
    return full_report, health, exception_rows


def _exception_csv_rows(
    by_platform: dict[str, dict[str, dict[str, Any]]],
    *,
    audit_date: str,
) -> list[dict[str, Any]]:
    rows = []
    for platform, fields in by_platform.items():
        for field_name, values in fields.items():
            for raw_value, entry in values.items():
                if entry["status"] not in {
                    "unknown",
                    "invalid_format",
                    "invalid_unconfigured",
                }:
                    continue
                rows.append(
                    {
                        "date": audit_date,
                        "platform": platform,
                        "field": field_name,
                        "raw_value": raw_value,
                        "count": entry["count"],
                        "sample_url": _sample_url(entry["samples"]),
                    }
                )
    return rows


def _health_report(
    full_report: dict[str, Any],
    exception_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = full_report["summary"]
    job_count = full_report["manifest"]["job_count"]
    field_health = {
        field_name: _field_health(
            field_name,
            job_count=job_count,
            summary=summary,
            by_platform=full_report["by_platform"],
        )
        for field_name in FIELD_CONFIG_FILES
    }
    unknown_count = sum(
        field_health[field_name]["unknown_count"] for field_name in FIELD_CONFIG_FILES
    )
    unconfigured_invalid_count = _count_status(
        full_report["by_platform"],
        "invalid_unconfigured",
    )

    blocking_reasons = []
    if job_count == 0:
        blocking_reasons.append("job_count is zero")
    if unknown_count > 0:
        blocking_reasons.append("unknown API enum values found")
    if unconfigured_invalid_count > 0:
        blocking_reasons.append("unconfigured invalid API enum values found")

    status = "fail" if blocking_reasons else "pass"
    can_continue = status == "pass"
    return {
        "manifest": full_report["manifest"],
        "status": status,
        "can_continue_to_batch_b": can_continue,
        "can_continue_to_clean_v2": can_continue,
        "education": field_health["education"],
        "experience": field_health["experience"],
        "signals": {
            "new_unknown_enum_found": unknown_count > 0,
            "invalid_enum_found": any(
                field_health[field_name]["invalid_count"] > 0
                for field_name in FIELD_CONFIG_FILES
            ),
            "missing_rate_spike": False,
            "platform_missing_rate_spike": False,
        },
        "blocking_reasons": blocking_reasons,
    }


def _field_health(
    field_name: str,
    *,
    job_count: int,
    summary: dict[str, int],
    by_platform: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    missing_count = summary[f"{field_name}_missing_count"]
    return {
        "known_count": summary[f"{field_name}_known_count"],
        "missing_count": missing_count,
        "unknown_count": summary[f"{field_name}_unknown_count"],
        "invalid_count": summary[f"{field_name}_invalid_count"],
        "missing_rate": round(missing_count / job_count, 6) if job_count else 0,
        "unknown_values": _sample_urls_by_raw_value(
            by_platform,
            field_name,
            statuses={"unknown"},
        ),
        "invalid_values": _sample_urls_by_raw_value(
            by_platform,
            field_name,
            statuses={"invalid_format", "invalid_unconfigured"},
        ),
    }


def _sample_urls_by_raw_value(
    by_platform: dict[str, dict[str, dict[str, Any]]],
    field_name: str,
    *,
    statuses: set[str],
) -> dict[str, str]:
    values: dict[str, str] = {}
    for fields in by_platform.values():
        for raw_value, entry in fields.get(field_name, {}).items():
            if entry["status"] not in statuses or raw_value in values:
                continue
            values[raw_value] = _sample_url(entry["samples"])
    return dict(sorted(values.items()))


def _count_status(
    by_platform: dict[str, dict[str, dict[str, Any]]],
    status: str,
) -> int:
    count = 0
    for fields in by_platform.values():
        for values in fields.values():
            for entry in values.values():
                if entry["status"] == status:
                    count += entry["count"]
    return count


def _failure_health(
    *,
    audit_date: str,
    input_file: str,
    generated_at: str,
    reason: str,
) -> dict[str, Any]:
    manifest = {
        "date": audit_date,
        "input_file": input_file,
        "generated_at": generated_at,
        "job_count": 0,
    }
    empty_field = {
        "known_count": 0,
        "missing_count": 0,
        "unknown_count": 0,
        "invalid_count": 0,
        "missing_rate": 0,
        "unknown_values": {},
        "invalid_values": {},
    }
    return {
        "manifest": manifest,
        "status": "fail",
        "can_continue_to_batch_b": False,
        "can_continue_to_clean_v2": False,
        "education": dict(empty_field),
        "experience": dict(empty_field),
        "signals": {
            "new_unknown_enum_found": False,
            "invalid_enum_found": False,
            "missing_rate_spike": False,
            "platform_missing_rate_spike": False,
        },
        "blocking_reasons": [reason],
    }


def write_exception_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=EXCEPTION_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run_enum_audit(
    input_path: Path,
    *,
    audit_date: str,
    output_dir: Path = Path("data/audit"),
    config_dir: Path = DEFAULT_CONFIG_DIR,
    debug_full: bool = False,
) -> tuple[Path, Path, Path | None, dict[str, Any]]:
    generated_at = datetime.now(timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    health_path = output_dir / f"{audit_date}_enum_health.json"
    exceptions_path = output_dir / f"{audit_date}_enum_exceptions.csv"
    full_path = output_dir / f"{audit_date}_enum_audit_full.json"

    try:
        jobs = load_jobs(input_path)
        full_report, health, exception_rows = audit_api_enums(
            jobs,
            audit_date=audit_date,
            input_file=str(input_path),
            generated_at=generated_at,
            configs=load_enum_configs(config_dir),
        )
    except ValueError as exc:
        full_report = None
        exception_rows = []
        health = _failure_health(
            audit_date=audit_date,
            input_file=str(input_path),
            generated_at=generated_at,
            reason=str(exc),
        )

    with health_path.open("w", encoding="utf-8") as file:
        json.dump(health, file, ensure_ascii=False, indent=2)
        file.write("\n")
    write_exception_csv(exception_rows, exceptions_path)
    if debug_full and full_report is not None:
        with full_path.open("w", encoding="utf-8") as file:
            json.dump(full_report, file, ensure_ascii=False, indent=2)
            file.write("\n")
        written_full_path: Path | None = full_path
    else:
        written_full_path = None
    return health_path, exceptions_path, written_full_path, health


def _date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit API enum values in clean jobs")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--date", type=_date, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/audit"),
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
    )
    parser.add_argument(
        "--debug-full",
        action="store_true",
        help="write full enum audit details with samples",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    health_path, exceptions_path, full_path, health = run_enum_audit(
        args.input,
        audit_date=args.date,
        output_dir=args.output_dir,
        config_dir=args.config_dir,
        debug_full=args.debug_full,
    )
    print(f"Audited {health['manifest']['job_count']} jobs")
    print(f"Status: {health['status']}")
    print(f"Wrote {health_path}")
    print(f"Wrote {exceptions_path}")
    if full_path is not None:
        print(f"Wrote {full_path}")


if __name__ == "__main__":
    main()
