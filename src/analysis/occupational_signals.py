"""Narrow JD evidence shared by Market and Fit, without pool decisions."""
from __future__ import annotations

import re
from typing import Mapping


def _clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r'[；;。\n\r]+', text) if part.strip()]


def product_management_evidence(job: Mapping[str, str]) -> list[str]:
    """Require product experience, research and planning, not 'AI product' alone."""
    duties = _clauses(job.get('description', ''))
    experience = [s for s in _clauses(job.get('requirements', ''))
                  if re.search(r'(?:\d+|[一二三四五六七八九十]+)\s*年(?:以上)?(?:的)?'
                               r'(?:互联网|AI|平台)?产品(?:工作|管理)?经验', s)
                  and not re.search(r'优先|加分', s)]
    research = [s for s in duties if re.search(r'用户调研|市场研究', s)]
    planning = [s for s in duties if re.search(
        r'(?:负责|主导|规划|制定).{0,24}(?:产品规划|产品路线|产品交付|规划方向|方向)', s)]
    qa_owner = any(re.search(r'(?:负责|主导).{0,24}(?:质量保障|测试开发|测试执行|自动化测试)', s)
                   for s in duties)
    return research + planning + experience if experience and research and planning and not qa_owner else []


def security_specialist_evidence(job: Mapping[str, str]) -> list[str]:
    """Recognize primary security business, not incidental application safeguards."""
    duties = [s for s in _clauses(job.get('description', ''))
              if re.search(r'负责|主导|开展|独立完成', s)
              and not re.search(r'协助|配合|无需|不负责|不涉及', s)]
    techniques = (r'漏洞挖掘', r'渗透测试', r'漏洞分析|沙箱逃逸')
    matched = [s for s in duties if any(re.search(p, s) for p in techniques)]
    breadth = sum(any(re.search(p, s) for s in duties) for p in techniques)
    security_business = [s for s in duties if re.search(
        r'(?:负责|主导)(?:[^，,：:]{0,12})?安全(?:系统|产品|业务)(?:的)?'
        r'(?:测试|质量保障)|(?:负责|主导)[^，,]{0,16}安全能力评测', s)]
    return security_business + matched if security_business or breadth >= 2 else []
