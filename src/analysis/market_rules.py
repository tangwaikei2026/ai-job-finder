"""Market occupational responsibilities; independent of personal-fit rules.

Only title, responsibilities and requirements enter this module. Patterns describe
deliverables and ownership, never posting identity. Clause order is not a weight.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

ROLE_FAMILIES = frozenset({'qa_test', 'quality_engineering', 'evaluation_engineering',
    'algorithm_research', 'development', 'product', 'operations', 'domain_expert'})
AI_RELATIONS = frozenset({'core_ai_evaluation', 'ai_product_quality', 'ai_for_testing'})
MARKET_FIELDS = ('in_scope', 'market_relevance', 'role_family', 'secondary_role_families', 'ai_relation')

def pattern(text):
    return re.compile(text, re.I)

AI = pattern(r'(?<![A-Za-z])AI(?![A-Za-z])|AIGC|人工智能|大模型|语言模型|LLM|\bVLM\b|Agent|智能体|机器学习|MaaS')
OWNER = pattern(r'负责|主导|统筹|建立|搭建|构建|建设|设计|制定|沉淀|丰富|完善|维护|开发|研发|输出|保障|\b(?:own|lead|build|design|develop)\b')
WEAK = pattern(r'^(?:[\d\s、.\-（）()]+)?(?:参与|协助|配合|了解|熟悉|有机会|探索(?:和|并)?(?:落地)?AI辅助开发)')
INDEPENDENT = pattern(r'负责|主导|统筹|独立|设计并|设计和|设计、|设计专项|负责自动化')
EVAL = pattern(r'(?:评测|评估|评价|效果测试).{0,8}(?:体系|框架|基准|标准|指标|方案|方法|集合|数据集|系统|平台|流水线)|'
    r'评测集|评测任务集|评测运行底座|评估打分|评测基线|打分标准|判分策略|能力测量|\bBenchmark\b|\bRubric\b|\bJudge\b|\bEvaluator\b|'
    r'\bEval(?:uation)?\s*(?:Infra|Platform|Pipeline|Set|System)\b')
EVAL_INFRA = pattern(r'评测.{0,12}(?:基础设施|Infra|执行系统|流水线)|(?:数据生产和评测|评测和数据生产).{0,12}基础设施|'
    r'\bEval(?:uation)?\s*(?:Infra|Platform|Pipeline|Execution System)\b|Judge\s*(?:Infrastructure|system)')
QUALITY_SYSTEM = pattern(r'质量(?:保障|保证|工程|管理|评估与管理)?体系|质量平台|质量度量|质量标准与度量体系|质量门禁|自动化测试基建')
QUALITY_WORK = pattern(r'质量保障|质量保证|业务质量|产品质量|功能测试|测试策略|测试设计|测试执行|测试方法|专项测试|测试工作|回归测试|质量风险|端到端质量|测试质量|体验和质量|测试项目|项目质量|质量专项|性能压测|功能正确性|测试技术|评测工作|质量与效能|产品评测|效果评测|评测能力|质量闭环')
TEST_METHOD = pattern(r'(?:AI|LLM|大模型|Agent).{0,70}(?:测试提效|提升测试效率|测试效率|用例生成|测试用例|测试助手|测试平台|测试工具|'
    r'测试全流程|测试能力|质量保障领域|在.{0,12}测试|运营与测试)|'
    r'(?:利用|引入|借助|应用).{0,12}(?:AI|LLM|大模型).{0,35}(?:测试|质量)|'
    r'测试.{0,12}(?:Agent|智能化|AI提效)|AI.{0,12}(?:辅助|驱动).{0,16}(?:质量|测试)')
PRODUCT_OBJECT = pattern(r'(?:AI|人工智能|大模型|LLM|(?<!测试)Agent|智能体)\s*'
    r'(?:(?:原生|Native|软件|等|的|相关|相关的)\s*)?(?:产品|工作台|应用|业务|助手|服务|模块|质量保障|能力及\s*SaaS\s*产品)|'
    r'(?:Prompt|Agent|Chain)(?:[/、](?:Prompt|Agent|Chain))+(?:等)?相关模块|'
    r'(?:业务质量|产品评测|负责.{0,12}评测能力).{0,30}(?:Agent|AIGC)|智能助手|模型服务|MaaS|大模型相关的评测工作')
PRODUCT_TITLE = pattern(r'大模型|LLM|多模态测试|Agent.{0,8}(?:产品|质量)|智能助手|手机助手|MaaS|基模生产平台|AI应用|AI产品')
QUALITY_TITLE = pattern(r'测试开发|测开|测试专家|测试架构|质量工程|质量保障|质量效能|质量架构|质效|工具质量|Agent质量|可观测性工程师')
QA_TITLE = pattern(r'测试工程师|软件测试|(?<![A-Za-z])QA(?![A-Za-z])|\bSDET\b|\btest engineer\b')
EVAL_TITLE = pattern(r'评测|评估|测评|\bEvaluation\b')
QA_REQUIREMENT = pattern(r'(?:\d|三|五).{0,16}(?:测试开发|质量工程|质量保障|软件测试).{0,12}经验')
EVAL_PROFESSION = pattern(r'独立.{0,16}评测平台.{0,12}(?:架构|实现)|评测平台核心模块|评估基础设施|评测.{0,8}研发流程')
MODEL_DECISION = pattern(r'模型与策略选型|模型.{0,8}选型决策|模型能力边界|模型缺陷归因|评测驱动Agent|模型内在机理|能力衰减')
MODEL_RESEARCH = pattern(r'算法.{0,8}(?:工程师|研究员)|研究科学家|数据算法|预训练.{0,8}算法|算法研究')
DEVELOPMENT = pattern(r'应用.{0,8}(?:设计|开发|研发)|(?:核心|后端|服务端).{0,8}(?:开发|研发)|架构设计与核心研发|定制(?:化)?(?:方案|开发)')

def clauses(text: str) -> list[str]:
    return sorted(set(s.strip() for s in re.split(r'[；;。\n\r]+', text) if s.strip()))

def owned(clause: str) -> bool:
    if re.search(r'(?:参与|协助|配合).{0,24}(?:评测|benchmark|回归)',clause,re.I) and not INDEPENDENT.search(clause):
        return False
    return bool(OWNER.search(clause) and (not WEAK.search(clause) or INDEPENDENT.search(clause)))

def validate_market_output(result: Mapping[str, Any]) -> None:
    if type(result.get('in_scope')) is not bool:
        raise ValueError('INVALID_MARKET_SCOPE')
    secondary = result.get('secondary_role_families')
    if not isinstance(secondary, list) or not all(isinstance(x, str) for x in secondary):
        raise ValueError('INVALID_MARKET_SECONDARY')
    if len(secondary)>2 or len(set(secondary))!=len(secondary) or not set(secondary)<=ROLE_FAMILIES:
        raise ValueError('INVALID_MARKET_SECONDARY')
    if result['in_scope']:
        if result.get('role_family') not in ROLE_FAMILIES or result.get('ai_relation') not in AI_RELATIONS:
            raise ValueError('INVALID_MARKET_ENUM')
        if result.get('market_relevance') not in {'core','adjacent'} or result['role_family'] in secondary:
            raise ValueError('INVALID_MARKET_ROLE_STRUCTURE')
    elif any(result.get(f) is not None for f in ('market_relevance','role_family','ai_relation')) or secondary:
        raise ValueError('MARKET_STOP_SEMANTICS_VIOLATION')
    if not isinstance(result.get('reason_codes'),dict) or not isinstance(result['reason_codes'].get('market'),list):
        raise ValueError('INVALID_MARKET_REASONS')
    if not all(isinstance(code, str) and code for code in result['reason_codes']['market']):
        raise ValueError('INVALID_MARKET_REASONS')
    if set(result.get('evidence',{}))!={'title','description','requirements'}:
        raise ValueError('INVALID_MARKET_EVIDENCE')
    if any(not isinstance(quotes, list) or any(not isinstance(q, str) or not q for q in quotes)
           for quotes in result['evidence'].values()):
        raise ValueError('INVALID_MARKET_EVIDENCE')

def classify(job: Mapping[str, str], *, seniority: str) -> dict[str, Any]:
    title, body, req = (job[f] for f in ('title','description','requirements'))
    duties = clauses(body)
    ai = bool(AI.search('\n'.join((title,body,req))))
    eval_duties = [s for s in duties if EVAL.search(s) and owned(s)]
    # Test-process efficiency/defect metrics measure the testing method, not model
    # capability. Their ownership remains quality engineering evidence.
    eval_duties = [s for s in eval_duties if not re.search(r'测试质量评估|AI\s*测试(?:效果)?评[估测]',s)]
    quality_duties = [s for s in duties if QUALITY_WORK.search(s) and owned(s)]
    quality_systems = [s for s in duties if QUALITY_SYSTEM.search(s) and owned(s)]
    methods = [s for s in duties if TEST_METHOD.search(s)]
    methods = [s for s in methods if not re.search(r'探索\s*AI测试工具',s) or re.search(r'落地|实现|持续使用',s)]
    infra = [s for s in duties if EVAL_INFRA.search(s) and owned(s)]
    # Quality assurance of a mixed training/data/evaluation product is not ownership
    # of model-measurement methods or a dedicated evaluation execution platform.
    mixed_platform = bool(re.search(r'数据生产.{0,12}训练.{0,12}评测平台.{0,12}质量',body))
    if mixed_platform:
        eval_duties=[s for s in eval_duties if not re.search(r'评测平台.{0,12}质量',s)]
        infra=[]
    dedicated_infra = bool(infra or (EVAL_TITLE.search(title) and re.search(r'Infra|基础设施|评测平台',title,re.I)))
    qa_identity = bool(QUALITY_TITLE.search(title) or QA_TITLE.search(title) or QA_REQUIREMENT.search(req))
    eval_identity = bool(EVAL_TITLE.search(title) and (eval_duties or (
        (AI.search(body) or re.search(r'模型.{0,12}评测|模型效果测试',body))
        and re.search(r'评测|评估打分|训练数据交付验收',body))))
    qa_tasks = [s for s in duties if QUALITY_WORK.search(s)] if qa_identity else quality_duties
    explicit_product = any(PRODUCT_OBJECT.search(s) for s in qa_tasks)
    traditional_target = any(re.search(r'客户端性能|服务端产品|传统软件|非AI业务',s) for s in qa_tasks)
    product_quality = bool(mixed_platform or explicit_product
        or (qa_tasks and PRODUCT_TITLE.search(title) and not (methods and traditional_target)))
    # A keyword in a title or ordinary engineering verification is insufficient.
    in_scope = ai and bool(eval_duties or infra or eval_identity or
        ((qa_identity or quality_systems) and (methods or product_quality)))
    result = dict(in_scope=bool(in_scope),market_relevance=None,role_family=None,
        secondary_role_families=[],ai_relation=None,seniority_level=seniority,
        reason_codes={'market':[]},evidence={'title':[],'description':[],'requirements':[]})
    if not in_scope:
        result['reason_codes']['market']=['AI_EVALUATION_NOT_ESTABLISHED']
        validate_market_output(result)
        return result

    if re.search(r'产品.{0,8}(?:经理|负责人|专家)|Product Manager',title,re.I):
        role='product'
    elif re.search(r'运营',title):
        role='operations'
    elif re.search(r'领域专家|行业专家|医师|医生',title) or (
            re.search(r'安全研究',title) and re.search(r'逆向工程|漏洞发现|渗透测试',req)):
        role='domain_expert'
    elif QUALITY_TITLE.search(title) or (QA_REQUIREMENT.search(req) and quality_duties and not QA_TITLE.search(title)):
        role='quality_engineering'
    elif QA_TITLE.search(title):
        role='qa_test'
        if re.search(r'团队成员招聘|招聘和培养|制定测试团队工作目标',body):
            role='quality_engineering'
    elif dedicated_infra and re.search(r'基础设施.{0,8}算法',title) and EVAL_PROFESSION.search(req):
        role='evaluation_engineering'
    elif MODEL_RESEARCH.search(title):
        role='algorithm_research'
    elif re.search(r'后台开发|后端开发|服务端开发',title):
        role='development'
    elif EVAL_TITLE.search(title):
        role='evaluation_engineering'
    else:
        role='development'
    # A test title can recruit an evaluation framework owner: require both the
    # accountable capability/selection deliverable and professional infra ability.
    if role=='qa_test' and eval_duties and MODEL_DECISION.search(body) and EVAL_PROFESSION.search(req):
        role='evaluation_engineering'

    testing_platform = bool(re.search(r'AI测试平台',body) and not re.search(r'模型能力|Agent任务评测',body))
    testing_system = bool(re.search(r'(?:设计|开发|搭建|建设|落地|主导).{0,30}(?:测试\s*Agent|Test Agent|AI\s*测试(?:能力|评测|平台|工具))',body,re.I))
    if role=='development' and eval_duties and not dedicated_infra:
        # Evaluation standards/measurement are independently accountable outputs;
        # application monitoring alone remains a secondary product-quality stream.
        standalone_measurement = bool(re.search(r'打分标准|效果度量标准|评测框架|评测集', '\n'.join(eval_duties)))
    else:
        standalone_measurement = bool(eval_duties)
    if dedicated_infra:
        relation='core_ai_evaluation'
    elif eval_duties and re.search(r'(?:AI|模型|Agent).{0,8}评测',title,re.I) and not re.search(r'产品质量保障|研发效能',title):
        relation='core_ai_evaluation'
    elif testing_platform:
        relation='ai_for_testing'
    elif role in {'qa_test','quality_engineering'} and product_quality:
        relation='ai_product_quality'
    elif role=='product' and product_quality and not re.search(r'策略.{0,16}训练|支撑策略与训练|模型效果.{0,16}系统性分析',body):
        relation='ai_product_quality'
    elif testing_system and not product_quality:
        relation='ai_for_testing'
    elif role=='development' and eval_duties and not standalone_measurement:
        relation='ai_product_quality'
    elif eval_duties or eval_identity:
        relation='core_ai_evaluation'
    else:
        relation='ai_for_testing'

    secondary=[]
    if role!='evaluation_engineering' and (eval_duties or dedicated_infra):
        # Infra reliability and test-tool evaluation are not additional evaluation
        # occupations merely because their quality metrics mention evaluation.
        reliability_only = bool(re.search(r'可观测性',title) and not re.search(r'评测(?:方法|指标|标准|集)',body))
        if not reliability_only and not testing_platform:
            secondary.append('evaluation_engineering')
    if role not in {'qa_test','quality_engineering'} and quality_systems:
        independent_quality = [s for s in quality_systems if not re.search(r'数据.{0,20}质量|标注.{0,20}质检',s)]
        if independent_quality:
            secondary.append('quality_engineering')

    relevance='core'
    if role=='development' and eval_duties and not dedicated_infra and not standalone_measurement:
        relevance='adjacent'
    elif role=='algorithm_research' and not EVAL_TITLE.search(title):
        co_core = bool(re.search(r'能力边界',body) and re.search(r'评测.{0,12}数据.{0,12}训练',body))
        if not co_core:relevance='adjacent'
    elif role=='operations' and relation=='ai_for_testing':
        relevance='adjacent'
    elif role=='domain_expert' and re.search(r'真实业务场景.{0,40}安全|安全风险.{0,30}安全水位',body):
        relevance='adjacent'

    result.update(role_family=role,market_relevance=relevance,secondary_role_families=secondary[:2],ai_relation=relation)
    result['reason_codes']['market']=[f'MARKET_{relevance.upper()}_ACCOUNTABLE_WORK',f'PRIMARY_{role.upper()}',f'RELATION_{relation.upper()}']
    if dedicated_infra:result['reason_codes']['market'].append('DEDICATED_EVALUATION_INFRA')
    if secondary:result['reason_codes']['market'].append('SUBSTANTIAL_SECONDARY_DELIVERABLES')
    result['evidence']['title']=[title] if title else []
    result['evidence']['description']=sorted(set(eval_duties+quality_duties+quality_systems+methods+infra))
    result['evidence']['requirements']=[s for s in clauses(req) if QA_REQUIREMENT.search(s) or EVAL_PROFESSION.search(s)]
    validate_market_output(result)
    return result
