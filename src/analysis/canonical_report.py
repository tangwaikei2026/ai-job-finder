"""Consume dated Canonical facts; never classify or expand the candidate pool."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from src.analysis.ai_eval_jobs import (
    _markdown_ranking, analyze_jobs, job_content_sha256,
)
from src.analysis.candidate_city import select_shenzhen_candidates
from src.analysis.classification import CLASSIFICATION_STATUSES
from src.analysis.lifecycle import identity, index_jobs
from src.analysis.market_rules import validate_market_output
from src.invocation import has_invocation_evidence, read, validate_analysis


def analyze_canonical_candidates(jobs, *, day, canonical_path, input_path,
                                 config_path, generated_at=None):
    canonical_path = Path(canonical_path)
    if canonical_path.stem != day:
        raise ValueError('CANONICAL_DATE_MISMATCH')
    if not canonical_path.is_file():
        raise ValueError(f'CANONICAL_MISSING: {canonical_path}')
    data_dir = Path(input_path).parent.parent
    manifest_path = data_dir / 'raw' / f'{day}_manifest.json'
    manifest = read(manifest_path) if manifest_path.exists() else {}
    if not isinstance(manifest, dict):
        raise ValueError('MANIFEST_INVALID')
    if has_invocation_evidence(data_dir, day, manifest):
        # validate_analysis binds these exact files, not an arbitrary CLI override.
        if (Path(input_path).resolve() != (data_dir / 'clean' / f'{day}.json').resolve()
                or canonical_path.resolve() !=
                (data_dir / 'analysis' / 'classification' / f'{day}.jsonl').resolve()):
            raise ValueError('CANONICAL_PUBLICATION_PATH_MISMATCH')
        context = manifest.get('invocation')
        expected_id = context.get('id', '') if isinstance(context, dict) else ''
        validate_analysis(data_dir, day, expected_id)
    rows = [json.loads(line) for line in canonical_path.read_text(encoding='utf-8').splitlines()
            if line.strip()]
    indexed = index_jobs(jobs)
    classified = index_jobs(rows)
    joined = []
    for key, row in classified.items():
        if row.get('snapshot_date') != day:
            raise ValueError('CANONICAL_DATE_MISMATCH')
        if key not in indexed:
            raise ValueError(f'CANONICAL_IDENTITY_UNLINKED: {key}')
        status = row.get('classification_status')
        if status not in CLASSIFICATION_STATUSES:
            raise ValueError(f'CANONICAL_STATUS_INVALID: {key}')
        # Unknown/review rows are evidence, not confirmed candidate qualifications.
        if status == 'review_required':
            if row.get('career_pool') in {'P1', 'P2'}:
                raise ValueError(f'CANONICAL_CANDIDATE_UNRESOLVED: {key}')
            continue
        validate_market_output(row)
        if row.get('career_pool') not in {'P1', 'P2', 'REF', 'X'}:
            raise ValueError(f'CANONICAL_FIT_INVALID: {key}')
        if not isinstance(row.get('reason_codes', {}).get('fit'), list) or not row.get('versions'):
            raise ValueError(f'CANONICAL_EVIDENCE_MISSING: {key}')
        job = indexed[key]
        if status == 'fresh' and row.get('content_sha256') != job_content_sha256(job):
            raise ValueError(f'CANONICAL_CONTENT_MISMATCH: {key}')
        # Inherited facts intentionally describe a prior reliable JD. Preserve that
        # status/hash/reason evidence; never reclassify today's partial content.
        if status == 'carried_forward' and 'CONTENT_CARRIED_FORWARD' not in row['reason_codes']['market']:
            raise ValueError(f'CANONICAL_EVIDENCE_MISSING: {key}')
        if row['in_scope']:
            joined.append({**job, **row, 'location': job.get('location', ''),
                           'title': job.get('title', '')})
    candidates = select_shenzhen_candidates(joined)
    explanations = {
        identity(row): {**row, 'cohort': row['ai_relation'], 'rule_id': 'CANONICAL_CLASSIFICATION',
                        'reason': '同日 Canonical 已确认结果', 'candidate_city_match': row['candidate_city_match']}
        for row in candidates
    }
    # Reuse descriptive analytics only, with all qualification decisions supplied.
    selected_jobs = [indexed[identity(row)] for row in candidates]
    analysis = analyze_jobs(
        selected_jobs, scope={key[0]: None for key in explanations}, configured_companies=[],
        input_path=input_path, config_path=config_path, generated_at=generated_at,
        canonical_selection=explanations,
    )
    for field in ('matched_jobs', 'raw_matches', 'shenzhen_candidates'):
        for row in analysis[field]:
            canonical = classified[identity(row)]
            row.update({key: canonical[key] for key in (
                'snapshot_date', 'in_scope', 'career_pool', 'role_family', 'reason_codes',
                'classification_status', 'content_sha256', 'versions', 'evidence', 'skill_tags',
            )})
    groups = defaultdict(list)
    for row in analysis['matched_jobs']:
        groups[job_content_sha256(indexed[identity(row)])].append(row)
    analysis['display_groups'] = [dict(content_sha256=key, jobs=members)
                                  for key, members in groups.items()]
    analysis['manifest'].update(
        report_mode='canonical_candidates', snapshot_date=day, canonical_file=str(canonical_path),
        source_input_job_count=len(jobs), source_unique_identity_count=len(indexed),
        display_group_count=len(groups), authority='Canonical Market / Classification',
    )
    analysis['methodology'].update(
        scope='同日 Canonical 已确认、深圳匹配的 P1/P2',
        selection='只消费 Canonical；不执行报告初筛或重新分类',
        deduplication_key=['platform', 'job_id'],
        share_denominator='真实候选岗位身份数；正文分组只影响展示',
    )
    return analysis


def render_candidate_report(analysis):
    manifest = analysis['manifest']
    lines = ['# Canonical 深圳正式候选报告', '',
             f"日期：{manifest['snapshot_date']}；真实岗位数：{manifest['selected_job_count']}；"
             f"展示分组数：{manifest['display_group_count']}。", '',
             f"资格、P1/P2、role_family、reason_codes 来自 `{manifest['canonical_file']}`。",
             '所有统计与技能分析均按独立岗位身份计算；正文相同仅折叠展示。',
             '技能与要求基于当日 clean 正文；carried_forward 岗位保留历史分类可靠性证据，'
             '当日正文可能不完整。地点冲突仅供审计，不阻断入池。', '']
    for title, field in [('热门技能', 'skills'), ('高频要求', 'requirements'),
                         ('学历', 'education'), ('经验', 'experience'),
                         ('专业', 'majors'), ('项目经验', 'project_experience')]:
        lines.extend([f'## {title}', '', _markdown_ranking(analysis[field]), ''])
    for number, group in enumerate(analysis['display_groups'], 1):
        lines.extend(['<details>', f"<summary>第 {number} 组：{len(group['jobs'])} 个岗位</summary>", ''])
        for row in group['jobs']:
            lines.extend([
                f"- {row['title']} — {row['company']} — `{row['platform']}/{row['job_id']}`",
                f"  招聘链接：{row['url']}；分类：{row['career_pool']} / {row['role_family']}；"
                f"可靠性：{row['classification_status']}",
                f"  原因：{json.dumps(row['reason_codes'], ensure_ascii=False)}",
            ])
        lines.extend(['', '</details>', ''])
    lines.append('完整岗位正文及原始链接见同名前缀的 `_ai_eval_hits.md` / `.jsonl` 明细。')
    return '\n'.join(lines) + '\n'
