from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from src.operations.daily_ops import DailyOperations, rebuild_daily_operations
from src.operations.presentation import build_presentation, render_status


DAY = '2026-09-16'


def _config(root: Path) -> Path:
    path = root / 'config.yaml'
    path.write_text('output_dir: data/raw\n', encoding='utf-8')
    return path


def _seed_raw(root: Path, config: Path, *, valid: bool = True) -> None:
    raw_dir = root / 'data' / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw = [{'platform': 'alpha', 'job_id': 'alpha-1'}] if valid else {'bad': True}
    manifest = {
        'config': str(config.resolve()),
        'job_count': 1,
        'complete': True,
        'platforms': [{
            'platform': 'alpha',
            'status': 'success',
            'complete': True,
            'jobs_in_scope': 1,
        }],
    }
    (raw_dir / f'{DAY}.json').write_text(json.dumps(raw), encoding='utf-8')
    (raw_dir / f'{DAY}_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')


def _seed_clean(root: Path, *, valid: bool = True) -> None:
    path = root / 'data' / 'clean' / f'{DAY}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        'platform': 'alpha',
        'job_id': 'alpha-1',
        'locations_norm': [],
        'location_level': [],
        'province_norm': [],
        'city_norm': [],
    }
    path.write_text(json.dumps([row] if valid else [{'bad': True}]), encoding='utf-8')


def _run(
    *,
    status: str = 'SUCCESS',
    crawl: str = 'SUCCESS',
    clean: str = 'SUCCESS',
    analysis: str = 'SUCCESS',
) -> dict:
    return {
        'date': DAY,
        'status': status,
        'crawl': {'status': crawl, 'retried_platforms': []},
        'clean': {'status': clean},
        'analysis': {'status': analysis},
    }


def _health(*, runner='SUCCESS', action='NO_NEW_ACTION', sources=None) -> dict:
    return {
        'date': DAY,
        'runner_status': runner,
        'technical_run_health': 'SUCCESS',
        'overall_action': action,
        'sources': sources or {
            'alpha': {
                'source_completeness': 'COMPLETE',
                'limitation_state': 'NORMAL',
                'matched_limitation_id': None,
            },
        },
    }


def _ops(root: Path) -> DailyOperations:
    return DailyOperations(
        data_dir=root / 'data',
        root=root,
        config_path=_config(root),
        trigger='test',
        generated_at=lambda: '2026-09-16T10:05:00+08:00',
    )


def _recovery_runner(root: Path, *, success: bool = True, calls: list | None = None):
    def runner(run_date, *, config_path, root, resume_from):
        if calls is not None:
            calls.append(resume_from)
        status = _run(
            status='SUCCESS' if success else 'FAILED',
            clean='SUCCESS' if success or resume_from == 'analysis' else 'FAILED',
            analysis='SUCCESS' if success else 'FAILED',
        )
        status['resume_from'] = resume_from
        path = root / 'data' / 'analysis' / 'runs' / f'{run_date}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(status), encoding='utf-8')
        return (0 if success else 1), path, status

    return runner


def test_success_no_action_is_healthy(tmp_path):
    artifact = _ops(tmp_path).publish(DAY, run=_run(), health=_health())

    assert artifact['ops_status'] == 'HEALTHY'
    assert artifact['human_action_required'] is False
    assert artifact['gpt_review_required'] is False


def test_degraded_known_limitation_is_quiet(tmp_path):
    health = _health(
        runner='DEGRADED',
        sources={
            'didi': {
                'source_completeness': 'PARTIAL',
                'limitation_state': 'KNOWN_LIMITATION',
                'matched_limitation_id': 'didi-dynamic-pagination',
            },
        },
    )
    artifact = _ops(tmp_path).publish(
        DAY,
        run=_run(status='DEGRADED', crawl='DEGRADED'),
        health=health,
    )

    assert artifact['ops_status'] == 'DEGRADED_KNOWN'
    assert artifact['human_action_required'] is False
    assert artifact['gpt_review_required'] is False
    assert not (tmp_path / 'data' / 'ops' / 'latest_incident.md').exists()


def test_new_regression_requires_action_and_gpt_without_crawl_retry(tmp_path):
    health = _health(
        runner='DEGRADED',
        action='ACTION_REQUIRED',
        sources={
            'bytedance': {
                'source_completeness': 'PARTIAL',
                'limitation_state': 'NEW_REGRESSION',
                'matched_limitation_id': None,
            },
        },
    )
    artifact = _ops(tmp_path).publish(
        DAY,
        run=_run(status='DEGRADED', crawl='DEGRADED'),
        health=health,
    )

    assert artifact['ops_status'] == 'ACTION_REQUIRED'
    assert artifact['gpt_review_required'] is True
    assert artifact['automatic_recovery']['attempted'] is False


def test_clean_failure_with_valid_raw_attempts_one_resume(tmp_path):
    operations = _ops(tmp_path)
    _seed_raw(tmp_path, operations.config_path)
    calls = []

    outcome = operations.attempt_recovery(
        DAY,
        _run(status='FAILED', clean='FAILED', analysis='SKIPPED'),
        runner=_recovery_runner(tmp_path, calls=calls),
    )

    assert calls == ['clean']
    assert outcome.as_dict() == {
        'attempted': True,
        'type': 'clean',
        'result': 'SUCCESS',
        'attempt_count': 1,
    }
    assert outcome.validator_results == {'raw_manifest': 'PASS'}


def test_analysis_failure_with_valid_clean_attempts_one_resume(tmp_path):
    operations = _ops(tmp_path)
    _seed_raw(tmp_path, operations.config_path)
    _seed_clean(tmp_path)
    calls = []

    outcome = operations.attempt_recovery(
        DAY,
        _run(status='FAILED', analysis='FAILED'),
        runner=_recovery_runner(tmp_path, calls=calls),
    )

    assert calls == ['analysis']
    assert outcome.result == 'SUCCESS'
    assert outcome.validator_results == {'raw_manifest': 'PASS', 'clean': 'PASS'}


def test_failed_recovery_does_not_loop_and_escalates(tmp_path):
    operations = _ops(tmp_path)
    _seed_raw(tmp_path, operations.config_path)
    failed_run = _run(status='FAILED', clean='FAILED', analysis='SKIPPED')
    calls = []

    first = operations.attempt_recovery(
        DAY,
        failed_run,
        runner=_recovery_runner(tmp_path, success=False, calls=calls),
    )
    second = operations.attempt_recovery(
        DAY,
        failed_run,
        runner=lambda *args, **kwargs: pytest.fail('recovery looped'),
    )
    artifact = operations.publish(DAY, run=failed_run, health=None, recovery=first)

    assert calls == ['clean']
    assert first.result == second.result == 'FAILED'
    assert first.attempt_count == second.attempt_count == 1
    assert artifact['ops_status'] == 'TECHNICAL_FAILURE'
    assert artifact['human_action_required'] is True
    assert artifact['gpt_review_required'] is True


def test_canonical_resume_marker_prevents_retry_after_ops_database_rebuild(tmp_path):
    operations = _ops(tmp_path)
    _seed_raw(tmp_path, operations.config_path)
    resumed_failure = _run(status='FAILED', clean='FAILED', analysis='SKIPPED')
    resumed_failure['resume_from'] = 'clean'

    outcome = operations.attempt_recovery(
        DAY,
        resumed_failure,
        runner=lambda *args, **kwargs: pytest.fail('canonical resume was repeated'),
    )

    assert outcome.attempted is True
    assert outcome.type == 'clean'
    assert outcome.result == 'FAILED'
    assert outcome.attempt_count == 1


def test_invalid_raw_blocks_clean_recovery(tmp_path):
    operations = _ops(tmp_path)
    _seed_raw(tmp_path, operations.config_path, valid=False)

    outcome = operations.attempt_recovery(
        DAY,
        _run(status='FAILED', clean='FAILED', analysis='SKIPPED'),
        runner=lambda *args, **kwargs: pytest.fail('invalid raw reached runner'),
    )

    assert outcome.attempted is False
    assert outcome.result == 'SKIPPED_INVALID_RAW'


def test_invalid_clean_blocks_analysis_recovery(tmp_path):
    operations = _ops(tmp_path)
    _seed_raw(tmp_path, operations.config_path)
    _seed_clean(tmp_path, valid=False)

    outcome = operations.attempt_recovery(
        DAY,
        _run(status='FAILED', analysis='FAILED'),
        runner=lambda *args, **kwargs: pytest.fail('invalid clean reached runner'),
    )

    assert outcome.attempted is False
    assert outcome.result == 'SKIPPED_INVALID_CLEAN'


def test_sqlite_upserts_are_idempotent_and_schema_is_versioned(tmp_path):
    operations = _ops(tmp_path)
    _seed_raw(tmp_path, operations.config_path)
    failed_run = _run(status='FAILED', clean='FAILED', analysis='SKIPPED')
    outcome = operations.attempt_recovery(
        DAY,
        failed_run,
        runner=_recovery_runner(tmp_path),
    )
    recovered = outcome.runner_result[2]
    operations.publish(DAY, run=recovered, health=_health(), recovery=outcome)
    operations.publish(DAY, run=recovered, health=_health(), recovery=outcome)

    with sqlite3.connect(operations.db_path) as connection:
        assert connection.execute('SELECT count(*) FROM runs').fetchone()[0] == 1
        assert connection.execute('SELECT count(*) FROM actions').fetchone()[0] == 1
        assert connection.execute('SELECT count(*) FROM sources').fetchone()[0] == 1
        assert connection.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()[0] == '2'
        assert connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='notifications'"
        ).fetchone()[0] == 1


def test_human_status_is_high_level_and_latest_markdown_is_not_required(tmp_path):
    operations = _ops(tmp_path)
    artifact = operations.publish(DAY, run=_run(), health=_health())
    summary = render_status(build_presentation(artifact))

    assert f'AI Job Finder — {DAY}' in summary
    assert 'Result:\nNORMAL' in summary
    assert 'No action required.' in summary
    assert 'crawl_status' not in summary
    assert 'technical_run_health' not in summary
    assert 'matched_limitation_id' not in summary
    assert 'reason_codes' not in summary
    assert not (operations.ops_dir / 'latest.md').exists()


def test_latest_json_has_stable_v1_fields(tmp_path):
    operations = _ops(tmp_path)
    operations.publish(DAY, run=_run(), health=_health())
    artifact = json.loads((operations.ops_dir / 'latest.json').read_text())

    assert set(artifact) == {
        'schema_version', 'date', 'generated_at', 'ops_status',
        'runner_status', 'crawl_status', 'clean_status', 'analysis_status',
        'technical_run_health', 'overall_action', 'source_summary',
        'automatic_recovery', 'human_action_required', 'gpt_review_required',
        'incident_id', 'canonical_evidence_refs',
        'human_outcome',
    }
    assert set(artifact['automatic_recovery']) == {
        'attempted', 'type', 'result', 'attempt_count',
    }


def test_incident_handoff_is_on_demand_bounded_and_contains_required_evidence(tmp_path):
    operations = _ops(tmp_path)
    log_path = tmp_path / 'data' / 'logs' / 'launchd-daily.stderr.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(('irrelevant full log line\n' * 10_000) + 'ERROR compact marker\n')
    health = _health(
        runner='DEGRADED',
        action='ACTION_REQUIRED',
        sources={
            'bytedance': {
                'source_completeness': 'PARTIAL',
                'limitation_state': 'NEW_REGRESSION',
                'matched_limitation_id': None,
            },
        },
    )

    operations.publish(
        DAY,
        run=_run(status='DEGRADED', crawl='DEGRADED'),
        health=health,
    )
    handoff = operations.render_incident_gpt()

    for expected in (
        f'Date: {DAY}', 'Git HEAD:', 'Platform: bytedance',
        'Error type: SOURCE_REGRESSION', 'Retry attempts:', 'Validator results:',
        'Technical health: SUCCESS', 'Overall action: ACTION_REQUIRED',
        'Data preservation:', 'Canonical evidence refs:', '请判断根因',
    ):
        adjusted = expected.replace('Retry attempts:', 'Retry:').replace(
            'Validator results:', 'Validators:'
        )
        assert adjusted in handoff
    assert len(handoff) < 6_000
    assert handoff.count('irrelevant full log line') == 0
    assert 'ERROR compact marker' not in handoff
    assert not (operations.ops_dir / 'latest_incident.md').exists()


def test_ops_database_can_be_rebuilt_from_canonical_artifacts_without_runner(tmp_path):
    operations = _ops(tmp_path)
    run = _run()
    run['resume_from'] = 'analysis'
    run_path = tmp_path / 'data' / 'analysis' / 'runs' / f'{DAY}.json'
    health_path = tmp_path / 'data' / 'analysis' / 'health' / f'{DAY}.json'
    run_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps(run), encoding='utf-8')
    health_path.write_text(json.dumps(_health()), encoding='utf-8')
    operations.publish(DAY, run=run, health=_health())
    shutil.rmtree(operations.ops_dir)

    rebuilt = rebuild_daily_operations(
        DAY,
        data_dir=tmp_path / 'data',
        root=tmp_path,
        config_path=operations.config_path,
    )

    assert rebuilt['ops_status'] == 'HEALTHY'
    with sqlite3.connect(operations.db_path) as connection:
        assert connection.execute('SELECT count(*) FROM runs').fetchone()[0] == 1
        assert connection.execute('SELECT count(*) FROM actions').fetchone()[0] == 1
        assert connection.execute(
            'SELECT action_type, attempt_count, result FROM actions'
        ).fetchone() == ('analysis', 1, 'SUCCESS')
