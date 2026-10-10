"""Deterministic city policy and fixed 10-09 cases; no production writes."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.analysis.candidate_city import match_shenzhen_candidate, select_shenzhen_candidates
from src.analysis.ai_eval_jobs import analyze_jobs, explain_job_selection
from src.analysis.classification import classify_record
from src.analysis.pipeline import load_settings
from src.analysis.source_health import Health
from src.clean.jobs import normalize_locations

CASES = json.loads(Path('tests/fixtures/shenzhen_candidate_cases_20261009.json').read_text())


@pytest.mark.parametrize('job', CASES, ids=lambda j: j['job_id'])
def test_eight_fixed_cases(job):
    original = deepcopy(job)
    match = match_shenzhen_candidate(job)
    assert match['matches'] and match['needs_verification']
    assert match['location_conflict']
    assert match['confirmed_openings'] is None
    assert match['evidence'] == {k: job[k] for k in ('title', 'location')}
    assert job == original


@pytest.mark.parametrize('location,title', [
    ('北京/深圳', '测试工程师'), ('深圳市', 'QA'), ('深圳/上海', 'QA'),
    ('北京', '测试工程师（北京/深圳）'), ('深圳', '测试工程师（北京）'),
    ('', '深圳测试工程师'), ('上海', '测试工程师（上海/深圳市）'),
])
def test_positive_either_source(location, title):
    assert match_shenzhen_candidate(dict(location=location, title=title))['matches']


@pytest.mark.parametrize('text', [
    '非深圳', '深圳除外', '深圳不招聘', '非深圳市', '深圳市不招聘',
    '不在深圳', '深圳不招人', '深圳无名额', '除深圳外', '不包括深圳',
])
@pytest.mark.parametrize('field', ['location', 'title'])
def test_negative_vetoes_other_positive_field(text, field):
    job = dict(location='深圳', title='深圳测试工程师')
    job[field] = text
    match = match_shenzhen_candidate(job)
    assert not match['matches']
    assert match['negative_fields'] == [field]
    assert match['needs_verification'] and match['location_conflict']


@pytest.mark.parametrize('job', [
    dict(location='北京', title='测试工程师'),
    dict(location='北京', title='QA', description='深圳研发团队'),
    dict(location='', title='', city_norm=['深圳']),
    dict(location='北京', title='深圳大学客户测试'),
    dict(location='深圳除外', title='测试工程师'),
    dict(location=None, title=None),
])
def test_no_positive_workplace(job):
    assert not match_shenzhen_candidate(job)['matches']


def test_mixed_positive_negative_in_one_field_is_pending():
    match = match_shenzhen_candidate(dict(location='北京', title='深圳工程师（深圳不招聘）'))
    assert not match['matches'] and match['needs_verification']


def test_pool_separation_and_input_preservation():
    rows = [dict(job_id=p, location='北京', title='QA（深圳）', career_pool=p,
                 role_family='qa_test', reason_codes={'fit': []}, city_norm=['北京'])
            for p in ['P1', 'P2', 'REF', 'X', None]]
    before = deepcopy(rows)
    selected = select_shenzhen_candidates(rows)
    assert [r['career_pool'] for r in selected] == ['P1', 'P2']
    for row in selected:
        assert {k: row[k] for k in before[0]} == next(r for r in before if r['job_id'] == row['job_id'])
    assert rows == before


def test_real_personal_selection_and_city_statistics_are_separate():
    job = json.loads(Path('tests/fixtures/classification_targeted_20261009.json').read_text())[0]
    job.update(location='北京', title='大模型测试工程师（深圳）', city_norm=['北京'])
    original = deepcopy(job)
    versions = load_settings()[1]
    before = classify_record('2026-10-09', job, Health(True, True), versions)[0]
    assert explain_job_selection(job)['candidate_city_match']['matches']
    report = analyze_jobs([job], scope={job['platform']: None},
                          configured_companies=[job['company']],
                          input_path=Path('fixture.json'), config_path=Path('fixture.yaml'))
    assert len(report['shenzhen_candidates']) == 1
    row = report['shenzhen_candidates'][0]
    assert row['city_norm'] == ['北京']
    assert [(c['name'], c['count']) for c in report['cities']] == [('北京', 1)]
    assert row['candidate_city_match']['confirmed_openings'] is None
    assert classify_record('2026-10-09', job, Health(True, True), versions)[0] == before
    assert job == original
    assert normalize_locations('杭州')['city_norm'] == normalize_locations('杭州市')['city_norm'] == ['杭州']
    assert normalize_locations('深圳市')['city_norm'] == ['深圳']
