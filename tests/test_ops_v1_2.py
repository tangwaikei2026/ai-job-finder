"""Daily Ops V1.2 human copy and isolated deferred-recovery acceptance."""
from __future__ import annotations

import json

from src.operations.notifications import NotificationService
from src.operations.presentation import build_presentation, render_status
from tests.test_ops_v1_1 import (
    DAY,
    TODAY,
    _health,
    _health_generator,
    _operations,
    _run,
    _runner,
    _seed_failed_run,
)


INTERNAL_TERMS = (
    'SUCCESS',
    'DEGRADED',
    'NO_NEW_ACTION',
    'technical_run_health',
    'overall_action',
    'Runner',
)


def _email(operations, run_date=DAY):
    return NotificationService(operations).render(run_date)


def test_normal_first_screen_says_complete_and_no_action(tmp_path):
    operations = _operations(tmp_path)
    operations.publish(DAY, run=_run(), health=_health())

    subject, body = _email(operations)

    assert subject == 'AI Job Finder｜今日运行完成｜无需处理'
    first_screen = body.split('\n\n', 1)[0]
    assert '已经完成' in first_screen
    assert '不需要处理' in first_screen
    assert '没有发现新的异常' in body
    assert all(term not in body for term in INTERNAL_TERMS)


def test_known_limitation_explains_impact_and_no_action(tmp_path):
    operations = _operations(tmp_path)
    operations.publish(
        DAY,
        run=_run(status='DEGRADED', crawl='DEGRADED'),
        health=_health(source_state='KNOWN_LIMITATION'),
    )

    subject, body = _email(operations)

    assert subject == 'AI Job Finder｜今日运行完成｜无需处理'
    assert '滴滴岗位数据可能不完整' in body
    assert '已经备案的问题' in body
    assert '本次没有发现新的变化' in body
    assert '你不需要处理' in body
    assert '没有执行额外的全量重跑' in body
    assert all(term not in body for term in INTERNAL_TERMS)


def test_action_required_gives_one_explicit_next_step(tmp_path):
    operations = _operations(tmp_path)
    operations.publish(
        DAY,
        run=_run(status='DEGRADED', crawl='DEGRADED'),
        health=_health(source_state='NEW_REGRESSION'),
    )

    subject, body = _email(operations)

    assert subject == 'AI Job Finder｜发现新问题｜需要查看'
    assert '发生了什么：' in body
    assert '岗位数据可能不完整' in body
    assert '系统已经自动：' in body
    assert '系统没有：\n- 自动再次执行完整岗位采集' in body
    assert '你现在需要：\n让 GPT 分析该异常。' in body
    assert 'opsctl.py incident --latest --format gpt' in body
    assert all(term not in body for term in INTERNAL_TERMS)


def test_technical_failure_names_stage_and_data_safety(tmp_path):
    operations = _operations(tmp_path)
    operations.publish(
        DAY,
        run=_run(status='FAILED', clean='FAILED', analysis='SKIPPED'),
        health=None,
    )

    subject, body = _email(operations)

    assert subject == 'AI Job Finder｜发现新问题｜需要查看'
    assert body.startswith('今天的自动任务没有完整完成。')
    assert '失败在哪一步：\n数据清洗。' in body
    assert '已有数据仍然保留' in body
    assert '没有用空结果覆盖旧数据' in body
    assert '本次没有成功完成恢复' in body
    assert '让 GPT 分析该异常' in body
    assert all(term not in body for term in INTERNAL_TERMS)


def test_auto_recovered_names_date_stage_and_no_recrawl(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='clean')
    calls: list[tuple[str, str]] = []
    operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    subject, body = _email(operations)

    assert subject == 'AI Job Finder｜今日运行完成｜无需处理'
    assert f'{DAY} 的自动任务曾在数据清洗步骤失败' in body
    assert '系统今天已从数据清洗步骤继续执行' in body
    assert '没有重新采集岗位' in body
    assert '恢复已经成功完成，你不需要处理' in body
    assert calls == [(DAY, 'clean')]
    assert all(term not in body for term in INTERNAL_TERMS)


def test_opsctl_status_uses_the_same_human_copy_as_email(tmp_path):
    operations = _operations(tmp_path)
    artifact = operations.publish(DAY, run=_run(), health=_health())

    status = render_status(build_presentation(artifact))
    _, email_body = _email(operations)

    assert email_body.rstrip() in status


def test_isolated_clean_recovery_e2e(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='clean')
    candidates = operations.deferred_recovery_candidates(TODAY)
    calls: list[tuple[str, str]] = []

    results = operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert [(item.run_date, item.recovery_type) for item in candidates] == [(DAY, 'clean')]
    assert calls == [(DAY, 'clean')]
    assert results == [{
        'date': DAY,
        'recovery_type': 'clean',
        'eligible': True,
        'reason': 'ELIGIBLE',
        'result': 'SUCCESS',
        'human_outcome': 'AUTO_RECOVERED',
    }]
    with operations._connect() as connection:
        action = connection.execute('SELECT * FROM actions').fetchone()
    assert action['attempt_count'] == 1
    assert json.loads(action['validator_results'])['raw_manifest'] == 'PASS'
    assert operations.incidents()[0]['status'] == 'AUTO_RECOVERED'


def test_isolated_analysis_recovery_e2e(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='analysis')
    candidates = operations.deferred_recovery_candidates(TODAY)
    calls: list[tuple[str, str]] = []

    results = operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert [(item.run_date, item.recovery_type) for item in candidates] == [(DAY, 'analysis')]
    assert calls == [(DAY, 'analysis')]
    assert results[0]['result'] == 'SUCCESS'
    with operations._connect() as connection:
        action = connection.execute('SELECT * FROM actions').fetchone()
    validators = json.loads(action['validator_results'])
    assert action['attempt_count'] == 1
    assert validators == {'clean': 'PASS', 'raw_manifest': 'PASS'}
    assert operations.incidents()[0]['status'] == 'AUTO_RECOVERED'


def test_isolated_invalid_raw_refuses_recovery(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='clean', valid_raw=False)
    calls: list[tuple[str, str]] = []

    candidates = operations.deferred_recovery_candidates(
        TODAY, include_ineligible=True
    )
    results = operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert candidates[0].eligible is False
    assert candidates[0].reason == 'CANONICAL_RAW_INVALID'
    assert calls == []
    assert results == []
    assert operations.incidents()[0]['status'] == 'NEEDS_HUMAN'


def test_isolated_loop_protection_blocks_second_attempt(tmp_path):
    operations = _operations(tmp_path)
    _seed_failed_run(operations, DAY, phase='clean')
    calls: list[tuple[str, str]] = []

    first = operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )
    second = operations.process_deferred_recovery(
        TODAY, runner=_runner(calls), health_generator=_health_generator
    )

    assert first[0]['result'] == 'SUCCESS'
    assert second == []
    assert calls == [(DAY, 'clean')]
    with operations._connect() as connection:
        assert connection.execute('SELECT count(*) FROM actions').fetchone()[0] == 1
