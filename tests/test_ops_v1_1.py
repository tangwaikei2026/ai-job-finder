from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.operations.daily_ops import (
    MAX_HISTORICAL_RECOVERY_DATES,
    DailyOperations,
)
from src.operations.notifications import (
    MAX_DELIVERY_ATTEMPTS,
    NotificationService,
)
from src.operations.presentation import build_presentation, render_status
from tools import opsctl


DAY = '2026-09-15'
TODAY = '2026-09-16'


def _config(root: Path) -> Path:
    path = root / 'config.yaml'
    path.write_text('output_dir: data/raw\n', encoding='utf-8')
    return path


def _operations(root: Path) -> DailyOperations:
    return DailyOperations(
        data_dir=root / 'data',
        root=root,
        config_path=_config(root),
        trigger='test',
        generated_at=lambda: '2026-09-16T11:00:00+08:00',
    )


def _run(
    run_date: str = DAY,
    *,
    status: str = 'SUCCESS',
    crawl: str = 'SUCCESS',
    clean: str = 'SUCCESS',
    analysis: str = 'SUCCESS',
) -> dict:
    return {
        'date': run_date,
        'status': status,
        'crawl': {'status': crawl, 'retried_platforms': []},
        'clean': {'status': clean},
        'analysis': {'status': analysis},
    }


def _health(run_date: str = DAY, *, source_state: str = 'NORMAL') -> dict:
    action = 'ACTION_REQUIRED' if source_state == 'NEW_REGRESSION' else 'NO_NEW_ACTION'
    completeness = 'PARTIAL' if source_state != 'NORMAL' else 'COMPLETE'
    return {
        'date': run_date,
        'technical_run_health': 'SUCCESS',
        'overall_action': action,
        'sources': {
            'didi' if source_state == 'KNOWN_LIMITATION' else 'bytedance': {
                'source_completeness': completeness,
                'limitation_state': source_state,
                'matched_limitation_id': (
                    'didi-dynamic-pagination'
                    if source_state == 'KNOWN_LIMITATION' else None
                ),
            },
        },
    }


def _seed_raw(root: Path, config: Path, run_date: str, *, valid: bool = True) -> None:
    raw_dir = root / 'data' / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = [{'platform': 'alpha', 'job_id': 'alpha-1'}] if valid else {'bad': True}
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
    (raw_dir / f'{run_date}.json').write_text(json.dumps(rows), encoding='utf-8')
    (raw_dir / f'{run_date}_manifest.json').write_text(
        json.dumps(manifest), encoding='utf-8'
    )


def _seed_clean(root: Path, run_date: str, *, valid: bool = True) -> None:
    path = root / 'data' / 'clean' / f'{run_date}.json'
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


def _seed_failed_run(
    operations: DailyOperations,
    run_date: str,
    *,
    phase: str,
    valid_raw: bool = True,
) -> dict:
    if phase == 'clean':
        run = _run(run_date, status='FAILED', clean='FAILED', analysis='SKIPPED')
    elif phase == 'analysis':
        run = _run(run_date, status='FAILED', analysis='FAILED')
    else:
        run = _run(
            run_date, status='FAILED', crawl='FAILED', clean='SKIPPED',
            analysis='SKIPPED'
        )
    if phase != 'crawl':
        _seed_raw(operations.root, operations.config_path, run_date, valid=valid_raw)
    if phase == 'analysis':
        _seed_clean(operations.root, run_date)
    path = operations.data_dir / 'analysis' / 'runs' / f'{run_date}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run), encoding='utf-8')
    operations.publish(run_date, run=run, health=None)
    return run


def _runner(calls: list[tuple[str, str]]):
    def run(run_date, *, config_path, root, resume_from):
        calls.append((run_date, resume_from))
        recovered = _run(run_date)
        recovered['resume_from'] = resume_from
        path = root / 'data' / 'analysis' / 'runs' / f'{run_date}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(recovered), encoding='utf-8')
        return 0, path, recovered

    return run


def _health_generator(run_date, *, data_dir):
    value = _health(run_date)
    path = data_dir / 'analysis' / 'health' / f'{run_date}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return path, value


class _Adapter:
    configured = True

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[str, str]] = []

    def send(self, subject: str, body: str) -> None:
        self.sent.append((subject, body))
        if self.fail:
            raise RuntimeError('smtp unavailable')


def test_known_limitation_has_one_human_meaning_and_no_action(tmp_path):
    operations = _operations(tmp_path)
    artifact = operations.publish(
        DAY,
        run=_run(status='DEGRADED', crawl='DEGRADED'),
        health=_health(source_state='KNOWN_LIMITATION'),
    )

    output = render_status(build_presentation(artifact))
    assert '今天的岗位采集和分析已经完成，你不需要处理。' in output
    assert '滴滴岗位数据可能不完整' in output
    assert '这是已经备案的问题，本次没有发现新的变化。' in output
    assert 'DEGRADED' not in output


def test_new_regression_email_is_semantic_and_requires_action(tmp_path):
    operations = _operations(tmp_path)
    operations.publish(
        DAY,
        run=_run(status='DEGRADED', crawl='DEGRADED'),
        health=_health(source_state='NEW_REGRESSION'),
    )

    subject, body = NotificationService(operations).render(DAY)
    assert subject == 'AI Job Finder｜发现新问题｜需要查看'
    assert '字节跳动出现新的数据完整性异常' in body
    assert '系统没有：\n- 自动再次执行完整岗位采集' in body
    assert '让 GPT 分析该异常' in body
    assert 'technical_run_health' not in body


def test_email_delivery_is_idempotent(tmp_path):
    operations = _operations(tmp_path)
    operations.publish(DAY, run=_run(), health=_health())
    adapter = _Adapter()
    service = NotificationService(operations, adapter=adapter)

    assert service.queue(DAY) is True
    assert service.queue(DAY) is False
    assert service.send_pending()[0]['delivery_status'] == 'DELIVERED'
    assert service.send_pending() == []
    assert len(adapter.sent) == 1
    assert service.state(DAY, 'DAILY_STATUS')['attempt_count'] == 1


def test_email_failure_does_not_change_health_and_retry_is_bounded(tmp_path):
    operations = _operations(tmp_path)
    operations.publish(DAY, run=_run(), health=_health())
    service = NotificationService(operations, adapter=_Adapter(fail=True))
    service.queue(DAY)

    for _ in range(MAX_DELIVERY_ATTEMPTS + 2):
        service.send_pending()

    assert service.state(DAY, 'DAILY_STATUS')['attempt_count'] == MAX_DELIVERY_ATTEMPTS
    assert service.state(DAY, 'DAILY_STATUS')['delivery_status'] == 'FAILED'
    assert operations.machine_status(DAY)['technical_run_health'] == 'SUCCESS'


def test_deferred_clean_recovery_revalidates_and_closes_incident(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='clean')
    operations.publish(TODAY, run=_run(TODAY), health=_health(TODAY))
    calls: list[tuple[str, str]] = []

    results = operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert calls == [(DAY, 'clean')]
    assert results[0]['result'] == 'SUCCESS'
    assert operations.incidents()[0]['status'] == 'AUTO_RECOVERED'
    assert operations.machine_status(DAY)['human_outcome'] == 'AUTO_RECOVERED'
    latest = json.loads((operations.ops_dir / 'latest.json').read_text())
    assert latest['date'] == TODAY


def test_deferred_analysis_recovery_uses_analysis_resume_only(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='analysis')
    calls: list[tuple[str, str]] = []

    operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert calls == [(DAY, 'analysis')]


def test_deferred_health_failure_does_not_close_incident(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='clean')

    def failed_health(run_date, *, data_dir):
        raise RuntimeError('health unavailable')

    results = operations.process_deferred_recovery(
        TODAY, runner=_runner([]), health_generator=failed_health
    )

    assert results[0]['result'] == 'HEALTH_FAILED'
    assert operations.incidents()[0]['status'] == 'OPEN'
    assert operations.machine_status(DAY)['human_outcome'] == 'TECHNICAL_FAILURE'


def test_historical_crawl_failure_is_never_recovered(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='crawl')
    calls: list[tuple[str, str]] = []

    results = operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert results == []
    assert calls == []
    assert operations.incidents()[0]['status'] == 'NEEDS_HUMAN'


def test_invalid_old_raw_fails_canonical_recheck_and_stays_human(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='clean', valid_raw=False)
    candidate = operations.deferred_recovery_candidates(
        TODAY, include_ineligible=True
    )[0]

    assert candidate.eligible is False
    assert candidate.reason == 'CANONICAL_RAW_INVALID'


def test_duplicate_backlog_processing_is_prevented(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='clean')
    calls: list[tuple[str, str]] = []

    operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )
    operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert calls == [(DAY, 'clean')]


def test_backlog_has_a_fixed_small_per_run_bound(tmp_path):
    operations = _operations(tmp_path)
    for run_date in ('2026-09-12', '2026-09-13', '2026-09-14'):
        _seed_failed_run(operations, run_date, phase='clean')
    calls: list[tuple[str, str]] = []

    operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert MAX_HISTORICAL_RECOVERY_DATES == 2
    assert len(calls) == 2


def test_opsctl_status_history_incidents_recover_and_handoff(tmp_path, capsys):
    operations = _operations(tmp_path)
    operations.publish(DAY, run=_run(), health=_health())
    _seed_failed_run(operations, '2026-09-14', phase='clean')
    base = ['--root', str(tmp_path)]

    assert opsctl.main([*base, 'status', '--date', DAY]) == 0
    assert '今天的岗位采集和分析已经完成，你不需要处理。' in capsys.readouterr().out
    assert opsctl.main([*base, 'history', '--days', '7']) == 0
    assert 'DATE        RESULT' in capsys.readouterr().out
    assert opsctl.main([*base, 'incidents', '--open']) == 0
    assert 'INC-2026-09-14' in capsys.readouterr().out
    assert opsctl.main([
        *base, 'recover', '--dry-run', '--as-of', TODAY
    ]) == 0
    assert '2026-09-14  clean' in capsys.readouterr().out
    assert opsctl.main([*base, 'incident', '--latest', '--format', 'gpt']) == 0
    assert 'Canonical evidence refs:' in capsys.readouterr().out


def test_opsctl_notification_dry_run_needs_no_credentials(tmp_path, capsys):
    operations = _operations(tmp_path)
    operations.publish(DAY, run=_run(), health=_health())

    assert opsctl.main([
        '--root', str(tmp_path), 'notify', '--date', DAY, '--dry-run'
    ]) == 0
    output = capsys.readouterr().out
    assert 'Subject: AI Job Finder｜今日运行完成｜无需处理' in output
    assert '今天的岗位采集和分析已经完成，你不需要处理。' in output


def test_opsctl_loads_private_email_config_before_constructing_adapter(
    tmp_path, monkeypatch
):
    operations = _operations(tmp_path)
    config_dir = tmp_path / 'private-email'
    config_dir.mkdir(mode=0o700)
    config = config_dir / 'email.json'
    config.write_text(json.dumps({
        'AI_JOB_FINDER_EMAIL_HOST': 'smtp.example.com',
        'AI_JOB_FINDER_EMAIL_PORT': '465',
        'AI_JOB_FINDER_EMAIL_FROM': 'sender@example.com',
        'AI_JOB_FINDER_EMAIL_TO': 'recipient@example.com',
        'AI_JOB_FINDER_EMAIL_USERNAME': 'sender@example.com',
        'AI_JOB_FINDER_EMAIL_PASSWORD': 'private-test-value',
        'AI_JOB_FINDER_EMAIL_SECURITY': 'ssl',
    }), encoding='utf-8')
    config.chmod(0o600)
    for key in (
        'AI_JOB_FINDER_EMAIL_HOST',
        'AI_JOB_FINDER_EMAIL_PORT',
        'AI_JOB_FINDER_EMAIL_FROM',
        'AI_JOB_FINDER_EMAIL_TO',
        'AI_JOB_FINDER_EMAIL_USERNAME',
        'AI_JOB_FINDER_EMAIL_PASSWORD',
        'AI_JOB_FINDER_EMAIL_SECURITY',
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(opsctl, 'EMAIL_CONFIG_PATH', config)

    service, error = opsctl._notification_service_with_config(operations)

    assert service.adapter.configured is True
    assert error is None


def test_opsctl_reports_non_secret_email_field_validation_error(
    tmp_path, monkeypatch
):
    operations = _operations(tmp_path)
    config_dir = tmp_path / 'private-email'
    config_dir.mkdir(mode=0o700)
    config = config_dir / 'email.json'
    config.write_text(json.dumps({
        'AI_JOB_FINDER_EMAIL_HOST': 'smtp.example.com',
        'AI_JOB_FINDER_EMAIL_FROM': 'sender@example.com',
        'AI_JOB_FINDER_EMAIL_TO': 'recipient@example.com',
        'AI_JOB_FINDER_EMAIL_SECURITY': 'invalid-private-value',
    }), encoding='utf-8')
    config.chmod(0o600)
    for key in (
        'AI_JOB_FINDER_EMAIL_HOST',
        'AI_JOB_FINDER_EMAIL_PORT',
        'AI_JOB_FINDER_EMAIL_FROM',
        'AI_JOB_FINDER_EMAIL_TO',
        'AI_JOB_FINDER_EMAIL_USERNAME',
        'AI_JOB_FINDER_EMAIL_PASSWORD',
        'AI_JOB_FINDER_EMAIL_SECURITY',
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(opsctl, 'EMAIL_CONFIG_PATH', config)

    service, error = opsctl._notification_service_with_config(operations)

    assert service.adapter.configured is False
    assert error == (
        'AI_JOB_FINDER_EMAIL_SECURITY must be starttls, ssl, or none'
    )
    assert 'invalid-private-value' not in error


def test_v1_sqlite_is_migrated_without_losing_history(tmp_path):
    operations = _operations(tmp_path)
    operations.ops_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(operations.db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY, run_date TEXT NOT NULL UNIQUE,
                generated_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                git_head TEXT, trigger TEXT NOT NULL, ops_status TEXT NOT NULL,
                runner_status TEXT NOT NULL, crawl_status TEXT NOT NULL,
                clean_status TEXT NOT NULL, analysis_status TEXT NOT NULL,
                technical_run_health TEXT NOT NULL, overall_action TEXT NOT NULL,
                human_action_required INTEGER NOT NULL,
                gpt_review_required INTEGER NOT NULL, incident_id TEXT,
                error_type TEXT, error_summary TEXT
            );
            INSERT INTO runs VALUES (
                '2026-09-14', '2026-09-14', 't', 't', NULL, 'test',
                'HEALTHY', 'SUCCESS', 'SUCCESS', 'SUCCESS', 'SUCCESS',
                'SUCCESS', 'NO_NEW_ACTION', 0, 0, NULL, NULL, NULL
            );
            """
        )

    with operations._connect() as connection:
        row = connection.execute(
            "SELECT human_outcome FROM runs WHERE run_id='2026-09-14'"
        ).fetchone()
        version = connection.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()[0]

    assert row['human_outcome'] == 'NORMAL'
    assert version == '2'
