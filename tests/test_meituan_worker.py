"""Real exec'd processes with fake HTTP, short budgets, and OS exit evidence."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from src.analysis.source_health import SourceHealth
from src.collectors.meituan_worker import (
    Budget, Receipts, WorkerBlocked, command_environment, supervise, _signal,
)
from src.models import CollectionManifest, RawJobPosting

ROOT = Path(__file__).resolve().parents[1]
CONFIG = dict(name='美团', list_api='https://offline.test/list',
              list_url='https://offline.test/jobs', detail_api='https://offline.test/detail',
              detail_workers=1, worker_term_grace_seconds=.1)


def context(tmp_path):
    from datetime import datetime
    now = datetime.now().astimezone()
    return dict(directory=str(tmp_path / 'evidence'), retry=False, config_sha256='a' * 64,
                invocation=dict(id=str(uuid4()), run_date=now.date().isoformat(),
                                started_at=now.isoformat()))


def command(mode):
    return lambda fd, token: [sys.executable, '-c',
        "exec(compile(open('tests/meituan_worker_fixture.py').read(), 'worker-fixture', 'exec'))",
        str(fd), token, mode]


def run(tmp_path, mode, seconds=2):
    b = Budget(seconds, context(tmp_path))
    try:
        result = supervise(CONFIG, {'cities': ['北京'], 'max_retries': 1}, b,
                           command_factory=command(mode))
    finally:
        b.close()
    audit = result.manifest.metadata['worker']
    assert audit['exit_confirmed'] is True, audit
    assert audit['remaining_descendants'] == []
    # Proof of actual process exit, independent of Future cancellation.
    with pytest.raises(ProcessLookupError):
        os.kill(audit['pid'], 0)
    with (b.directory / 'budget.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert audit['pid'] == audit['pgid'] == audit['sid']
    assert audit['pgid'] != os.getpgrp()
    print('PROCESS_EXIT_EVIDENCE ' + json.dumps(audit, sort_keys=True))
    return result


@pytest.mark.parametrize('mode,successes,failed', [('normal', 4, 0), ('partial', 3, 1),
                                                  ('no_descendants', 4, 0)])
def test_normal_and_partial(tmp_path, mode, successes, failed):
    result = run(tmp_path, mode)
    m = result.manifest
    a = m.metadata['worker']
    assert a['exit_reason'] == 'completed'
    assert a['returncode'] == 0 and not a['sigterm'] and not a['sigkill']
    assert m.complete is (failed == 0)
    assert m.details_fetched == successes and m.detail_failed == failed
    assert len(result.jobs) == 4
    health = SourceHealth({'job_count': 4, 'platforms': [m.to_dict()]},
                          [j.to_dict() for j in result.jobs])
    if failed:
        assert health.tolerates_detail_gap('meituan', max_failed=1, max_failure_rate=.3)


@pytest.mark.parametrize('mode', ['hang', 'fail_forever', 'list_hang', 'list_partial'])
def test_budget_reaps_real_worker_and_keeps_truth(tmp_path, mode):
    result = run(tmp_path, mode, .65)
    m = result.manifest
    a = m.metadata['worker']
    assert a['exit_reason'] == 'budget_exhausted'
    assert a['budget_exhausted'] and a['sigterm']
    assert a['elapsed_seconds'] < 3
    assert m.status == 'error' and m.complete is False
    assert a['detail_targets'] == (a['detail_succeeded'] + a['detail_failed']
                                   + a['detail_unattempted'] + a['detail_unknown'])
    if mode != 'fail_forever':
        assert a['sigkill'] and a['returncode'] == -signal.SIGKILL
    if mode == 'hang':
        assert a['detail_succeeded'] == 1 and a['detail_unknown'] == 1
        assert a['detail_unattempted'] == 2 and a['detail_failed'] == 0
        assert result.jobs[0].description == '负责大模型评测质量与测试'
        assert a['list_complete']
    if mode == 'list_partial':
        assert a['list_discovered'] == 4 and a['detail_unattempted'] == 4
        assert not a['list_complete']
    jobs = [j.to_dict() for j in result.jobs]
    health = SourceHealth({'job_count': len(jobs), 'platforms': [m.to_dict()]}, jobs)
    assert not health.resolve('meituan').presence_reliable
    assert all(not health.resolve('meituan', '美团', j).content_reliable for j in jobs)


@pytest.mark.parametrize('mode', ['crash', 'ipc_close'])
def test_abnormal_exit_and_truncated_ipc(tmp_path, mode):
    result = run(tmp_path, mode, .65)
    a = result.manifest.metadata['worker']
    assert result.manifest.status == 'error'
    assert a['detail_succeeded'] == 1
    assert a['detail_unknown'] == 1
    assert not result.manifest.complete


def test_shared_budget_cannot_restart(tmp_path):
    ctx = context(tmp_path)
    b = Budget(.65, ctx)
    first = supervise(CONFIG, {}, b, command_factory=command('hang'))
    b.close()
    ctx['retry'] = True
    retry = Budget(.65, ctx)
    called = []
    second = supervise(CONFIG, {}, retry, command_factory=lambda *args: called.append(args))
    retry.close()
    a, b = [r.manifest.metadata['worker'] for r in (first, second)]
    assert a['budget_deadline'] == b['budget_deadline']
    assert b['remaining_at_start'] == 0 and b['pid'] is None and not called
    with pytest.raises(ProcessLookupError):
        os.kill(a['pid'], 0)


def test_retry_before_exhaustion_gets_only_remaining_budget(tmp_path):
    ctx = context(tmp_path)
    b = Budget(1., ctx)
    first = supervise(CONFIG, {}, b, command_factory=command('crash'))
    b.close()
    ctx['retry'] = True
    b = Budget(1., ctx)
    second = supervise(CONFIG, {}, b, command_factory=command('hang'))
    b.close()
    a, b = [r.manifest.metadata['worker'] for r in (first, second)]
    assert 0 < b['remaining_at_start'] < a['remaining_at_start']
    assert a['budget_deadline'] == b['budget_deadline']
    assert b['budget_exhausted'] and b['exit_confirmed']


def test_missing_changed_or_locked_budget_is_blocked(tmp_path):
    ctx = context(tmp_path)
    ctx['retry'] = True
    with pytest.raises(WorkerBlocked, match='missing'):
        Budget(1800, ctx)
    ctx['retry'] = False
    b = Budget(1800, ctx)
    with pytest.raises(BlockingIOError):
        Budget(1800, ctx)
    b.close()
    ctx['invocation']['id'] = str(uuid4())
    with pytest.raises(WorkerBlocked, match='identity'):
        Budget(1800, ctx)


def test_no_signal_to_nonisolated_process(monkeypatch):
    class Process:
        pid = os.getpid()
        def poll(self):
            return None
    calls = []
    monkeypatch.setattr(os, 'kill', lambda *args: calls.append(args))
    with pytest.raises(WorkerBlocked):
        _signal(Process(), signal.SIGKILL, {})
    assert not calls


def test_receipts_deduplicate_and_reject_unconfirmed_completion():
    r = Receipts('美团')
    job = RawJobPosting(platform='meituan', job_id='1', title='a', company='美团')
    m = CollectionManifest(platform='meituan', name='美团')
    msg = dict(seq=1, event='list', manifest=m.to_dict(), jobs=[job.to_dict()])
    r.accept(msg); r.accept(msg)
    assert len(r.jobs) == 1
    r.accept(dict(seq=2, event='attempt', job_id='1'))
    m.details_fetched = 1
    with pytest.raises(ValueError, match='receipts'):
        r.accept(dict(seq=3, event='done', manifest=m.to_dict()))
    assert not r.succeeded and not r.done
    with pytest.raises(ValueError, match='order'):
        r.accept(dict(seq=4, event='success', job=job.to_dict()))


def test_monotonic_budget_does_not_charge_sleep_but_date_gate_stays(tmp_path, monkeypatch):
    import src.collectors.meituan_worker as worker
    ctx = context(tmp_path)
    b = Budget(1800, ctx)
    remaining = b.remaining()
    monkeypatch.setattr(worker.time, 'time', lambda: b.state['wall_start'] + 20000)
    assert b.remaining() == pytest.approx(remaining, abs=.1)
    ctx['invocation']['started_at'] = '2026-01-01T00:00:00+08:00'
    ctx['invocation']['run_date'] = '2026-01-01'
    with pytest.raises(ValueError, match='DATE_MISMATCH'):
        b.check_date()
    b.close()


def test_official_command_context_is_invocation_scoped(tmp_path):
    config = tmp_path/'config.yaml'; config.write_text('platforms: {}')
    ctx = context(tmp_path)
    inv = ctx['invocation']
    cmd = [sys.executable, '-m', 'src.main', '--config', str(config), '--date', inv['run_date'],
           '--invocation-id', inv['id'], '--started-at', inv['started_at'],
           '--output-dir', str(tmp_path/'data/raw')]
    from src.collectors.meituan_worker import CONTEXT_ENV
    first = json.loads(command_environment(cmd)[CONTEXT_ENV])
    second = json.loads(command_environment(cmd+['--merge-existing'])[CONTEXT_ENV])
    assert first['directory'] == second['directory']
    assert first['invocation'] == second['invocation'] == inv
    assert second['retry'] and not first['retry']


def test_kill_is_limited_to_worker_and_next_platform_runs(tmp_path, monkeypatch):
    from src import main
    from src.models import CollectionResult
    sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'],
                                start_new_session=True)
    reached = []
    class Isolated:
        def __init__(self, *args): pass
        def collect(self): return run(tmp_path, 'hang', .65)
        def close(self): pass
    class Next:
        def __init__(self, *args): pass
        def collect(self):
            reached.append(True)
            return CollectionResult([], CollectionManifest(platform='next', name='next',
                                    status='success', complete=True))
        def close(self): pass
    monkeypatch.setitem(main.COLLECTOR_REGISTRY, 'meituan', Isolated)
    monkeypatch.setitem(main.COLLECTOR_REGISTRY, 'next', Next)
    try:
        jobs, manifests = main.collect_all({'platforms': {'meituan': {'enabled': True},
                                                         'next': {'enabled': True}}})
        assert reached == [True] and len(jobs) == 4
        assert manifests[0].status == 'error' and manifests[1].complete
        assert sentinel.poll() is None
    finally:
        sentinel.terminate(); sentinel.wait(timeout=2)


def test_journal_failure_still_reaps_and_preserves_receipts(tmp_path, monkeypatch):
    import src.collectors.meituan_worker as worker
    original = Path.open
    class FailedJournal:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def write(self, value): raise OSError('offline disk failure')
    def open_file(path, *args, **kwargs):
        if path.suffix == '.jsonl': return FailedJournal()
        return original(path, *args, **kwargs)
    b = Budget(.65, context(tmp_path))
    monkeypatch.setattr(Path, 'open', open_file)
    result = supervise(CONFIG, {}, b, command_factory=command('hang'))
    b.close()
    audit = result.manifest.metadata['worker']
    assert audit['exit_confirmed'] and audit['exit_reason'] == 'ipc_or_start_failure'
    assert len(result.jobs) == 4 and audit['detail_succeeded'] == 0
    with pytest.raises(ProcessLookupError): os.kill(audit['pid'], 0)


@pytest.mark.parametrize('mode', ['duplicate', 'unconfirmed', 'malformed'])
def test_real_ipc_retransmission_and_unconfirmed_frames(tmp_path, mode):
    result = run(tmp_path, mode, .65)
    a = result.manifest.metadata['worker']
    assert len(result.jobs) == 1
    if mode == 'duplicate':
        assert result.manifest.complete and a['detail_succeeded'] == 1
        assert a['last_confirmed_sequence'] == 5
    else:
        assert result.manifest.status == 'error' and not result.manifest.complete
        assert a['detail_succeeded'] == 0 and a['detail_unknown'] == 1
        assert a['last_confirmed_sequence'] == 3


def test_final_evidence_failure_preserves_received_jobs(tmp_path, monkeypatch):
    import src.collectors.meituan_worker as worker
    b = Budget(2, context(tmp_path))
    original = worker.write_json_atomic
    def fail(path, value):
        if path.name.endswith('-result.json'):
            raise OSError('offline evidence disk failure')
        original(path, value)
    monkeypatch.setattr(worker, 'write_json_atomic', fail)
    result = supervise(CONFIG, {}, b, command_factory=command('normal'))
    b.close()
    assert len(result.jobs) == result.manifest.details_fetched == 4
    assert result.manifest.status == 'error' and not result.manifest.complete
    assert result.manifest.stopped_by == 'worker_evidence_failure'
    assert result.manifest.metadata['worker']['exit_confirmed']


def test_configured_1800_seconds_with_accelerated_parent_clock(tmp_path, monkeypatch):
    import types
    import src.collectors.meituan_worker as worker
    import yaml
    configured = yaml.safe_load((ROOT/'config.yaml').read_text())['platforms']['meituan']
    assert configured['worker_budget_seconds'] == 1800
    assert configured['worker_term_grace_seconds'] == 10
    base = time.monotonic()
    monkeypatch.setattr(worker, 'time', types.SimpleNamespace(
        monotonic=lambda: base + (time.monotonic()-base)*2000,
        time=time.time, sleep=time.sleep))
    b = Budget(1800, context(tmp_path))
    result = supervise(dict(CONFIG, worker_term_grace_seconds=10), {}, b,
                       command_factory=command('hang'))
    b.close()
    a = result.manifest.metadata['worker']
    assert a['budget_deadline'] - a['budget_start'] == pytest.approx(1800)
    assert a['elapsed_seconds'] >= 1800 and a['budget_exhausted']
    assert a['sigterm'] and a['sigkill'] and a['exit_confirmed']
    with pytest.raises(ProcessLookupError): os.kill(a['pid'], 0)


def test_real_time_safety_check_bounds_grace_after_sleep(tmp_path, monkeypatch):
    import types
    import src.collectors.meituan_worker as worker
    base, wall = time.monotonic(), time.time()
    monkeypatch.setattr(worker, 'time', types.SimpleNamespace(
        monotonic=time.monotonic, time=lambda: wall+(time.monotonic()-base)*1000,
        sleep=time.sleep))
    b = Budget(.65, context(tmp_path))
    result = supervise(dict(CONFIG, worker_term_grace_seconds=10), {}, b,
                       command_factory=command('hang'))
    b.close()
    a = result.manifest.metadata['worker']
    assert a['grace_exit_reason'] == 'wall_safety'
    assert a['shutdown_seconds'] < 2 and a['sleep_or_wall_adjustment_seconds'] > 30
    assert a['exit_confirmed'] and a['sigkill']


def test_date_expiry_terminates_active_worker(tmp_path):
    b = Budget(1800, context(tmp_path))
    begin = time.monotonic()
    def expires():
        if time.monotonic() - begin > .65:
            raise ValueError('MANIFEST_DATE_MISMATCH')
    b.check_date = expires
    result = supervise(CONFIG, {}, b, command_factory=command('hang'))
    b.close()
    a = result.manifest.metadata['worker']
    assert a['exit_reason'] == 'date_window_expired' and not a['budget_exhausted']
    assert a['exit_confirmed'] and a['sigkill']


def test_interrupted_observation_never_confirms_removal_or_growth(tmp_path):
    from src.analysis.lifecycle import Lifecycle
    result = run(tmp_path, 'list_partial', .65)
    rows = [j.to_dict() for j in result.jobs]
    old = dict(rows[0], job_id='previously-known')
    prior = CollectionManifest(platform='meituan', name='美团', status='success', complete=True,
        source_total=1, expected_pages=1, pages_fetched=1, records_fetched=1,
        jobs_mapped=1, jobs_in_scope=1, stopped_by='source_total_reached')
    lifecycle = Lifecycle()
    lifecycle.observe('2026-01-01', [old], SourceHealth(
        {'platforms': [prior.to_dict()], 'job_count': 1}, [old]))
    health = SourceHealth({'platforms': [result.manifest.to_dict()], 'job_count': len(rows)}, rows)
    for day in ['2026-01-02', '2026-01-03', '2026-01-04']:
        events = lifecycle.observe(day, rows, health)
        assert not any(e['event_type'] in {'NEW', 'REMOVED'} for e in events)
        assert all(e['event_status'] == 'provisional' for e in events)
    assert lifecycle.state[('meituan', 'previously-known')].missing_streak == 0


def test_retry_cannot_hide_missing_exit_evidence(tmp_path):
    from src.collectors.meituan_worker import verify_worker_cleanup
    directory = tmp_path/'meituan-worker'; directory.mkdir()
    (directory/'a-launch.json').write_text(json.dumps({'pid': 123, 'launch_token': 'test'}))
    with pytest.raises(WorkerBlocked, match='missing'):
        verify_worker_cleanup(tmp_path/'data/raw')


@pytest.mark.parametrize('audit', [
    dict(pid=123, exit_reason='BLOCKED', exit_confirmed=False, remaining_descendants=[]),
    dict(pid=123, exit_reason='ipc_or_start_failure', exit_confirmed=False, remaining_descendants=[]),
])
def test_unproven_exit_before_launch_audit_also_blocks_retry(tmp_path, audit):
    from src.collectors.meituan_worker import verify_worker_cleanup
    directory = tmp_path/'meituan-worker'; directory.mkdir()
    (directory/'a-result.json').write_text(json.dumps({'manifest': {'metadata': {'worker': audit}}}))
    with pytest.raises(WorkerBlocked, match='cleanup'):
        verify_worker_cleanup(tmp_path/'data/raw')
