from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.audit.text_splitter import SentenceSpan, split_text_sections


DEFAULT_CONFIG_DIR = Path("configs/normalization")
MISSING_VALUES = {"", "<missing>"}
NUMBER_PATTERN = r"(?:\d+|[一二两三四五六七八九十])"
CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

EDUCATION_EVIDENCE_FIELDS = (
    "platform",
    "job_id",
    "title",
    "company",
    "source_section",
    "sentence",
    "pattern_name",
    "suggested_value",
    "barrier",
    "preferred",
    "confidence",
    "evidence_start",
    "evidence_end",
    "reason",
    "description",
    "requirements",
    "url",
)
EXPERIENCE_EVIDENCE_FIELDS = (
    "platform",
    "job_id",
    "title",
    "company",
    "source_section",
    "sentence",
    "pattern_name",
    "suggested_value",
    "min_years",
    "max_years",
    "bucket",
    "confidence",
    "evidence_start",
    "evidence_end",
    "reason",
    "description",
    "requirements",
    "url",
)
UNKNOWN_FIELDS = (
    "platform",
    "job_id",
    "title",
    "company",
    "field",
    "source_section",
    "sentence",
    "reason",
    "description",
    "requirements",
    "url",
)

EDUCATION_KEYWORDS = (
    "学历",
    "本科",
    "硕士",
    "博士",
    "doctorate",
    "phd",
    "大专",
    "专科",
    "研究生",
    "专业背景",
    "专业",
    "学科背景",
    "教育背景",
    "学位",
)
MAJOR_KEYWORDS = ("专业背景", "专业", "学科背景", "教育背景")
EXPERIENCE_KEYWORDS = (
    "经验",
    "经历",
    "工作经验",
    "工作经历",
    "相关经验",
    "相关经历",
    "年以上",
    "年及以上",
    "年限",
    "背景",
)
IGNORED_MAJOR_TEXT_PATTERN = re.compile(
    r"(专业能力|专业知识|专业技能|专业判断|专业服务|专业团队|专业工具|"
    r"专业经验|专业精神|专业素养)"
)
MAJOR_NAME_PATTERN = re.compile(
    r"(计算机|软件|人工智能|智能|信息技术|通信|电气|自动化|数学|统计|"
    r"计算语言学|语言学|汉语言文学|翻译|小语种|理工科|电子信息|"
    r"金融|经济|数据科学|机器学习|自然语言处理|工程|AI)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextHit:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class DegreeResult:
    hard_pattern: str
    hard_value: str
    hard_barrier: str
    hard_reason: str
    hard_span: TextHit | None
    preferred: str
    preferred_span: TextHit | None


@dataclass(frozen=True)
class MajorResult:
    pattern: str
    value: str
    barrier: str
    preferred: str
    reason: str
    span: TextHit | None


@dataclass(frozen=True)
class EducationEvidence:
    pattern_name: str
    suggested_value: str
    barrier: str
    preferred: str
    confidence: str
    start: int
    end: int
    reason: str


@dataclass(frozen=True)
class ExperienceEvidence:
    pattern_name: str
    suggested_value: str
    min_years: int | None
    max_years: int | None
    bucket: str
    confidence: str
    start: int
    end: int
    reason: str


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    return _stringify(value) in MISSING_VALUES


def load_jobs(input_path: Path) -> list[dict[str, Any]]:
    with input_path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{input_path} must contain a JSON array")
    for row_number, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{input_path} row {row_number} must be an object")
    return data


def load_text_pattern_configs(config_dir: Path = DEFAULT_CONFIG_DIR) -> dict[str, Any]:
    configs: dict[str, Any] = {}
    for file_name in ("education_text_patterns.yaml", "experience_text_patterns.yaml"):
        config_path = config_dir / file_name
        with config_path.open(encoding="utf-8") as file:
            configs[file_name] = yaml.safe_load(file) or {}
    return configs


def find_education_evidence(sentence: str) -> EducationEvidence | None:
    degree = _find_degree(sentence)
    major = _find_major(sentence)
    spans = _education_spans(degree, major)
    if not spans:
        return None

    has_hard = bool(degree.hard_pattern or major.barrier == "no_requirement" or major.pattern == "major_required")
    has_preferred = bool(degree.preferred or major.preferred)
    pattern_name = _education_pattern_name(degree, major)
    suggested_value = _education_suggested_value(degree, major)
    barrier = _education_barrier(degree, major)
    preferred = _join_non_empty([degree.preferred, major.preferred])
    reason = _education_reason(degree, major)

    if has_preferred and not has_hard:
        confidence = "low"
    elif has_preferred:
        confidence = "medium"
    else:
        confidence = "high"

    return EducationEvidence(
        pattern_name=pattern_name,
        suggested_value=suggested_value,
        barrier=barrier,
        preferred=preferred,
        confidence=confidence,
        start=min(span.start for span in spans),
        end=max(span.end for span in spans),
        reason=reason,
    )


def _find_degree(sentence: str) -> DegreeResult:
    hard = _find_hard_degree(sentence)
    preferred = _find_preferred_degree(sentence)
    return DegreeResult(
        hard_pattern=hard[0] if hard else "",
        hard_value=hard[1] if hard else "",
        hard_barrier=hard[2] if hard else "",
        hard_reason=hard[3] if hard else "",
        hard_span=hard[4] if hard else None,
        preferred=preferred.text if preferred else "",
        preferred_span=preferred,
    )


def _find_hard_degree(sentence: str) -> tuple[str, str, str, str, TextHit] | None:
    patterns = (
        ("no_requirement", "no_requirement", "no_requirement", "degree_no_requirement_found", r"(?:学历不限|不限学历)"),
        ("college_plus", "college_plus", "college_plus", "hard_degree_requirement_found", r"(?:大专|专科)\s*(?:及以上|以上|或以上)(?:学历|学位)?"),
        ("bachelor_plus", "bachelor_plus", "bachelor_plus", "hard_degree_requirement_found", r"(?:大学)?本科\s*(?:及以上|以上|或以上)(?:学历|学位)?"),
        ("bachelor_plus", "bachelor_plus", "bachelor_plus", "hard_degree_requirement_found", r"(?:全日制|统招)\s*本科(?:\s*(?:及以上|以上|或以上))?(?:学历|学位)?"),
        ("master_plus", "master_plus", "master_plus", "hard_degree_requirement_found", r"(?:硕士|研究生)\s*(?:及以上|以上|或以上)(?:学历|学位)?"),
        ("phd", "phd", "phd", "hard_degree_requirement_found", r"(?:博士(?:学历|学位)?|doctorate|phd)"),
    )
    for pattern_name, value, barrier, reason, pattern in patterns:
        match = re.search(pattern, sentence, flags=re.IGNORECASE)
        if not match:
            continue
        if _is_preferred_context(sentence, match.start(), match.end()):
            continue
        return (
            pattern_name,
            value,
            barrier,
            reason,
            TextHit(match.group(0), match.start(), match.end()),
        )
    return None


def _find_preferred_degree(sentence: str) -> TextHit | None:
    patterns = (
        r"(?P<phrase>硕士\s*(?:或|/|、)\s*博士|硕士|研究生|博士|doctorate|phd)\s*(?:学历|学位|毕业)?\s*(?:优先|preferred)",
        r"(?:优先考虑|preferred)\s*(?P<phrase>硕士\s*(?:或|/|、)\s*博士|硕士|研究生|博士|doctorate|phd)",
    )
    for pattern in patterns:
        match = re.search(pattern, sentence, flags=re.IGNORECASE)
        if match:
            phrase = _normalize_degree_preferred(match.group("phrase"))
            return TextHit(phrase, match.start("phrase"), match.end())
    return None


def _normalize_degree_preferred(text: str) -> str:
    value = re.sub(r"\s+", "", text)
    value = re.sub(r"(?i)doctorate|phd", "博士", value)
    value = value.replace("/", "或").replace("、", "或")
    if value in {"硕士或博士", "博士或硕士"}:
        return "硕士或博士"
    return value


def _is_preferred_context(sentence: str, start: int, end: int) -> bool:
    tail = sentence[end : min(len(sentence), end + 8)]
    return bool(re.match(r"\s*(?:学历|学位|毕业)?\s*(?:优先|preferred)", tail, flags=re.IGNORECASE))


def _find_major(sentence: str) -> MajorResult:
    no_requirement = re.search(r"(?:专业不限|不限专业)", sentence)
    if no_requirement:
        return MajorResult(
            pattern="major_no_requirement",
            value="no_requirement",
            barrier="no_requirement",
            preferred="",
            reason="major_no_requirement_found",
            span=TextHit(no_requirement.group(0), no_requirement.start(), no_requirement.end()),
        )

    preferred = _find_preferred_major(sentence)
    required = _find_required_major(sentence, preferred)
    if required:
        return MajorResult(
            pattern="major_required",
            value=required.text,
            barrier=required.text,
            preferred=preferred.text if preferred else "",
            reason="hard_major_requirement_found",
            span=_merge_text_hits([required, preferred] if preferred else [required]),
        )
    if preferred:
        return MajorResult(
            pattern="major_preferred_only",
            value=preferred.text,
            barrier="",
            preferred=preferred.text,
            reason="",
            span=preferred,
        )
    return MajorResult("", "", "", "", "", None)


def _find_preferred_major(sentence: str) -> TextHit | None:
    for match in re.finditer(r"(?:优先|preferred)", sentence, flags=re.IGNORECASE):
        phrase_start = _clause_start(sentence, match.start())
        phrase = sentence[phrase_start : match.start()]
        hit = _major_hit_from_phrase(phrase, phrase_start)
        if hit:
            return TextHit(hit.text, hit.start, match.end())
    return None


def _find_required_major(sentence: str, preferred: TextHit | None) -> TextHit | None:
    patterns = (
        r"(?P<phrase>[^，,。；;\n]{1,90}?(?:等)?相关专业)(?=(?:本科|硕士|博士|大专|专科|学历|学位))",
        r"(?P<phrase>[^，,。；;\n]{1,90}?(?:等)?(?:相关专业|专业背景|学科背景|教育背景|类专业|专业))",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, sentence):
            start = match.start("phrase")
            end = match.end("phrase")
            if preferred and _ranges_overlap(start, end, preferred.start, preferred.end):
                continue
            tail = sentence[end : min(len(sentence), end + 4)]
            if re.match(r"\s*(?:优先|preferred)", tail, flags=re.IGNORECASE):
                continue
            hit = _major_hit_from_phrase(match.group("phrase"), start)
            if hit:
                return hit
    return None


def _major_hit_from_phrase(phrase: str, absolute_start: int) -> TextHit | None:
    original = phrase.strip(" ，,、；;。:：")
    cleaned = _clean_major_phrase(phrase)
    if not cleaned or IGNORED_MAJOR_TEXT_PATTERN.search(cleaned):
        return None
    if not re.search(r"(专业|专业背景|学科背景|教育背景)", cleaned):
        return None
    if not MAJOR_NAME_PATTERN.search(cleaned):
        return None
    relative_start = phrase.find(original)
    if relative_start < 0:
        relative_start = len(phrase) - len(phrase.lstrip(" ，,、；;。:："))
    original_end = relative_start + len(original)
    return TextHit(
        cleaned,
        absolute_start + relative_start,
        absolute_start + original_end,
    )


def _clean_major_phrase(phrase: str) -> str:
    cleaned = phrase.strip(" ，,、；;。:：")
    cleaned = re.sub(
        r"^(?:要求|任职要求|具备|拥有|具有|有|需|需要|本科及以上学历|本科及以上|"
        r"硕士及以上学历|学历不限|不限学历)\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(r"^(?:相关)?专业(?:要求)?[:：]\s*", "", cleaned)
    cleaned = cleaned.strip(" ，,、；;。:：")
    cleaned = re.sub(r"者$", "", cleaned)
    cleaned = cleaned.replace("等相关专业", "相关专业")
    cleaned = cleaned.replace("或相关专业", "相关专业")
    cleaned = cleaned.replace("及相关专业", "相关专业")
    cleaned = cleaned.replace("相关专业背景", "相关专业")
    cleaned = cleaned.replace("专业背景", "专业")
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned.strip(" ，,、；;。")


def _clause_start(sentence: str, end: int) -> int:
    boundary = -1
    for delimiter in ("，", ",", "；", ";", "。", "\n", "\r"):
        boundary = max(boundary, sentence.rfind(delimiter, 0, end))
    return boundary + 1


def _merge_text_hits(hits: list[TextHit | None]) -> TextHit | None:
    present = [hit for hit in hits if hit is not None]
    if not present:
        return None
    start = min(hit.start for hit in present)
    end = max(hit.end for hit in present)
    return TextHit("", start, end)


def _education_spans(degree: DegreeResult, major: MajorResult) -> list[TextHit]:
    spans: list[TextHit] = []
    if degree.hard_span:
        spans.append(degree.hard_span)
    if degree.preferred_span:
        spans.append(degree.preferred_span)
    if major.span:
        spans.append(major.span)
    return spans


def _education_pattern_name(degree: DegreeResult, major: MajorResult) -> str:
    parts: list[str] = []
    if degree.hard_pattern:
        parts.append(degree.hard_pattern)
    elif degree.preferred:
        parts.append("preferred_only")
    if degree.hard_pattern and degree.preferred:
        parts.append("preferred_only")
    if major.pattern:
        parts.append(major.pattern)
    return ";".join(parts) if parts else "unknown"


def _education_suggested_value(degree: DegreeResult, major: MajorResult) -> str:
    if degree.hard_value:
        degree_value = degree.hard_value
    elif degree.preferred:
        degree_value = "preferred_only"
    else:
        degree_value = "unknown"
    major_value = major.value if major.value else "unknown"
    if degree_value == "unknown" and major_value == "unknown":
        return "unknown"
    return f"{degree_value};{major_value}"


def _education_barrier(degree: DegreeResult, major: MajorResult) -> str:
    parts = []
    if degree.hard_barrier:
        parts.append(degree.hard_barrier)
    if major.pattern == "major_required":
        parts.append(major.barrier)
    elif major.barrier == "no_requirement" and "no_requirement" not in parts:
        parts.append("no_requirement")
    if not parts:
        return "unknown"
    if "no_requirement" in parts:
        return "no_requirement" if len(parts) == 1 else ";".join(parts)
    return ";".join(parts)


def _education_reason(degree: DegreeResult, major: MajorResult) -> str:
    reasons: list[str] = []
    if degree.hard_reason:
        reasons.append(degree.hard_reason)
    if major.reason:
        reasons.append(major.reason)
    has_hard = bool(degree.hard_pattern or major.pattern == "major_required" or major.barrier == "no_requirement")
    if degree.preferred:
        if degree.hard_pattern:
            reasons.append("degree_preferred_found")
        else:
            reasons.append("degree_preferred_only_no_hard_requirement")
    if major.preferred:
        if has_hard:
            reasons.append("major_preferred_only_found")
        else:
            reasons.append("major_preferred_only_no_hard_requirement")
    return ";".join(dict.fromkeys(reasons))


def find_experience_evidence(sentence: str) -> list[ExperienceEvidence]:
    matches: list[ExperienceEvidence] = []
    matches.extend(_find_experience_no_requirement(sentence))
    matches.extend(_find_experience_ranges(sentence))
    matches.extend(_find_experience_minimums(sentence))
    matches.extend(_find_experience_exact_years(sentence))
    return _dedupe_experience_matches(matches)


def _find_experience_no_requirement(sentence: str) -> list[ExperienceEvidence]:
    matches: list[ExperienceEvidence] = []
    patterns = (
        ("no_requirement", "no_requirement", None, None, "no_requirement", r"(?:经验不限|不限经验)"),
        ("fresh_graduate", "fresh_graduate", 0, 1, "fresh_graduate", r"应届毕业生"),
    )
    for pattern_name, suggested_value, min_years, max_years, bucket, pattern in patterns:
        for match in re.finditer(pattern, sentence):
            matches.append(
                ExperienceEvidence(
                    pattern_name=pattern_name,
                    suggested_value=suggested_value,
                    min_years=min_years,
                    max_years=max_years,
                    bucket=bucket,
                    confidence="high",
                    start=match.start(),
                    end=match.end(),
                    reason="explicit_experience_requirement_found",
                )
            )
    return matches


def _find_experience_ranges(sentence: str) -> list[ExperienceEvidence]:
    matches: list[ExperienceEvidence] = []
    pattern = re.compile(
        rf"(?P<min>{NUMBER_PATTERN})\s*(?:-|~|到|至)\s*(?P<max>{NUMBER_PATTERN})\s*年"
    )
    for match in pattern.finditer(sentence):
        if _blocked_experience_context(sentence, match.start(), match.end()):
            continue
        min_years = _parse_year_number(match.group("min"))
        max_years = _parse_year_number(match.group("max"))
        if min_years is None or max_years is None:
            continue
        matches.append(
            ExperienceEvidence(
                pattern_name="year_range",
                suggested_value=f"{min_years}-{max_years}年",
                min_years=min_years,
                max_years=max_years,
                bucket="range",
                confidence="high",
                start=match.start(),
                end=match.end(),
                reason="year_range_found",
            )
        )
    return matches


def _find_experience_minimums(sentence: str) -> list[ExperienceEvidence]:
    matches: list[ExperienceEvidence] = []
    pattern = re.compile(
        rf"(?:(?:至少|不少于)\s*)?(?P<years>{NUMBER_PATTERN})\s*年\s*(?:及以上|以上)"
        rf"|(?:(?:至少|不少于)\s*)(?P<prefix_years>{NUMBER_PATTERN})\s*年"
    )
    for match in pattern.finditer(sentence):
        if _blocked_experience_context(sentence, match.start(), match.end()):
            continue
        raw_years = match.group("years") or match.group("prefix_years")
        min_years = _parse_year_number(raw_years)
        if min_years is None:
            continue
        matches.append(
            ExperienceEvidence(
                pattern_name="min_years",
                suggested_value=f"{min_years}年以上",
                min_years=min_years,
                max_years=None,
                bucket="min_years",
                confidence="high",
                start=match.start(),
                end=match.end(),
                reason="minimum_year_requirement_found",
            )
        )
    return matches


def _find_experience_exact_years(sentence: str) -> list[ExperienceEvidence]:
    matches: list[ExperienceEvidence] = []
    pattern = re.compile(rf"(?P<years>{NUMBER_PATTERN})\s*年(?!\s*(?:内|间|前|后|来|度|月))")
    for match in pattern.finditer(sentence):
        if _overlaps_stronger_year_pattern(sentence, match) or _blocked_experience_context(sentence, match.start(), match.end()):
            continue
        context = sentence[max(0, match.start() - 12) : min(len(sentence), match.end() + 18)]
        if not re.search(r"(经验|经历|工作|相关|研发|开发|产品|运营|测试|管理)", context):
            continue
        years = _parse_year_number(match.group("years"))
        if years is None:
            continue
        matches.append(
            ExperienceEvidence(
                pattern_name="exact_years",
                suggested_value=f"{years}年",
                min_years=years,
                max_years=years,
                bucket="exact_years",
                confidence="medium",
                start=match.start(),
                end=match.end(),
                reason="exact_year_requirement_found",
            )
        )
    return matches


def _blocked_experience_context(sentence: str, start: int, end: int) -> bool:
    context = sentence[max(0, start - 8) : min(len(sentence), end + 10)]
    return bool(
        re.search(
            r"(?:负责|管理|支持|完成|近|每周|项目|团队|案例|模块|QPS|个月|月|天|人团队|个项目)",
            context,
            flags=re.IGNORECASE,
        )
    )


def _overlaps_stronger_year_pattern(sentence: str, match: re.Match[str]) -> bool:
    head = sentence[max(0, match.start() - 4) : match.start()]
    tail = sentence[match.end() : min(len(sentence), match.end() + 4)]
    return bool(re.search(r"(?:-|~|到|至)\s*$", head) or re.match(r"\s*(?:及以上|以上)", tail))


def _parse_year_number(value: str) -> int | None:
    cleaned = value.strip()
    if cleaned.isdigit():
        return int(cleaned)
    return CHINESE_NUMBERS.get(cleaned)


def _dedupe_experience_matches(matches: list[ExperienceEvidence]) -> list[ExperienceEvidence]:
    priority = {"no_requirement": 0, "fresh_graduate": 0, "year_range": 1, "min_years": 2, "exact_years": 3}
    selected: list[ExperienceEvidence] = []
    for candidate in sorted(matches, key=lambda item: (item.start, priority[item.pattern_name])):
        if any(_ranges_overlap(candidate.start, candidate.end, item.start, item.end) for item in selected):
            continue
        selected.append(candidate)
    return selected


def extract_missing_evidence(
    jobs: list[dict[str, Any]],
    *,
    input_file: str,
    generated_at: str,
) -> dict[str, Any]:
    education_rows: list[dict[str, Any]] = []
    experience_rows: list[dict[str, Any]] = []
    unknown_rows: list[dict[str, Any]] = []
    platform_counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {"education": _empty_counts(), "experience": _empty_counts()}
    )

    for job in jobs:
        platform = _stringify(job.get("platform")) or "<missing>"
        sentences = split_text_sections(
            {"requirements": job.get("requirements"), "description": job.get("description")}
        )

        if _is_missing(job.get("education")):
            platform_counts[platform]["education"]["missing_input_count"] += 1
            rows, unknown = _extract_education_rows(job, sentences)
            education_rows.extend(rows)
            unknown_rows.extend(unknown)
            platform_counts[platform]["education"]["evidence_found_count"] += len(rows)
            platform_counts[platform]["education"]["unknown_pattern_count"] += len(unknown)

        if _is_missing(job.get("experience")):
            platform_counts[platform]["experience"]["missing_input_count"] += 1
            rows, unknown = _extract_experience_rows(job, sentences)
            experience_rows.extend(rows)
            unknown_rows.extend(unknown)
            platform_counts[platform]["experience"]["evidence_found_count"] += len(rows)
            platform_counts[platform]["experience"]["unknown_pattern_count"] += len(unknown)

    report = _build_report(
        jobs=jobs,
        input_file=input_file,
        generated_at=generated_at,
        education_rows=education_rows,
        experience_rows=experience_rows,
        unknown_rows=unknown_rows,
        platform_counts=platform_counts,
    )
    return {
        "education_rows": education_rows,
        "experience_rows": experience_rows,
        "unknown_rows": unknown_rows,
        "report": report,
    }


def _empty_counts() -> dict[str, int]:
    return {
        "missing_input_count": 0,
        "evidence_found_count": 0,
        "unknown_pattern_count": 0,
    }


def _extract_education_rows(
    job: dict[str, Any],
    sentences: list[SentenceSpan],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence_rows: list[dict[str, Any]] = []
    unknown_rows: list[dict[str, Any]] = []
    for sentence in sentences:
        evidence = find_education_evidence(sentence.sentence)
        if evidence:
            evidence_rows.append(_education_row(job, sentence, evidence))
        elif _contains_education_unknown(sentence.sentence):
            unknown_rows.append(
                _unknown_row(
                    job,
                    sentence,
                    field="education",
                    reason=_education_unknown_reason(sentence.sentence),
                )
            )
    return evidence_rows, unknown_rows


def _extract_experience_rows(
    job: dict[str, Any],
    sentences: list[SentenceSpan],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence_rows: list[dict[str, Any]] = []
    unknown_rows: list[dict[str, Any]] = []
    for sentence in sentences:
        matches = find_experience_evidence(sentence.sentence)
        if matches:
            evidence_rows.extend(_experience_row(job, sentence, match) for match in matches)
        elif _contains_experience_unknown(sentence.sentence):
            unknown_rows.append(
                _unknown_row(
                    job,
                    sentence,
                    field="experience",
                    reason=_experience_unknown_reason(sentence.sentence),
                )
            )
    return evidence_rows, unknown_rows


def _education_row(
    job: dict[str, Any],
    sentence: SentenceSpan,
    evidence: EducationEvidence,
) -> dict[str, Any]:
    return _blank_none(
        {
            **_job_base(job),
            "source_section": sentence.source_section,
            "sentence": sentence.sentence,
            "pattern_name": evidence.pattern_name,
            "suggested_value": evidence.suggested_value,
            "barrier": evidence.barrier,
            "preferred": evidence.preferred,
            "confidence": evidence.confidence,
            "evidence_start": evidence.start,
            "evidence_end": evidence.end,
            "reason": evidence.reason,
            "description": _stringify(job.get("description")),
            "requirements": _stringify(job.get("requirements")),
            "url": _stringify(job.get("url")),
        }
    )


def _experience_row(
    job: dict[str, Any],
    sentence: SentenceSpan,
    evidence: ExperienceEvidence,
) -> dict[str, Any]:
    return _blank_none(
        {
            **_job_base(job),
            "source_section": sentence.source_section,
            "sentence": sentence.sentence,
            "pattern_name": evidence.pattern_name,
            "suggested_value": evidence.suggested_value,
            "min_years": evidence.min_years,
            "max_years": evidence.max_years,
            "bucket": evidence.bucket,
            "confidence": evidence.confidence,
            "evidence_start": evidence.start,
            "evidence_end": evidence.end,
            "reason": evidence.reason,
            "description": _stringify(job.get("description")),
            "requirements": _stringify(job.get("requirements")),
            "url": _stringify(job.get("url")),
        }
    )


def _unknown_row(
    job: dict[str, Any],
    sentence: SentenceSpan,
    *,
    field: str,
    reason: str,
) -> dict[str, Any]:
    return _blank_none(
        {
            **_job_base(job),
            "field": field,
            "source_section": sentence.source_section,
            "sentence": sentence.sentence,
            "reason": reason,
            "description": _stringify(job.get("description")),
            "requirements": _stringify(job.get("requirements")),
            "url": _stringify(job.get("url")),
        }
    )


def _job_base(job: dict[str, Any]) -> dict[str, str]:
    return {
        "platform": _stringify(job.get("platform")),
        "job_id": _stringify(job.get("job_id")),
        "title": _stringify(job.get("title")),
        "company": _stringify(job.get("company")),
    }


def _blank_none(row: dict[str, Any]) -> dict[str, Any]:
    return {key: ("" if value is None else value) for key, value in row.items()}


def _contains_education_unknown(sentence: str) -> bool:
    lowered = sentence.lower()
    if IGNORED_MAJOR_TEXT_PATTERN.search(sentence):
        return False
    return any(keyword.lower() in lowered for keyword in EDUCATION_KEYWORDS)


def _contains_experience_unknown(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(keyword.lower() in lowered for keyword in EXPERIENCE_KEYWORDS)


def _education_unknown_reason(sentence: str) -> str:
    lowered = sentence.lower()
    if any(keyword.lower() in lowered for keyword in MAJOR_KEYWORDS):
        return "contains_major_keyword_but_unsupported_pattern"
    if re.search(r"(学历|本科|硕士|博士|doctorate|phd|大专|专科|研究生|学位)", sentence, flags=re.IGNORECASE):
        return "contains_degree_keyword_but_no_hard_requirement"
    return "unsupported_pattern"


def _experience_unknown_reason(sentence: str) -> str:
    if re.search(rf"{NUMBER_PATTERN}\s*年", sentence):
        return "contains_year_number_but_unclear_context"
    if re.search(r"(经验|经历|工作经验|工作经历|相关经验|相关经历)", sentence):
        return "contains_experience_keyword_but_no_year"
    return "unsupported_pattern"


def _build_report(
    *,
    jobs: list[dict[str, Any]],
    input_file: str,
    generated_at: str,
    education_rows: list[dict[str, Any]],
    experience_rows: list[dict[str, Any]],
    unknown_rows: list[dict[str, Any]],
    platform_counts: dict[str, dict[str, dict[str, int]]],
) -> dict[str, Any]:
    education_unknown_count = sum(1 for row in unknown_rows if row["field"] == "education")
    experience_unknown_count = sum(1 for row in unknown_rows if row["field"] == "experience")
    return {
        "manifest": {
            "input_file": input_file,
            "generated_at": generated_at,
            "job_count": len(jobs),
        },
        "education": {
            "missing_input_count": sum(
                counts["education"]["missing_input_count"] for counts in platform_counts.values()
            ),
            "evidence_found_count": len(education_rows),
            "unknown_pattern_count": education_unknown_count,
            "by_platform": _report_platforms(platform_counts, "education"),
        },
        "experience": {
            "missing_input_count": sum(
                counts["experience"]["missing_input_count"] for counts in platform_counts.values()
            ),
            "evidence_found_count": len(experience_rows),
            "unknown_pattern_count": experience_unknown_count,
            "by_platform": _report_platforms(platform_counts, "experience"),
        },
    }


def _report_platforms(
    platform_counts: dict[str, dict[str, dict[str, int]]],
    field: str,
) -> dict[str, dict[str, int]]:
    return {
        platform: dict(counts[field])
        for platform, counts in sorted(platform_counts.items())
        if counts[field]["missing_input_count"] > 0
    }


def write_csv(
    rows: list[dict[str, Any]],
    output_path: Path,
    fieldnames: tuple[str, ...],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_missing_evidence(
    input_path: Path,
    *,
    audit_date: str,
    output_dir: Path = Path("data/review"),
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> tuple[Path, Path, Path, Path, dict[str, Any]]:
    load_text_pattern_configs(config_dir)
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    jobs = load_jobs(input_path)
    result = extract_missing_evidence(
        jobs,
        input_file=str(input_path),
        generated_at=generated_at,
    )

    education_path = output_dir / f"{audit_date}_missing_education_evidence.csv"
    experience_path = output_dir / f"{audit_date}_missing_experience_evidence.csv"
    unknown_path = output_dir / f"{audit_date}_unknown_patterns.csv"
    report_path = output_dir / f"{audit_date}_missing_evidence_report.json"

    write_csv(result["education_rows"], education_path, EDUCATION_EVIDENCE_FIELDS)
    write_csv(result["experience_rows"], experience_path, EXPERIENCE_EVIDENCE_FIELDS)
    write_csv(result["unknown_rows"], unknown_path, UNKNOWN_FIELDS)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(result["report"], file, ensure_ascii=False, indent=2)
        file.write("\n")
    return education_path, experience_path, unknown_path, report_path, result["report"]


def _join_non_empty(values: list[str]) -> str:
    return ";".join(value for value in values if value)


def _ranges_overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return left_start < right_end and right_start < left_end


def _date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract missing education and experience evidence from clean jobs"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--date", type=_date, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/review"))
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    education_path, experience_path, unknown_path, report_path, report = run_missing_evidence(
        args.input,
        audit_date=args.date,
        output_dir=args.output_dir,
        config_dir=args.config_dir,
    )
    print(f"Reviewed {report['manifest']['job_count']} jobs")
    print(f"Wrote {education_path}")
    print(f"Wrote {experience_path}")
    print(f"Wrote {unknown_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
