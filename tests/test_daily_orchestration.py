from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread

import pytest
import yaml

from tools.run_daily_with_health import run_daily_with_health
from tests.test_invocation import execution  # noqa: F401


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


def test_clean_failure_is_recovered_once_then_ops_runs_after_health(tmp_path):
    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump({'output_dir': 'data/raw'}))
    raw_dir = tmp_path / 'data' / 'raw'
    raw_dir.mkdir(parents=True)
    raw = [{'platform': 'alpha', 'job_id': 'alpha-1'}]
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
    (raw_dir / f'{DAY}.json').write_text(json.dumps(raw))
    (raw_dir / f'{DAY}_manifest.json').write_text(json.dumps(manifest))
    calls = []

    def recovering_runner(run_date, *, config_path, root, resume_from):
        calls.append(resume_from)
        success = resume_from == 'clean'
        status = {
            'date': run_date,
            'status': 'SUCCESS' if success else 'FAILED',
            'crawl': {'status': 'SUCCESS', 'retried_platforms': []},
            'clean': {'status': 'SUCCESS' if success else 'FAILED'},
            'analysis': {'status': 'SUCCESS' if success else 'SKIPPED'},
        }
        if resume_from:
            status['resume_from'] = resume_from
        path = tmp_path / 'data' / 'analysis' / 'runs' / f'{run_date}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(status))
        return (0 if success else 1), path, status

    def complete_health(run_date, *, data_dir):
        artifact = {
            'date': run_date,
            'runner_status': 'SUCCESS',
            'technical_run_health': 'SUCCESS',
            'overall_action': 'NO_NEW_ACTION',
            'sources': {
                'alpha': {
                    'source_completeness': 'COMPLETE',
                    'limitation_state': 'NORMAL',
                    'matched_limitation_id': None,
                },
            },
        }
        path = data_dir / 'analysis' / 'health' / f'{run_date}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact))
        return path, artifact

    code, summary = run_daily_with_health(
        DAY,
        root=tmp_path,
        config_path=config,
        runner=recovering_runner,
        health_generator=complete_health,
    )

    latest = json.loads((tmp_path / 'data' / 'ops' / 'latest.json').read_text())
    assert code == 0
    assert calls == [None, 'clean']
    assert summary['phase'] == 'complete'
    assert summary['ops_status'] == 'HEALTHY'
    assert latest['automatic_recovery'] == {
        'attempted': True,
        'type': 'clean',
        'result': 'SUCCESS',
        'attempt_count': 1,
    }


# Exercise the existing Runner and stage entrypoints over temporary offline data.


@pytest.mark.parametrize('phase', ['clean', 'analysis'])
@pytest.mark.parametrize('previous_published', [False, True])
def test_offline_staged_failure_recovers_once_without_recrawl(
    execution, monkeypatch, phase, previous_published, record_property,
):
    """A transient downstream failure with valid staging can resume once.

    The existing contract preserves invocation identity and skips Crawl. The
    outcome assertions alone do not prove which files the Ops precheck read;
    prior published data is a separate control, not staging provenance evidence.
    """
    import tools.run_daily as daily
    import src.operations.daily_ops as ops_module
    from src.invocation import read, validate_raw, validate_clean, validate_analysis
    from src.operations.daily_ops import DailyOperations
    from src.operations.notifications import NotificationService
    from tests.test_invocation import DAY as day

    e = execution
    data = e['root'] / 'data'
    # Record the actual Ops precheck inputs without substituting validators.
    # Successful recovery with old output alone cannot establish that this
    # precheck read the failed invocation's staging rather than the old output.
    precheck_inputs = []
    validate_observation = ops_module._validate_existing_observation
    validate_clean_artifact = ops_module._validate_clean_artifact

    def observed_raw(raw_path, manifest_path, config_path):
        precheck_inputs.append(dict(stage='raw', path=str(raw_path),
                                    manifest_path=str(manifest_path)))
        return validate_observation(raw_path, manifest_path, config_path)

    def observed_clean(clean_path, manifest, raw_rows):
        precheck_inputs.append(dict(stage='clean', path=str(clean_path),
                                    invocation=manifest.get('invocation')))
        return validate_clean_artifact(clean_path, manifest, raw_rows)

    monkeypatch.setattr(ops_module, '_validate_existing_observation', observed_raw)
    monkeypatch.setattr(ops_module, '_validate_clean_artifact', observed_clean)
    published_before = {}
    if previous_published:
        code, _, prior = e['run']()
        assert code == 0
        published_before = {
            p: p.read_bytes()
            for folder in ('raw', 'clean', 'analysis/classification',
                           'analysis/events', 'analysis/trends/snapshots', 'analysis/audit')
            for p in (data / folder).glob('*') if p.is_file()
        }

    # Inject a transient stage launch failure once; all successful stages call
    # the existing real entrypoints with only the collector boundary mocked.
    stage_calls, invocations, resume_calls = [], [], []
    failed_once = False
    failing_module = 'src.clean.cli' if phase == 'clean' else 'src.analysis.pipeline'

    def command_runner(command, root):
        nonlocal failed_once
        stage_calls.append(list(command))
        if command[2] == failing_module and not failed_once:
            failed_once = True
            return 1
        return e['runner'](command, root)

    def real_runner(run_date, *, config_path, root, resume_from):
        resume_calls.append(resume_from)
        result = daily.run_daily(
            run_date, config_path=config_path, root=root,
            resume_from=resume_from, command_runner=command_runner,
        )
        status = result[2]
        invocations.append(status['invocation']['id'])
        if resume_from is None:
            assert result[0] == 1 and status[phase]['status'] == 'FAILED'
            staging = data / 'analysis' / 'invocations' / invocations[-1] / 'data'
            validate_raw(day, read(staging / 'raw' / f'{day}_manifest.json'),
                         read(staging / 'raw' / f'{day}.json'), invocations[-1], config_path)
            if phase == 'analysis':
                validate_clean(staging, day, invocations[-1])
            assert all(p.read_bytes() == content for p, content in published_before.items())
            if not previous_published:
                assert not (data / 'raw' / f'{day}.json').exists()
            else:
                assert prior['invocation']['id'] != invocations[-1]
        return result

    # No external delivery; Ops and actual Daily Health still run normally.
    monkeypatch.setattr(NotificationService, 'send_pending', lambda self: [])
    e['now'] = f'{day}T10:00:00+08:00'
    code, summary = run_daily_with_health(
        day, root=e['root'], config_path=e['config'], runner=real_runner,
    )
    recovery = summary.get('automatic_recovery', {})
    record_property('recovery', json.dumps(recovery, sort_keys=True))
    record_property('failed_phase', phase)
    record_property('previous_published', previous_published)
    record_property('resume_calls', json.dumps(resume_calls))
    record_property('ops_precheck_inputs', json.dumps(precheck_inputs, sort_keys=True))
    record_property('failed_invocation', invocations[0])
    assert sum(command[2] == 'src.main' for command in stage_calls) == 1
    assert code == 0 and recovery.get('result') == 'SUCCESS', (
        f'Valid {phase} staging did not recover: code={code}, recovery={recovery}'
    )
    assert resume_calls == [None, phase]
    assert invocations == [invocations[0], invocations[0]]
    validate_analysis(data, day, invocations[0])
    assert read(data / 'analysis' / 'health' / f'{day}.json')['technical_run_health'] == 'SUCCESS'

    # A repeated Ops check must not trigger a second downstream attempt.
    operations = DailyOperations(data_dir=data, root=e['root'], config_path=e['config'])
    latest_run = read(data / 'analysis' / 'runs' / f'{day}.json')
    operations.attempt_recovery(day, latest_run, runner=real_runner)
    assert resume_calls == [None, phase]
