from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread

import pytest

from tools.run_daily_with_health import run_daily_with_health


DAY = '2026-09-14'


def runner_result(
    root: Path,
    *,
    status='SUCCESS',
    return_code=0,
    data_name='custom-data',
    calls=None,
):
    status_path = root / data_name / 'analysis' / 'runs' / f'{DAY}.json'

    def runner(run_date, *, config_path, root, resume_from):
        if calls is not None:
            calls.append({
                'date': run_date,
                'config_path': config_path,
                'root': root,
                'resume_from': resume_from,
            })
        value = {'date': run_date, 'status': status}
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(value), encoding='utf-8')
        return return_code, status_path, value

    return runner, status_path


def health_result(*, action='NO_NEW_ACTION', calls=None, fail=False):
    def generate(run_date, *, data_dir):
        path = data_dir / 'analysis' / 'health' / f'{run_date}.json'
        if calls is not None:
            calls.append({'date': run_date, 'data_dir': data_dir, 'stale_exists': path.exists()})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('partial new artifact', encoding='utf-8')
        if fail:
            raise RuntimeError('health failed')
        artifact = {'date': run_date, 'overall_action': action}
        path.write_text(json.dumps(artifact), encoding='utf-8')
        return path, artifact

    return generate


def test_success_runs_health_after_final_status_and_exits_zero(tmp_path):
    runner_calls, health_calls = [], []
    runner, status_path = runner_result(tmp_path, calls=runner_calls)

    code, summary = run_daily_with_health(
        DAY,
        root=tmp_path,
        runner=runner,
        health_generator=health_result(calls=health_calls),
    )

    assert code == 0
    assert summary['runner_status'] == 'SUCCESS'
    assert summary['overall_action'] == 'NO_NEW_ACTION'
    assert status_path.exists()
    assert health_calls == [{
        'date': DAY,
        'data_dir': status_path.parents[2],
        'stale_exists': False,
    }]


def test_degraded_runner_still_runs_health(tmp_path):
    health_calls = []
    runner, _ = runner_result(tmp_path, status='DEGRADED')

    code, summary = run_daily_with_health(
        DAY,
        root=tmp_path,
        runner=runner,
        health_generator=health_result(calls=health_calls),
    )

    assert code == 0
    assert summary['runner_status'] == 'DEGRADED'
    assert len(health_calls) == 1


@pytest.mark.parametrize(
    ('return_code', 'status'),
    [(1, 'FAILED'), (0, 'FAILED'), (1, 'SUCCESS')],
)
def test_runner_failure_or_inconsistent_result_skips_health(tmp_path, return_code, status):
    health_calls = []
    runner, _ = runner_result(tmp_path, status=status, return_code=return_code)

    code, summary = run_daily_with_health(
        DAY,
        root=tmp_path,
        runner=runner,
        health_generator=health_result(calls=health_calls),
    )

    assert code == 1
    assert summary['phase'] == 'runner'
    assert health_calls == []


def test_health_failure_preserves_runner_status_and_removes_stale_or_partial_health(tmp_path):
    runner, status_path = runner_result(tmp_path)
    runner(DAY, config_path=Path('config.yaml'), root=tmp_path, resume_from=None)
    original_status = status_path.read_bytes()
    health_path = status_path.parents[2] / 'analysis' / 'health' / f'{DAY}.json'
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text('stale', encoding='utf-8')

    code, summary = run_daily_with_health(
        DAY,
        root=tmp_path,
        runner=runner,
        health_generator=health_result(fail=True),
    )

    assert code == 1
    assert summary['phase'] == 'health'
    assert status_path.read_bytes() == original_status
    assert not health_path.exists()


def test_action_required_exits_two_without_becoming_technical_failure(tmp_path):
    runner, _ = runner_result(tmp_path)

    code, summary = run_daily_with_health(
        DAY,
        root=tmp_path,
        runner=runner,
        health_generator=health_result(action='ACTION_REQUIRED'),
    )

    assert code == 2
    assert summary['phase'] == 'complete'
    assert summary['overall_action'] == 'ACTION_REQUIRED'


def test_custom_data_root_is_derived_only_from_status_path(tmp_path):
    calls = []
    runner, status_path = runner_result(tmp_path, data_name='outside/default/data-root')

    code, _ = run_daily_with_health(
        DAY,
        root=tmp_path,
        runner=runner,
        health_generator=health_result(calls=calls),
    )

    assert code == 0
    assert calls[0]['data_dir'] == status_path.parents[2]
    assert calls[0]['data_dir'] != tmp_path / 'data'


def test_stale_health_is_removed_immediately_before_generation(tmp_path):
    calls = []
    runner, status_path = runner_result(tmp_path)
    health_path = status_path.parents[2] / 'analysis' / 'health' / f'{DAY}.json'
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text('stale', encoding='utf-8')

    code, _ = run_daily_with_health(
        DAY,
        root=tmp_path,
        runner=runner,
        health_generator=health_result(calls=calls),
    )

    assert code == 0
    assert calls[0]['stale_exists'] is False
    assert json.loads(health_path.read_text())['overall_action'] == 'NO_NEW_ACTION'


@pytest.mark.parametrize('resume_from', ['clean', 'analysis'])
def test_resume_from_is_passed_through_unchanged(tmp_path, resume_from):
    calls = []
    runner, _ = runner_result(tmp_path, calls=calls)

    code, _ = run_daily_with_health(
        DAY,
        root=tmp_path,
        resume_from=resume_from,
        runner=runner,
        health_generator=health_result(),
    )

    assert code == 0
    assert calls[0]['resume_from'] == resume_from


def test_second_concurrent_invocation_fails_fast(tmp_path):
    started = Event()
    release = Event()
    first_result = []
    second_runner_calls = []
    first_runner, _ = runner_result(tmp_path)

    def blocking_runner(*args, **kwargs):
        started.set()
        assert release.wait(timeout=5)
        return first_runner(*args, **kwargs)

    thread = Thread(
        target=lambda: first_result.append(run_daily_with_health(
            DAY,
            root=tmp_path,
            runner=blocking_runner,
            health_generator=health_result(),
        )),
    )
    thread.start()
    assert started.wait(timeout=5)
    second_runner, _ = runner_result(tmp_path, calls=second_runner_calls)

    second_code, second_summary = run_daily_with_health(
        DAY,
        root=tmp_path,
        runner=second_runner,
        health_generator=health_result(),
    )
    release.set()
    thread.join(timeout=5)

    assert second_code == 1
    assert second_summary['phase'] == 'lock'
    assert second_runner_calls == []
    assert first_result[0][0] == 0
    assert not thread.is_alive()
