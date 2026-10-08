"""Offline policy boundaries, frozen incidents, and downstream contract guards."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.analysis.daily_health import build_daily_health, DailyHealthError
from src.analysis.source_health import SourceHealth
from src.analysis.pipeline import load_settings, replay
from src.analysis.classification import classify_record
from src.analysis.lifecycle import Lifecycle, identity
from src.analysis.trends import compare_trends
from src.operations.daily_ops import DailyOperations
from src.operations.presentation import build_presentation
from tools.run_weekly_report import run_weekly_report

FROZEN = json.loads((Path(__file__).parent / 'fixtures/detail_gap_history.json').read_text())
DAY = '2026-10-08'
VERSIONS = load_settings()[1]


def job(platform, job_id, company='Company'):
    return dict(platform=platform, job_id=str(job_id), company=company,
                title='大模型测试工程师', description='负责大模型产品质量保障和评测体系建设。',
                requirements='熟悉Python。', url='https://example.test/job', city_norm=['北京'])


def inputs(total=1000, failed=5, platform='test'):
    jobs = [job(platform, i) for i in range(total)]
    row = dict(platform=platform, status='partial' if failed else 'success',
               complete=not failed, source_total=total, expected_pages=1, pages_fetched=1,
               records_fetched=total, jobs_mapped=total, jobs_in_scope=total,
               details_fetched=total-failed, detail_failed=failed, outside_city_scope=0,
               duplicate_records=0, missing_job_id=0, failed_companies=[], metadata={},
               detail_failed_job_ids=[str(i) for i in range(failed)], error='',
               stopped_by='detail_errors' if failed else 'source_total_reached')
    return wrap([row], jobs), jobs


def wrap(rows, jobs, day=DAY):
    return dict(generated_at=f'{day}T12:00:00+08:00', job_count=len(jobs),
                complete=all(r['complete'] for r in rows), cities=['北京'], platforms=rows)


def build(manifest, jobs, day=DAY, **kwargs):
    run = deepcopy(FROZEN['run_2026_10_08'])
    run['date'] = day
    return build_daily_health(day, run, manifest, jobs, **kwargs)


@pytest.mark.parametrize('total,failed,tolerated', [
    (1915, 3, True), (1825, 1, True), (1000, 5, True), (999, 5, False),
    (200, 1, True), (199, 1, False), (10000, 6, False), (1000, 1000, False),
])
def test_policy_boundaries_and_no_human_incident(tmp_path, total, failed, tolerated):
    manifest, jobs = inputs(total, failed)
    frozen = deepcopy((manifest, jobs))
    health = build(manifest, jobs)
    source = health['sources']['test']
    assert source['source_complete'] is False
    assert source['source_completeness'] == 'PARTIAL'
    assert source['detail_failed'] == failed
    assert source['warnings'] == (['TOLERATED_DETAIL_GAP'] if tolerated else [])
    assert health['overall_action'] == ('NO_NEW_ACTION' if tolerated else 'ACTION_REQUIRED')
    assert (manifest, jobs) == frozen
    config = tmp_path / 'config.yaml'
    config.write_text('output_dir: data/raw\n')
    ops = DailyOperations(data_dir=tmp_path / 'data', root=tmp_path, config_path=config)
    artifact = ops.publish(DAY, run=FROZEN['run_2026_10_08'], health=health)
    assert artifact['human_action_required'] is (not tolerated)
    assert artifact['incident_id'] is None if tolerated else artifact['incident_id'] is not None
    assert build_presentation(artifact).action_required is (not tolerated)


@pytest.mark.parametrize('changes', [
    {'pages_fetched': 0}, {'source_total': 1001}, {'missing_job_id': 1},
    {'jobs_mapped': 1001}, {'outside_city_scope': 1}, {'details_fetched': 994},
    {'detail_failed': True}, {'detail_failed_job_ids': ['0']},
    {'detail_failed_job_ids': ['0'] * 5},
    {'detail_failed_job_ids': ['0', '1', '2', '3', 'absent']},
    {'detail_failed_job_ids': None}, {'error': 'offline'},
    {'failed_companies': ['Company']}, {'metadata': {'list_complete': False}},
    {'metadata': {'list_error': True}}, {'metadata': {'completeness_reasons': ['repeated_page']}},
])
def test_corrupt_or_unverified_coverage_never_tolerated(changes):
    manifest, jobs = inputs()
    manifest['platforms'][0].update(changes)
    health = build(manifest, jobs)
    assert health['overall_action'] == 'ACTION_REQUIRED'
    assert health['sources']['test']['warnings'] == []


@pytest.mark.parametrize('damage', ['count', 'body', 'duplicate'])
def test_snapshot_corruption_cannot_be_hidden_by_warning(damage):
    manifest, jobs = inputs()
    if damage == 'count':
        manifest['job_count'] += 1
    elif damage == 'body':
        jobs[-1].update(title='', description='', requirements='')
    else:
        jobs[-1] = deepcopy(jobs[-2])
    assert build(manifest, jobs)['overall_action'] == 'ACTION_REQUIRED'


def test_stage_failure_still_requires_human_even_with_tolerated_source():
    manifest, jobs = inputs()
    run = deepcopy(FROZEN['run_2026_10_08'])
    run['analysis']['status'] = 'FAILED'
    assert build_daily_health(DAY, run, manifest, jobs)['overall_action'] == 'ACTION_REQUIRED'


@pytest.mark.parametrize('policy', ['max_failed: true\nmax_failure_rate: 0.005',
                                    'max_failed: 5\nmax_failure_rate: .nan', '{}'])
def test_invalid_policy_fails_closed(tmp_path, policy):
    path = tmp_path / 'policy.yaml'
    path.write_text(policy)
    manifest, jobs = inputs()
    with pytest.raises(DailyHealthError, match='INVALID_DETAIL_TOLERANCE_POLICY'):
        build(manifest, jobs, detail_tolerance_path=path)


@pytest.mark.parametrize('sample', FROZEN['samples'], ids=lambda s: s['date']+'-'+s['source']['platform'])
def test_frozen_history(sample):
    row = deepcopy(sample['source'])
    platform, day = row['platform'], sample['date']
    ids = list(row.get('detail_failed_job_ids', []))
    ids += [f'sibling-{i}' for i in range(row['jobs_in_scope'] - len(ids))]
    jobs = [job(platform, i, 'MiniMax' if platform == 'feishu' else 'Company') for i in ids]
    health = build(wrap([row], jobs, day), jobs, day)
    tolerated = (day, platform) in {('2026-09-17', 'tencent'), (DAY, 'tencent'), (DAY, 'meituan')}
    assert bool(health['sources'][platform]['warnings']) is tolerated
    assert health['overall_action'] == ('NO_NEW_ACTION' if tolerated else 'ACTION_REQUIRED')


@pytest.mark.parametrize('pool', ['P1', 'P2'])
def test_known_priority_job_preserves_classification_and_is_marked_for_verification(pool):
    manifest, jobs = inputs(200, 1)
    good = SourceHealth(*inputs(200, 0))
    previous, _ = classify_record('2026-10-07', jobs[0], good.resolve('test', 'Company', jobs[0]), VERSIONS)
    previous['career_pool'] = pool
    current, _ = classify_record(DAY, jobs[0], SourceHealth(manifest, jobs).resolve('test', 'Company', jobs[0]), VERSIONS, previous)
    assert current['classification_status'] == 'carried_forward'
    assert 'DETAIL_VERIFICATION_REQUIRED' in current['reason_codes']['fit']
    for key in ('career_pool', 'in_scope', 'market_relevance', 'role_family', 'skill_tags', 'content_sha256'):
        assert current[key] == previous[key]


def test_frozen_detail_failures_and_company_gap_preserve_events_and_weekly(tmp_path):
    rows = [deepcopy(s['source']) for s in FROZEN['samples'] if s['date'] == DAY]
    jobs = []
    for row in rows:
        ids = list(row.get('detail_failed_job_ids', []))
        ids += [f'sibling-{i}' for i in range(row['jobs_in_scope'] - len(ids))]
        jobs += [job(row['platform'], i, 'MiniMax' if row['platform']=='feishu' else 'Company') for i in ids]
    manifest = wrap(rows, jobs)
    health = build(manifest, jobs)
    assert [p for p,s in health['sources'].items() if s['limitation_state']=='NEW_REGRESSION'] == ['feishu']
    # Warm up the 15 absent Baichuan identities using a verified observation.
    before_jobs = deepcopy(jobs) + [job('feishu', f'baichuan-{i}', '百川智能') for i in range(15)]
    before = deepcopy(manifest)
    before['job_count'] += 15
    before['complete'] = True
    for row in before['platforms']:
        row.update(status='success', complete=True, error='', detail_failed=0,
                   detail_failed_job_ids=[], failed_companies=[], stopped_by='source_total_reached')
        if row['platform']=='feishu':
            for key in ('source_total','records_fetched','jobs_mapped','jobs_in_scope'):
                row[key] += 15
    life = Lifecycle(2)
    prior_health = SourceHealth(before, before_jobs)
    life.observe('2026-10-07', before_jobs, prior_health)
    resolved = SourceHealth(manifest, jobs)
    events = life.observe(DAY, jobs, resolved)
    missing = [e for e in events if e['company']=='百川智能']
    assert len(missing)==15
    assert all(e['event_type']=='MISSING' and e['event_status']=='provisional' for e in missing)
    failed = {(r['platform'], i) for r in rows for i in r['detail_failed_job_ids']}
    assert not any(identity(e) in failed and e['event_type'] in {'UPDATED','MISSING','REMOVED'} for e in events)
    # Full offline pipeline + actual weekly renderer, all writes under tmp_path.
    data = tmp_path / 'data'
    for day, observations, m in [('2026-10-07', before_jobs, before), (DAY, jobs, manifest)]:
        for folder, suffix, value in [('clean','',observations), ('raw','_manifest',m)]:
            target = data / folder / f'{day}{suffix}.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value))
    out = tmp_path / 'analysis'
    result = replay('2026-10-07', DAY, data_dir=data, output_dir=out)
    assert result['historical_replay_verified']
    a, b = [json.loads((out/'trends/snapshots'/f'{day}.json').read_text()) for day in ['2026-10-07',DAY]]
    comparison = compare_trends(a,b)
    for family in ('inventory','presence_flow'):
        assert 'feishu' in comparison['comparability'][family]['excluded_platforms']
        assert {'tencent','meituan'} <= set(comparison['comparability'][family]['included_platforms'])
    code, report = run_weekly_report('2026-10-07',DAY,trend_root=out/'trends', output_dir=tmp_path/'reports')
    assert code==0 and report.is_file()
    bundle=json.loads((out/'audit'/f'{DAY}_bundle.json').read_text())
    reviewed={identity(r) for r in bundle['jobs'] if 'REVIEW_REQUIRED' in r['categories']}
    assert failed <= reviewed


def test_zero_failures_remain_complete_without_warning():
    manifest, jobs = inputs(200, 0)
    health = build(manifest, jobs)
    assert health['overall_action'] == 'NO_NEW_ACTION'
    assert health['sources']['test']['source_completeness'] == 'COMPLETE'
    assert health['sources']['test']['warnings'] == []


def test_policy_can_be_disabled_without_changing_collection(tmp_path):
    path = tmp_path / 'policy.yaml'
    path.write_text('max_failed: 0\nmax_failure_rate: 0\n')
    manifest, jobs = inputs()
    assert build(manifest, jobs, detail_tolerance_path=path)['overall_action'] == 'ACTION_REQUIRED'


def test_future_source_health_reason_is_never_silenced(monkeypatch):
    from src.analysis.source_health import Health
    monkeypatch.setattr(SourceHealth, 'resolve', lambda *args: Health(True, True, ('FUTURE_REASON',)))
    manifest, jobs = inputs()
    assert build(manifest, jobs)['overall_action'] == 'ACTION_REQUIRED'
