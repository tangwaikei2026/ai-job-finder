"""Deterministic offline execution of real stage entrypoints, with a fake collector."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from src import main as collector
from src.analysis.daily_health import build_daily_health, generate_daily_health, DailyHealthError
from src.analysis.pipeline import replay
from src.analysis.source_health import SourceHealth
from src.clean import jobs as clean_module
from src.clean.cli import main as clean_main
from src.invocation import (read, validate_raw, validate_clean, validate_analysis)
import src.invocation as proof
from src.models import CollectionManifest, RawJobPosting
import tools.run_daily as daily

DAY = '2026-10-11'


@pytest.fixture
def execution(tmp_path, monkeypatch):
    state = dict(now=f'{DAY}T10:00:00+08:00', finish=f'{DAY}T11:00:00+08:00',
                 calls=[], ids=[], retry=False, retry_success=False, mutate=None)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime.fromisoformat(state['now'])
            return value if tz is None else value.astimezone(tz)
    for module in (daily, proof, collector, clean_module):
        monkeypatch.setattr(module, 'datetime', Clock)
    config = tmp_path / 'config.yaml'
    config.write_text('output_dir: data/raw\ncities: [北京]\nplatforms: {}\n')

    def collect(config, selected=None):
        begin = state['now']
        state['now'] = state['finish']
        end = state['now']
        names = [selected] if selected else (['tencent', 'bytedance'] if state['retry'] else ['tencent'])
        rows, manifests = [], []
        for name in names:
            failed = name == 'bytedance' and (not selected or not state['retry_success'])
            rows.append(RawJobPosting(platform=name, job_id=name+'-1', company=name,
                                      title='大模型测试工程师', description='负责大模型评测质量与测试',
                                      requirements='Python', location='北京', scraped_at=end))
            manifests.append(CollectionManifest(
                platform=name, name=name, status='error' if failed else 'success',
                complete=not failed, source_total=2 if failed else 1, records_fetched=1,
                expected_pages=2 if failed else 1, pages_fetched=1,
                jobs_mapped=1, jobs_in_scope=1, detail_failed=0,
                stopped_by='error' if failed else 'source_total_reached',
                error='offline fixture failure' if failed else '', started_at=begin, finished_at=end))
        return rows, manifests
    monkeypatch.setattr(collector, 'collect_all', collect)

    def runner(command, root):
        command = list(command); state['calls'].append(command)
        name = command[2]
        try:
            if name == 'src.main':
                state['ids'].append(command[command.index('--invocation-id')+1])
                monkeypatch.setattr(sys, 'argv', ['collector', *command[3:]])
                try:collector.main()
                except SystemExit as exc:code = exc.code
                except RuntimeError:code = 1
                else:code = 0
            elif name == 'src.clean.cli':
                monkeypatch.setattr(sys, 'argv', ['clean', *command[3:]])
                clean_main();code = 0
            else:
                current = Path(command[command.index('--data-dir')+1])
                invocation_id = command[command.index('--invocation-id')+1]
                report = replay(DAY, DAY, data_dir=current, invocation_id=invocation_id)
                code = 0 if report['historical_replay_verified'] else 1
        except ValueError:
            code = 1
        if state['mutate']:
            state['mutate'](name, command)
        return code

    def run():
        state['now'] = f'{DAY}T10:00:00+08:00'
        return daily.run_daily(DAY, root=tmp_path, config_path=config, command_runner=runner)
    state.update(run=run, root=tmp_path, config=config, runner=runner)
    return state


@pytest.mark.parametrize('finish', ['2026-10-11T11:00:00+08:00', '2026-10-12T08:00:00+08:00'])
def test_same_and_next_day_real_offline_stage_chain(execution, finish):
    e = execution;e['finish'] = finish
    code, _, status = e['run']()
    assert code == 0
    data = e['root'] / 'data'
    m, jobs = validate_clean(data, DAY, status['invocation']['id'])
    validate_analysis(data, DAY, status['invocation']['id'])
    assert m['date'] == status['invocation']['run_date'] == DAY
    assert m['generated_at'][:10] == finish[:10]
    assert jobs[0]['scraped_at'] == finish
    _, health = generate_daily_health(DAY, data_dir=data)
    assert health['technical_run_health'] == 'SUCCESS'
    assert health['sources']['tencent']['source_completeness'] == 'COMPLETE'


@pytest.mark.parametrize('mutation', ['identity', 'missing_identity', 'missing_digest', 'digest', 'raw', 'missing_time'])
def test_bad_crawl_rejected_before_clean_or_analysis(execution, mutation):
    e = execution
    def mutate(name, cmd):
        if name != 'src.main':return
        raw_dir = Path(cmd[cmd.index('--output-dir')+1])
        path = raw_dir/f'{DAY}_manifest.json';m=read(path)
        if mutation=='identity':m['invocation']['id']=str(uuid4())
        elif mutation=='missing_identity':m.pop('invocation')
        elif mutation=='missing_digest':m.pop('raw_sha256')
        elif mutation=='digest':m['raw_sha256']='0'*64
        elif mutation=='missing_time':m['generated_at']=DAY
        else:
            raw=read(raw_dir/f'{DAY}.json');raw[0]['description']='different invocation'
            (raw_dir/f'{DAY}.json').write_text(json.dumps(raw))
        path.write_text(json.dumps(m))
    e['mutate']=mutate
    code,_,status=e['run']()
    assert code==1 and status['crawl']['status']=='FAILED'
    assert [c[2] for c in e['calls']]==['src.main']
    assert not (e['root']/f'data/raw/{DAY}.json').exists()


def test_third_day_rejected_before_retry(execution):
    e=execution;e.update(finish='2026-10-13T00:00:00+08:00',retry=True)
    code,_,status=e['run']()
    assert code==1 and len(e['calls'])==1
    assert 'MANIFEST_DATE_MISMATCH' in status['crawl']['error']


@pytest.mark.parametrize('success', [False, True])
def test_retry_retains_identity_date_and_valid_prior_results(execution, success):
    e=execution;e.update(retry=True,retry_success=success,finish='2026-10-12T08:00:00+08:00')
    code,_,status=e['run']()
    assert code==0 and len(e['ids'])==2 and len(set(e['ids']))==1
    assert all(c[c.index('--date')+1]==DAY for c in e['calls'])
    m=read(e['root']/f'data/raw/{DAY}_manifest.json')
    assert m['invocation']==status['invocation']
    byte=next(r for r in m['platforms'] if r['platform']=='bytedance')
    assert byte['status']==('success' if success else 'error')
    _,h=generate_daily_health(DAY,data_dir=e['root']/'data')
    assert h['technical_run_health']=='SUCCESS'
    assert h['sources']['bytedance']['source_completeness']==('COMPLETE' if success else 'UNKNOWN')
    assert h['sources']['bytedance']['source_health']['presence_reliable'] is success


def test_two_runs_have_distinct_identity_and_failed_second_preserves_first(execution):
    e=execution;code,_,first=e['run']();assert code==0
    data=e['root']/'data';raw=data/f'raw/{DAY}.json';manifest=data/f'raw/{DAY}_manifest.json'
    prior=(raw.read_bytes(),manifest.read_bytes())
    def corrupt(name,cmd):
        if name=='src.main':
            p=Path(cmd[cmd.index('--output-dir')+1])/f'{DAY}_manifest.json'
            p.write_bytes(prior[1])
    e['mutate']=corrupt
    code,_,second=e['run']()
    assert code==1 and first['invocation']['id']!=second['invocation']['id']
    assert (raw.read_bytes(),manifest.read_bytes())==prior


def test_successful_second_run_cannot_reuse_first_analysis(execution):
    e=execution;code,_,first=e['run']();assert code==0
    code,_,second=e['run']();assert code==0
    assert first['invocation']['id']!=second['invocation']['id']
    validate_analysis(e['root']/'data',DAY,second['invocation']['id'])
    with pytest.raises(ValueError,match='INVOCATION'):
        validate_clean(e['root']/'data',DAY,first['invocation']['id'])


def test_clean_tampering_rejected_before_analysis(execution):
    e=execution
    def corrupt(name,cmd):
        if name=='src.clean.cli':
            p=Path(cmd[cmd.index('--output-dir')+1])/f'{DAY}.json'
            jobs=read(p);jobs[0]['title']='other batch';p.write_text(json.dumps(jobs))
    e['mutate']=corrupt
    code,_,status=e['run']()
    assert code==1 and status['clean']['status']=='FAILED'
    assert all(c[2]!='src.analysis.pipeline' for c in e['calls'])


def test_analysis_digest_tampering_not_published(execution):
    e=execution
    def corrupt(name,cmd):
        if name=='src.analysis.pipeline':
            p=Path(cmd[cmd.index('--data-dir')+1])/f'analysis/events/{DAY}.jsonl'
            p.write_text('{}\n')
    e['mutate']=corrupt
    assert e['run']()[0]==1
    assert not (e['root']/f'data/raw/{DAY}.json').exists()


def test_source_health_unchanged_by_provenance(execution):
    e=execution;e.update(retry=True,finish='2026-10-12T08:00:00+08:00')
    assert e['run']()[0]==0
    data=e['root']/'data';m=read(data/f'raw/{DAY}_manifest.json');jobs=read(data/f'clean/{DAY}.json')
    legacy={k:v for k,v in m.items() if k not in {'invocation','raw_sha256','config_sha256','date'}}
    old,new=SourceHealth(legacy,jobs),SourceHealth(m,jobs)
    assert all(old.resolve(j['platform'],j['company'],j)==new.resolve(j['platform'],j['company'],j) for j in jobs)


@pytest.mark.parametrize(('day','generated'), [('2026-09-19','2026-09-29'),('2026-10-11','2026-10-12')])
def test_legacy_incidents_never_gain_identity_or_next_day_exemption(day, generated):
    m={'generated_at':generated+' 08:00:00','platforms':[],'job_count':0}
    with pytest.raises(ValueError,match='INVOCATION_PROOF_MISSING'):
        validate_raw(day,m,[],str(uuid4()))
    run={'date':day,'status':'DEGRADED','crawl':{'status':'DEGRADED'},
         'clean':{'status':'SUCCESS'},'analysis':{'status':'SUCCESS'}}
    with pytest.raises(DailyHealthError,match='MANIFEST_DATE_MISMATCH'):
        build_daily_health(day,run,m,[])


def test_publication_io_failure_restores_previous_files(tmp_path, monkeypatch):
    stage=tmp_path/'attempt/data';dest=tmp_path/'production'
    for name in ['raw/a.json','clean/a.json']:
        for root,value in [(stage,'new'),(dest,'old')]:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
    real=daily.os.replace;count=0
    def fail_second(source,target):
        nonlocal count
        count+=1
        if count==2:raise OSError('injected publication failure')
        return real(source,target)
    monkeypatch.setattr(daily.os,'replace',fail_second)
    with pytest.raises(OSError):daily._publish(stage,dest,DAY)
    assert (dest/'raw/a.json').read_text()==(dest/'clean/a.json').read_text()=='old'


def test_unknown_clean_identity_is_rejected(execution):
    e=execution
    def corrupt(name,cmd):
        if name=='src.clean.cli':
            p=Path(cmd[cmd.index('--output-dir')+1])/f'{DAY}_report.json'
            value=read(p);value['provenance']['invocation']['id']=str(uuid4())
            p.write_text(json.dumps(value))
    e['mutate']=corrupt
    assert e['run']()[0]==1
    assert all(c[2]!='src.analysis.pipeline' for c in e['calls'])


def test_modern_history_is_validated_without_changing_lifecycle(execution, monkeypatch):
    e=execution
    monkeypatch.setattr(sys.modules[__name__],'DAY','2026-10-10')
    e['finish']='2026-10-10T11:00:00+08:00'
    assert e['run']()[0]==0
    monkeypatch.setattr(sys.modules[__name__],'DAY','2026-10-11')
    e['finish']='2026-10-11T11:00:00+08:00'
    assert e['run']()[0]==0
    data=e['root']/'data'
    assert (data/'analysis/events/2026-10-11.jsonl').read_text()==''
    (data/'analysis/events/2026-10-10.jsonl').write_text('{}\n')
    code,_,status=e['run']()
    assert code==1 and status['analysis']['status']=='FAILED'


def test_new_daily_inputs_cannot_bypass_pipeline_gate_by_omitting_id(execution):
    e=execution;assert e['run']()[0]==0
    with pytest.raises(ValueError,match='INVOCATION_ID_REQUIRED'):
        replay(DAY,DAY,data_dir=e['root']/'data')


def test_health_rejects_missing_or_inconsistent_digest(execution):
    e=execution;code,_,status=e['run']();assert code==0
    data=e['root']/'data';m=read(data/f'raw/{DAY}_manifest.json');jobs=read(data/f'clean/{DAY}.json')
    m.pop('raw_sha256')
    with pytest.raises(DailyHealthError,match='PROVENANCE'):
        build_daily_health(DAY,status,m,jobs)


def test_completed_collection_does_not_allow_third_day_analysis(execution):
    e=execution
    def delay(name,cmd):
        if name=='src.clean.cli':e['now']='2026-10-13T00:00:00+08:00'
    e['mutate']=delay
    code,_,status=e['run']()
    assert code==1 and status['analysis']['status']=='SKIPPED'
    assert all(c[2]!='src.analysis.pipeline' for c in e['calls'])


def test_retry_output_gate_rejects_mixed_manifest_before_clean(execution):
    e=execution;e.update(retry=True,retry_success=True)
    def corrupt(name,cmd):
        if name=='src.main' and '--merge-existing' in cmd:
            p=Path(cmd[cmd.index('--output-dir')+1])/f'{DAY}_manifest.json'
            m=read(p);m['invocation']['id']=str(uuid4());p.write_text(json.dumps(m))
    e['mutate']=corrupt
    code,_,status=e['run']()
    assert code==1 and status['crawl']['status']=='FAILED'
    assert len(e['calls'])==2 and all(c[2]=='src.main' for c in e['calls'])


def test_failed_second_clean_preserves_previous_published_observation(execution):
    e=execution;assert e['run']()[0]==0
    data=e['root']/'data'
    protected=[p for folder in ['raw','clean','analysis/classification','analysis/events',
                               'analysis/trends/snapshots','analysis/audit']
               for p in (data/folder).glob('*') if p.is_file()]
    before={p:p.read_bytes() for p in protected}
    def corrupt(name,cmd):
        if name=='src.clean.cli':
            p=Path(cmd[cmd.index('--output-dir')+1])/f'{DAY}_report.json'
            p.write_text('{}')
    e['mutate']=corrupt
    assert e['run']()[0]==1
    assert all(p.read_bytes()==value for p,value in before.items())


def test_partial_publication_cannot_fall_back_to_legacy_health(execution):
    e=execution;assert e['run']()[0]==0
    data=e['root']/'data'
    for path in [data/f'raw/{DAY}_manifest.json',data/f'analysis/runs/{DAY}.json']:
        value=read(path);value.pop('invocation');path.write_text(json.dumps(value))
    with pytest.raises(DailyHealthError):generate_daily_health(DAY,data_dir=data)
    with pytest.raises(ValueError,match='INVOCATION_ID_REQUIRED'):
        replay(DAY,DAY,data_dir=data)


def test_partial_publication_cannot_enter_legacy_history_warmup(execution, monkeypatch):
    e=execution
    monkeypatch.setattr(sys.modules[__name__],'DAY','2026-10-10')
    e['finish']='2026-10-10T11:00:00+08:00';assert e['run']()[0]==0
    path=e['root']/'data/raw/2026-10-10_manifest.json'
    manifest=read(path);manifest.pop('invocation');path.write_text(json.dumps(manifest))
    monkeypatch.setattr(sys.modules[__name__],'DAY','2026-10-11')
    e['finish']='2026-10-11T11:00:00+08:00'
    code,_,status=e['run']()
    assert code==1 and status['analysis']['status']=='FAILED'
    assert not (e['root']/'data/raw/2026-10-11.json').exists()


@pytest.mark.parametrize('mode', ['single_day', 'warmup', 'trend_only'])
def test_run_only_modern_evidence_blocks_other_replay_paths(execution, mode, record_property):
    e = execution
    assert e['run']()[0] == 0
    data = e['root'] / 'data'
    status = read(data / 'analysis' / 'runs' / f'{DAY}.json')
    validate_analysis(data, DAY, status['invocation']['id'])
    path = data / 'raw' / f'{DAY}_manifest.json'
    manifest = read(path)
    manifest.pop('invocation')
    path.write_text(json.dumps(manifest))
    (data / 'analysis' / 'audit' / f'{DAY}_invocation.json').unlink()
    before = {p.relative_to(data): p.read_bytes() for p in data.rglob('*') if p.is_file()}
    if mode == 'single_day':
        with pytest.raises(ValueError, match='INVOCATION_ID_REQUIRED'):
            replay(DAY, DAY, data_dir=data)
    else:
        with pytest.raises(FileNotFoundError):
            replay('2026-10-12' if mode == 'warmup' else DAY, '2026-10-13',
                   data_dir=data, trend_only=mode == 'trend_only')
    after = {p.relative_to(data): p.read_bytes() for p in data.rglob('*') if p.is_file()}
    changed = sorted(str(p) for p in before.keys() | after.keys()
                     if before.get(p) != after.get(p))
    record_property('changed_protected_artifacts', json.dumps(changed))
    assert not changed


@pytest.mark.parametrize('trend_only', [False, True])
def test_legacy_replay_with_run_without_invocation_remains_usable(tmp_path, trend_only):
    from tests.test_daily_health import run_status
    from tests.test_market_pipeline import job, write_day

    for day in ('2026-09-01', '2026-09-02'):
        write_day(tmp_path, day, [job()])
        run_path = tmp_path / 'analysis' / 'runs' / f'{day}.json'
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(json.dumps(run_status(day=day)))
        assert 'invocation' not in read(run_path)
    # Generate the Legacy event ledger required by trend-only, without migrating
    # old observations to invocation proofs or stripping markers from modern data.
    replay('2026-09-01', '2026-09-02', data_dir=tmp_path)
    result = replay('2026-09-01', '2026-09-02', data_dir=tmp_path, trend_only=trend_only)
    assert len(result['observations']) == 2
    assert (tmp_path / 'analysis/trends/comparisons/2026-09-01_2026-09-02.json').is_file()


# Contract basis: validate_clean binds raw/clean to one invocation; the existing
# single-day and history-warmup gates must not be bypassed by a date range.
# These are modern inputs, not an attempt to retrofit proof onto legacy data.
@pytest.mark.parametrize('damage', [
    'missing_clean_proof', 'mixed_invocation', 'tampered_clean',
    'missing_manifest_invocation_and_proof',
])
@pytest.mark.parametrize('damaged_day', ['2026-10-10', '2026-10-11'])
def test_multiday_replay_rejects_unproven_inputs_and_preserves_affected_publications(
    execution, monkeypatch, damage, damaged_day, record_property,
):
    """Reject invalid modern proof without changing sources or dependent outputs.

    An earlier valid date may finish; diagnostics and staging may be created.
    Neither unchanged bytes nor a successful replay establishes input trust.
    """
    e = execution
    data = e['root'] / 'data'
    old_reports = {}
    identifiers = {}
    for day in ('2026-10-10', '2026-10-11'):
        monkeypatch.setattr(sys.modules[__name__], 'DAY', day)
        e['finish'] = f'{day}T11:00:00+08:00'
        code, _, first = e['run']()
        assert code == 0
        old_reports[day] = (data / 'clean' / f'{day}_report.json').read_bytes()
        code, _, second = e['run']()
        assert code == 0
        assert first['invocation']['id'] != second['invocation']['id']
        identifiers[day] = second['invocation']['id']
        validate_analysis(data, day, identifiers[day])

    report_path = data / 'clean' / f'{damaged_day}_report.json'
    if damage == 'missing_clean_proof':
        value = read(report_path)
        value.pop('provenance')
        report_path.write_text(json.dumps(value))
    elif damage == 'mixed_invocation':
        report_path.write_bytes(old_reports[damaged_day])
    elif damage == 'missing_manifest_invocation_and_proof':
        manifest_path = data / 'raw' / f'{damaged_day}_manifest.json'
        value = read(manifest_path)
        value.pop('invocation')
        manifest_path.write_text(json.dumps(value))
        (data / 'analysis' / 'audit' / f'{damaged_day}_invocation.json').unlink()
        status = read(data / 'analysis' / 'runs' / f'{damaged_day}.json')
        assert status['invocation']['id'] == identifiers[damaged_day]
        assert status['status'] == 'SUCCESS'
    else:
        path = data / 'clean' / f'{damaged_day}.json'
        rows = read(path)
        rows[0]['description'] += '\nUNPROVEN_REPLAY_CONTENT'
        path.write_text(json.dumps(rows))

    # An existing production validator establishes invalidity independently of
    # replay's current behavior and without prescribing a new classifier rule.
    expected_error = ('INVOCATION_PROOF_MISSING'
                      if damage == 'missing_manifest_invocation_and_proof'
                      else 'CLEAN_PROVENANCE_MISMATCH')
    with pytest.raises(ValueError, match=expected_error):
        validate_clean(data, damaged_day, identifiers[damaged_day])
    # Source data is immutable input to replay (the existing historical replay
    # contract). Preserve the dated published observation for the invalid date
    # and later dates whose lifecycle/trends would depend on it. Do not require
    # transaction-wide rollback of an earlier valid date, staging work, new logs,
    # or every file under analysis; no such directory-wide contract is frozen.
    source_paths = [p for folder in ('raw', 'clean')
                    for p in (data / folder).glob('*.json') if p.is_file()]
    affected_paths = []
    for day in ('2026-10-10', '2026-10-11'):
        if day < damaged_day:
            continue
        affected_paths.extend(data / 'analysis' / relative for relative in (
            f'classification/{day}.jsonl', f'events/{day}.jsonl',
            f'trends/snapshots/{day}.json', f'audit/{day}_bundle.json',
            f'audit/{day}_invocation.json', f'runs/{day}.json',
        ))
    protected_paths = source_paths + affected_paths
    assert all(path.is_file() for path in protected_paths
               if damage != 'missing_manifest_invocation_and_proof'
               or path.name != f'{damaged_day}_invocation.json')
    # This pair depends on the invalid date in either parameterized case. A
    # comparison is a formal trend artifact even if it did not exist before;
    # creating one from untrusted input must also be detected.
    protected_paths.append(data / 'analysis' / 'trends' / 'comparisons' /
                           '2026-10-10_2026-10-11.json')
    before = {path.relative_to(data): path.read_bytes() if path.is_file() else None
              for path in protected_paths}
    error = None
    try:
        replay('2026-10-10', '2026-10-11', data_dir=data)
    except (ValueError, OSError) as exc:
        error = str(exc)
    after = {path.relative_to(data): path.read_bytes() if path.is_file() else None
             for path in protected_paths}
    changed = sorted(str(path) for path in before if before[path] != after[path])
    record_property('damage', f'{damaged_day}: {damage}')
    record_property('replay_error', error or 'NONE')
    record_property('changed_protected_artifacts', json.dumps(changed))
    record_property('protected_artifacts', json.dumps(sorted(str(path) for path in before)))
    assert error is not None and not changed, (
        f'Unproven modern input was accepted or an affected publication was replaced: '
        f'error={error!r}, changed={changed}'
    )
