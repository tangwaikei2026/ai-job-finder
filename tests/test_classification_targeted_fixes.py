"""Offline cases captured from 2026-10-09; never read production data."""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from src.analysis.ai_eval_jobs import classify_market, classify_personal_fit
from src.analysis.pipeline import main as analysis_main
from src.clean.cli import main as clean_main
from src.clean.jobs import normalize_locations


FIXTURE = Path(__file__).parent / 'fixtures/classification_targeted_20261009.json'
CASES = {row['job_id']: row for row in json.loads(FIXTURE.read_text())}
EXPECTED = {
    '2077607078800834560': ('qa_test', 'P1'),
    '2095051503260844032': ('qa_test', 'X'),
    '2088194556695855104': ('qa_test', 'X'),
    '7657774830384974133': ('product', 'X'),
    '100016463005': ('evaluation_engineering', 'P2'),
    '1997884330793394176': ('evaluation_engineering', 'P2'),
    '6990611257088002340': ('quality_engineering', 'P1'),
}


def classify(job):
    market = classify_market(job)
    return market, classify_personal_fit(job, market) if market['in_scope'] else None


@pytest.mark.parametrize('job_id', EXPECTED)
def test_real_case_and_identity_independence(job_id):
    job = deepcopy(CASES[job_id])
    for row in (job, dict(job, job_id='unseen', platform='other', company='Other', location='北京')):
        market, fit = classify(row)
        assert market['in_scope']
        assert (market['role_family'], fit['career_pool']) == EXPECTED[job_id]


@pytest.mark.parametrize('title,description', [
    ('模型平台研发工程师', '负责大模型生产平台核心研发、模型部署与推理服务开发。'),
    ('模型平台研发工程师', '负责大模型生产平台研发与上线验证，保障服务稳定性。'),
    ('Agent开发工程师', '负责大模型生产平台Agent核心开发、工具调用和接口集成。'),
    ('模型算法研究员', '负责大模型生产平台模型训练、算法研究及上线验证。'),
    ('测试工程师', '负责传统服务端产品质量保障。'),
    ('测试工程师', '参与大模型生产平台技术交流，负责普通业务功能测试。'),
])
def test_model_platform_is_not_a_blanket_market_admission(title, description):
    assert not classify_market(dict(title=title, description=description,
                                    requirements='熟悉大模型生产平台技术。'))['in_scope']


@pytest.mark.parametrize('requirements', [
    '熟悉Python，有渗透测试、漏洞挖掘、逆向分析和PoC/EXP经验优先。',
    '熟练使用Python，熟练使用漏洞利用工具。',
])
def test_security_skills_do_not_replace_primary_duties(requirements):
    job = dict(CASES['2088194556695855104'], requirements=requirements,
               description='负责AI应用质量保障，包括接口、功能及权限、数据保护测试。')
    assert classify(job)[1]['career_pool'] == 'P1'


def test_security_primary_duties_work_without_security_title():
    job = dict(CASES['2095051503260844032'], title='AI产品测试工程师')
    assert classify(job)[1] == {'career_pool': 'X', 'fit_reason_codes': ['domain_security']}


def test_security_primary_duties_do_not_depend_on_required_skills():
    job = dict(CASES['2095051503260844032'],
               requirements='熟悉Python，熟练使用逆向分析工具及PoC/EXP脚本者优先。')
    assert classify(job)[1]['career_pool'] == 'X'


def test_security_cooperation_is_not_offensive_security_ownership():
    job = dict(CASES['2088194556695855104'],
               description='负责AI产品质量保障。配合安全团队开展漏洞挖掘、渗透测试。',
               requirements='熟练使用Python和漏洞利用工具。')
    assert classify(job)[1]['career_pool'] == 'P1'


@pytest.mark.parametrize('changes', [
    {'description': '负责AI产品质量保障和自动化测试。参与用户调研，为产品规划方向提供测试反馈。'},
    {'requirements': '本科，熟悉Python。三年以上互联网产品经验优先。',
     'description': '负责AI产品质量保障和评测体系建设，结合用户调研提供产品规划建议。'},
    {'description': '负责AI产品质量保障、大模型评测体系建设、评测集与自动化评测工具开发。'},
])
def test_product_signals_do_not_exclude_qa_or_evaluation_engineering(changes):
    job = dict(CASES['7657774830384974133'], title='AI产品测试工程师', **changes)
    market, fit = classify(job)
    assert market['role_family'] == 'qa_test'
    assert fit['career_pool'] == 'P1'


def test_product_role_comes_from_duties_not_title_only():
    job = dict(CASES['7657774830384974133'], title='AIGC效果评测专员')
    market, fit = classify(job)
    assert market['role_family'] == 'product'
    assert fit == {'career_pool': 'X', 'fit_reason_codes': ['role_product']}
    assert any('产品经验' in s for s in market['evidence']['requirements'])
    assert any('用户调研' in s for s in market['evidence']['description'])


@pytest.mark.parametrize('city', ['杭州', '深圳', '北京', '上海', '广州'])
def test_city_aliases_preserve_existing_mappings_and_deduplicate(city):
    assert normalize_locations(f'{city}/{city}市')['city_norm'] == [city]


def test_offline_clean_and_analysis_production_entrypoints(tmp_path, monkeypatch):
    # Single fixture snapshot, isolated outputs: no scheduler, crawl or backfill.
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError('Offline classification must not access the network')

    monkeypatch.setattr(socket.socket, 'connect', no_network)
    jobs = deepcopy(list(CASES.values()))
    # Exact duplicates are tolerated by the real analysis entrypoint.
    jobs.append(deepcopy(jobs[0]))
    conflict = dict(CASES['2077607078800834560'], job_id='city-conflict',
                    title='大模型测试工程师（深圳）', location='北京')
    jobs.append(conflict)
    raw_dir = tmp_path / 'raw'
    raw_dir.mkdir()
    raw_path = raw_dir / '2026-10-09.json'
    raw_path.write_text(json.dumps(jobs, ensure_ascii=False))
    original = raw_path.read_bytes()
    clean_dir = tmp_path / 'clean'
    monkeypatch.setattr('sys.argv', ['clean', 'clean-jobs', '--input', str(raw_path),
                                   '--date', '2026-10-09', '--output-dir', str(clean_dir)])
    clean_main()
    cleaned = json.loads((clean_dir / '2026-10-09.json').read_text())
    by_id = {j['job_id']: j for j in cleaned}
    assert by_id['100016463005']['city_norm'] == ['杭州']
    assert by_id['2077607078800834560']['city_norm'] == ['深圳']
    assert by_id['city-conflict']['city_norm'] == ['北京']
    for job_id, city in [('1997884330793394176', '深圳'), ('6990611257088002340', '北京')]:
        assert by_id[job_id]['city_norm'] == [city]
        assert by_id[job_id]['location'] == CASES[job_id]['location']
        assert by_id[job_id]['title'] == CASES[job_id]['title']
    counts = Counter(j['platform'] for j in by_id.values())
    manifest = {'job_count': len(by_id), 'cities': ['深圳', '杭州', '北京'], 'platforms': [
        dict(platform=platform, status='success', complete=True, source_total=count,
             expected_pages=1, pages_fetched=1, records_fetched=count,
             jobs_mapped=count, jobs_in_scope=count, detail_failed=0,
             stopped_by='source_total_reached', error='')
        for platform, count in counts.items()
    ]}
    (raw_dir / '2026-10-09_manifest.json').write_text(json.dumps(manifest))
    assert analysis_main(['run', '--date', '2026-10-09', '--data-dir', str(tmp_path)]) == 0
    result_path = tmp_path / 'analysis/classification/2026-10-09.jsonl'
    result = [json.loads(line) for line in result_path.read_text().splitlines()]
    assert len(result) == len(by_id)
    for row in result:
        assert row['classification_status'] == 'fresh'
        if row['job_id'] in EXPECTED:
            assert (row['role_family'], row['career_pool']) == EXPECTED[row['job_id']]
        assert row['city_norm'] == by_id[row['job_id']]['city_norm']
    assert raw_path.read_bytes() == original
