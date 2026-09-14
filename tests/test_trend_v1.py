"""Trend contract tests use frozen-shape labels, never re-evaluate classifier rules."""
from copy import deepcopy
import json

import pytest

from src.analysis.lifecycle import identity
from src.analysis.source_health import SourceHealth
from src.analysis.trends import compare_trends, trend_snapshot, validate_snapshot, validate_comparison

VERSIONS = {'market': 'market_v1', 'fit': 'fit_v1', 'skills': 'skills_v1'}


def row(job_id='1', platform='tencent', **changes):
    result = dict(platform=platform, job_id=job_id, company='Company',
                  title='Frozen fixture', description='Reliable description', requirements='',
                  content_sha256='same-content', in_scope=True, market_relevance='core',
                  role_family='evaluation_engineering', secondary_role_families=[],
                  ai_relation='core_ai_evaluation', career_pool='P1', skill_tags=['Python'],
                  classification_status='fresh', reason_codes={'market': [], 'fit': []},
                  versions=dict(VERSIONS))
    result.update(changes)
    return result


def observation(day, rows, *, events=(), platforms=('tencent',), unhealthy=None, jobs=None):
    jobs = list({identity(r): r for r in rows}.values()) if jobs is None else jobs
    records = []
    for platform in sorted(set(platforms) | {r['platform'] for r in jobs}):
        count = sum(r['platform'] == platform for r in jobs)
        record = dict(platform=platform, status='success', complete=True,
                      source_total=count, expected_pages=1, pages_fetched=1,
                      records_fetched=count, jobs_mapped=count, jobs_in_scope=count,
                      detail_failed=0, stopped_by='source_total_reached', error='')
        record.update((unhealthy or {}).get(platform, {}))
        records.append(record)
    health = SourceHealth(dict(job_count=len(jobs), cities=['北京'], platforms=records), jobs)
    return dict(date=day, classifications=rows, events=list(events), versions=dict(VERSIONS),
                health=health, present_keys={identity(r) for r in jobs}, jobs_by_identity={identity(r): r for r in jobs})


def event(kind, job_id='1', platform='tencent', **changes):
    result = dict(platform=platform, job_id=job_id, company='Company', event_type=kind,
                  event_status='confirmed', previous_sha256='old-content', current_sha256='same-content')
    result.update(changes)
    return result


def test_identity_is_platform_and_job_id_not_content_or_title():
    a = row(secondary_role_families=['product', 'evaluation_engineering', 'product'], skill_tags=['Python', 'Python'])
    rows = [a, deepcopy(a), row('2'), row(platform='alibaba'), row('outside', in_scope=False)]
    snap = trend_snapshot([observation('2026-09-01', rows)])
    assert snap['active_jobs'] == 3
    assert snap['unique_content_versions'] == 1
    assert snap['metric_semantics']['unique_content_versions'] == 'DIAGNOSTIC_ONLY'
    assert snap['by_role_family'] == {'evaluation_engineering': 3}
    assert snap['by_role_family_any'] == {'evaluation_engineering': 3, 'product': 1}
    assert snap['metric_semantics']['by_role_family_any'] == 'NON_ADDITIVE'
    assert snap['by_skill_tag'] == {'Python': 3}
    assert snap['metric_semantics']['by_skill_tag'] == 'NON_ADDITIVE'
    assert snap['hybrid_role_count'] == 1
    assert snap['hybrid_role_share'] == {'count': 1, 'denominator': 3, 'share': 1 / 3}
    assert snap['by_company']['Company']['active_jobs'] == 3
    assert snap['by_company']['Company']['P1'] == 3


def test_conflicting_identity_fails_instead_of_selecting_arbitrary_version():
    with pytest.raises(ValueError, match='IDENTITY_CONFLICT'):
        trend_snapshot([observation('2026-09-01', [row(), row(content_sha256='different')])])


@pytest.mark.parametrize('field,value,error', [
    ('in_scope', None, 'SCHEMA_REPLAY_REQUIRED'),
    ('career_pool', None, 'FIT_INVARIANT'),
    ('market_relevance', 'unknown', 'INVALID_MARKET'),
    ('role_family', 'unknown', 'INVALID_MARKET'),
    ('ai_relation', None, 'INVALID_MARKET'),
    ('secondary_role_families', None, 'INVALID_LIST'),
    ('skill_tags', 'Python', 'INVALID_LIST'),
    ('content_sha256', '', 'INCOMPLETE'),
])
def test_upstream_schema_fails_closed(field, value, error):
    with pytest.raises(ValueError, match=error):
        trend_snapshot([observation('2026-09-01', [row(**{field: value})])])


def test_empty_inventory_and_zero_baseline_do_not_divide_by_zero():
    a = trend_snapshot([observation('2026-09-01', [])])
    b = trend_snapshot([observation('2026-09-02', [row()])])
    assert a['hybrid_role_share'] == {'count': 0, 'denominator': 0, 'share': None}
    result = compare_trends(a, b)
    assert result['market']['active_jobs'] == {'from': 0, 'to': 1, 'delta': 1, 'pct_change': None, 'comparable': True}
    assert result['market']['hybrid_role_share']['delta'] is None
    assert not result['market']['hybrid_role_share']['comparable']


def test_common_platform_intersection_prevents_false_growth():
    a = observation('2026-09-01', [row(platform='tencent'), row(platform='alibaba'), row(platform='bytedance')],
                    unhealthy={'bytedance': {'complete': False, 'stopped_by': 'incomplete_list'}})
    b = observation('2026-09-02', [row(platform='tencent'), row(platform='alibaba'),
                                    *[row(str(i), platform='bytedance') for i in range(100)]])
    result = compare_trends(trend_snapshot([a]), trend_snapshot([a, b]))
    info = result['comparability']['inventory']
    assert info['included_platforms'] == ['alibaba', 'tencent']
    assert info['excluded_platforms'] == ['bytedance']
    assert info['comparable']
    assert result['observed_full_snapshot']['from']['active_jobs'] == 3
    assert result['observed_full_snapshot']['to']['active_jobs'] == 102
    assert result['market']['active_jobs']['delta'] == 0
    for side in ('from', 'to'):
        assert result['comparable_subset']['inventory'][side]['active_jobs'] == 2
        assert result['by_skill_tag']['Python']['share'][side]['denominator'] == 2


@pytest.mark.parametrize('failure', ['presence', 'review', 'missing_platform', 'version', 'scope'])
def test_no_comparable_set_never_emits_changes(failure):
    a, b = observation('2026-09-01', [row()]), observation('2026-09-02', [row('2')])
    if failure == 'presence':
        a = observation('2026-09-01', [row()], unhealthy={'tencent': {'complete': False}})
    if failure == 'review':
        a['classifications'][0]['classification_status'] = 'review_required'
    if failure == 'missing_platform':
        a = observation('2026-09-01', [row(platform='alibaba')], platforms=('alibaba',))
    if failure == 'version':
        a['versions']['market'] = 'old'
    if failure == 'scope':
        a['health'].cities = ('上海',)
    result = compare_trends(trend_snapshot([a]), trend_snapshot([b]))
    assert not result['comparability']['inventory']['comparable']
    assert result['market']['active_jobs']['delta'] is None
    assert result['market']['active_jobs']['pct_change'] is None
    validate_comparison(result)


def test_carried_forward_requires_contract_and_classification_coverage():
    broken = row(description='', requirements='')
    carry = row(classification_status='carried_forward', reason_codes={'market': ['CONTENT_CARRIED_FORWARD'], 'fit': []})
    a = observation('2026-09-01', [row()])
    b = observation('2026-09-02', [carry], jobs=[broken], unhealthy={'tencent': {
        'detail_failed': 1, 'detail_failed_job_ids': ['1'], 'stopped_by': 'detail_errors'}})
    result = compare_trends(trend_snapshot([a]), trend_snapshot([a, b]))
    assert result['comparability']['inventory']['comparable']
    assert result['comparability']['presence_flow']['comparable']
    assert not result['comparability']['content_flow']['comparable']
    b['classifications'][0]['reason_codes']['market'] = []
    bad = trend_snapshot([a, b])
    assert bad['active_jobs'] == 0
    assert not bad['platforms']['tencent']['reliability']['inventory']['reliable']


def test_detail_failure_without_classification_blocks_inventory():
    a = observation('2026-09-01', [row()])
    b = observation('2026-09-02', [], jobs=[row(description='')], unhealthy={'tencent': {'detail_failed': 1}})
    result = compare_trends(trend_snapshot([a]), trend_snapshot([a, b]))
    assert not result['comparability']['inventory']['comparable']
    assert result['market']['active_jobs']['delta'] is None


def test_canonical_lifecycle_flows_keep_missing_reappearance_and_updates_distinct():
    a = observation('2026-09-01', [row('gone'), row('back'), row('changed', content_sha256='old-content')])
    b = observation('2026-09-02', [row('back'), row('changed'), row('new')], events=[
        event('REMOVED', 'gone'), event('REAPPEARED', 'back'), event('UPDATED', 'changed'), event('NEW', 'new'),
        event('MISSING', 'gone', event_status='provisional'), event('FIRST_SEEN', 'unconfirmed', event_status='provisional')])
    snap = trend_snapshot([a, b])
    for field in ('new_jobs', 'removed_jobs', 'reappeared_jobs', 'updated_jobs'):
        assert snap[field] == snap['by_company']['Company'][field] == 1
    assert snap['diagnostics']['missing_diagnostic_events'] == 1
    result = compare_trends(trend_snapshot([a]), snap)
    assert result['lifecycle']['NEW']['to'] == 1
    assert result['lifecycle']['REAPPEARED']['to'] == 1


def test_provisional_missing_does_not_become_removal():
    a = observation('2026-09-01', [row()])
    b = observation('2026-09-02', [], events=[event('MISSING', event_status='provisional')])
    snap = trend_snapshot([a, b])
    assert snap['removed_jobs'] == 0
    assert snap['new_jobs'] == 0


def test_presence_and_content_failures_block_their_flow_deltas():
    a = observation('2026-09-01', [row('gone'), row()])
    b = observation('2026-09-02', [row()], events=[event('REMOVED', 'gone'), event('UPDATED')],
                    unhealthy={'tencent': {'complete': False, 'detail_failed': 1, 'detail_failed_job_ids': ['1']}})
    snap = trend_snapshot([a, b])
    assert snap['removed_jobs'] == snap['updated_jobs'] == 0
    result = compare_trends(trend_snapshot([a]), snap)
    for kind in ('NEW', 'REMOVED', 'REAPPEARED', 'UPDATED'):
        assert result['lifecycle'][kind]['delta'] is None
        assert result['lifecycle'][kind]['pct_change'] is None
        assert not result['lifecycle'][kind]['comparable']


def test_leaving_scope_clears_cached_removal_label():
    a = observation('2026-09-01', [row()])
    b = observation('2026-09-02', [], jobs=[row(in_scope=False)])
    c = observation('2026-09-03', [], events=[event('REMOVED')])
    assert trend_snapshot([a, b, c])['removed_jobs'] == 0


def test_stale_removed_label_version_blocks_presence_comparison():
    a = observation('2026-09-01', [row(versions={**VERSIONS, 'market': 'old'})])
    b = observation('2026-09-02', [], events=[event('REMOVED')])
    snap = trend_snapshot([a, b])
    assert snap['removed_jobs'] == 0
    assert not snap['platforms']['tencent']['reliability']['presence_flow']['reliable']


def test_feishu_failed_company_excludes_platform_without_coverage_threshold():
    a = observation('2026-09-01', [row(platform='feishu', company='OK')], platforms=('feishu',),
                    unhealthy={'feishu': {'status': 'partial', 'complete': False, 'stopped_by': 'company_error',
                                         'attempted_companies': ['OK', 'Failed'], 'failed_companies': ['Failed']}})
    b = observation('2026-09-02', [row(platform='feishu', company='OK')], platforms=('feishu',),
                    unhealthy={'feishu': {'attempted_companies': ['OK', 'Failed'], 'stopped_by': 'all_companies_complete'}})
    result = compare_trends(trend_snapshot([a]), trend_snapshot([a, b]))
    assert result['comparability']['inventory']['excluded_platforms'] == ['feishu']
    assert not result['comparability']['presence_flow']['comparable']


def test_validation_rejects_corrupt_denominators_and_noncomparable_deltas():
    snap = trend_snapshot([observation('2026-09-01', [row()])])
    snap['shares']['by_role_family']['evaluation_engineering']['denominator'] = 2
    with pytest.raises(ValueError, match='DENOMINATOR'):
        validate_snapshot(snap)
    a = trend_snapshot([observation('2026-09-01', [])])
    b = trend_snapshot([observation('2026-09-02', [], unhealthy={'tencent': {'complete': False}})])
    result = compare_trends(a, b)
    result['market']['active_jobs']['delta'] = 0
    with pytest.raises(ValueError, match='NOT_COMPARABLE_DELTA'):
        validate_comparison(result)


def test_trend_only_replay_reads_existing_events_and_preserves_all_upstream(tmp_path, monkeypatch):
    from src.analysis.pipeline import replay
    from src.analysis import pipeline
    for day in ('2026-09-01', '2026-09-02'):
        jobs = [dict(platform='tencent', job_id='1', company='Company', title='大模型评测工程师',
                     description='负责大模型评测体系与评测平台建设。', requirements='Python')]
        obs = observation(day, [], jobs=jobs)
        files = {f'clean/{day}.json': json.dumps(jobs),
                 f'raw/{day}_manifest.json': json.dumps(obs['health'].manifest),
                 f'analysis/events/{day}.jsonl': '',
                 f'analysis/classification/{day}.jsonl': 'legacy upstream untouched\n'}
        for name, value in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
    original = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    def fail(*args, **kwargs):
        raise AssertionError('Trend must consume lifecycle, not regenerate it')
    monkeypatch.setattr(pipeline.Lifecycle, 'observe', fail)
    result = replay('2026-09-01', '2026-09-02', data_dir=tmp_path, trend_only=True)
    assert result['historical_replay_verified']
    assert all(p.read_bytes() == value for p, value in original.items())
    assert (tmp_path / 'analysis/trends/snapshots/2026-09-01.json').exists()
    assert (tmp_path / 'analysis/trends/comparisons/2026-09-01_2026-09-02.json').exists()
    assert not (tmp_path / 'analysis/audit').exists()


def test_unknown_removal_label_is_not_silently_zero_reliable_flow():
    snap = trend_snapshot([observation('2026-09-02', [], events=[event('REMOVED', 'unseen')])])
    assert snap['removed_jobs'] == 0
    assert snap['diagnostics']['unclassified_flow_events'] == 1
    assert not snap['platforms']['tencent']['reliability']['presence_flow']['reliable']
    assert 'FLOW_CLASSIFICATION_UNAVAILABLE' in snap['platforms']['tencent']['reliability']['presence_flow']['reason_codes']


@pytest.mark.parametrize('changes', [
    {'previous_sha256': None}, {'current_sha256': None},
    {'previous_sha256': 'same-content'}, {'current_sha256': 'wrong-version'},
])
def test_invalid_update_versions_are_excluded_and_block_comparison(changes):
    snap = trend_snapshot([observation('2026-09-02', [row()], events=[event('UPDATED', **changes)])])
    assert snap['updated_jobs'] == 0
    assert not snap['platforms']['tencent']['reliability']['content_flow']['reliable']


def test_different_code_or_lifecycle_contract_is_not_comparable():
    a = trend_snapshot([observation('2026-09-01', [row()])])
    b = trend_snapshot([observation('2026-09-02', [row()])])
    b['trend_code_sha256'] = 'different'
    result = compare_trends(a, b)
    assert all(not info['comparable'] for info in result['comparability'].values())
    b['trend_code_sha256'] = a['trend_code_sha256']
    b['lifecycle_contract']['removal_confirmation_runs'] = 3
    result = compare_trends(a, b)
    assert all(not info['comparable'] for info in result['comparability'].values())
