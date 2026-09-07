from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
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
CLASSIFICATION_INPUT_FIELDS = ("title", "description", "requirements")

ROLE_FAMILIES = {
    "qa_test",
    "quality_engineering",
    "evaluation_engineering",
    "algorithm_research",
    "product",
    "development",
    "operations",
    "domain_expert",
}
AI_RELATIONS = {
    "core_ai_evaluation",
    "ai_product_quality",
    "ai_for_testing",
    "ai_context_only",
    "none",
}
SENIORITY_LEVELS = {"regular", "senior", "expert_lead", "intern"}
CAREER_POOLS = {"P1", "P2", "REF", "X"}

QA_TEST_TITLE_PATTERN = re.compile(
    r"(?i)(?:(?<![A-Za-z])QA(?![A-Za-z])|(?<![A-Za-z])SDET(?![A-Za-z])|"
    r"测试工程师|系统集成测试|软件测试|测试实习生)"
)
QUALITY_ENGINEERING_TITLE_PATTERN = re.compile(
    r"(?i)(?:测试开发|测试专家|测试架构师|质量工程师|质量保障(?:工程师)?|"
    r"质量平台|质量工具|质量负责人|质量架构师|质量效能|质效)"
)
EVALUATION_ENGINEERING_TITLE_PATTERN = re.compile(
    r"(?i)(?:评测|测评|评估)"
)
PRODUCT_ROLE_PATTERN = re.compile(
    r"(?:产品.{0,8}(?:经理|负责人|专家|运营)|(?:经理|负责人).{0,8}产品)"
)
AGENT_DEVELOPMENT_ROLE_PATTERN = re.compile(
    r"(?i)(?:(?:AI\s*|质量)?Agent开发|智能体开发)"
)
ALGORITHM_OR_RESEARCH_ROLE_PATTERN = re.compile(
    r"(?:算法.{0,8}(?:工程师|研究员|研究科学家)|(?:工程师|研究员).{0,8}算法|"
    r"模型训练|研究科学家)"
)
GENERAL_RND_ROLE_PATTERN = re.compile(
    r"(?:后台开发|后端开发|AI产品研发|数据质量研发|搜索质量算法研发|"
    r"质效研发|平台研发|研发架构师|普通研发工程师)"
)
OPERATIONS_ROLE_PATTERN = re.compile(r"(?:运营|运维工程师)")
DOMAIN_EXPERT_ROLE_PATTERN = re.compile(
    r"(?:领域专家|行业专家|医学影像科医生|临床医生|医师)"
)
EXPERT_LEAD_TITLE_PATTERN = re.compile(
    r"(?i)(?:专家|架构(?:师|工程师)|负责人|"
    r"(?<![A-Za-z])Lead(?:er)?(?![A-Za-z]))"
)
SENIOR_TITLE_PATTERN = re.compile(
    r"(?i)(?:高级|资深|(?<![A-Za-z])Senior(?![A-Za-z]))"
)
INTERN_TITLE_PATTERN = re.compile(r"(?:实习|校招实习)")
HARDWARE_DOMAIN_PATTERN = re.compile(
    r"(?i)(?:SSD|AI\s*芯片|芯片|硬件|GPU|NPU|服务器|驱动|固件|"
    r"编译器|加速器|加速卡|系统集成测试)"
)
GAME_DOMAIN_PATTERN = re.compile(r"(?:游戏|手游|端游|电竞)")
SECURITY_DOMAIN_TITLE_PATTERN = re.compile(
    r"(?i)^(?:[\w-]+)?(?:安全评测工程师|Security(?:\s+Evaluation)?\s+Engineer)"
)
MANAGEMENT_DUTY_PATTERN = re.compile(
    r"(?:招聘(?:团队)?成员|团队成员招聘|培养(?:团队)?成员|团队成员培养|"
    r"人才梯队(?:建设)?|团队资源分配|制定测试团队工作目标|"
    r"制定团队目标|对(?:团队|组织)(?:的)?(?:交付|结果)负责|"
    r"组织并管理.{0,12}团队)"
)
MANAGEMENT_REQUIREMENT_PATTERN = re.compile(
    r"(?:具备|具有|要求|至少).{0,16}(?:团队管理.{0,8}梯队建设|"
    r"团队管理和梯队建设|人员管理|团队资源分配)"
)
SIX_PLUS_YEARS_PATTERN = re.compile(r"(?:6|六)\s*(?:年|年以上|年及以上)")
CORE_EVALUATION_DUTY_PATTERN = re.compile(
    r"(?i)(?:模型能力评测|Agent任务评测|模型缺陷归因|评测驱动|"
    r"评测结果.{0,24}(?:模型|算法).{0,12}(?:优化|迭代)|"
    r"(?:AI算法|模型|Agent).{0,16}评测(?:标准|流程|体系|指标|方法)|"
    r"(?:评测标准|评测流程|评测体系|评测指标|Benchmark|评测集).{0,24}"
    r"(?:AI算法|模型|Agent|智能体)|"
    r"(?:构建|建设|制定|设计).{0,16}(?:Benchmark|评测集|评测标准|"
    r"评测指标|评测框架))"
)
CORE_EVALUATION_TITLE_PATTERN = re.compile(
    r"(?i)(?:(?:AI|算法|模型|大模型|Agent|智能体).{0,12}(?:评测|测评)|"
    r"(?:评测|测评).{0,12}(?:AI|算法|模型|大模型|Agent|智能体))"
)
CORE_EVALUATION_DECISION_PATTERN = re.compile(
    r"(?:支撑模型与策略选型|影响框架演进|评测驱动Agent|"
    r"模型内在机理|模型失效点|模型缺陷归因)"
)
AI_FOR_TESTING_DUTY_PATTERN = re.compile(
    r"(?is)(?:测试\s*Agent|Test\s*Agent|Agentic\s*QA|智能测试机器人|"
    r"AI\s*自动化测试|"
    r"用例(?:智能|自动)生成|测试用例生成|脚本生成|测试自愈|智能回归|"
    r"智能(?:执行|诊断|归因)|缺陷(?:智能)?(?:诊断|归因|修复)|"
    r"AI(?:赋能|驱动|辅助).{0,36}(?:测试|质量|研发效能)|"
    r"(?:AI|大模型).{0,30}在(?:测试|质量保障|质量工程).{0,12}(?:领域)?(?:的)?应用|"
    r"(?:AI|Agent|智能体).{0,96}(?:支撑|实现).{0,24}(?:用例生成|脚本生成|缺陷修复)|"
    r"(?:AI|大模型|LLM|Agent|智能体).{0,24}(?:应用|落地|融入|用于)"
    r".{0,24}(?:测试|质量保障|质量工程)|"
    r"(?:测试|质量保障|质量工程).{0,24}(?:应用|落地|引入|使用)"
    r".{0,20}(?:AI|大模型|LLM|Agent|智能体)|"
    r"(?:提升测试效率|测试提效|提效提质).{0,24}(?:AI|大模型|Agent)|"
    r"(?:AI|大模型|Agent).{0,24}(?:提升测试效率|测试提效|提效提质)|"
    r"从[“\"]?自动化.{0,16}智能化|AI测试工具|AI自动化测试)"
)
AI_FOR_TESTING_STRONG_PATTERN = re.compile(
    r"(?is)(?:(?:设计|搭建|构建|开发|落地|实现|建设|推动).{0,20}"
    r"(?:测试\s*Agent|Test\s*Agent|Agentic\s*QA|智能测试)|"
    r"(?:测试\s*Agent|Test\s*Agent|Agentic\s*QA|智能测试)"
    r".{0,20}(?:设计|搭建|构建|开发|落地|实现|建设|推动)|"
    r"测试用例(?:的)?(?:自动|智能)?生成|用例自动生成|用例与脚本生成|"
    r"AI\s*Agent.{0,96}(?:用例生成|缺陷修复)|测试自愈|"
    r"探索并(?:实践|落地).{0,28}(?:AI|大模型|Agent).{0,28}"
    r"(?:测试|质量保障|质量工程))"
)
AI_PRODUCT_QUALITY_DUTY_PATTERN = re.compile(
    r"(?is)(?:(?:负责|保障|开展|覆盖|面向|结合).{0,28}"
    r"(?:AI\s*(?:产品|应用|工作台)|大模型产品|大模型业务|模型服务|"
    r"基础模型生产平台|基模生产平台|Agent\s*(?:产品|服务|平台|运行链路)|"
    r"智能助手|MaaS|AIGC).{0,72}"
    r"(?:测试|质量保障|质量体系|质量|稳定性|可靠性|验收|验证)|"
    r"(?:AI\s*(?:产品|应用|工作台)|大模型产品|大模型业务|模型服务|"
    r"基础模型生产平台|基模生产平台|Agent\s*(?:产品|服务|平台|运行链路)|"
    r"智能助手|MaaS|AIGC).{0,20}(?:全链路|端到端).{0,20}"
    r"(?:测试|质量|保障|验证)|"
    r"(?:AIGC|大模型|Agent|智能体|算法).{0,28}"
    r"(?:效果评测|评测工作|评测能力建设|自动化评估)|"
    r"(?:大模型|模型|Agent)\s*(?:服务|产品|平台).{0,28}"
    r"(?:质量保障|质量体系|稳定性|可靠性|测试)|"
    r"(?:小程序Agent|Agent\s*服务).{0,120}"
    r"(?:测试|质量保障|质量体系|稳定性|可靠性|验证|功能正确性|"
    r"高可用性|性能压测|系统稳定)|"
    r"(?:AI产品业务特点|AI质量体系|大模型相关质量体系|"
    r"Prompt/Agent/Chain).{0,64}(?:测试|质量|评测|稳定性)|"
    r"基于AIGC技术.{0,28}(?:质量保证体系|优化测试过程)|"
    r"产品评测.{0,48}(?:评测标准|评测Agent|评测数据集)|"
    r"大模型应用效果.{0,24}(?:性能|稳定性|质量))"
)
AI_PRODUCT_QUALITY_TITLE_PATTERN = re.compile(
    r"(?i)(?:MaaS|基模生产平台|AI\s*(?:产品|应用|助手)|智能助手|"
    r"大模型方向|大模型测试|多模态测试|Agent稳定性测试|Agent测试工程师)"
)
AI_PRODUCT_QUALITY_PRIMARY_TITLE_PATTERN = re.compile(
    r"(?i)(?:MaaS|基模生产平台|AI方向|AI效能与质量保障|AI测试架构师|"
    r"大模型测试开发|大模型方向|AI\s*软件测试|AI智能化方向)"
)
AI_CONTEXT_ONLY_PATTERN = re.compile(
    r"(?i)(?:AI|AIGC|大模型|LLM|Agent|智能体|机器学习|深度学习)"
)
ALGORITHM_RESEARCH_HARD_PATTERN = re.compile(
    r"(?is)(?:算法研究员|研究科学家|模型结构.{0,24}训练过程|"
    r"深度参与.{0,20}(?:预训练|SFT|RLHF)|"
    r"基模.{0,20}(?:评测和优化|设计评测和优化)|"
    r"(?:扎实的研究|论文经验).{0,20}(?:机器学习|多模态|评测)|"
    r"(?:机器学习|多模态|评测).{0,20}(?:扎实的研究|论文经验))"
)

EXCLUSION_REASON_LABELS = {
    "outside_config_scope": "不在 config.yaml 启用的平台/公司范围",
    "role_product": "产品岗位，不是 QA/测试主职能",
    "role_agent_development": "Agent 开发岗位，不是 QA/测试主职能",
    "role_algorithm_or_research": "算法、模型训练或研究岗位",
    "role_general_rnd": "普通研发或平台研发岗位，不是 QA/测试主职能",
    "role_operations": "运营或运维岗位，不是 QA/测试主职能",
    "role_domain_expert": "领域专家岗位，不是 QA/测试主职能",
    "level_expert_lead": "专家、架构师、负责人或人员管理岗位进入 REF 池",
    "level_intern": "实习岗位不进入个人候选池",
    "domain_hardware": "硬件、芯片、GPU、服务器或基础设施测试方向",
    "domain_game": "游戏业务方向不进入个人候选池",
    "domain_security": "安全业务方向不进入个人候选池",
    "ai_not_primary_duty": "AI 只作为背景、偏好或弱探索，不是岗位主责",
}

EXCLUSION_REASON_PRIORITY = (
    "outside_config_scope",
    "role_product",
    "role_agent_development",
    "role_algorithm_or_research",
    "role_general_rnd",
    "role_operations",
    "role_domain_expert",
    "domain_hardware",
    "domain_game",
    "domain_security",
    "level_expert_lead",
    "level_intern",
    "ai_not_primary_duty",
)


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


def normalize_content_text(value: Any) -> str:
    """Normalize one frozen/job content field for hashing and deduplication."""
    text = value if isinstance(value, str) else ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in text.split("\n"):
        normalized_line = re.sub(r"\s+", " ", line).strip()
        if normalized_line:
            lines.append(normalized_line)
    return "\n".join(lines).casefold()


def classification_input(job: Mapping[str, Any]) -> dict[str, str]:
    """Copy only the three fields authorized as classifier inputs."""
    return {field: _text(job.get(field)) for field in CLASSIFICATION_INPUT_FIELDS}


def normalized_job_content(job: Mapping[str, Any]) -> tuple[str, str, str]:
    """Return the normalized title/description/requirements content key."""
    return tuple(
        normalize_content_text(job.get(field))
        for field in CLASSIFICATION_INPUT_FIELDS
    )  # type: ignore[return-value]


def job_content_sha256(job: Mapping[str, Any]) -> str:
    """Hash the canonical three-field content payload."""
    title, description, requirements = normalized_job_content(job)
    payload = f"{title}\n---\n{description}\n---\n{requirements}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _responsibility_segments(job: Mapping[str, Any]) -> list[str]:
    """Return bounded responsibility clauses without using requirements."""
    description = _text(job.get("description"))
    if not description:
        return []
    segments = [
        " ".join(segment.split())
        for segment in re.split(r"[；;。\n\r]+", description)
    ]
    return list(dict.fromkeys(segment for segment in segments if segment))


def _pattern_evidence(pattern: Pattern[str], text: str) -> list[str]:
    return _matched_terms(pattern, text)


def _role_classification(title: str) -> tuple[str, str | None, list[str]]:
    ordered_patterns: tuple[tuple[str, str | None, Pattern[str]], ...] = (
        ("product", "role_product", PRODUCT_ROLE_PATTERN),
        ("operations", "role_operations", OPERATIONS_ROLE_PATTERN),
        ("domain_expert", "role_domain_expert", DOMAIN_EXPERT_ROLE_PATTERN),
        (
            "development",
            "role_agent_development",
            AGENT_DEVELOPMENT_ROLE_PATTERN,
        ),
        (
            "quality_engineering",
            None,
            QUALITY_ENGINEERING_TITLE_PATTERN,
        ),
        ("qa_test", None, QA_TEST_TITLE_PATTERN),
        ("development", "role_general_rnd", GENERAL_RND_ROLE_PATTERN),
        (
            "algorithm_research",
            "role_algorithm_or_research",
            ALGORITHM_OR_RESEARCH_ROLE_PATTERN,
        ),
        (
            "evaluation_engineering",
            None,
            EVALUATION_ENGINEERING_TITLE_PATTERN,
        ),
    )
    for role_family, reason_code, pattern in ordered_patterns:
        terms = _pattern_evidence(pattern, title)
        if terms:
            return role_family, reason_code, terms
    return "development", "role_general_rnd", []


def _seniority_classification(job: Mapping[str, Any]) -> tuple[str, list[str]]:
    title = _text(job.get("title"))
    if INTERN_TITLE_PATTERN.search(title):
        return "intern", _pattern_evidence(INTERN_TITLE_PATTERN, title)
    if EXPERT_LEAD_TITLE_PATTERN.search(title):
        return "expert_lead", _pattern_evidence(EXPERT_LEAD_TITLE_PATTERN, title)
    description = _text(job.get("description"))
    requirements = _text(job.get("requirements"))
    management_evidence = _pattern_evidence(
        MANAGEMENT_DUTY_PATTERN, description
    ) + _pattern_evidence(MANAGEMENT_REQUIREMENT_PATTERN, requirements)
    if management_evidence:
        return "expert_lead", management_evidence
    if SENIOR_TITLE_PATTERN.search(title):
        return "senior", _pattern_evidence(SENIOR_TITLE_PATTERN, title)
    if SIX_PLUS_YEARS_PATTERN.search(requirements):
        return "senior", _pattern_evidence(SIX_PLUS_YEARS_PATTERN, requirements)
    return "regular", []


def _relation_evidence(
    pattern: Pattern[str],
    field: str,
    text: str,
) -> dict[str, Any] | None:
    terms = _pattern_evidence(pattern, text)
    if not terms:
        return None
    return {"field": field, "text": text, "terms": terms}


def _ai_relation_classification(
    job: Mapping[str, Any],
    *,
    role_family: str,
    hard_domain_reason: str | None,
) -> tuple[str, dict[str, Any] | None, str]:
    title = _text(job.get("title"))
    description = _text(job.get("description"))
    requirements = _text(job.get("requirements"))
    all_text = "\n".join((title, description, requirements))

    if hard_domain_reason == "domain_security":
        return "none", None, "hard_security_non_ai_evaluation"
    if hard_domain_reason == "domain_hardware":
        relation = "ai_context_only" if AI_CONTEXT_ONLY_PATTERN.search(all_text) else "none"
        return relation, None, "hardware_context_not_ai_quality"

    if role_family in {"evaluation_engineering", "algorithm_research"}:
        has_ai_context = bool(AI_CONTEXT_ONLY_PATTERN.search(all_text))
        has_evaluation_duty = bool(
            EVALUATION_ENGINEERING_TITLE_PATTERN.search(title)
            or CORE_EVALUATION_DUTY_PATTERN.search(description)
        )
        if not (has_ai_context and has_evaluation_duty):
            relation = "ai_context_only" if has_ai_context else "none"
            return relation, None, "evaluation_role_without_ai_evaluation_duty"
        evidence = _relation_evidence(
            CORE_EVALUATION_DUTY_PATTERN, "description", description
        ) or _relation_evidence(
            EVALUATION_ENGINEERING_TITLE_PATTERN, "title", title
        )
        return "core_ai_evaluation", evidence, "evaluation_role_primary"

    if role_family in {"product", "operations", "domain_expert", "development"}:
        if role_family == "development" and AGENT_DEVELOPMENT_ROLE_PATTERN.search(title):
            evidence = _relation_evidence(
                AI_FOR_TESTING_DUTY_PATTERN, "description", description
            )
            return "ai_for_testing", evidence, "agent_development_for_testing"
        if EVALUATION_ENGINEERING_TITLE_PATTERN.search(title) or CORE_EVALUATION_DUTY_PATTERN.search(description):
            evidence = _relation_evidence(
                CORE_EVALUATION_DUTY_PATTERN, "description", description
            ) or _relation_evidence(
                EVALUATION_ENGINEERING_TITLE_PATTERN, "title", title
            )
            return "core_ai_evaluation", evidence, "non_target_evaluation_role"
        evidence = _relation_evidence(
            AI_FOR_TESTING_DUTY_PATTERN, "description", description
        )
        if evidence:
            return "ai_for_testing", evidence, "non_target_ai_for_testing"
        relation = "ai_context_only" if AI_CONTEXT_ONLY_PATTERN.search(all_text) else "none"
        return relation, None, "non_target_context_only"

    core_evidence = _relation_evidence(
        CORE_EVALUATION_DUTY_PATTERN, "description", description
    )
    core_title = CORE_EVALUATION_TITLE_PATTERN.search(title)
    core_decision = CORE_EVALUATION_DECISION_PATTERN.search(description)
    if core_evidence and (core_title or core_decision):
        return "core_ai_evaluation", core_evidence, "model_evaluation_primary"

    product_evidence = _relation_evidence(
        AI_PRODUCT_QUALITY_DUTY_PATTERN, "description", description
    )
    testing_evidence = _relation_evidence(
        AI_FOR_TESTING_DUTY_PATTERN, "description", description
    )
    strong_testing = AI_FOR_TESTING_STRONG_PATTERN.search(description)
    first_duties = "\n".join(_responsibility_segments(job)[:1])
    testing_is_lead_duty = bool(
        strong_testing and AI_FOR_TESTING_STRONG_PATTERN.search(first_duties)
    )
    if AI_PRODUCT_QUALITY_PRIMARY_TITLE_PATTERN.search(title) and re.search(
        r"(?:测试|质量保障|质量体系|质量闭环|评测|验收|稳定性)",
        description,
    ):
        return "ai_product_quality", product_evidence, "title_primary_ai_product_quality"
    if testing_is_lead_duty:
        return "ai_for_testing", testing_evidence, "ai_testing_capability_primary"
    if product_evidence:
        return "ai_product_quality", product_evidence, "ai_product_quality_primary"
    if strong_testing:
        return "ai_for_testing", testing_evidence, "ai_testing_capability_primary"
    if testing_evidence and AI_CONTEXT_ONLY_PATTERN.search(title):
        return "ai_for_testing", testing_evidence, "title_supported_ai_for_testing"

    title_product = AI_PRODUCT_QUALITY_TITLE_PATTERN.search(title)
    ordinary_qa_duty = re.search(
        r"(?:测试|质量保障|质量体系|质量闭环|验收|稳定性)", description
    )
    if title_product and ordinary_qa_duty:
        evidence = _relation_evidence(
            AI_PRODUCT_QUALITY_TITLE_PATTERN, "title", title
        )
        return "ai_product_quality", evidence, "title_supported_ai_product_quality"

    if AI_CONTEXT_ONLY_PATTERN.search(all_text):
        return "ai_context_only", None, "ai_context_not_primary"
    return "none", None, "no_ai_relation"


def _hard_domain_classification(job: Mapping[str, Any]) -> tuple[str | None, list[str]]:
    title = _text(job.get("title"))
    ordered_patterns = (
        ("domain_hardware", HARDWARE_DOMAIN_PATTERN),
        ("domain_game", GAME_DOMAIN_PATTERN),
        ("domain_security", SECURITY_DOMAIN_TITLE_PATTERN),
    )
    for reason_code, pattern in ordered_patterns:
        terms = _pattern_evidence(pattern, title)
        if terms:
            return reason_code, terms
    return None, []


def _ordered_reason_codes(reason_codes: Iterable[str]) -> list[str]:
    unique = set(reason_codes)
    return [code for code in EXCLUSION_REASON_PRIORITY if code in unique]


def classify_body_primary_ai_evaluation(
    job: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify one job through the production AI/Agent career-pool rules."""
    job = classification_input(job)
    title = _text(job.get("title"))
    role_family, role_reason, role_terms = _role_classification(title)
    if role_family == "qa_test" and MANAGEMENT_DUTY_PATTERN.search(
        _text(job.get("description"))
    ):
        role_family = "quality_engineering"
    seniority_level, seniority_terms = _seniority_classification(job)
    hard_domain_reason, hard_domain_terms = _hard_domain_classification(job)
    non_target_roles = {"product", "development", "operations", "domain_expert"}
    effective_hard_domain_reason = (
        None if role_family in non_target_roles else hard_domain_reason
    )
    ai_relation, ai_evidence, relation_rule = _ai_relation_classification(
        job,
        role_family=role_family,
        hard_domain_reason=effective_hard_domain_reason,
    )

    algorithm_research_hard = bool(
        role_family == "algorithm_research"
        and ALGORITHM_RESEARCH_HARD_PATTERN.search(
            "\n".join(
                (
                    title,
                    _text(job.get("description")),
                    _text(job.get("requirements")),
                )
            )
        )
    )
    if effective_hard_domain_reason:
        career_pool = "X"
        reason_codes = [effective_hard_domain_reason]
    elif role_family in non_target_roles:
        career_pool = "X"
        reason_codes = [role_reason or "role_general_rnd"]
    elif seniority_level == "intern":
        career_pool = "X"
        reason_codes = ["level_intern"]
    elif role_family == "algorithm_research" and (
        algorithm_research_hard
        or ai_relation not in {"core_ai_evaluation"}
    ):
        career_pool = "X"
        reason_codes = ["role_algorithm_or_research"]
    elif ai_relation in {"ai_context_only", "none"}:
        career_pool = "X"
        reason_codes = ["ai_not_primary_duty"]
    elif seniority_level == "expert_lead":
        career_pool = "REF"
        reason_codes = ["level_expert_lead"]
    elif role_family in {"qa_test", "quality_engineering"}:
        career_pool = "P1"
        reason_codes = []
    else:
        career_pool = "P2"
        reason_codes = (
            ["role_algorithm_or_research"]
            if role_family == "algorithm_research"
            else []
        )

    reason_codes = _ordered_reason_codes(reason_codes)
    rule_id = f"{role_family}_{ai_relation}_{career_pool.lower()}"
    hard_exclusion_evidence: dict[str, list[str]] = {}
    if role_reason and role_terms:
        hard_exclusion_evidence[role_reason] = role_terms
    if effective_hard_domain_reason:
        hard_exclusion_evidence[effective_hard_domain_reason] = hard_domain_terms
    if seniority_level in {"expert_lead", "intern"}:
        hard_exclusion_evidence[
            "level_expert_lead" if seniority_level == "expert_lead" else "level_intern"
        ] = seniority_terms
    evidence = {
        "role": {"field": "title", "text": title, "terms": role_terms},
        "ai_primary_duty": ai_evidence,
        "hard_exclusions": hard_exclusion_evidence,
    }
    if career_pool != "X":
        reason = (
            f"三字段证据判定岗位主职能为 {role_family}；AI 关系为 "
            f"{ai_relation}；层级为 {seniority_level}；进入 {career_pool} 池。"
        )
    else:
        labels = [EXCLUSION_REASON_LABELS[code] for code in reason_codes]
        reason = "；".join(labels) + "。"
    return {
        "body_primary_ai_evaluation": {
            "role_family": role_family,
            "ai_relation": ai_relation,
            "seniority_level": seniority_level,
            "career_pool": career_pool,
        },
        "reason_codes": reason_codes,
        "rule_id": rule_id,
        "triggered_rules": [relation_rule, *reason_codes],
        "reason": reason,
        "evidence": evidence,
    }


def explain_job_selection(job: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return auditable evidence for the P1/P2/REF positive pools."""
    evaluation = classify_body_primary_ai_evaluation(job)
    classification = evaluation["body_primary_ai_evaluation"]
    if classification["career_pool"] == "X":
        return None
    return {
        **classification,
        "cohort": classification["ai_relation"],
        "rule_id": evaluation["rule_id"],
        "reason": evaluation["reason"],
        "evidence": evaluation["evidence"],
        "reason_codes": evaluation["reason_codes"],
    }


def explain_job_exclusion(
    job: Mapping[str, Any],
    *,
    scope: Mapping[str, set[str] | None],
) -> dict[str, Any] | None:
    """Return stable, ordered reason codes for a non-selected job."""
    evaluation = classify_body_primary_ai_evaluation(job)
    classification = evaluation["body_primary_ai_evaluation"]
    if not _in_scope(job, scope):
        reason_codes = _ordered_reason_codes(
            ("outside_config_scope", *evaluation["reason_codes"])
        )
    elif classification["career_pool"] != "X":
        return None
    else:
        reason_codes = evaluation["reason_codes"]
    return {
        **classification,
        "cohort": classification["ai_relation"],
        "reason_code": reason_codes[0],
        "reason_codes": reason_codes,
        "reason": "；".join(
            EXCLUSION_REASON_LABELS[code] for code in reason_codes
        ) + "。",
        "evidence": evaluation["evidence"],
    }


def classify_job(job: Mapping[str, Any]) -> str | None:
    explanation = explain_job_selection(job)
    if explanation is None:
        return None
    return str(explanation["cohort"])


def _dedupe_key(job: Mapping[str, Any]) -> tuple[str, ...]:
    return normalized_job_content(job)


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
        evaluation = classify_body_primary_ai_evaluation(job)
        classification = evaluation["body_primary_ai_evaluation"]
        if classification["career_pool"] != "X":
            selected_raw.append(
                (
                    job,
                    {
                        **classification,
                        "cohort": classification["ai_relation"],
                        "rule_id": evaluation["rule_id"],
                        "reason": evaluation["reason"],
                        "evidence": evaluation["evidence"],
                        "reason_codes": evaluation["reason_codes"],
                    },
                )
            )

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
                "exclusion_reason_codes": exclusion["reason_codes"],
                "exclusion_reason": exclusion["reason"],
                "exclusion_evidence": exclusion["evidence"],
                "body_primary_ai_evaluation": {
                    field: exclusion[field]
                    for field in (
                        "role_family",
                        "ai_relation",
                        "seniority_level",
                        "career_pool",
                    )
                },
                "description_present": bool(_text(job.get("description"))),
                "requirements_present": bool(_text(job.get("requirements"))),
            }
        )

    selected: list[tuple[Mapping[str, Any], str]] = []
    raw_matches: list[dict[str, Any]] = []
    first_match_by_key: dict[tuple[str, ...], tuple[int, str]] = {}
    for match_number, (job, explanation) in enumerate(selected_raw, start=1):
        key = _dedupe_key(job)
        job_id = _text(job.get("job_id"))
        first_match = first_match_by_key.get(key)
        included_after_deduplication = first_match is None
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
                "body_primary_ai_evaluation": {
                    field: explanation[field]
                    for field in (
                        "role_family",
                        "ai_relation",
                        "seniority_level",
                        "career_pool",
                    )
                },
                "role_family": explanation["role_family"],
                "ai_relation": explanation["ai_relation"],
                "cohort": explanation["cohort"],
                "seniority_level": explanation["seniority_level"],
                "career_pool": explanation["career_pool"],
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
        explanation = explain_job_selection(job)
        if explanation is None:  # pragma: no cover - guarded by selected_raw
            raise AssertionError("selected job must have a positive career-pool classification")
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
                "body_primary_ai_evaluation": {
                    "role_family": explanation["role_family"],
                    "ai_relation": explanation["ai_relation"],
                    "seniority_level": explanation["seniority_level"],
                    "career_pool": explanation["career_pool"],
                },
                "role_family": explanation["role_family"],
                "ai_relation": explanation["ai_relation"],
                "cohort": cohort,
                "seniority_level": explanation["seniority_level"],
                "career_pool": explanation["career_pool"],
                "selection_rule_id": explanation["rule_id"],
                "selection_reason": explanation["reason"],
                "selection_evidence": explanation["evidence"],
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
        reason_code
        for row in excluded_jobs
        for reason_code in row["exclusion_reason_codes"]
    )
    exclusion_companies: dict[str, Counter[str]] = defaultdict(Counter)
    exclusion_examples: dict[str, list[str]] = defaultdict(list)
    for row in excluded_jobs:
        company = row["company"] or "<missing>"
        title = row["title"] or "<missing>"
        for reason_code in row["exclusion_reason_codes"]:
            exclusion_companies[reason_code][company] += 1
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
                "按硬排除域、角色主职能、AI 关系与层级依次分类；"
                "P1、P2、REF 写入正例候选名单，X 排除"
            ),
            "deduplication_key": [
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

- **共识别 {manifest['selected_job_count']} 个去重后的 AI/Agent 正例岗位。** 原始命中 {manifest['selected_raw_count']} 条，按规范化后的 title、description、requirements 去除 {manifest['duplicates_removed']} 条重复记录，覆盖 {manifest['selected_company_count']} 家公司。
- **热门技能集中在：** {skill_summary}。
- **高频要求集中在：** {requirement_summary}。

## 分析口径

输入为 `{manifest['input_file']}`，公司范围沿用 `{manifest['config_file']}` 中 `enabled: true` 的平台配置。生产分类入口基于 title、description、requirements 判断角色、AI 关系、层级和岗位池，其中 description 的主要职责证据最强，requirements 只作支持。技能、专业和项目经验读取 `description + requirements`；城市读取 `city_norm`；学历优先读取 `education`，为空时从正文推断；工作经验读取 `experience`。除公司“占全部岗位”外，各分析占比的分母均为 {manifest['selected_job_count']} 个去重后的正例岗位；多城市、多专业和多项目主题可以重复计数，因此相关占比不可相加。公司“占全部岗位”的分母是配置范围内全部 {manifest['eligible_job_count']:,} 条岗位。

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
        "判断规则：由 title、description、requirements 按字段职责共同判断角色、AI 关系和层级；"
        "description 的日常职责权重最高，requirements 只作支持证据。P1/P2/REF 写入本文件，"
        "X 排除。",
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
- 生产分类入口识别 P1/P2/REF 正例 **{manifest['selected_raw_count']:,}** 条，X 或配置范围外排除 **{manifest['excluded_job_count']:,}** 条。随后按规范化后的 title、description、requirements 做内容去重，得到 {manifest['selected_job_count']:,} 条。
- 排除只表示岗位进入 X 或不在配置范围；它不表示岗位与 AI 行业无关。评测工程与边界算法岗可进入 P2，专家/负责人或人员管理岗可进入 REF。

## 排除原因分布

{chr(10).join(reason_rows)}

每个被排除岗位的 `job_id`、公司、标题、URL、有序且去重的原因码和命中证据写入 `{manifest['excluded_jobs_jsonl_file']}`，可按 `exclusion_reason_codes` 逐条复核。

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

- 正例池由合同派生：P1、P2、REF 为正例，X 为负例；角色、AI 关系、资历和硬排除分别判定。
- `requirements` 用于准入门槛和支持证据，不能把“某经验优先”单独解释成岗位主责；description 的日常职责证据最强。
- 正式 jobs 与冻结回归集使用同一套三字段 NFKC/逐行空白折叠/casefold 规范化内容键去重，不使用 job_id、公司或地区。
- 排除原因按固定优先级排序并去重；输出显式写入 P1/P2/REF/X 岗位池。
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
