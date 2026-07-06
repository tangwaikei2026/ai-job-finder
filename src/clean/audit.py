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
        "requirements": job.get("requirements")
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
) -> dict[str, Any]:
    """Build a quality report without modifying the supplied job records."""
    required_issue = _missing_field_issue(jobs, REQUIRED_FIELDS)
    optional_issue = _missing_field_issue(
        jobs,
        OPTIONAL_FIELDS,
        samples_per_platform=2,
    )

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
    }
    issue_counts = {
        issue_name: issue["count"]
        for issue_name, issue in issues.items()
    }
    platform_counts = Counter(
        _text(job.get("platform")) or "<missing>"
        for job in jobs
    )

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
            "platform_counts": dict(sorted(platform_counts.items())),
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
        for field_name, field_issue in issue["by_field"].items():
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

    return "\n".join(lines).rstrip() + "\n"


def run_audit(
    input_path: Path,
    *,
    audit_date: str,
    output_dir: Path = Path("data/audit"),
) -> tuple[Path, Path, dict[str, Any]]:
    jobs = load_jobs(input_path)
    report = audit_jobs(jobs, input_file=str(input_path))
    json_path = output_dir / f"{audit_date}_quality_report.json"
    markdown_path = output_dir / f"{audit_date}_quality_report.md"
    _write_text_atomic(
        json_path,
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )
    _write_text_atomic(markdown_path, render_markdown(report))
    return json_path, markdown_path, report
