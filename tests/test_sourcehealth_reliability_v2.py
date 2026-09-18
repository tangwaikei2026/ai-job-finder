from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analysis.classification import classification_unknown, classify_record
from src.analysis.daily_health import build_daily_health
from src.analysis.lifecycle import identity
from src.analysis.pipeline import load_settings
from src.analysis.source_health import SourceHealth
from src.analysis.trends import compare_trends, trend_snapshot


DATA = Path('data')
VERSIONS = load_settings()[1]


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def _historical_observation(day: str) -> dict:
    jobs = json.loads((DATA / 'clean' / f'{day}.json').read_text(encoding='utf-8'))
    manifest = json.loads((DATA / 'raw' / f'{day}_manifest.json').read_text(encoding='utf-8'))
    classifications = _jsonl(DATA / 'analysis' / 'classification' / f'{day}.jsonl')
    events = _jsonl(DATA / 'analysis' / 'events' / f'{day}.jsonl')
    health = SourceHealth(manifest, jobs)
    classified = {identity(row) for row in classifications}
    for job in jobs:
        key = identity(job)
        if key in classified:
            continue
        resolved = health.resolve(key[0], str(job.get('company', '')), job)
        if resolved.content_reliable:
            continue
        row, _ = classify_record(day, job, resolved, VERSIONS)
        if row is not None:
            classifications.append(row)
    return {
        'date': day,
        'classifications': classifications,
        'events': events,
        'versions': dict(VERSIONS),
        'health': health,
        'present_keys': {identity(job) for job in jobs},
        'jobs_by_identity': {identity(job): job for job in jobs},
    }


def test_tencent_2026_09_17_record_unknown_keeps_siblings_and_flows_usable():
    observation = _historical_observation('2026-09-17')
    failed_key = ('tencent', '2093528517592662016')
    failed_job = observation['jobs_by_identity'][failed_key]
    failed = next(row for row in observation['classifications'] if identity(row) == failed_key)
    tencent_health = observation['health'].resolve('tencent')

    assert failed_job['title'] == '腾讯金融科技-清算机构合作对接'
    assert tencent_health.presence_reliable
    assert tencent_health.content_reliable
    assert not observation['health'].resolve('tencent', '腾讯', failed_job).content_reliable
    assert classification_unknown(failed)
    assert failed['in_scope'] is None
    assert failed['career_pool'] is None
    assert failed['skill_tags'] == []

    before = json.loads((DATA / 'analysis/trends/snapshots/2026-09-17.json').read_text())
    snapshot = trend_snapshot([observation], trend_version='trend_v2')
    tencent = snapshot['platforms']['tencent']
    assert tencent['metrics']['active_jobs'] == before['platforms']['tencent']['metrics']['active_jobs']
    assert tencent['metrics']['unknown_classification_count'] == 1
    assert tencent['metrics']['unknown_new_jobs'] == 1
    assert all(tencent['reliability'][family]['reliable']
               for family in ('inventory', 'presence_flow', 'content_flow'))
    assert all(failed['career_pool'] != pool for pool in ('P1', 'P2', 'REF', 'X'))


def test_tencent_detail_anomaly_remains_daily_action_but_data_is_usable():
    day = '2026-09-17'
    run = json.loads((DATA / 'analysis' / 'runs' / f'{day}.json').read_text())
    manifest = json.loads((DATA / 'raw' / f'{day}_manifest.json').read_text())
    jobs = json.loads((DATA / 'clean' / f'{day}.json').read_text())
    health = build_daily_health(day, run, manifest, jobs)
    tencent = health['sources']['tencent']

    assert tencent['source_health']['presence_reliable']
    assert tencent['source_health']['content_reliable']
    assert tencent['source_completeness'] == 'PARTIAL'
    assert tencent['limitation_state'] == 'NEW_REGRESSION'
    assert health['overall_action'] == 'ACTION_REQUIRED'


@pytest.mark.parametrize(('day', 'failed'), [
    ('2026-07-07', 1194),
    ('2026-09-07', 829),
])
def test_meituan_severe_detail_failure_keeps_confirmed_subset_and_unknown(day, failed):
    observation = _historical_observation(day)
    before = json.loads((DATA / f'analysis/trends/snapshots/{day}.json').read_text())
    snapshot = trend_snapshot([observation], trend_version='trend_v2')
    meituan = snapshot['platforms']['meituan']

    assert meituan['metrics']['unknown_classification_count'] == failed
    assert meituan['metrics']['active_jobs'] == before['platforms']['meituan']['metrics']['active_jobs']
    assert meituan['metrics']['by_skill_tag'] == before['platforms']['meituan']['metrics']['by_skill_tag']
    assert meituan['metrics']['active_jobs'] > 0
    assert all(meituan['reliability'][family]['reliable']
               for family in ('inventory', 'presence_flow', 'content_flow'))


def test_didi_2026_09_04_keeps_list_failure_strict_but_preserves_known_content():
    observation = _historical_observation('2026-09-04')
    snapshot = trend_snapshot([observation], trend_version='trend_v2')
    didi = snapshot['platforms']['didi']
    didi_unknown = [row for row in observation['classifications']
                    if row['platform'] == 'didi' and classification_unknown(row)]

    assert len(didi_unknown) == didi['metrics']['unknown_classification_count'] == 9
    assert all(row['career_pool'] is None and not row['skill_tags'] for row in didi_unknown)
    assert didi['metrics']['active_jobs'] > 0
    assert didi['metrics']['by_skill_tag']
    assert not didi['reliability']['inventory']['reliable']
    assert not didi['reliability']['presence_flow']['reliable']
    assert didi['reliability']['content_flow']['reliable']
    assert 'SOURCE_PRESENCE_UNRELIABLE' in didi['reliability']['inventory']['reason_codes']


def test_weekly_endpoint_comparison_keeps_unknown_platforms_and_list_guard():
    sep_1 = trend_snapshot([_historical_observation('2026-09-01')], trend_version='trend_v2')
    sep_3 = trend_snapshot([_historical_observation('2026-09-03')], trend_version='trend_v2')
    sep_4 = trend_snapshot([_historical_observation('2026-09-04')], trend_version='trend_v2')
    sep_7 = trend_snapshot([_historical_observation('2026-09-07')], trend_version='trend_v2')
    sep_16 = trend_snapshot([_historical_observation('2026-09-16')], trend_version='trend_v2')
    sep_17 = trend_snapshot([_historical_observation('2026-09-17')], trend_version='trend_v2')

    tencent_week = compare_trends(sep_16, sep_17)
    assert 'tencent' in tencent_week['comparability']['inventory']['included_platforms']
    assert 'tencent' in tencent_week['comparability']['presence_flow']['included_platforms']
    assert 'tencent' in tencent_week['comparability']['content_flow']['included_platforms']
    assert tencent_week['market']['unknown_classification_count']['to'] >= 1
    assert tencent_week['lifecycle']['UNKNOWN_NEW']['to'] >= 1

    meituan_week = compare_trends(sep_1, sep_7)
    assert 'meituan' in meituan_week['comparability']['inventory']['included_platforms']
    assert meituan_week['comparable_subset']['inventory']['to']['unknown_classification_count'] >= 829
    assert meituan_week['comparable_subset']['inventory']['to']['by_skill_tag']

    didi_week = compare_trends(sep_3, sep_4)
    assert 'didi' in didi_week['comparability']['inventory']['excluded_platforms']
    assert 'didi' in didi_week['comparability']['presence_flow']['excluded_platforms']
    assert didi_week['comparability']['content_flow']['included_platforms']


def test_normal_snapshot_remains_confirmed_with_zero_unknowns():
    snapshot = trend_snapshot([_historical_observation('2026-09-16')], trend_version='trend_v2')
    healthy = [item for item in snapshot['platforms'].values()
               if all(family['reliable'] for family in item['reliability'].values())
               and item['metrics']['unknown_classification_count'] == 0]
    assert healthy
    for item in healthy:
        assert item['metrics']['observed_inventory_count'] == item['metrics']['active_jobs']
