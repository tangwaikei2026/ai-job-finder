from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import src.analysis.daily_health as daily_health
from src.analysis.daily_health import (
    DailyHealthError,
    build_daily_health,
    derive_source_completeness,
    derive_technical_run_health,
    generate_daily_health,
)
from src.analysis.known_limitations import DEFAULT_REGISTRY


DAY = '2026-09-14'
LIMITATION_ID = 'didi_dynamic_offset_pagination_v1'
REFERENCE = '964eeb8d3b482a3c9921c04ab77d75e3dc829943'


def job(job_id='1', platform='didi', company='滴滴'):
    return {
        'job_id': job_id,
        'platform': platform,
        'company': company,
        'title': '大模型测试工程师',
        'description': '负责大模型测试与评测。',
        'requirements': '熟悉 Python。',
    }


def source(platform='aliyun', **changes):
    row = {
        'platform': platform,
        'status': 'success',
        'complete': True,
        'source_total': 1,
        'expected_pages': 1,
        'pages_fetched': 1,
        'records_fetched': 1,
        'jobs_mapped': 1,
        'jobs_in_scope': 1,
        'detail_failed': 0,
        'detail_failed_job_ids': [],
        'failed_companies': [],
        'stopped_by': 'all_partitions_complete',
        'error': '',
        'metadata': {},
    }
    row.update(changes)
    return row


def didi_partial(**changes):
    row = source(
        'didi',
        status='partial',
        complete=False,
        source_total=3,
        records_fetched=2,
        jobs_mapped=1,
        jobs_in_scope=1,
        duplicate_records=1,
        stopped_by='dynamic_total',
        metadata={
            'pagination_mode': 'offset_dynamic',
            'stable_snapshot_mechanism': False,
            'list_complete': False,
            'list_error': False,
            'completeness_reasons': [
                'dynamic_total',
                'duplicate_pagination',
                'unique_deficit',
            ],
        },
    )
    row.update(changes)
    return row


def run_status(
    *, status='SUCCESS', crawl='SUCCESS', clean='SUCCESS', analysis='SUCCESS', day=DAY,
):
    return {
        'date': day,
        'status': status,
        'crawl': {'status': crawl},
        'clean': {'status': clean},
        'analysis': {'status': analysis},
    }


def manifest(rows, jobs, *, day=DAY, **changes):
    value = {
        'date': day,
        'generated_at': f'{day}T12:00:00+08:00',
        'complete': all(row['complete'] for row in rows),
        'job_count': len(jobs),
        'cities': ['北京'],
        'platforms': rows,
    }
    value.update(changes)
    return value


def build(rows, jobs, *, run=None, day=DAY, registry_path=DEFAULT_REGISTRY):
    return build_daily_health(
        day,
        run or run_status(day=day),
        manifest(rows, jobs, day=day),
        jobs,
        registry_path=registry_path,
    )


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (run_status(), 'SUCCESS'),
        (run_status(status='DEGRADED', crawl='DEGRADED'), 'SUCCESS'),
        (run_status(status='FAILED', crawl='FAILED'), 'FAILED'),
        (run_status(status='DEGRADED', crawl='DEGRADED', clean='FAILED'), 'FAILED'),
        (run_status(status='DEGRADED', crawl='DEGRADED', analysis='FAILED'), 'FAILED'),
    ],
)
def test_technical_run_health(value, expected):
    assert derive_technical_run_health(value) == expected


@pytest.mark.parametrize(
    ('status', 'complete', 'expected'),
    [
        ('success', True, 'COMPLETE'),
        ('partial', False, 'PARTIAL'),
        ('error', False, 'UNKNOWN'),
    ],
)
def test_source_completeness_mapping(status, complete, expected):
    assert derive_source_completeness({'status': status, 'complete': complete}) == expected


@pytest.mark.parametrize(
    ('status', 'complete'),
    [('success', False), ('partial', True), ('error', True), ('future', False)],
)
def test_illegal_source_completeness_fails_closed(status, complete):
    with pytest.raises(DailyHealthError):
        derive_source_completeness({'status': status, 'complete': complete})


def test_didi_strict_match_is_registry_driven_and_preserves_partial():
    result = build([didi_partial()], [job()])
    didi = result['sources']['didi']

    assert didi['source_completeness'] == 'PARTIAL'
    assert didi['limitation_state'] == 'KNOWN_LIMITATION'
    assert didi['matched_limitation_id'] == LIMITATION_ID
    assert didi['matched_limitation'] == {
        'category': 'SOURCE_DYNAMIC_PAGINATION_LIMITATION',
        'review_after': '2026-12-13',
        'review_cadence_days': 90,
        'reference': {'type': 'git_commit', 'value': REFERENCE},
    }
    assert result['registry_version'] == 1
    assert result['overall_action'] == 'NO_NEW_ACTION'


def _negative_didi_case(case):
    row = didi_partial()
    if case == 'request_error':
        row.update(error='request failed', stopped_by='request_error')
        row['metadata']['completeness_reasons'] = ['request_error']
    elif case == 'incomplete_list':
        row['metadata']['completeness_reasons'] = ['incomplete_list']
    elif case == 'detail_errors':
        row['metadata']['completeness_reasons'] = ['detail_errors']
    elif case == 'unknown_reason':
        row['metadata']['completeness_reasons'] = ['future_unknown_reason']
    elif case == 'unknown_stopped_by':
        row['stopped_by'] = 'future_unknown_stop'
    elif case == 'missing_error_field':
        row.pop('error')
    elif case == 'stopped_by_not_in_reasons':
        row['metadata']['completeness_reasons'] = [
            'duplicate_pagination',
            'unique_deficit',
        ]
    elif case == 'unexplained_record_deficit':
        row['metadata']['completeness_reasons'] = [
            'dynamic_total',
            'duplicate_pagination',
        ]
    elif case == 'unexplained_page_deficit':
        row.update(expected_pages=2, pages_fetched=1)
    elif case == 'status_error':
        row.update(status='error', error='offline', stopped_by='request_error')
    elif case == 'list_error':
        row['metadata']['list_error'] = True
    elif case == 'detail_failed':
        row['detail_failed'] = 1
    elif case == 'detail_failed_job_ids':
        row['detail_failed_job_ids'] = ['1']
    elif case == 'empty_reasons':
        row['metadata']['completeness_reasons'] = []
    elif case == 'wrong_pagination_mode':
        row['metadata']['pagination_mode'] = 'cursor'
    elif case == 'stable_snapshot':
        row['metadata']['stable_snapshot_mechanism'] = True
    else:  # pragma: no cover - protects the test table itself
        raise AssertionError(case)
    return row


@pytest.mark.parametrize(
    'case',
    [
        'request_error',
        'incomplete_list',
        'detail_errors',
        'unknown_reason',
        'unknown_stopped_by',
        'missing_error_field',
        'stopped_by_not_in_reasons',
        'unexplained_record_deficit',
        'unexplained_page_deficit',
        'status_error',
        'list_error',
        'detail_failed',
        'detail_failed_job_ids',
        'empty_reasons',
        'wrong_pagination_mode',
        'stable_snapshot',
    ],
)
def test_didi_matcher_fails_closed(case):
    result = build([_negative_didi_case(case)], [job()])
    didi = result['sources']['didi']

    assert didi['limitation_state'] == 'NEW_REGRESSION'
    assert didi['matched_limitation_id'] is None
    assert result['overall_action'] == 'ACTION_REQUIRED'


def test_normal_source_and_action():
    result = build([source()], [job(platform='aliyun', company='阿里云')])
    aliyun = result['sources']['aliyun']

    assert aliyun['source_completeness'] == 'COMPLETE'
    assert aliyun['source_health']['presence_reliable'] is True
    assert aliyun['source_health']['content_reliable'] is True
    assert aliyun['source_health']['reason_codes'] == []
    assert aliyun['limitation_state'] == 'NORMAL'
    assert result['overall_action'] == 'NO_NEW_ACTION'


def test_technical_failure_requires_action_even_when_source_is_normal():
    failed_run = run_status(status='FAILED', crawl='FAILED', clean='SKIPPED', analysis='SKIPPED')
    result = build(
        [source()],
        [job(platform='aliyun', company='阿里云')],
        run=failed_run,
    )

    assert result['technical_run_health'] == 'FAILED'
    assert result['sources']['aliyun']['limitation_state'] == 'NORMAL'
    assert result['overall_action'] == 'ACTION_REQUIRED'


def test_feishu_company_observation_grain_is_preserved():
    jobs = [job(platform='feishu', company='商汤科技')]
    row = source(
        'feishu',
        attempted_companies=['商汤科技'],
        stopped_by='all_companies_complete',
    )
    result = build([row], jobs)
    feishu = result['sources']['feishu']

    assert feishu['source_health']['scopes'] == [{
        'company': '商汤科技',
        'presence_reliable': True,
        'content_reliable': True,
        'reason_codes': [],
    }]
    assert feishu['limitation_state'] == 'NORMAL'


@pytest.mark.parametrize(
    'invalid_run',
    [
        {'date': DAY, 'crawl': {'status': 'SUCCESS'}, 'clean': {'status': 'SUCCESS'},
         'analysis': {'status': 'SUCCESS'}},
        run_status(status='FUTURE'),
        {'date': DAY, 'status': 'SUCCESS', 'clean': {'status': 'SUCCESS'},
         'analysis': {'status': 'SUCCESS'}},
    ],
)
def test_invalid_daily_run_fails_closed(invalid_run):
    with pytest.raises(DailyHealthError):
        build([source()], [job(platform='aliyun')], run=invalid_run)


def test_manifest_date_identity_and_shape_fail_closed():
    jobs = [job(platform='aliyun')]
    row = source()
    cases = [
        {},
        manifest([row], jobs, day='2026-09-13'),
        manifest([row, deepcopy(row)], jobs),
        manifest([dict(row, status='success', complete=False)], jobs, complete=False),
    ]
    for value in cases:
        with pytest.raises(DailyHealthError):
            build_daily_health(DAY, run_status(), value, jobs)


def test_source_health_evaluation_failure_is_wrapped(monkeypatch):
    class BrokenSourceHealth:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError('broken owner')

    monkeypatch.setattr(daily_health, 'SourceHealth', BrokenSourceHealth)
    with pytest.raises(DailyHealthError, match='SOURCE_HEALTH_EVALUATION_FAILED'):
        build([source()], [job(platform='aliyun')])


def test_unknown_source_health_reason_cannot_match_known_limitation(monkeypatch):
    class FutureSourceHealth:
        def __init__(self, *_args, **_kwargs):
            pass

        def scopes(self):
            return {('didi', '')}

        def resolve(self, *_args, **_kwargs):
            return SimpleNamespace(
                presence_reliable=False,
                content_reliable=True,
                reason_codes=('FUTURE_SOURCE_HEALTH_REASON',),
            )

    monkeypatch.setattr(daily_health, 'SourceHealth', FutureSourceHealth)
    result = build([didi_partial()], [job()])

    assert result['sources']['didi']['limitation_state'] == 'NEW_REGRESSION'
    assert result['sources']['didi']['matched_limitation_id'] is None
    assert result['overall_action'] == 'ACTION_REQUIRED'


def _write_registry(path: Path, registry):
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding='utf-8')


def test_invalid_registry_fails_closed_through_daily_health(tmp_path):
    path = tmp_path / 'registry.yaml'
    path.write_text('version: 1\nlimitations: []\n', encoding='utf-8')

    with pytest.raises(DailyHealthError, match='INVALID_KNOWN_LIMITATION_REGISTRY'):
        build([source()], [job(platform='aliyun')], registry_path=path)


def test_duplicate_structural_limitation_match_fails_closed(tmp_path):
    registry = yaml.safe_load(DEFAULT_REGISTRY.read_text(encoding='utf-8'))
    duplicate = deepcopy(registry['limitations'][0])
    duplicate['id'] = 'didi_dynamic_offset_pagination_second_v1'
    registry['limitations'].append(duplicate)
    path = tmp_path / 'registry.yaml'
    _write_registry(path, registry)

    with pytest.raises(DailyHealthError, match='DUPLICATE_LIMITATION_MATCH'):
        build([didi_partial()], [job()], registry_path=path)


def test_unknown_limitation_category_fails_closed(tmp_path):
    registry = yaml.safe_load(DEFAULT_REGISTRY.read_text(encoding='utf-8'))
    registry['limitations'][0]['category'] = 'FUTURE_CATEGORY'
    path = tmp_path / 'registry.yaml'
    _write_registry(path, registry)

    with pytest.raises(DailyHealthError, match='INVALID_KNOWN_LIMITATION_REGISTRY'):
        build([didi_partial()], [job()], registry_path=path)


@pytest.mark.parametrize(
    ('day', 'state', 'action', 'governance_reasons'),
    [
        ('2026-12-12', 'KNOWN_LIMITATION', 'NO_NEW_ACTION', []),
        ('2026-12-13', 'NEW_REGRESSION', 'ACTION_REQUIRED', ['KNOWN_LIMITATION_REVIEW_DUE']),
        ('2026-12-14', 'NEW_REGRESSION', 'ACTION_REQUIRED', ['KNOWN_LIMITATION_REVIEW_DUE']),
    ],
)
def test_review_boundary(day, state, action, governance_reasons):
    result = build([didi_partial()], [job()], day=day)
    didi = result['sources']['didi']

    assert didi['limitation_state'] == state
    assert didi['matched_limitation_id'] == LIMITATION_ID
    assert didi['matched_limitation']['review_after'] == '2026-12-13'
    assert didi['governance_reasons'] == governance_reasons
    assert result['overall_action'] == action


def test_semantic_output_is_deterministic():
    rows = [source(), didi_partial()]
    jobs = [job(platform='aliyun', company='阿里云'), job()]

    assert build(rows, jobs) == build(deepcopy(rows), deepcopy(jobs))


def test_generator_reads_canonical_inputs_and_writes_only_health_artifact(tmp_path):
    data_dir = tmp_path / 'data'
    rows = [source()]
    jobs = [job(platform='aliyun')]
    paths = {
        data_dir / 'analysis' / 'runs' / f'{DAY}.json': run_status(),
        data_dir / 'raw' / f'{DAY}_manifest.json': manifest(rows, jobs),
        data_dir / 'clean' / f'{DAY}.json': jobs,
    }
    for path, value in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    output, artifact = generate_daily_health(
        DAY,
        data_dir=data_dir,
        generated_at='2026-09-15T12:00:00+08:00',
    )

    assert output == data_dir / 'analysis' / 'health' / f'{DAY}.json'
    assert json.loads(output.read_text(encoding='utf-8')) == artifact
    assert artifact['generated_at'] == '2026-09-15T12:00:00+08:00'


@pytest.mark.parametrize('missing', ['run', 'manifest', 'clean'])
def test_generator_missing_required_input_fails_closed_without_output(tmp_path, missing):
    data_dir = tmp_path / 'data'
    rows = [source()]
    jobs = [job(platform='aliyun')]
    paths = {
        'run': (data_dir / 'analysis' / 'runs' / f'{DAY}.json', run_status()),
        'manifest': (data_dir / 'raw' / f'{DAY}_manifest.json', manifest(rows, jobs)),
        'clean': (data_dir / 'clean' / f'{DAY}.json', jobs),
    }
    for key, (path, value) in paths.items():
        if key == missing:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    with pytest.raises(DailyHealthError):
        generate_daily_health(DAY, data_dir=data_dir)
    assert not (data_dir / 'analysis' / 'health' / f'{DAY}.json').exists()
