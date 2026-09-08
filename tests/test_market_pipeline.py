from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.analysis.ai_eval_jobs import (
    SKILL_PATTERNS, classify_market, classify_personal_fit, classify_skills, job_content_sha256,
)
from src.analysis.ai_eval_regression import run_split_regression
from src.analysis.classification import classify_record
from src.analysis.lifecycle import Lifecycle, identity, index_jobs
from src.analysis.pipeline import load_settings, replay
from src.analysis.source_health import SourceHealth
from src.analysis.trends import aggregate_trends

VERSIONS = load_settings()[1]


def job(job_id='a', platform='test', company='Company', **changes):
    return dict(job_id=job_id, platform=platform, company=company, title='大模型测试工程师',
                description='负责大模型产品质量保障和评测体系建设。', requirements='熟悉Python。',
                url='https://example.test/a', city_norm=['北京'], **changes)


def manifest(jobs, **changes):
    row = dict(platform='test', status='success', complete=True, source_total=len(jobs),
               expected_pages=1 if jobs else 0, pages_fetched=1 if jobs else 0,
               records_fetched=len(jobs), jobs_mapped=len(jobs), jobs_in_scope=len(jobs),
               detail_failed=0, stopped_by='source_total_reached', error='')
    row.update(changes)
    return dict(job_count=len(jobs), cities=['北京'], platforms=[row])


def observe(life, day, jobs, **changes):
    health = SourceHealth(manifest(jobs, **changes), jobs)
    return life.observe(day, jobs, health)


def observation(day, jobs, *, versions=None, events=None, **changes):
    versions = dict(versions or VERSIONS)
    health = SourceHealth(manifest(jobs, **changes), jobs)
    rows = [classify_record(day, row, health.resolve(row['platform'], row['company'], row), versions)[0] for row in jobs]
    return dict(date=day, classifications=[row for row in rows if row], versions=versions,
                health=health, events=events or [], present_keys={identity(row) for row in jobs})


def history_days():
    return [observation((date(2026, 9, 1) + timedelta(days=i)).isoformat(), [job()]) for i in range(8)]


def test_split_frozen_evaluators():
    report = run_split_regression(Path('tests/fixtures/ai_eval_regression_set_v1_117_frozen.yaml'),
                                  Path('tests/fixtures/ai_eval_market_expectations.yaml'))
    assert report['market']['total'] == report['market']['passed'] == 117
    assert report['fit']['total'] == report['fit']['passed'] == 114


def test_market_does_not_call_personal_rules(monkeypatch):
    import src.analysis.ai_eval_jobs as rules
    def fail(*args, **kwargs):
        raise AssertionError('market touched personal rules')
    monkeypatch.setattr(rules, '_hard_domain_classification', fail)
    monkeypatch.setattr(rules, '_personal_fit_decision', fail)
    assert classify_market(job())['in_scope']


def test_fit_refuses_non_market():
    row = dict(job(), title='普通招聘专员', description='负责人才招聘。', requirements='沟通能力。')
    with pytest.raises(ValueError):
        classify_personal_fit(row, classify_market(row))
    assert classify_record('2026-09-01', row, SourceHealth(manifest([row]), [row]).resolve('test', 'Company', row), VERSIONS)[0] is None


def test_market_includes_personal_x():
    row = dict(job(), title='大模型评测产品经理', description='负责大模型评测体系建设。')
    market = classify_market(row)
    assert market['in_scope']
    assert classify_personal_fit(row, market) == {'career_pool': 'X', 'fit_reason_codes': ['role_product']}
    trend = aggregate_trends([observation('2026-09-01', [row])])
    assert trend['market']['active_jobs'] == 1
    assert trend['qa_bridge']['active_jobs'] == 0


def test_real_near_misses_are_not_testing_market():
    cases = json.loads(Path('tests/fixtures/ai_eval_market_near_misses.json').read_text())
    for row in cases:
        assert not classify_market(row)['in_scope'], row['title']


def test_hash_is_content_only_and_ontology_is_controlled():
    original = job()
    changed = dict(original, company='Other', career_pool='X', city_norm=['上海'], versions={'market': 'other'})
    assert job_content_sha256(original) == job_content_sha256(changed)
    assert job_content_sha256(original) == job_content_sha256(dict(original, title='  大模型测试工程师  '))
    assert set(classify_skills(dict(original, requirements='python Agent 神秘技能XYZ'))) <= {name for name, _ in SKILL_PATTERNS}
    assert '神秘技能XYZ' not in classify_skills(original)


def test_complete_absent_missing_removed_once():
    life = Lifecycle()
    assert observe(life, '2026-09-01', [job()])[0]['event_type'] == 'FIRST_SEEN'
    assert observe(life, '2026-09-02', [])[0]['event_type'] == 'MISSING'
    removed = observe(life, '2026-09-03', [])
    assert removed[0]['event_type'] == 'REMOVED'
    assert removed[0]['event_status'] == 'confirmed'
    assert observe(life, '2026-09-04', []) == []


@pytest.mark.parametrize('changes', [
    dict(source_total=10, records_fetched=0), dict(expected_pages=10, pages_fetched=0),
    dict(stopped_by='empty_page'), dict(status='error', error='offline'),
    dict(jobs_mapped=0, records_fetched=2), dict(missing_job_id=1),
])
def test_incomplete_source_never_advances_removal(changes):
    life = Lifecycle()
    observe(life, '2026-09-01', [job()])
    for day in ('2026-09-02', '2026-09-03'):
        events = observe(life, day, [], **changes)
        assert events[0]['event_type'] == 'MISSING'
        assert 'SOURCE_UNRELIABLE' in events[0]['reason_codes']
    assert life.state[('test', 'a')].missing_streak == 0


def test_unreliable_run_does_not_count_as_healthy_run():
    life = Lifecycle()
    observe(life, '2026-09-01', [job()])
    observe(life, '2026-09-02', [])
    observe(life, '2026-09-03', [], status='error')
    assert life.state[('test', 'a')].missing_streak == 1
    assert observe(life, '2026-09-04', [])[0]['event_type'] == 'REMOVED'


@pytest.mark.parametrize('legacy', [True, False])
def test_feishu_company_failure_is_scoped(legacy):
    life = Lifecycle()
    jobs = [job('a', 'feishu', 'Healthy'), job('b', 'feishu', 'Failed')]
    first = manifest(jobs, platform='feishu', attempted_companies=['Healthy', 'Failed'], stopped_by='all_companies_complete')
    life.observe('2026-09-01', jobs, SourceHealth(first, jobs))
    # Healthy still exists as a scope when it has zero postings.
    changes = dict(platform='feishu', complete=False, status='partial', stopped_by='company_error',
                   error='Failed: portal list API was not observed', source_total=10, expected_pages=2)
    if legacy:
        present = [job('c', 'feishu', 'Healthy')]
    else:
        present = []
        changes.update(failed_companies=['Failed'], attempted_companies=['Healthy', 'Failed'])
    m = manifest(present, **changes)
    health = SourceHealth(m, present)
    assert health.resolve('feishu', 'Healthy').presence_reliable
    assert not health.resolve('feishu', 'Failed').presence_reliable
    life.observe('2026-09-02', present, health)
    events = life.observe('2026-09-03', present, health)
    assert next(row for row in events if row['job_id'] == 'a')['event_type'] == 'REMOVED'
    assert next(row for row in events if row['job_id'] == 'b')['event_type'] == 'MISSING'


def test_unknown_legacy_company_scope_is_not_reliable():
    health = SourceHealth(manifest([], platform='feishu', status='partial', complete=False,
                                   stopped_by='company_error', error='unparseable'), [])
    assert not health.resolve('feishu', 'Unknown').presence_reliable


@pytest.mark.parametrize('explicit_ids', [True, False])
def test_detail_failure_presence_carry_no_update(explicit_ids):
    life = Lifecycle()
    original = job()
    old_health = SourceHealth(manifest([original]), [original])
    life.observe('2026-09-01', [original], old_health)
    previous = classify_record('2026-09-01', original, old_health.resolve('test', 'Company', original), VERSIONS)[0]
    broken = dict(original, description='', requirements='')
    changes = dict(status='partial', complete=False, detail_failed=1, stopped_by='detail_errors')
    if explicit_ids:
        changes['detail_failed_job_ids'] = ['a']
    health = SourceHealth(manifest([broken], **changes), [broken])
    assert health.resolve('test').presence_reliable
    resolved = health.resolve('test', 'Company', broken)
    assert not resolved.content_reliable
    assert life.observe('2026-09-02', [broken], health) == []
    carried = classify_record('2026-09-02', broken, resolved, VERSIONS, previous)[0]
    assert carried['classification_status'] == 'carried_forward'
    assert carried['content_sha256'] == previous['content_sha256']
    assert previous['classification_status'] == 'fresh'


def test_requirements_alone_empty_is_not_failure():
    row = dict(job(), requirements='')
    health = SourceHealth(manifest([row], detail_failed=1, stopped_by='detail_errors', status='partial', complete=False), [row])
    assert health.resolve('test', 'Company', row).content_reliable


def test_explicit_failure_even_with_partial_body():
    row = job()
    health = SourceHealth(manifest([row], detail_failed=1, detail_failed_job_ids=['a']), [row])
    assert not health.resolve('test', 'Company', row).content_reliable


def test_review_required_no_safe_version_carry():
    row = dict(job(), title='大模型评测工程师', description='', requirements='')
    health = SourceHealth(manifest([row], detail_failed=1), [row]).resolve('test', 'Company', row)
    good = job()
    previous = observation('2026-09-01', [good])['classifications'][0]
    previous['versions']['market'] = 'old'
    result = classify_record('2026-09-02', row, health, VERSIONS, previous)[0]
    assert result['classification_status'] == 'review_required'
    assert result['career_pool'] is None


def test_reappeared_is_never_new():
    life = Lifecycle()
    observe(life, '2026-09-01', [job()])
    observe(life, '2026-09-02', [])
    observe(life, '2026-09-03', [])
    assert [row['event_type'] for row in observe(life, '2026-09-04', [job()])] == ['REAPPEARED']


def test_reliable_content_change_and_stable_identity():
    life = Lifecycle()
    observe(life, '2026-09-01', [job()])
    changed = dict(job(), requirements='Python与RAG经验。')
    events = observe(life, '2026-09-02', [changed])
    assert len(events) == 1 and events[0]['event_type'] == 'UPDATED'
    assert events[0]['previous_sha256'] != events[0]['current_sha256']
    assert observe(life, '2026-09-03', [dict(changed, company='Renamed')]) == []


def test_new_requires_previous_and_current_healthy_absence():
    life = Lifecycle()
    observe(life, '2026-09-01', [])
    event = observe(life, '2026-09-02', [job()])[0]
    assert event['event_type'] == 'NEW' and event['event_status'] == 'confirmed'
    life = Lifecycle()
    observe(life, '2026-09-01', [], status='error')
    assert observe(life, '2026-09-02', [job()])[0]['event_type'] == 'FIRST_SEEN'


def test_scope_changes_block_absence_inference():
    life = Lifecycle()
    observe(life, '2026-09-01', [job()])
    changed = manifest([])
    changed['cities'] = ['上海']
    events = life.observe('2026-09-02', [], SourceHealth(changed, []))
    assert 'SOURCE_SCOPE_CHANGED' in events[0]['reason_codes']
    assert life.state[('test', 'a')].missing_streak == 0


def test_identity_dedup_and_conflict():
    assert len(index_jobs([job(), job()])) == 1
    assert len(index_jobs([job(), job('b')])) == 2  # same JD, two actual postings
    with pytest.raises(ValueError, match='CONFLICT'):
        index_jobs([job(), dict(job(), company='Other')])
    with pytest.raises(ValueError, match='MISSING'):
        index_jobs([dict(job(), job_id='')])


def test_market_version_mismatch_blocks_trend():
    history = history_days()
    history[0]['versions']['market'] = 'old'
    trend = aggregate_trends(history)
    assert not trend['coverage']['comparable']
    assert {'CLASSIFIER_VERSION_MISMATCH', 'REPLAY_REQUIRED'} <= set(trend['coverage']['reason_codes'])
    assert trend['market']['new_7d'] is None


def test_fit_version_mismatch_only_blocks_qa_bridge():
    history = history_days()
    history[0]['versions']['fit'] = 'old'
    trend = aggregate_trends(history)
    assert trend['coverage']['comparable']
    assert trend['market']['new_7d'] == 0
    assert not trend['coverage']['qa_bridge_comparable']
    assert trend['qa_bridge']['new_7d'] is None
    assert 'REPLAY_REQUIRED' in trend['coverage']['qa_bridge_reason_codes']


def test_skill_version_mismatch_does_not_block_market():
    history = history_days()
    history[0]['versions']['skills'] = 'old'
    trend = aggregate_trends(history)
    assert trend['coverage']['comparable']
    assert not trend['coverage']['skills_comparable']
    assert all(row['change_7d'] is None for row in trend['skills']['top'])


def test_healthy_daily_window_is_comparable_and_no_version_event():
    history = history_days()
    trend = aggregate_trends(history)
    assert trend['coverage']['comparable']
    assert trend['market']['active_jobs'] == trend['qa_bridge']['active_jobs'] == 1
    assert trend['market']['new_7d'] == trend['market']['removed_7d'] == 0


def test_skills_share_and_breadth_prevent_single_company_growth_claim():
    history = history_days()
    history[-1] = observation('2026-09-08', [job(), job('b')])
    trend = aggregate_trends(history)
    python = next(row for row in trend['skills']['top'] if row['skill'] == 'Python')
    assert python['count'] == 2 and python['change_7d'] == 1
    assert python['mention_share'] == 1 and python['mention_share_change_7d'] == 0
    assert python['company_breadth'] == 1
    assert not trend['skills']['rising']


def test_removed_metrics_use_market_membership_before_disappearance():
    life, history = Lifecycle(), []
    for i in range(8):
        day = (date(2026, 9, 1) + timedelta(days=i)).isoformat()
        jobs = [job()] if i < 6 else []
        events = observe(life, day, jobs)
        history.append(observation(day, jobs, events=events))
    trend = aggregate_trends(history)
    assert trend['market']['removed_7d'] == trend['qa_bridge']['removed_7d'] == 1
    assert trend['market']['active_jobs'] == 0


def test_reclassification_does_not_make_lifecycle_events_or_market_removal():
    life, history = Lifecycle(), []
    for i in range(8):
        day = (date(2026, 9, 1) + timedelta(days=i)).isoformat()
        row = job() if i < 4 else dict(job(), title='人事经理', description='负责招聘管理', requirements='招聘经验')
        events = observe(life, day, [row])
        history.append(observation(day, [row], events=events))
    trend = aggregate_trends(history)
    assert trend['market']['removed_7d'] == 0
    assert trend['market']['active_jobs'] == 0


def write_day(root, day, jobs, **changes):
    for folder in ('clean', 'raw'):
        (root / folder).mkdir(exist_ok=True)
    (root / 'clean' / f'{day}.json').write_text(json.dumps(jobs))
    (root / 'raw' / f'{day}_manifest.json').write_text(json.dumps(manifest(jobs, **changes)))


def test_replay_outputs_deterministically_and_preserves_sources(tmp_path):
    write_day(tmp_path, '2026-09-01', [job()])
    write_day(tmp_path, '2026-09-02', [])
    write_day(tmp_path, '2026-09-03', [])
    original = (tmp_path / 'clean/2026-09-01.json').read_bytes()
    result = replay('2026-09-02', '2026-09-04', data_dir=tmp_path)
    assert result['warmup_dates'] == ['2026-09-01']
    assert result['incomplete_history'][0]['date'] == '2026-09-04'
    assert result['observations'][1]['event_counts']['REMOVED'] == 1
    path = tmp_path / 'analysis/events/2026-09-03.jsonl'
    before = path.read_bytes()
    replay('2026-09-02', '2026-09-04', data_dir=tmp_path)
    assert before == path.read_bytes()
    assert original == (tmp_path / 'clean/2026-09-01.json').read_bytes()
    assert not (tmp_path / 'analysis/classification/2026-09-01.jsonl').exists()


def test_replay_rejects_fake_version_and_input_output_overlap(tmp_path):
    with pytest.raises(ValueError, match='UNSUPPORTED_MARKET_VERSION'):
        replay('2026-09-01', '2026-09-02', data_dir=tmp_path, market_version='fake')
    with pytest.raises(ValueError, match='OVERLAP'):
        replay('2026-09-01', '2026-09-02', data_dir=tmp_path, output_dir=tmp_path / 'clean')


def test_hits_only_history_is_not_a_snapshot(tmp_path):
    (tmp_path / 'analysis').mkdir()
    (tmp_path / 'analysis/2026-09-01_ai_eval_hits.jsonl').write_text('{}\n')
    result = replay('2026-09-01', '2026-09-01', data_dir=tmp_path)
    assert not result['historical_replay_verified']
    assert result['incomplete_history'][0]['reason_codes'] == ['HISTORICAL_SOURCE_INCOMPLETE']
    assert not (tmp_path / 'analysis/classification').exists()


def test_changed_city_scope_cannot_remove_older_scope_jobs_on_later_runs():
    life = Lifecycle()
    observe(life, '2026-09-01', [job()])
    for day in ('2026-09-02', '2026-09-03', '2026-09-04'):
        changed = manifest([])
        changed['cities'] = ['上海']
        events = life.observe(day, [], SourceHealth(changed, []))
        assert events[0]['event_type'] == 'MISSING'
        assert 'SOURCE_SCOPE_CHANGED' in events[0]['reason_codes']
    assert not life.state[('test', 'a')].removed


def test_no_source_manifest_cannot_be_comparable():
    history = history_days()
    for obs in history:
        obs['health'] = SourceHealth({'job_count': 0, 'platforms': []}, [])
    assert not aggregate_trends(history)['coverage']['comparable']


def test_old_removal_label_version_blocks_trend_even_outside_window():
    history = history_days()
    old = deepcopy(history[0])
    old['date'] = '2026-08-01'
    old['classifications'][0]['versions']['market'] = 'old'
    for obs in history:
        obs['classifications'] = []
        obs['present_keys'] = set()
        obs['events'] = [dict(platform='test', job_id='a', event_type='MISSING', event_status='provisional')]
    history[-1]['events'] = [dict(platform='test', job_id='a', event_type='REMOVED', event_status='confirmed')]
    trend = aggregate_trends([old, *history])
    assert 'CLASSIFIER_VERSION_MISMATCH' in trend['coverage']['reason_codes']


def test_audit_bundle_is_bounded_and_does_not_update_ontology(tmp_path):
    from src.analysis.audit_bundle import export_bundle
    from src.analysis.pipeline import load_settings
    jobs = [dict(job(str(i)), requirements='Python NovelHarnessXYZ') for i in range(8)]
    obs = observation('2026-09-01', jobs)
    settings = load_settings()[0]
    config = dict(settings['audit'], max_jobs=2, max_per_category=2)
    events = [dict(platform='test', job_id=row['job_id'], event_type='NEW', event_status='confirmed') for row in jobs]
    bundle = export_bundle('2026-09-01', jobs, obs['classifications'],
                           {identity(row): classify_market(row) for row in jobs}, obs['health'], events,
                           aggregate_trends([obs]), None, config)
    assert len(bundle['jobs']) == 2 and bundle['truncated']
    assert any(row['term'] == 'novelharnessxyz' for row in bundle['skill_candidates'])
    assert all('NovelHarnessXYZ' not in row['skill_tags'] for row in obs['classifications'])
    assert all('description' in row and row['deterministic_delta'] for row in bundle['jobs'])


def test_carried_fit_version_is_not_forged():
    original = job()
    previous = observation('2026-09-01', [original])['classifications'][0]
    previous['versions']['fit'] = 'old'
    broken = dict(original, description='', requirements='')
    health = SourceHealth(manifest([broken], detail_failed=1), [broken]).resolve('test', 'Company', broken)
    row = classify_record('2026-09-02', broken, health, VERSIONS, previous)[0]
    assert row['classification_status'] == 'review_required'
    assert row['career_pool'] is None
    assert row['versions']['fit'] == 'old'
    assert 'REPLAY_REQUIRED' in row['reason_codes']['fit']


def test_manifest_count_mismatch_blocks_presence():
    m = manifest([job()])
    m['job_count'] = 2
    assert not SourceHealth(m, [job()]).resolve('test').presence_reliable


def test_all_failed_empty_replay_preserves_existing_classifications(tmp_path):
    write_day(tmp_path, '2026-09-01', [], status='error', complete=False, stopped_by='error', error='offline')
    target = tmp_path / 'analysis/classification/2026-09-01.jsonl'
    target.parent.mkdir(parents=True)
    target.write_text('previous reliable artifact\n')
    report = replay('2026-09-01', '2026-09-01', data_dir=tmp_path)
    assert target.read_text() == 'previous reliable artifact\n'
    assert 'OUTPUT_PRESERVED' in report['incomplete_history'][0]['reason_codes']
    assert not report['historical_replay_verified']


def test_neither_company_nor_location_can_decide_market_or_fit():
    row = job()
    other = dict(row, company='Excluded company', city_norm=['不存在'], career_pool='X')
    market = classify_market(row)
    assert market == classify_market(other)
    assert classify_personal_fit(row, market) == classify_personal_fit(other, market)


def test_skill_version_change_does_not_report_new_ontology_as_new_market_skill():
    history = history_days()
    history[0]['versions']['skills'] = 'old'
    history[-1]['classifications'][0]['skill_tags'].append('new-version-tag')
    trend = aggregate_trends(history)
    assert not trend['skills']['newly_observed']


def test_fit_review_does_not_remove_inherited_market_fact():
    history = history_days()
    row = history[-1]['classifications'][0]
    row['classification_status'] = 'review_required'
    row['reason_codes']['market'].append('CONTENT_CARRIED_FORWARD')
    row['reason_codes']['fit'] = ['REPLAY_REQUIRED']
    row['career_pool'] = None
    row['versions']['fit'] = 'old'
    trend = aggregate_trends(history)
    assert trend['market']['active_jobs'] == 1
    assert trend['coverage']['comparable']
    assert not trend['coverage']['qa_bridge_comparable']


def test_audit_includes_insufficient_non_ai_titled_record():
    from src.analysis.audit_bundle import export_bundle
    row = dict(job(), title='SA', description='', requirements='')
    obs = observation('2026-09-01', [row])
    bundle = export_bundle('2026-09-01', [row], obs['classifications'], {identity(row): classify_market(row)},
                           obs['health'], [], aggregate_trends([obs]), None, load_settings()[0]['audit'])
    assert bundle['jobs'][0]['categories'] == ['REVIEW_REQUIRED']
    assert bundle['jobs'][0]['current_classification'] is None


def test_skill_version_change_preserves_carried_personal_fit():
    previous = observation('2026-09-01', [job()])['classifications'][0]
    previous['versions']['skills'] = 'old'
    broken = dict(job(), description='', requirements='')
    health = SourceHealth(manifest([broken], detail_failed=1), [broken]).resolve('test', 'Company', broken)
    row = classify_record('2026-09-02', broken, health, VERSIONS, previous)[0]
    assert row['classification_status'] == 'carried_forward'
    assert row['career_pool'] == 'P1'
    assert row['versions']['fit'] == VERSIONS['fit']
    assert row['versions']['skills'] == 'old'
