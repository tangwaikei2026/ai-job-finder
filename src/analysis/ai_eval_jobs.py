from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Pattern, Sequence
from zoneinfo import ZoneInfo

import yaml


DEFAULT_CLEAN_DIR = Path("data/clean")
DEFAULT_CONFIG = Path("config.yaml")
DEFAULT_OUTPUT_DIR = Path("data/analysis")
BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")

AI_CONTEXT_PATTERN = re.compile(
    r"(?i)(?:(?<![A-Za-z])AI(?![A-Za-z])|AIGC|大模型|大语言模型|"
    r"(?<![A-Za-z])LLMs?(?![A-Za-z])|智能体|"
    r"(?<![A-Za-z])Agent(?:ic|s)?(?![A-Za-z])|生成式|多模态|机器学习|"
    r"深度学习|自然语言|(?<![A-Za-z])NLP(?![A-Za-z])|算法模型|"
    r"模型训练|模型推理|(?<![A-Za-z])Prompt(?![A-Za-z])|"
    r"(?<![A-Za-z])RAG(?![A-Za-z]))"
)
AGENT_PATTERN = re.compile(
    r"(?i)(?:智能体|多智能体|(?<![A-Za-z])Agent(?:ic|s)?(?![A-Za-z]))"
)
EVALUATION_TITLE_PATTERN = re.compile(
    r"(?i)(?:评测|测评|评估|评价|\bEvaluation\b|\bEvaluator\b|"
    r"\bBenchmark\b|红队|\bRed[ -]?Team(?:ing)?\b)"
)
QUALITY_TITLE_PATTERN = re.compile(
    r"(?i)(?:测试|质量|质保|(?<![A-Za-z])QA(?![A-Za-z])|"
    r"(?<![A-Za-z])Test(?:ing|er)?(?![A-Za-z])|"
    r"(?<![A-Za-z])Quality(?![A-Za-z]))"
)
ADJACENT_EXCLUSION_PATTERN = re.compile(
    r"(?:芯片|硬件|射频|电源|电池|机械|结构工程|工艺测试|可靠性测试|"
    r"生产测试|制造测试|整车测试|车载测试)"
)

EXCLUSION_REASON_LABELS = {
    "outside_config_scope": "不在 config.yaml 启用的平台/公司范围",
    "missing_title": "标题为空，无法满足标题职责词规则",
    "evaluation_title_without_ai_context": "标题有评测词，但正文无 AI/Agent 上下文",
    "hardware_or_manufacturing_test_excluded": "AI 测试标题命中硬件/制造排除词",
    "ai_title_without_evaluation_or_quality_term": "标题有 AI，但无评测/测试/质量职责词",
    "quality_title_ai_context_only_in_body": "测试/质量标题的 AI 上下文只在正文",
    "ai_context_only_in_body_without_role_title_terms": "AI 上下文只在正文，标题无相关职责词",
    "no_ai_context": "标题和正文均无 AI/Agent 上下文",
}


SKILL_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    (
        "评测体系与指标设计",
        re.compile(
            r"(?i)(?:评测体系|评估体系|评价体系|指标体系|评测指标|"
            r"评估指标|evaluation framework|evaluation metric)"
        ),
    ),
    ("Agent/智能体", AGENT_PATTERN),
    (
        "Python",
        re.compile(r"(?i)(?:(?<![A-Za-z])Python(?![A-Za-z])|PyTorch|TensorFlow)"),
    ),
    (
        "数据分析与处理",
        re.compile(
            r"(?i)(?:数据分析|数据处理|数据挖掘|数据清洗|数据标注|"
            r"数据构建|数据治理|\bPandas\b|\bNumPy\b)"
        ),
    ),
    (
        "Benchmark与评测集",
        re.compile(
            r"(?i)(?:\bBenchmark(?:ing|s)?\b|评测集|评估集|测评集|"
            r"测试集|基准测试|黄金集|golden set)"
        ),
    ),
    (
        "评测平台与自动化工具链",
        re.compile(
            r"(?i)(?:自动化评测|自动化测试|评测平台|评估平台|测试平台|"
            r"评测工具|评估工具|测试工具|工具链|evaluation pipeline)"
        ),
    ),
    (
        "大语言模型/LLM",
        re.compile(r"(?i)(?:大语言模型|大模型|\bLLMs?\b|语言模型)"),
    ),
    (
        "机器学习/深度学习",
        re.compile(
            r"(?i)(?:机器学习|深度学习|\bML\b|\bPyTorch\b|"
            r"\bTensorFlow\b|\bTransformer\b)"
        ),
    ),
    (
        "Prompt工程",
        re.compile(
            r"(?i)(?:(?<![A-Za-z])Prompt(?:ing)?(?![A-Za-z])|提示词)"
        ),
    ),
    (
        "测试与质量保障",
        re.compile(
            r"(?i)(?:软件测试|功能测试|性能测试|自动化测试|测试用例|"
            r"质量保障|质量保证|\bQA\b|quality assurance)"
        ),
    ),
    (
        "安全评测与红队",
        re.compile(
            r"(?i)(?:安全评测|安全测试|模型安全|内容安全|红队|对抗测试|"
            r"越狱攻击|\bRed[ -]?Team(?:ing)?\b|\bAlignment\b|对齐)"
        ),
    ),
    ("NLP", re.compile(r"(?i)(?:自然语言处理|\bNLP\b)")),
    (
        "多模态与计算机视觉",
        re.compile(r"(?i)(?:多模态|计算机视觉|\bCV\b|视觉语言模型|\bVLM\b)"),
    ),
    (
        "RAG与检索",
        re.compile(r"(?i)(?:\bRAG\b|检索增强|信息检索|向量检索|知识库)"),
    ),
    (
        "强化学习/RLHF",
        re.compile(r"(?i)(?:强化学习|\bRLHF\b|\bRLAIF\b|奖励模型)"),
    ),
    ("SQL", re.compile(r"(?i)\bSQL\b")),
)

REQUIREMENT_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    (
        "评测/测试相关经验",
        re.compile(
            r"(?is)(?:评测|测评|评估|测试|质量).{0,28}(?:经验|经历|背景|能力)|"
            r"(?:经验|经历|背景).{0,28}(?:评测|测评|评估|测试|质量)"
        ),
    ),
    (
        "沟通协作能力",
        re.compile(r"(?:沟通|协作|合作|跨团队|团队协同|表达能力|协调能力)"),
    ),
    (
        "本科及以上学历",
        re.compile(r"(?:本科及以上|本科或以上|大学本科|本科以上|本科.?学历)"),
    ),
    (
        "AI/大模型相关经验",
        re.compile(
            r"(?is)(?:AI|人工智能|大模型|大语言模型|LLM|Agent|智能体|"
            r"机器学习|深度学习).{0,32}(?:经验|经历|背景|能力|理解|知识)|"
            r"(?:经验|经历|背景).{0,32}(?:AI|人工智能|大模型|LLM|Agent|智能体)"
        ),
    ),
    (
        "编程与工程能力",
        re.compile(
            r"(?i)(?:编程能力|代码能力|工程能力|工程实践|开发经验|"
            r"\bPython\b|\bC\+\+\b|\bJava\b)"
        ),
    ),
    (
        "数据分析能力",
        re.compile(
            r"(?i)(?:数据分析|数据处理|数据挖掘|数据建模|统计分析|"
            r"\bSQL\b|\bPandas\b)"
        ),
    ),
    (
        "计算机/数学等相关专业",
        re.compile(
            r"(?:计算机|软件工程|人工智能|数学|统计学|数据科学|"
            r"电子信息|自动化).{0,16}(?:专业|背景)"
        ),
    ),
    (
        "产品与业务理解",
        re.compile(r"(?:产品思维|产品能力|业务理解|业务洞察|用户需求|用户体验)"),
    ),
    (
        "自驱力与责任心",
        re.compile(r"(?i)(?:自驱|主动性|责任心|ownership|主人翁|抗压)"),
    ),
    (
        "英语能力",
        re.compile(r"(?i)(?:英语|英文|CET[- ]?[46]|TOEFL|IELTS)"),
    ),
    (
        "硕士/博士优先",
        re.compile(r"(?:硕士|博士|研究生).{0,12}(?:优先|及以上|以上)"),
    ),
    (
        "论文/竞赛/开源成果",
        re.compile(r"(?:顶会|论文|竞赛|比赛|开源项目|GitHub|学术成果)"),
    ),
    (
        "三年以上经验",
        re.compile(r"(?:3|三)\s*(?:年|年以上|年及以上|年以上)"),
    ),
    (
        "五年以上经验",
        re.compile(r"(?:5|五)\s*(?:年|年以上|年及以上|年以上)"),
    ),
)

EDUCATION_TEXT_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    ("博士", re.compile(r"博士")),
    ("硕士及以上", re.compile(r"(?:硕士|研究生).{0,8}(?:及以上|以上)")),
    ("本科及以上", re.compile(r"本科.{0,8}(?:及以上|以上|或以上)")),
    ("大专及以上", re.compile(r"(?:大专|专科).{0,8}(?:及以上|以上|或以上)")),
    ("学历不限", re.compile(r"学历不限|不限学历")),
)

MAJOR_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    (
        "计算机/软件工程",
        re.compile(r"(?:计算机|软件工程|计算机科学|网络工程).{0,16}(?:专业|背景|相关)"),
    ),
    (
        "人工智能/数据科学",
        re.compile(r"(?:人工智能|数据科学|机器学习).{0,16}(?:专业|背景|相关)"),
    ),
    (
        "数学/统计学",
        re.compile(r"(?:数学|统计学|应用统计).{0,16}(?:专业|背景|相关)"),
    ),
    (
        "电子信息/自动化",
        re.compile(r"(?:电子信息|电子工程|通信工程|自动化).{0,16}(?:专业|背景|相关)"),
    ),
    (
        "语言学/心理学/认知科学",
        re.compile(r"(?:语言学|心理学|认知科学).{0,16}(?:专业|背景|相关)"),
    ),
)

PROJECT_EXPERIENCE_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    (
        "明确要求项目经验",
        re.compile(r"(?:项目经验|项目经历|项目实践|实际项目|完整项目)"),
    ),
    (
        "AI/大模型落地经验",
        re.compile(
            r"(?is)(?:AI|人工智能|大模型|LLM|Agent|智能体).{0,30}"
            r"(?:落地|项目).{0,16}(?:经验|经历|实践)|(?:落地|项目).{0,20}"
            r"(?:AI|大模型|LLM|Agent|智能体).{0,12}(?:经验|经历|实践)"
        ),
    ),
    (
        "从0到1/完整交付",
        re.compile(r"(?i)(?:从\s*0\s*到\s*1|0\s*[-到]\s*1|端到端|完整交付)"),
    ),
    (
        "开源项目经历",
        re.compile(r"(?i)(?:开源项目|GitHub).{0,20}(?:经验|经历|贡献|项目)?"),
    ),
)

EDUCATION_ALIASES = {
    "doctorate": "博士",
    "other": "其他",
}
EXPERIENCE_ALIASES = {
    "一年以上工作经验": "1年以上",
    "两年以上工作经验": "2年以上",
    "三年以上工作经验": "3年以上",
    "五年以上工作经验": "5年以上",
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


def resolve_input_path(
    input_path: Path | None = None,
    *,
    analysis_date: str | None = None,
    now: datetime | None = None,
) -> Path:
    if input_path is not None and analysis_date is not None:
        raise ValueError("input_path and analysis_date are mutually exclusive")
    if input_path is not None:
        return input_path
    if analysis_date is not None:
        try:
            datetime.strptime(analysis_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("analysis_date must use YYYY-MM-DD") from exc
        date_value = analysis_date
    else:
        current = now or datetime.now(BEIJING_TIMEZONE)
        if current.tzinfo is None:
            current = current.replace(tzinfo=BEIJING_TIMEZONE)
        date_value = current.astimezone(BEIJING_TIMEZONE).strftime("%Y-%m-%d")
    return DEFAULT_CLEAN_DIR / f"{date_value}.json"


def _date_arg(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    return value


def load_company_scope(config_path: Path) -> dict[str, set[str] | None]:
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not isinstance(config, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping")
    platforms = config.get("platforms")
    if not isinstance(platforms, dict):
        raise ValueError(f"{config_path} platforms must be a mapping")

    scope: dict[str, set[str] | None] = {}
    for platform, settings in platforms.items():
        if not isinstance(settings, dict) or settings.get("enabled") is not True:
            continue
        companies = settings.get("companies")
        if isinstance(companies, list):
            names = {
                company.get("name").strip()
                for company in companies
                if isinstance(company, dict)
                and isinstance(company.get("name"), str)
                and company.get("name").strip()
            }
            scope[str(platform)] = names
        else:
            scope[str(platform)] = None
    return scope


def configured_company_names(
    config_path: Path,
    scope: Mapping[str, set[str] | None] | None = None,
) -> list[str]:
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    platforms = config.get("platforms", {}) if isinstance(config, dict) else {}
    active_scope = scope or load_company_scope(config_path)
    names: list[str] = []
    for platform, company_filter in active_scope.items():
        settings = platforms.get(platform, {})
        if company_filter is not None:
            names.extend(sorted(company_filter))
        elif isinstance(settings, dict) and isinstance(settings.get("name"), str):
            names.append(settings["name"].strip())
    return sorted({name for name in names if name})


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        values = [_text(item) for item in value]
    else:
        values = [_text(value)]
    return list(dict.fromkeys(item for item in values if item))


def _job_body(job: Mapping[str, Any]) -> str:
    return "\n".join(
        (_text(job.get("description")), _text(job.get("requirements")))
    )


def _education_values(job: Mapping[str, Any]) -> list[str]:
    structured = _text(job.get("education"))
    if structured:
        return [EDUCATION_ALIASES.get(structured.casefold(), structured)]
    return _matches(_job_body(job), EDUCATION_TEXT_PATTERNS)


def _experience_values(job: Mapping[str, Any]) -> list[str]:
    structured = _text(job.get("experience"))
    if not structured:
        return []
    return [EXPERIENCE_ALIASES.get(structured, structured)]


def _normalized(value: Any) -> str:
    return " ".join(_text(value).casefold().split())


def _in_scope(job: Mapping[str, Any], scope: Mapping[str, set[str] | None]) -> bool:
    platform = _text(job.get("platform"))
    if platform not in scope:
        return False
    company_filter = scope[platform]
    return company_filter is None or _text(job.get("company")) in company_filter


def _matched_terms(pattern: Pattern[str], text: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        term = match.group(0).strip()
        normalized = term.casefold()
        if term and normalized not in seen:
            seen.add(normalized)
            terms.append(term)
    return terms


def _field_matches(
    pattern: Pattern[str],
    job: Mapping[str, Any],
) -> dict[str, list[str]]:
    matches = {}
    for field in ("title", "description", "requirements"):
        terms = _matched_terms(pattern, _text(job.get(field)))
        if terms:
            matches[field] = terms
    return matches


def _describe_field_matches(matches: Mapping[str, Sequence[str]]) -> str:
    return "、".join(
        f"{field} 命中“{'、'.join(terms)}”"
        for field, terms in matches.items()
    )


def explain_job_selection(job: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the exact matching evidence for one selected job."""
    title = _text(job.get("title"))
    evaluation_terms = _matched_terms(EVALUATION_TITLE_PATTERN, title)
    quality_terms = _matched_terms(QUALITY_TITLE_PATTERN, title)
    exclusion_terms = _matched_terms(ADJACENT_EXCLUSION_PATTERN, title)
    ai_matches = _field_matches(AI_CONTEXT_PATTERN, job)
    agent_matches = _field_matches(AGENT_PATTERN, job)

    cohort: str | None = None
    rule_id: str | None = None
    reason_parts: list[str] = []
    if evaluation_terms and agent_matches:
        cohort = "Agent评测"
        rule_id = "title_evaluation_term_and_agent_context"
        reason_parts = [
            f"title 命中评测/评估职责词“{'、'.join(evaluation_terms)}”",
            _describe_field_matches(agent_matches),
            "满足 Agent 评测核心岗位规则",
        ]
    elif evaluation_terms and ai_matches:
        cohort = "AI/模型评测"
        rule_id = "title_evaluation_term_and_ai_context"
        reason_parts = [
            f"title 命中评测/评估职责词“{'、'.join(evaluation_terms)}”",
            _describe_field_matches(ai_matches),
            "满足 AI/模型评测核心岗位规则",
        ]
    elif quality_terms and ai_matches.get("title") and not exclusion_terms:
        cohort = "AI质量与测试（相邻岗位）"
        rule_id = "title_ai_context_and_quality_term"
        reason_parts = [
            f"title 命中测试/质量职责词“{'、'.join(quality_terms)}”",
            f"title 同时命中 AI/Agent 上下文“{'、'.join(ai_matches['title'])}”",
            "title 未命中硬件/制造排除词",
            "满足 AI 质量与测试相邻岗位规则",
        ]
    if cohort is None or rule_id is None:
        return None

    return {
        "cohort": cohort,
        "rule_id": rule_id,
        "reason": "；".join(reason_parts) + "。",
        "evidence": {
            "title_evaluation_terms": evaluation_terms,
            "title_quality_terms": quality_terms,
            "ai_context_terms_by_field": ai_matches,
            "agent_terms_by_field": agent_matches,
            "title_exclusion_terms": exclusion_terms,
        },
    }


def explain_job_exclusion(
    job: Mapping[str, Any],
    *,
    scope: Mapping[str, set[str] | None],
) -> dict[str, Any] | None:
    """Return one mutually exclusive reason when a job is not selected."""
    title = _text(job.get("title"))
    evaluation_terms = _matched_terms(EVALUATION_TITLE_PATTERN, title)
    quality_terms = _matched_terms(QUALITY_TITLE_PATTERN, title)
    exclusion_terms = _matched_terms(ADJACENT_EXCLUSION_PATTERN, title)
    ai_matches = _field_matches(AI_CONTEXT_PATTERN, job)

    if not _in_scope(job, scope):
        reason_code = "outside_config_scope"
    elif explain_job_selection(job) is not None:
        return None
    elif not title:
        reason_code = "missing_title"
    elif evaluation_terms and not ai_matches:
        reason_code = "evaluation_title_without_ai_context"
    elif quality_terms and ai_matches.get("title") and exclusion_terms:
        reason_code = "hardware_or_manufacturing_test_excluded"
    elif ai_matches.get("title"):
        reason_code = "ai_title_without_evaluation_or_quality_term"
    elif ai_matches and quality_terms:
        reason_code = "quality_title_ai_context_only_in_body"
    elif ai_matches:
        reason_code = "ai_context_only_in_body_without_role_title_terms"
    else:
        reason_code = "no_ai_context"

    return {
        "reason_code": reason_code,
        "reason": EXCLUSION_REASON_LABELS[reason_code],
        "evidence": {
            "title_evaluation_terms": evaluation_terms,
            "title_quality_terms": quality_terms,
            "ai_context_terms_by_field": ai_matches,
            "title_exclusion_terms": exclusion_terms,
        },
    }


def classify_job(job: Mapping[str, Any]) -> str | None:
    explanation = explain_job_selection(job)
    if explanation is None:
        return None
    return str(explanation["cohort"])


def _dedupe_key(job: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _normalized(job.get(field))
        for field in ("company", "title", "description", "requirements")
    )


def _matches(
    text: str,
    patterns: Sequence[tuple[str, Pattern[str]]],
) -> list[str]:
    return [name for name, pattern in patterns if pattern.search(text)]


def _rank_matches(
    match_map: Mapping[str, Sequence[str]],
    jobs_by_key: Mapping[str, Mapping[str, Any]],
    denominator: int,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for job_key, matches in match_map.items():
        title = _text(jobs_by_key[job_key].get("title"))
        for name in matches:
            counts[name] += 1
            if title and title not in examples[name] and len(examples[name]) < 3:
                examples[name].append(title)
    return [
        {
            "name": name,
            "count": count,
            "share": round(count / denominator, 4) if denominator else 0.0,
            "example_titles": examples[name],
        }
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def analyze_jobs(
    jobs: Sequence[Mapping[str, Any]],
    *,
    scope: Mapping[str, set[str] | None],
    configured_companies: Sequence[str],
    input_path: Path,
    config_path: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    eligible = [job for job in jobs if _in_scope(job, scope)]
    selected_raw: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for job in eligible:
        explanation = explain_job_selection(job)
        if explanation is not None:
            selected_raw.append((job, explanation))

    excluded_jobs: list[dict[str, Any]] = []
    for job in jobs:
        exclusion = explain_job_exclusion(job, scope=scope)
        if exclusion is None:
            continue
        excluded_jobs.append(
            {
                "job_id": _text(job.get("job_id")),
                "platform": _text(job.get("platform")),
                "company": _text(job.get("company")),
                "title": _text(job.get("title")),
                "url": _text(job.get("url")),
                "exclusion_reason_code": exclusion["reason_code"],
                "exclusion_reason": exclusion["reason"],
                "exclusion_evidence": exclusion["evidence"],
                "description_present": bool(_text(job.get("description"))),
                "requirements_present": bool(_text(job.get("requirements"))),
            }
        )

    selected: list[tuple[Mapping[str, Any], str]] = []
    raw_matches: list[dict[str, Any]] = []
    first_match_by_key: dict[tuple[str, ...], tuple[int, str]] = {}
    for match_number, (job, explanation) in enumerate(selected_raw, start=1):
        key = _dedupe_key(job)
        first_match = first_match_by_key.get(key)
        included_after_deduplication = first_match is None
        job_id = _text(job.get("job_id"))
        if included_after_deduplication:
            first_match_by_key[key] = (match_number, job_id)
            selected.append((job, str(explanation["cohort"])))

        field_text = _job_body(job)
        raw_matches.append(
            {
                "match_number": match_number,
                "job_id": job_id,
                "platform": _text(job.get("platform")),
                "company": _text(job.get("company")),
                "title": _text(job.get("title")),
                "url": _text(job.get("url")),
                "description": _text(job.get("description")),
                "requirements": _text(job.get("requirements")),
                "city_norm": _text_list(job.get("city_norm")),
                "education": _text(job.get("education")),
                "experience": _text(job.get("experience")),
                "cohort": explanation["cohort"],
                "selection_rule_id": explanation["rule_id"],
                "selection_reason": explanation["reason"],
                "selection_evidence": explanation["evidence"],
                "skill_matches": _matches(field_text, SKILL_PATTERNS),
                "requirement_matches": _matches(
                    field_text, REQUIREMENT_PATTERNS
                ),
                "included_after_content_deduplication": (
                    included_after_deduplication
                ),
                "duplicate_of_match_number": (
                    first_match[0] if first_match is not None else None
                ),
                "duplicate_of_job_id": (
                    first_match[1] if first_match is not None else None
                ),
            }
        )

    jobs_by_key: dict[str, Mapping[str, Any]] = {}
    skill_matches: dict[str, list[str]] = {}
    requirement_matches: dict[str, list[str]] = {}
    city_matches: dict[str, list[str]] = {}
    education_matches: dict[str, list[str]] = {}
    experience_matches: dict[str, list[str]] = {}
    major_matches: dict[str, list[str]] = {}
    project_experience_matches: dict[str, list[str]] = {}
    matched_jobs: list[dict[str, Any]] = []
    for index, (job, cohort) in enumerate(selected, start=1):
        job_key = f"job-{index}"
        jobs_by_key[job_key] = job
        field_text = _job_body(job)
        skills = _matches(field_text, SKILL_PATTERNS)
        requirements = _matches(field_text, REQUIREMENT_PATTERNS)
        cities = _text_list(job.get("city_norm"))
        education_values = _education_values(job)
        experience_values = _experience_values(job)
        majors = _matches(field_text, MAJOR_PATTERNS)
        project_experience = _matches(
            field_text, PROJECT_EXPERIENCE_PATTERNS
        )
        skill_matches[job_key] = skills
        requirement_matches[job_key] = requirements
        city_matches[job_key] = cities
        education_matches[job_key] = education_values
        experience_matches[job_key] = experience_values
        major_matches[job_key] = majors
        project_experience_matches[job_key] = project_experience
        matched_jobs.append(
            {
                "job_id": _text(job.get("job_id")),
                "platform": _text(job.get("platform")),
                "company": _text(job.get("company")),
                "title": _text(job.get("title")),
                "cohort": cohort,
                "skill_matches": skills,
                "requirement_matches": requirements,
                "city_norm": cities,
                "education": _text(job.get("education")),
                "experience": _text(job.get("experience")),
                "major_matches": majors,
                "project_experience_matches": project_experience,
                "url": _text(job.get("url")),
            }
        )

    denominator = len(selected)
    cohort_counts = Counter(cohort for _, cohort in selected)
    company_counts = Counter(_text(job.get("company")) for job, _ in selected)
    all_company_counts = Counter(_text(job.get("company")) for job in eligible)
    observed_companies = {
        _text(job.get("company")) for job in eligible if _text(job.get("company"))
    }
    selected_companies = set(company_counts)
    configured_set = set(configured_companies)

    missing_total = {
        field: sum(not _text(job.get(field)) for job in eligible)
        for field in ("title", "description", "requirements")
    }
    missing_selected = {
        field: sum(not _text(job.get(field)) for job, _ in selected)
        for field in ("title", "description", "requirements")
    }
    missing_threshold_selected = {
        "city_norm": sum(
            not _text_list(job.get("city_norm")) for job, _ in selected
        ),
        "education_structured": sum(
            not _text(job.get("education")) for job, _ in selected
        ),
        "education_after_fallback": sum(
            not values for values in education_matches.values()
        ),
        "experience": sum(
            not _text(job.get("experience")) for job, _ in selected
        ),
    }
    eligible_unique_keys = {_dedupe_key(job) for job in eligible}
    input_job_ids = [_text(job.get("job_id")) for job in jobs]
    nonempty_input_job_ids = [job_id for job_id in input_job_ids if job_id]
    raw_match_job_ids = [
        row["job_id"] for row in raw_matches if row["job_id"]
    ]
    exclusion_counts = Counter(
        row["exclusion_reason_code"] for row in excluded_jobs
    )
    exclusion_companies: dict[str, Counter[str]] = defaultdict(Counter)
    exclusion_examples: dict[str, list[str]] = defaultdict(list)
    for row in excluded_jobs:
        reason_code = row["exclusion_reason_code"]
        company = row["company"] or "<missing>"
        exclusion_companies[reason_code][company] += 1
        title = row["title"] or "<missing>"
        if title not in exclusion_examples[reason_code]:
            exclusion_examples[reason_code].append(title)
    excluded_count = len(excluded_jobs)
    structured_field_coverage: dict[str, dict[str, Any]] = {}
    for field in ("education", "experience"):
        present_jobs = [job for job, _ in selected if _text(job.get(field))]
        exact_value_absent = 0
        value_counts: Counter[str] = Counter()
        for job in present_jobs:
            value = _text(job.get(field))
            value_counts[value] += 1
            body = _job_body(job)
            if value.casefold() not in body.casefold():
                exact_value_absent += 1
        structured_field_coverage[field] = {
            "present_in_selected_jobs": len(present_jobs),
            "exact_value_absent_from_description_and_requirements": (
                exact_value_absent
            ),
            "top_values": [
                {"value": value, "count": count}
                for value, count in value_counts.most_common(10)
            ],
        }

    return {
        "manifest": {
            "generated_at": generated_at
            or datetime.now().astimezone().isoformat(timespec="seconds"),
            "input_file": str(input_path),
            "config_file": str(config_path),
            "input_job_count": len(jobs),
            "eligible_job_count": len(eligible),
            "selected_raw_count": len(selected_raw),
            "selected_job_count": denominator,
            "excluded_job_count": excluded_count,
            "duplicates_removed": len(selected_raw) - denominator,
            "selected_company_count": len(selected_companies),
        },
        "methodology": {
            "scope": "config.yaml 中 enabled=true 的平台；含 companies 的平台按公司名收窄",
            "selection": (
                "核心岗位要求标题出现评测/评估等职责词并具有 AI/Agent 上下文；"
                "标题同时出现 AI/Agent 与测试/质量词的岗位单列为相邻岗位"
            ),
            "deduplication_key": [
                "company",
                "title",
                "description",
                "requirements",
            ],
            "skill_and_requirement_source_fields": [
                "description",
                "requirements",
            ],
            "city_source_field": "city_norm",
            "education_source": (
                "education 优先；为空时从 description + requirements 推断"
            ),
            "experience_source_field": "experience",
            "major_and_project_source_fields": [
                "description",
                "requirements",
            ],
            "share_denominator": "配置范围内、内容去重后的相关岗位",
        },
        "data_quality": {
            "missing_fields_in_eligible_jobs": missing_total,
            "missing_fields_in_selected_jobs": missing_selected,
            "missing_threshold_fields_in_selected_jobs": (
                missing_threshold_selected
            ),
            "description_or_requirements_missing_in_eligible_jobs": sum(
                not _text(job.get("description"))
                or not _text(job.get("requirements"))
                for job in eligible
            ),
            "description_and_requirements_both_missing_in_eligible_jobs": sum(
                not _text(job.get("description"))
                and not _text(job.get("requirements"))
                for job in eligible
            ),
            "content_duplicates_in_eligible_jobs": (
                len(eligible) - len(eligible_unique_keys)
            ),
            "nonempty_job_id_count": len(nonempty_input_job_ids),
            "unique_nonempty_job_id_count": len(set(nonempty_input_job_ids)),
            "duplicate_job_id_rows": (
                len(nonempty_input_job_ids) - len(set(nonempty_input_job_ids))
            ),
            "raw_match_unique_job_id_count": len(set(raw_match_job_ids)),
            "raw_match_duplicate_job_id_rows": (
                len(raw_match_job_ids) - len(set(raw_match_job_ids))
            ),
            "configured_company_count": len(configured_set),
            "observed_company_count": len(observed_companies),
            "configured_companies_without_data": sorted(
                configured_set - observed_companies
            ),
            "configured_companies_without_matches": sorted(
                (configured_set & observed_companies) - selected_companies
            ),
        },
        "cohorts": [
            {
                "name": name,
                "count": count,
                "share": round(count / denominator, 4) if denominator else 0.0,
            }
            for name, count in sorted(
                cohort_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "skills": _rank_matches(
            skill_matches, jobs_by_key, denominator
        ),
        "requirements": _rank_matches(
            requirement_matches, jobs_by_key, denominator
        ),
        "cities": _rank_matches(city_matches, jobs_by_key, denominator),
        "education": _rank_matches(
            education_matches, jobs_by_key, denominator
        ),
        "experience": _rank_matches(
            experience_matches, jobs_by_key, denominator
        ),
        "majors": _rank_matches(major_matches, jobs_by_key, denominator),
        "project_experience": _rank_matches(
            project_experience_matches, jobs_by_key, denominator
        ),
        "companies": [
            {
                "name": name,
                "count": count,
                "share": round(count / denominator, 4) if denominator else 0.0,
                "all_job_count": all_company_counts[name],
                "all_job_share": (
                    round(all_company_counts[name] / len(eligible), 4)
                    if eligible
                    else 0.0
                ),
            }
            for name, count in sorted(
                company_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "exclusion_reasons": [
            {
                "reason_code": reason_code,
                "reason": EXCLUSION_REASON_LABELS[reason_code],
                "count": count,
                "share_of_input": round(count / len(jobs), 4) if jobs else 0.0,
                "share_of_excluded": (
                    round(count / excluded_count, 4) if excluded_count else 0.0
                ),
                "top_companies": [
                    {"name": name, "count": company_count}
                    for name, company_count in exclusion_companies[
                        reason_code
                    ].most_common(5)
                ],
                "example_titles": exclusion_examples[reason_code][:5],
            }
            for reason_code, count in sorted(
                exclusion_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "field_provenance": [
            {
                "dimension": "城市",
                "current_ranking_source": "city_norm",
                "available_clean_fields": [
                    "location",
                    "locations_norm",
                    "city_norm",
                    "province_norm",
                ],
            },
            {
                "dimension": "学历",
                "current_ranking_source": (
                    "education 优先；为空时读取 description + requirements"
                ),
                "available_clean_fields": ["education"],
            },
            {
                "dimension": "专业",
                "current_ranking_source": "description + requirements 正则命中",
                "available_clean_fields": [],
            },
            {
                "dimension": "工作经验",
                "current_ranking_source": "experience",
                "available_clean_fields": ["experience"],
            },
            {
                "dimension": "项目经验",
                "current_ranking_source": "description + requirements 正则命中",
                "available_clean_fields": [],
            },
            {
                "dimension": "技能",
                "current_ranking_source": "description + requirements 正则命中",
                "available_clean_fields": [],
            },
        ],
        "structured_field_coverage": structured_field_coverage,
        "raw_matches": raw_matches,
        "excluded_jobs": excluded_jobs,
        "matched_jobs": matched_jobs,
    }


def _percent(value: float) -> str:
    return f"{value:.1%}"


def _markdown_ranking(rows: Iterable[Mapping[str, Any]]) -> str:
    rendered = ["| 排名 | 项目 | 岗位数 | 占比 |", "|---:|---|---:|---:|"]
    for rank, row in enumerate(rows, start=1):
        rendered.append(
            f"| {rank} | {row['name']} | {row['count']} | "
            f"{_percent(float(row['share']))} |"
        )
    return "\n".join(rendered)


def _markdown_company_table(rows: Iterable[Mapping[str, Any]]) -> str:
    rendered = [
        "| 排名 | 公司 | AI评测岗位数 | 占AI评测岗位 | 公司全部岗位数 | 占全部岗位 |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(rows, start=1):
        rendered.append(
            f"| {rank} | {row['name']} | {row['count']} | "
            f"{_percent(float(row['share']))} | {row['all_job_count']} | "
            f"{_percent(float(row['all_job_share']))} |"
        )
    return "\n".join(rendered)


def build_markdown_report(analysis: Mapping[str, Any]) -> str:
    manifest = analysis["manifest"]
    skills = analysis["skills"]
    requirements = analysis["requirements"]
    cohorts = analysis["cohorts"]
    companies = analysis["companies"]
    cities = analysis["cities"]
    education = analysis["education"]
    experience = analysis["experience"]
    majors = analysis["majors"]
    project_experience = analysis["project_experience"]
    quality = analysis["data_quality"]
    top_skills = skills[:10]
    top_requirements = requirements[:10]

    skill_summary = "、".join(
        f"{row['name']}（{_percent(row['share'])}）" for row in top_skills[:3]
    ) or "未识别出稳定高频项"
    requirement_summary = "、".join(
        f"{row['name']}（{_percent(row['share'])}）"
        for row in top_requirements[:3]
    ) or "未识别出稳定高频项"
    absent = "、".join(quality["configured_companies_without_data"]) or "无"
    no_matches = "、".join(quality["configured_companies_without_matches"]) or "无"

    cohort_table = _markdown_ranking(cohorts)
    skill_table = _markdown_ranking(top_skills)
    requirement_table = _markdown_ranking(top_requirements)
    city_table = _markdown_ranking(cities[:10])
    education_table = _markdown_ranking(education[:10])
    experience_table = _markdown_ranking(experience[:10])
    major_table = _markdown_ranking(majors[:10])
    project_experience_table = _markdown_ranking(project_experience[:10])
    company_table = _markdown_company_table(companies)
    missing_threshold = quality["missing_threshold_fields_in_selected_jobs"]

    return f"""# AI 与 Agent 评测岗位热门技能报告

## Executive Summary

- **共识别 {manifest['selected_job_count']} 个去重后的相关岗位。** 原始命中 {manifest['selected_raw_count']} 条，按公司、标题、description、requirements 去除 {manifest['duplicates_removed']} 条内容重复记录，覆盖 {manifest['selected_company_count']} 家公司。
- **热门技能集中在：** {skill_summary}。
- **高频要求集中在：** {requirement_summary}。

## 分析口径

输入为 `{manifest['input_file']}`，公司范围沿用 `{manifest['config_file']}` 中 `enabled: true` 的平台配置。岗位相关性由标题与正文共同判断。技能、专业和项目经验读取 `description + requirements`；城市读取 `city_norm`；学历优先读取 `education`，为空时从正文推断；工作经验读取 `experience`。除公司“占全部岗位”外，各分析占比的分母均为 {manifest['selected_job_count']} 个去重后的相关岗位；多城市、多专业和多项目主题可以重复计数，因此相关占比不可相加。公司“占全部岗位”的分母是配置范围内全部 {manifest['eligible_job_count']:,} 条岗位。

### 岗位分层

{cohort_table}

## 热门技能

以下排名反映招聘描述中反复出现的能力主题，可用于设计学习优先级或候选人能力矩阵。

{skill_table}

## 高频要求

这些要求更接近招聘门槛、通用能力和背景偏好；“优先”类表述不等同于硬性要求。

{requirement_table}

## 城市分布

城市直接使用 clean 文件中的 `city_norm`。一个岗位可对应多个城市，因此城市占比不可相加；缺失城市的命中岗位为 {missing_threshold['city_norm']} 条。

{city_table}

## 学历门槛

学历优先采用结构化 `education`；该字段为空时才从 description 和 requirements 推断，避免结构化门槛被忽略。结构化学历为空的命中岗位为 {missing_threshold['education_structured']} 条，经过正文补充后仍未识别学历门槛的岗位为 {missing_threshold['education_after_fallback']} 条。

{education_table}

## 工作经验门槛

工作经验采用结构化 `experience`；未填充该字段的命中岗位为 {missing_threshold['experience']} 条。

{experience_table}

## 专业背景

专业背景从 description 和 requirements 中识别，同一岗位可以命中多个专业族。

{major_table}

## 项目经验

项目经验从 description 和 requirements 中识别明确项目经历、AI/大模型落地、从0到1/完整交付和开源项目等主题。未命中不代表岗位明确不要求项目经验，只表示正文未出现这些可识别表述。

{project_experience_table}

## 公司覆盖

“占AI评测岗位”以去重后的相关岗位为分母；“占全部岗位”以配置范围内全部岗位为分母，后者包含该公司的非AI评测岗位。

{company_table}

## 建议

1. 优先补齐前三项技能，并用可复现的评测集、指标定义和错误分析案例证明能力。
2. 项目经历应同时呈现评测设计、数据处理、自动化执行和结果闭环，避免只罗列模型或工具名称。
3. 针对 Agent 岗位，单独准备任务完成度、工具调用、长链路稳定性与安全边界的评测案例。

## 进一步问题

- 不同公司和岗位族的技能组合是否存在显著差异？
- 高频要求中哪些是硬门槛，哪些只是“优先”偏好？
- 若加入更多日期快照，热门技能的排名是否稳定？

## 局限与数据质量

- 配置中无岗位数据的公司：{absent}。
- 有数据但本口径未命中相关岗位的公司：{no_matches}。
- 配置范围内有 {quality['content_duplicates_in_eligible_jobs']:,} 条内容重复记录；缺失 description {quality['missing_fields_in_eligible_jobs']['description']} 条、缺失 requirements {quality['missing_fields_in_eligible_jobs']['requirements']} 条。入选岗位中对应缺失分别为 {quality['missing_fields_in_selected_jobs']['description']} 条和 {quality['missing_fields_in_selected_jobs']['requirements']} 条；缺失 city_norm、结构化 education、正文补充后仍未识别 education、experience 分别为 {missing_threshold['city_norm']}、{missing_threshold['education_structured']}、{missing_threshold['education_after_fallback']}、{missing_threshold['experience']} 条。
- 这是基于关键词主题的描述性分析，不等同于岗位需求强度或候选人录用概率；相邻的 AI 质量/测试岗位已单独分层，便于审阅边界。
"""


def _markdown_quote(text: str) -> str:
    if not text:
        return "> `<missing>`"
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def build_match_audit_markdown(analysis: Mapping[str, Any]) -> str:
    manifest = analysis["manifest"]
    sections = [
        "# AI 与 Agent 评测岗位逐条命中审计",
        "",
        (
            f"输入共 {manifest['input_job_count']:,} 行；规则原始命中 "
            f"{manifest['selected_raw_count']:,} 条。本文件保留内容重复行，"
            "并标记其首次命中记录，供逐条检查。"
        ),
        "",
        "判断规则：核心岗位要求 title 命中评测/测评/评估等职责词，且 title、"
        "description 或 requirements 至少一处命中 AI/Agent 上下文；相邻岗位要求 "
        "title 同时命中 AI/Agent 与测试/质量词，并且不命中硬件/制造排除词。",
        "",
    ]
    for row in analysis["raw_matches"]:
        duplicate_note = "保留进入汇总"
        if not row["included_after_content_deduplication"]:
            duplicate_note = (
                f"内容重复；对应第 {row['duplicate_of_match_number']} 条"
                f"（job_id={row['duplicate_of_job_id']}）"
            )
        url = row["url"] or "<missing>"
        cities = "、".join(row["city_norm"]) or "<missing>"
        education = row["education"] or "<missing>"
        experience = row["experience"] or "<missing>"
        sections.extend(
            [
                f"## {row['match_number']}. {row['title']}",
                "",
                f"- job_id: `{row['job_id']}`",
                f"- company: {row['company']}",
                f"- platform: `{row['platform']}`",
                f"- url: {url}",
                f"- city_norm: {cities}",
                f"- education: {education}",
                f"- experience: {experience}",
                f"- 分类: {row['cohort']}",
                f"- 规则: `{row['selection_rule_id']}`",
                f"- 去重状态: {duplicate_note}",
                f"- 判断理由: {row['selection_reason']}",
                "",
                "### description",
                "",
                _markdown_quote(row["description"]),
                "",
                "### requirements",
                "",
                _markdown_quote(row["requirements"]),
                "",
            ]
        )
    return "\n".join(sections)


def build_exclusion_report_markdown(analysis: Mapping[str, Any]) -> str:
    """Build a compact audit report for every non-selected job."""
    manifest = analysis["manifest"]
    quality = analysis["data_quality"]
    coverage = analysis["structured_field_coverage"]
    reason_rows = [
        "| 排除原因 | 岗位数 | 占全部输入 | 占全部排除 | 示例标题 |",
        "|---|---:|---:|---:|---|",
    ]
    for row in analysis["exclusion_reasons"]:
        examples = "；".join(
            str(title).replace("|", "\\|") for title in row["example_titles"][:3]
        )
        reason_rows.append(
            f"| {row['reason']} (`{row['reason_code']}`) | {row['count']:,} | "
            f"{_percent(row['share_of_input'])} | "
            f"{_percent(row['share_of_excluded'])} | {examples} |"
        )

    provenance_rows = [
        "| 维度 | 当前高频统计来源 | clean 中可用的结构化字段 | 已知缺口 |",
        "|---|---|---|---|",
    ]
    for row in analysis["field_provenance"]:
        fields = "、".join(row["available_clean_fields"]) or "无"
        provenance_rows.append(
            f"| {row['dimension']} | {row['current_ranking_source']} | "
            f"{fields} | {row.get('known_gap', '无')} |"
        )

    return f"""# AI / Agent 评测岗位过滤审计报告

## 结论

- 输入文件实际包含 **{manifest['input_job_count']:,}** 条岗位；非空 `job_id` 为 {quality['nonempty_job_id_count']:,} 个，唯一 `job_id` 为 {quality['unique_nonempty_job_id_count']:,} 个。
- 相关性规则原始命中 **{manifest['selected_raw_count']:,}** 条，排除 **{manifest['excluded_job_count']:,}** 条。随后只对命中项按公司、标题、description、requirements 做内容去重，得到 {manifest['selected_job_count']:,} 条；原始命中数不是对全部岗位去重后的总数。
- 排除并不表示岗位一定与 AI 无关；它只表示岗位未满足当前“标题职责词 + AI/Agent 上下文”的高精度规则。正文出现 AI、但标题没有评测/测试职责词的岗位会被明确归入下表对应类别。

## 排除原因分布

{chr(10).join(reason_rows)}

每个被排除岗位的 `job_id`、公司、标题、URL、互斥原因和命中证据写入 `{manifest['excluded_jobs_jsonl_file']}`，可按 `exclusion_reason_code` 逐条复核。

## 字段空值与 clean 行为

- 配置范围内缺失 description {quality['missing_fields_in_eligible_jobs']['description']:,} 条，缺失 requirements {quality['missing_fields_in_eligible_jobs']['requirements']:,} 条；两者任一缺失 {quality['description_or_requirements_missing_in_eligible_jobs']:,} 条，两者同时缺失 {quality['description_and_requirements_both_missing_in_eligible_jobs']:,} 条。
- `src.clean.jobs.clean_job_locations` 对每行做浅复制，仅根据原始 `location` 写入 `locations_norm`、`location_level`、`province_norm`、`city_norm`，不会删除、补写或改写 description、requirements、education、experience。

## 高频统计字段来源

{chr(10).join(provenance_rows)}

技能、专业和项目经验来自 `description + requirements`；城市来自 `city_norm`；学历优先读取 `education`，为空时从正文推断；工作经验来自 `experience`。在 {manifest['selected_job_count']:,} 个去重命中岗位中，`education` 非空 {coverage['education']['present_in_selected_jobs']:,} 条，其中 {coverage['education']['exact_value_absent_from_description_and_requirements']:,} 条的结构化学历值没有原样出现在 description/requirements；`experience` 非空 {coverage['experience']['present_in_selected_jobs']:,} 条，其中 {coverage['experience']['exact_value_absent_from_description_and_requirements']:,} 条的结构化经验值没有原样出现在正文。

## 可复现命令

每日依次执行采集、清洗和分析时，统一使用北京时间日期变量：

```bash
RUN_DATE=$(TZ=Asia/Shanghai date +%F)

python -m src.main --config config.yaml --date "$RUN_DATE"

python -m src.clean.cli clean-jobs \\
  --input "data/raw/$RUN_DATE.json" \\
  --date "$RUN_DATE"

python -m src.analysis.ai_eval_jobs \\
  --date "$RUN_DATE" \\
  --config config.yaml \\
  --output-dir data/analysis
```

分析命令省略 `--input` 和 `--date` 时，也会自动选择北京时间当天的 `data/clean/YYYY-MM-DD.json`。raw 采集命令会访问配置中的招聘来源；本次本地分析没有重跑真实采集。

## 方法与限制

- 核心命中：标题含评测/测评/评估/评价/Evaluation/Evaluator/Benchmark/红队等词，并且 title、description、requirements 至少一处含 AI/Agent 上下文。
- 相邻命中：标题同时含测试/质量词和 AI/Agent 上下文，且标题不含硬件/制造排除词。
- 排除原因按固定优先级互斥分类，所有输入行满足“原始命中或某一排除原因”，便于总量对账。
- 这是规则审计，不是人工标注的召回率评估；“正文 AI 上下文但标题无职责词”是最值得人工抽样复核的召回风险组。
"""


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        file.write(text)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, path)


def _json_line(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(value, ensure_ascii=False)
    for character, escaped in (
        ("\u0085", "\\u0085"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        serialized = serialized.replace(character, escaped)
    return serialized


def run_analysis(
    input_path: Path | None = None,
    *,
    analysis_date: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    input_path = resolve_input_path(
        input_path,
        analysis_date=analysis_date,
    )
    jobs = load_jobs(input_path)
    scope = load_company_scope(config_path)
    companies = configured_company_names(config_path, scope)
    analysis = analyze_jobs(
        jobs,
        scope=scope,
        configured_companies=companies,
        input_path=input_path,
        config_path=config_path,
        generated_at=generated_at,
    )

    stem = input_path.stem
    json_path = output_dir / f"{stem}_ai_eval_analysis.json"
    report_path = output_dir / f"{stem}_ai_eval_report.md"
    raw_matches_jsonl_path = output_dir / f"{stem}_ai_eval_hits.jsonl"
    raw_matches_report_path = output_dir / f"{stem}_ai_eval_hits.md"
    excluded_jobs_jsonl_path = output_dir / f"{stem}_ai_eval_exclusions.jsonl"
    exclusion_report_path = output_dir / f"{stem}_ai_eval_exclusion_report.md"
    analysis["manifest"]["analysis_file"] = str(json_path)
    analysis["manifest"]["report_file"] = str(report_path)
    analysis["manifest"]["raw_matches_jsonl_file"] = str(
        raw_matches_jsonl_path
    )
    analysis["manifest"]["raw_matches_report_file"] = str(
        raw_matches_report_path
    )
    analysis["manifest"]["excluded_jobs_jsonl_file"] = str(
        excluded_jobs_jsonl_path
    )
    analysis["manifest"]["exclusion_report_file"] = str(
        exclusion_report_path
    )
    _write_text_atomic(
        json_path,
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
    )
    _write_text_atomic(report_path, build_markdown_report(analysis))
    _write_text_atomic(
        raw_matches_jsonl_path,
        "\n".join(
            _json_line(row)
            for row in analysis["raw_matches"]
        )
        + "\n",
    )
    _write_text_atomic(
        raw_matches_report_path,
        build_match_audit_markdown(analysis),
    )
    _write_text_atomic(
        excluded_jobs_jsonl_path,
        "\n".join(_json_line(row) for row in analysis["excluded_jobs"])
        + ("\n" if analysis["excluded_jobs"] else ""),
    )
    _write_text_atomic(
        exclusion_report_path,
        build_exclusion_report_markdown(analysis),
    )
    return json_path, report_path, analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze AI/Agent evaluation roles from cleaned local job data"
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--input",
        type=Path,
        help="clean JSON path; overrides the date-derived default",
    )
    input_group.add_argument(
        "--date",
        dest="analysis_date",
        type=_date_arg,
        help="clean snapshot date in YYYY-MM-DD; defaults to today's Asia/Shanghai date",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--print-matches",
        action="store_true",
        help="print every raw match as one JSON object per line",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    json_path, report_path, analysis = run_analysis(
        args.input,
        analysis_date=args.analysis_date,
        config_path=args.config,
        output_dir=args.output_dir,
    )
    manifest = analysis["manifest"]
    print(
        f"Analyzed {manifest['eligible_job_count']} eligible jobs; "
        f"selected {manifest['selected_job_count']} deduplicated jobs"
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {report_path}")
    print(f"Wrote {manifest['raw_matches_jsonl_file']}")
    print(f"Wrote {manifest['raw_matches_report_file']}")
    print(f"Wrote {manifest['excluded_jobs_jsonl_file']}")
    print(f"Wrote {manifest['exclusion_report_file']}")
    if args.print_matches:
        for row in analysis["raw_matches"]:
            print(_json_line(row))


if __name__ == "__main__":
    main()
