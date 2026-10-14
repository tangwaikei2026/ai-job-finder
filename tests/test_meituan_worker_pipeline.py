"""Real Worker -> Raw -> Clean -> Analysis -> staged publication, entirely offline."""
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time

import pytest
import yaml

from src import main as raw
from src.collectors import meituan_worker as worker
from src.clean.cli import main as clean_main
from src.analysis.pipeline import replay
from src.analysis.daily_health import generate_daily_health
from src.invocation import read, validate_analysis, validate_clean
from src.models import CollectionResult, CollectionManifest, RawJobPosting
import tools.run_daily as daily
from test_meituan_worker import command, CONFIG


@pytest.fixture
def execution(tmp_path, monkeypatch):
    day = datetime.now().astimezone().date().isoformat()
    config = tmp_path/'config.yaml'
    config.write_text(yaml.safe_dump(dict(output_dir='data/raw', cities=['北京'],
        max_retries=1, platforms=dict(meituan=dict(CONFIG, enabled=True, worker_budget_seconds=.65),
                                    next=dict(enabled=True)))))
    calls = []
    state = dict(mode='hang', next_delay=0)
    actual = worker.supervise
    def supervise(pc, cc, budget):
        return actual(pc, cc, budget, command_factory=command(state['mode']))
    monkeypatch.setattr(worker, 'supervise', supervise)
    class Next:
        def __init__(self, *args): pass
        def collect(self):
            time.sleep(state['next_delay'])
            job = RawJobPosting(platform='next', job_id='1', title='大模型测试工程师',
                                company='Next', location='北京', description='负责大模型评测质量与测试',
                                requirements='Python')
            return CollectionResult([job], CollectionManifest(platform='next', name='Next',
                status='success', complete=True, source_total=1, records_fetched=1,
                expected_pages=1, pages_fetched=1, jobs_mapped=1, jobs_in_scope=1,
                stopped_by='source_total_reached',
                finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        def close(self): pass
    monkeypatch.setitem(raw.COLLECTOR_REGISTRY, 'next', Next)
    def runner(cmd, root):
        cmd = list(cmd); calls.append(cmd)
        env = worker.command_environment(cmd)
        with monkeypatch.context() as patch:
            if worker.CONTEXT_ENV in env:
                patch.setenv(worker.CONTEXT_ENV, env[worker.CONTEXT_ENV])
            patch.setattr(sys, 'argv', [cmd[2], *cmd[3:]])
            try:
                if cmd[2] == 'src.main': raw.main()
                elif cmd[2] == 'src.clean.cli': clean_main()
                else:
                    report = replay(day, day, data_dir=Path(cmd[cmd.index('--data-dir')+1]),
                                    invocation_id=cmd[cmd.index('--invocation-id')+1])
                    return 0 if report['historical_replay_verified'] else 1
            except SystemExit as exc: return exc.code
        return 0
    return dict(day=day, config=config, runner=runner, calls=calls, root=tmp_path, state=state)


def test_worker_kill_continues_clean_analysis_and_publishes_true_health(execution):
    e = execution
    code, _, status = daily.run_daily(e['day'], config_path=e['config'], root=e['root'],
                                      command_runner=e['runner'])
    assert code == 0 and status['status'] == 'DEGRADED'
    assert [c[2] for c in e['calls']] == ['src.main', 'src.clean.cli', 'src.analysis.pipeline']
    assert status['crawl']['retry_budget_exhausted'] == ['meituan']
    data = e['root']/'data'
    manifest, jobs = validate_clean(data, e['day'], status['invocation']['id'])
    validate_analysis(data, e['day'], status['invocation']['id'])
    row = next(m for m in manifest['platforms'] if m['platform'] == 'meituan')
    assert row['status'] == 'error' and not row['complete']
    audit = row['metadata']['worker']
    assert audit['exit_confirmed'] and audit['sigkill']
    with pytest.raises(ProcessLookupError): os.kill(audit['pid'], 0)
    assert len([j for j in jobs if j['platform'] == 'meituan']) == 4
    assert jobs[0]['description'] == '负责大模型评测质量与测试'
    _, health = generate_daily_health(e['day'], data_dir=data)
    assert health['sources']['meituan']['source_completeness'] != 'COMPLETE'
    assert not health['sources']['meituan']['source_health']['presence_reliable']
    events = (data/'analysis/events'/f"{e['day']}.jsonl").read_text()
    assert 'REMOVED' not in events
    trend = read(data/'analysis/trends/snapshots'/f"{e['day']}.json")
    source = trend['platforms']['meituan']
    assert not source['reliability']['inventory']['reliable']
    assert not source['reliability']['presence_flow']['reliable']
    assert source['metrics']['new_jobs'] == 0

    # Worker evidence is outside staged data; not copied into published Raw.
    assert not (data/'meituan-worker').exists()


def test_publication_failure_preserves_existing_observation_and_worker_evidence(execution, monkeypatch):
    e = execution
    data = e['root']/'data'
    rawdir = data/'raw'; rawdir.mkdir(parents=True)
    prior = rawdir/f"{e['day']}.json"; prior.write_text('[{"old":true}]')
    original = daily.os.replace
    def fail(source, destination):
        if str(source).endswith('.invocation-tmp'):
            raise OSError('offline publication failure')
        return original(source, destination)
    monkeypatch.setattr(daily.os, 'replace', fail)
    code, _, status = daily.run_daily(e['day'], config_path=e['config'], root=e['root'],
                                      command_runner=e['runner'])
    assert code == 1 and 'publication failed' in status['analysis']['error']
    assert prior.read_text() == '[{"old":true}]'
    evidence = data/'analysis/invocations'/status['invocation']['id']/'meituan-worker'
    results = list(evidence.glob('*-result.json'))
    assert len(results) == 1
    result = read(results[0]); audit = result['manifest']['metadata']['worker']
    assert audit['detail_succeeded'] == 1 and len(result['jobs']) == 4
    assert audit['exit_confirmed']
    with pytest.raises(ProcessLookupError): os.kill(audit['pid'], 0)


def test_expiry_during_next_platform_does_not_start_retry(execution):
    e = execution
    e['state'].update(mode='crash', next_delay=.8)
    code, _, status = daily.run_daily(e['day'], config_path=e['config'], root=e['root'],
                                      command_runner=e['runner'])
    assert code == 0 and status['status'] == 'DEGRADED'
    assert status['crawl']['retry_budget_exhausted'] == ['meituan']
    assert status['crawl']['retried_platforms'] == []
    assert [c[2] for c in e['calls']] == ['src.main', 'src.clean.cli', 'src.analysis.pipeline']
    manifest = read(e['root']/'data/raw'/f"{e['day']}_manifest.json")
    audit = next(row for row in manifest['platforms'] if row['platform'] == 'meituan')['metadata']['worker']
    assert audit['budget_exhausted'] is False  # Deadline expired only after this observation.
    assert audit['exit_confirmed'] and audit['returncode'] == 7
