from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REQUIRED_FIELDS = (
    "job_id",
    "platform",
    "title",
    "company",
    "description",
    "location",
    "url",
)
OPTIONAL_FIELDS = (
    "department",
    "experience",
    "education",
    "salary",
    "requirements",
)
SHORT_DESCRIPTION_MIN_LENGTH = 50
MAX_SAMPLES = 20
NORMAL_STOPPED_BY = {
    "configured_max_pages",
    "empty_page",
    "repeated_page",
    "source_total_reached",
}
EDUCATION_PATTERN = re.compile(
    r"(不限|无要求|博士|硕士|研究生|本科|学士|大专|专科|高中|中专|中技|"
    r"初中|doctor|phd|master|bachelor|college|associate|high school)",
    re.IGNORECASE,
)
EXPERIENCE_YEARS_PATTERN = re.compile(
    r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百]+)\s*(?:[-~—至到]\s*"
    r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百]+)\s*)?"
    r"(?:年|years?)",
    re.IGNORECASE,
)


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).casefold()


def _sample(job: dict[str, Any], row_number: int, **extra: Any) -> dict[str, Any]:
    sample = {
        "row_number": row_number,
        "platform": job.get("platform"),
        "job_id": job.get("job_id"),
        "company": job.get("company"),
        "title": job.get("title"),
        "location": job.get("location"),
        "description": job.get("description"),
        "requirements": job.get("requirements"),
        "education": job.get("education"),
        "experience": job.get("experience")
    }
    sample.update(extra)
    return sample


def _sample_per_platform(
    samples: list[dict[str, Any]],
    *,
    per_platform: int,
) -> list[dict[str, Any]]:
    samples_by_platform: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        platform = _text(sample.get("platform")) or "<missing>"
        samples_by_platform[platform].append(sample)
    return [
        sample
        for platform in sorted(samples_by_platform)
        for sample in samples_by_platform[platform][:per_platform]
    ]


def _valid_http_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlsplit(value.strip())
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _parseable_scraped_at(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def _unparseable_field_issue(
    jobs: list[dict[str, Any]],
    field_name: str,
    predicate: Any,
) -> dict[str, Any]:
    samples = [
        _sample(job, row_number, **{field_name: job.get(field_name)})
        for row_number, job in enumerate(jobs, start=1)
        if not predicate(job.get(field_name))
    ]
    return {
        "count": len(samples),
        "samples": _sample_per_platform(samples, per_platform=2),
    }


def _missing_field_issue(
    jobs: list[dict[str, Any]],
    fields: tuple[str, ...],
    *,
    samples_per_platform: int | None = None,
) -> dict[str, Any]:
    by_field: dict[str, Any] = {}
    missing_fields_by_row = {
        row_number: [
            field_name
            for field_name in fields
            if _is_missing(job.get(field_name))
        ]
        for row_number, job in enumerate(jobs, start=1)
    }
    total = 0
    for field_name in fields:
        samples = [
            _sample(
                job,
                row_number,
                missing_fields=missing_fields_by_row[row_number],
            )
            for row_number, job in enumerate(jobs, start=1)
            if _is_missing(job.get(field_name))
        ]
        count = len(samples)
        total += count
        by_field[field_name] = {
            "count": count,
            "samples": samples[:MAX_SAMPLES],
        }
    issue = {
        "count": total,
        "missing_fields": {
            field_name: field_issue["count"]
            for field_name, field_issue in by_field.items()
        },
        "by_field": by_field,
    }
    if samples_per_platform is not None:
        job_samples = [
            _sample(
                job,
                row_number,
                missing_fields=missing_fields_by_row[row_number],
            )
            for row_number, job in enumerate(jobs, start=1)
            if missing_fields_by_row[row_number]
        ]
        issue["samples"] = _sample_per_platform(
            job_samples,
            per_platform=samples_per_platform,
        )
    return issue


def _duplicate_issue(
    jobs: list[dict[str, Any]],
    *,
    fields: tuple[str, ...],
    require_fields: tuple[str, ...],
    sample_fields: tuple[str, ...] = (),
    samples_per_platform: int | None = None,
) -> dict[str, Any]:
    groups: dict[tuple[str, ...], list[tuple[int, dict[str, Any]]]] = defaultdict(
        list
    )
    for row_number, job in enumerate(jobs, start=1):
        if any(_is_missing(job.get(field_name)) for field_name in require_fields):
            continue
        key = tuple(_normalized(job.get(field_name)) for field_name in fields)
        groups[key].append((row_number, job))

    duplicate_groups = [
        (key, rows)
        for key, rows in groups.items()
        if len(rows) > 1
    ]
    duplicate_groups.sort(key=lambda item: item[1][0][0])

    if samples_per_platform is not None:
        selected_group_indexes: set[int] = set()
        sampled_platform_counts: Counter[str] = Counter()
        for index, (_, rows) in enumerate(duplicate_groups):
            group_platform_counts = Counter(
                _text(job.get("platform")) or "<missing>"
                for _, job in rows
            )
            if any(
                sampled_platform_counts[platform] < samples_per_platform
                for platform in group_platform_counts
            ):
                selected_group_indexes.add(index)
                sampled_platform_counts.update(group_platform_counts)
    else:
        selected_group_indexes = set(
            range(min(MAX_SAMPLES, len(duplicate_groups)))
        )

    samples = []
    for index in sorted(selected_group_indexes):
        key, rows = duplicate_groups[index]
        platforms = sorted(
            {
                _text(job.get("platform")) or "<missing>"
                for _, job in rows
            }
        )
        samples.append(
            {
                "key": dict(zip(fields, key)),
                "platforms": platforms,
                "occurrences": len(rows),
                "rows": [
                    _sample(
                        job,
                        row_number,
                        **{
                            field_name: job.get(field_name)
                            for field_name in sample_fields
                        },
                    )
                    for row_number, job in (
                        rows
                        if samples_per_platform is not None
                        else rows[:MAX_SAMPLES]
                    )
                ],
            }
        )

    return {
        "count": sum(len(rows) - 1 for _, rows in duplicate_groups),
        "group_count": len(duplicate_groups),
        "samples": samples,
    }


def audit_jobs(
    jobs: list[dict[str, Any]],
    *,
    input_file: str,
    generated_at: str | None = None,
    collection_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a quality report without modifying the supplied job records."""
    required_issue = _missing_field_issue(jobs, REQUIRED_FIELDS)
    optional_issue = _missing_field_issue(
        jobs,
        OPTIONAL_FIELDS,
        samples_per_platform=2,
    )
    optional_issue.pop("by_field")

    short_description_samples = []
    empty_content_samples = []
    invalid_url_samples = []
    for row_number, job in enumerate(jobs, start=1):
        description = _text(job.get("description"))
        requirements = _text(job.get("requirements"))
        if len(description)+len(requirements) < SHORT_DESCRIPTION_MIN_LENGTH:
            short_description_samples.append(
                _sample(
                    job,
                    row_number,
                    description=job.get("description"),
                    requirements=job.get("requirements"),
                    url=job.get("url"),
                    length=len(description) + len(requirements),
                )
            )
        if not description and not requirements:
            empty_content_samples.append(_sample(job, row_number))
        if not _valid_http_url(job.get("url")):
            invalid_url_samples.append(
                _sample(job, row_number, url=job.get("url"))
            )

    duplicate_platform_job_id = _duplicate_issue(
        jobs,
        fields=("platform", "job_id"),
        require_fields=("platform", "job_id"),
    )
    suspected_duplicate = _duplicate_issue(
        jobs,
        fields=("title", "location", "company", "description"),
        require_fields=("title", "location", "company", "description"),
        sample_fields=("url",),
        samples_per_platform=2,
    )
    manifest_platforms = (
        collection_manifest.get("platforms", [])
        if isinstance(collection_manifest, dict)
        else []
    )
    if not isinstance(manifest_platforms, list):
        manifest_platforms = []
    manifest_platforms = [
        platform
        for platform in manifest_platforms
        if isinstance(platform, dict)
    ]
    manifest_job_count = (
        collection_manifest.get("job_count")
        if isinstance(collection_manifest, dict)
        else None
    )
    manifest_count_checked = isinstance(manifest_job_count, int)
    incomplete_platforms = [
        {
            "platform": platform.get("platform"),
            "complete": platform.get("complete"),
            "status": platform.get("status"),
            "stopped_by": platform.get("stopped_by"),
        }
        for platform in manifest_platforms
        if platform.get("complete") is False
    ]
    abnormal_stops = [
        {
            "platform": platform.get("platform"),
            "complete": platform.get("complete"),
            "status": platform.get("status"),
            "stopped_by": platform.get("stopped_by"),
        }
        for platform in manifest_platforms
        if platform.get("stopped_by") not in NORMAL_STOPPED_BY
    ]
    raw_platform_counts = Counter(
        _text(job.get("platform")) or "<missing>"
        for job in jobs
    )
    manifest_platform_by_name = {
        _text(platform.get("platform")) or "<missing>": platform
        for platform in manifest_platforms
    }
    platform_names = sorted(
        set(raw_platform_counts) | set(manifest_platform_by_name)
    )
    platform_collection_counts = [
        {
            "platform": platform_name,
            "raw": raw_platform_counts.get(platform_name, 0),
            "in_scope": manifest_platform_by_name.get(
                platform_name, {}
            ).get("jobs_in_scope"),
            "details_fetched": manifest_platform_by_name.get(
                platform_name, {}
            ).get("details_fetched"),
            "detail_failed": manifest_platform_by_name.get(
                platform_name, {}
            ).get("detail_failed"),
        }
        for platform_name in platform_names
    ]

    issues = {
        "missing_required_fields": required_issue,
        "missing_optional_fields": optional_issue,
        "description_too_short": {
            "count": len(short_description_samples),
            "threshold": SHORT_DESCRIPTION_MIN_LENGTH,
            "samples": _sample_per_platform(
                short_description_samples,
                per_platform=2,
            ),
        },
        "description_and_requirements_empty": {
            "count": len(empty_content_samples),
            "samples": empty_content_samples[:MAX_SAMPLES],
        },
        "invalid_or_missing_url": {
            "count": len(invalid_url_samples),
            "samples": invalid_url_samples[:MAX_SAMPLES],
        },
        "duplicate_platform_job_id": duplicate_platform_job_id,
        "suspected_duplicate_company_title_location": suspected_duplicate,
        "manifest_job_count_mismatch": {
            "count": int(
                manifest_count_checked and manifest_job_count != len(jobs)
            ),
            "checked": manifest_count_checked,
            "manifest_job_count": manifest_job_count,
            "raw_job_count": len(jobs),
            "samples": (
                platform_collection_counts
                if manifest_count_checked and manifest_job_count != len(jobs)
                else []
            ),
        },
        "manifest_incomplete_platforms": {
            "count": len(incomplete_platforms),
            "samples": incomplete_platforms,
        },
        "manifest_abnormal_stopped_by": {
            "count": len(abnormal_stops),
            "normal_values": sorted(NORMAL_STOPPED_BY),
            "samples": abnormal_stops,
        },
        "unparseable_education": _unparseable_field_issue(
            jobs,
            "education",
            lambda value: bool(EDUCATION_PATTERN.search(_text(value))),
        ),
        "unparseable_experience_years": _unparseable_field_issue(
            jobs,
            "experience",
            lambda value: bool(EXPERIENCE_YEARS_PATTERN.search(_text(value))),
        ),
        "unparseable_scraped_at": _unparseable_field_issue(
            jobs,
            "scraped_at",
            _parseable_scraped_at,
        ),
    }
    issue_counts = {
        issue_name: issue["count"]
        for issue_name, issue in issues.items()
    }
    return {
        "manifest": {
            "generated_at": generated_at
            or datetime.now().astimezone().isoformat(timespec="seconds"),
            "input_file": input_file,
            "job_count": len(jobs),
            "issue_counts": issue_counts,
        },
        "summary": {
            "job_count": len(jobs),
            "platform_counts": dict(sorted(raw_platform_counts.items())),
            "platform_collection_counts": platform_collection_counts,
        },
        "issues": issues,
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


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, path)


def _markdown_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _sample_table(samples: list[dict[str, Any]]) -> list[str]:
    if not samples:
        return ["无样例。", ""]
    show_missing_fields = any("missing_fields" in sample for sample in samples)
    lines = [
        (
            "| 行号 | platform | job_id | company | title | location | "
            f"{'缺失字段 | ' if show_missing_fields else ''}详情 |"
        ),
        (
            "| ---: | --- | --- | --- | --- | --- | "
            f"{'--- | ' if show_missing_fields else ''}--- |"
        ),
    ]
    core_fields = {
        "row_number",
        "platform",
        "job_id",
        "company",
        "title",
        "location",
        "description",
        "missing_fields",
    }
    for sample in samples:
        details = ", ".join(
            f"{key}={_markdown_value(value)}"
            for key, value in sample.items()
            if key not in core_fields
        )
        missing_fields = ", ".join(sample.get("missing_fields", []))
        lines.append(
            "| {row_number} | {platform} | {job_id} | {company} | "
            "{title} | {location} | "
            f"{'{missing_fields} | ' if show_missing_fields else ''}"
            "{details} |".format(
                details=details,
                missing_fields=_markdown_value(missing_fields),
                **{
                    key: _markdown_value(sample.get(key))
                    for key in core_fields
                    if key != "missing_fields"
                },
            )
        )
    lines.append("")
    return lines


def _duplicate_sample_table(samples: list[dict[str, Any]]) -> list[str]:
    if not samples:
        return ["无样例。", ""]
    lines = [
        "| 重复键 | 出现次数 | 行号 | URL |",
        "| --- | ---: | --- | --- |",
    ]
    for sample in samples:
        key = ", ".join(
            f"{field}={_markdown_value(value)}"
            for field, value in sample["key"].items()
        )
        row_numbers = ", ".join(
            str(row["row_number"])
            for row in sample["rows"]
        )
        urls = "<br>".join(
            _markdown_value(row.get("url"))
            for row in sample["rows"]
            if row.get("url") is not None
        )
        lines.append(
            f"| {key} | {sample['occurrences']} | {row_numbers} | {urls} |"
        )
    lines.append("")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    manifest = report["manifest"]
    summary = report["summary"]
    issues = report["issues"]
    lines = [
        "# RawJobPosting 数据质量报告",
        "",
        f"- 生成时间：{manifest['generated_at']}",
        f"- 输入文件：`{manifest['input_file']}`",
        f"- 总岗位数：{manifest['job_count']}",
        (
            "- 计数口径：缺失字段按缺失字段值计数；重复按同一键中"
            "超过首条的额外记录数计数。"
        ),
        (
            f"- 短描述定义：去除首尾空白后少于 "
            f"{SHORT_DESCRIPTION_MIN_LENGTH} 个字符。"
        ),
        "",
        "## 按 platform 统计",
        "",
        "| platform | 数量 |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {_markdown_value(platform)} | {count} |"
        for platform, count in summary["platform_counts"].items()
    )
    lines.extend(
        [
            "",
            "## 平台采集计数",
            "",
            "| platform | raw | in_scope | details_fetched | detail_failed |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(
        "| {platform} | {raw} | {in_scope} | {details_fetched} | "
        "{detail_failed} |".format(
            **{
                key: _markdown_value(item.get(key))
                for key in (
                    "platform",
                    "raw",
                    "in_scope",
                    "details_fetched",
                    "detail_failed",
                )
            }
        )
        for item in summary["platform_collection_counts"]
    )
    lines.extend(["", "## 问题汇总", "", "| 问题 | 数量 |", "| --- | ---: |"])
    lines.extend(
        f"| {issue_name} | {count} |"
        for issue_name, count in manifest["issue_counts"].items()
    )

    for issue_name in ("missing_required_fields", "missing_optional_fields"):
        issue = issues[issue_name]
        lines.extend(
            [
                "",
                f"## {issue_name}",
                "",
                f"总缺失字段值：{issue['count']}",
                "",
                "| 缺失字段 | 数量 |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            f"| {_markdown_value(field_name)} | {count} |"
            for field_name, count in issue["missing_fields"].items()
        )
        lines.append("")
        if issue_name == "missing_optional_fields":
            lines.extend(
                [
                    "### 按平台岗位样例（每个平台 2 条，不足则全部）",
                    "",
                ]
            )
            lines.extend(_sample_table(issue["samples"]))
        for field_name, field_issue in issue.get("by_field", {}).items():
            lines.extend(
                [
                    f"### {field_name}（{field_issue['count']}）",
                    "",
                ]
            )
            lines.extend(_sample_table(field_issue["samples"]))

    for issue_name in (
        "description_too_short",
        "description_and_requirements_empty",
        "invalid_or_missing_url",
        "unparseable_education",
        "unparseable_experience_years",
        "unparseable_scraped_at",
    ):
        issue = issues[issue_name]
        lines.extend(
            [
                f"## {issue_name}（{issue['count']}）",
                "",
            ]
        )
        lines.extend(_sample_table(issue["samples"]))

    for issue_name in (
        "duplicate_platform_job_id",
        "suspected_duplicate_company_title_location",
    ):
        issue = issues[issue_name]
        lines.extend(
            [
                f"## {issue_name}（{issue['count']}）",
                "",
                f"重复组数：{issue['group_count']}",
                "",
            ]
        )
        lines.extend(_duplicate_sample_table(issue["samples"]))

    for issue_name in (
        "manifest_incomplete_platforms",
        "manifest_abnormal_stopped_by",
    ):
        issue = issues[issue_name]
        lines.extend(
            [
                f"## {issue_name}（{issue['count']}）",
                "",
                "| platform | complete | status | stopped_by |",
                "| --- | --- | --- | --- |",
            ]
        )
        lines.extend(
            "| {platform} | {complete} | {status} | {stopped_by} |".format(
                **{
                    key: _markdown_value(platform.get(key))
                    for key in ("platform", "complete", "status", "stopped_by")
                }
            )
            for platform in issue["samples"]
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def run_audit(
    input_path: Path,
    *,
    audit_date: str,
    output_dir: Path = Path("data/audit"),
) -> tuple[Path, Path, dict[str, Any]]:
    jobs = load_jobs(input_path)
    manifest_path = input_path.with_name(f"{input_path.stem}_manifest.json")
    collection_manifest = None
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as file:
            loaded_manifest = json.load(file)
        if not isinstance(loaded_manifest, dict):
            raise ValueError(f"{manifest_path} must contain a JSON object")
        collection_manifest = loaded_manifest
    report = audit_jobs(
        jobs,
        input_file=str(input_path),
        collection_manifest=collection_manifest,
    )
    json_path = output_dir / f"{audit_date}_quality_report.json"
    markdown_path = output_dir / f"{audit_date}_quality_report.md"
    _write_text_atomic(
        json_path,
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )
    _write_text_atomic(markdown_path, render_markdown(report))
    return json_path, markdown_path, report
