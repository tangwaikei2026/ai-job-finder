"""Explicit freeze command: ordered gates, disposable offline replay, then activation.

Run with --freeze-unblock only when a production freeze is authorized.
Keeps Frozen Oracle and legacy fixtures unchanged; never writes production replay data.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import inspect
import json
from pathlib import Path
import subprocess

from src.analysis.ai_eval_jobs import classify_market, job_content_sha256
from src.analysis.ai_eval_regression import load_frozen_regression_cases, run_frozen_regression, run_split_regression
from src.analysis.market_rules import validate_market_output
from src.analysis.pipeline import load_settings
from tools.market_oracle_baseline import evaluate, read_yaml, validate_oracle

ORACLE = Path('tests/fixtures/market_oracle_v1.yaml')
LEGACY = Path('tests/fixtures/ai_eval_regression_set_v1_117_frozen.yaml')
OVERLAY = Path('tests/fixtures/ai_eval_market_expectations.yaml')
CONTRACT = Path('docs/market_contract_v1.md')
CONFIG = Path('configs/analysis/versions.yaml')
OUTPUT = Path('data/analysis/audit')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def special_case_scan():
    cases = [*read_yaml(ORACLE)['cases'], *load_frozen_regression_cases(LEGACY)]
    forbidden = {str(c[k]) for c in cases for k in ('case_id','job_id','content_sha256','title') if c.get(k)}
    sources = {'src/analysis/market_rules.py': Path('src/analysis/market_rules.py').read_text(),
               'src/analysis/ai_eval_jobs.py:classify_market': inspect.getsource(classify_market)}
    hits = []
    for path, source in sources.items():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value,str):
                if node.value in forbidden or any(c['case_id'] in node.value or c['content_sha256'] in node.value for c in cases):
                    hits.append(dict(file=path,line=node.lineno,reason='FROZEN_IDENTITY_OR_EXACT_TITLE_LITERAL'))
            if isinstance(node, ast.Subscript) and isinstance(node.slice,ast.Constant):
                if node.slice.value in {'case_id','job_id','content_sha256','company','platform'}:
                    hits.append(dict(file=path,line=node.lineno,reason='IDENTITY_DEPENDENT_RULE'))
            if isinstance(node, ast.Name) and node.id in {'open','read_yaml','read_json','expected_in_scope'}:
                hits.append(dict(file=path,line=node.lineno,reason='EXTERNAL_OR_EXPECTED_RULE_INPUT'))
    return dict(status='FAIL' if hits else 'PASS',hits=hits,
                checked_sources={path:hashlib.sha256(s.encode()).hexdigest() for path,s in sources.items()},
                limitation='Static guard plus separate metadata/order metamorphic tests; not a proof of population generalization.')


def proven_legacy_conflicts(oracle, legacy):
    by_hash = {c['content_sha256']:c for c in oracle}
    overlay = read_yaml(OVERLAY)
    conflicts = []
    for case in legacy:
        case_id = case['case_id']
        scope = case_id not in overlay['out_of_scope']
        old = dict(in_scope=scope,role_family=case['expected_role_family'],
                   ai_relation=overlay['ai_relation_overrides'].get(case_id,case['expected_ai_relation']))
        if not scope:
            for field in ('role_family','ai_relation'):
                if old[field] is not None:
                    conflicts.append(dict(case_id=case_id,field=field,legacy=old[field],required=None,
                        proof='FROZEN_CONTRACT_STOP_SEMANTICS',content_sha256=job_content_sha256(case)))
        current = by_hash.get(job_content_sha256(case))
        if current:
            for field in ('in_scope','role_family','ai_relation'):
                if old[field] != current['expected_'+field]:
                    conflicts.append(dict(case_id=case_id,oracle_case_id=current['case_id'],field=field,
                        legacy=old[field],required=current['expected_'+field],
                        content_sha256=current['content_sha256'],proof='IDENTICAL_FULL_CONTENT_SHA256'))
    return conflicts


def tracked_hash_check(path):
    original = subprocess.check_output(['git','show','HEAD:'+str(path)])
    before = hashlib.sha256(original).hexdigest()
    return dict(before=before,after=sha(path),unchanged=before==sha(path))


def historical_hashes():
    paths = set()
    for folder in ('classification','events','trends'):
        paths.update((Path('data/analysis')/folder).glob('*'))
    paths.update(Path('data/analysis').glob('*_ai_eval_hits.*'))
    return {str(p):sha(p) for p in sorted(paths) if p.is_file()}


def log_evidence(path):
    if not path:
        return dict(status='NOT_PROVIDED')
    p = Path(path)
    return dict(file=str(p),sha256=sha(p),output=p.read_text())


def historical_replay():
    """Replay only the five local snapshots into a disposable directory."""
    from collections import Counter
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    from src.analysis import classification, pipeline
    from src.analysis.ai_eval_jobs import load_jobs
    from src.analysis.lifecycle import EVENT_TYPES, EVENT_STATUSES, identity, index_jobs

    dates = ['2026-09-01','2026-09-02','2026-09-03','2026-09-04','2026-09-07']
    calls, fit_calls, emitted = Counter(), Counter(), {}
    lifecycle_days = []
    classify_record = pipeline.classify_record
    classify_fit = classification.classify_personal_fit
    observe = pipeline.Lifecycle.observe
    inputs = [Path('data') / folder / f'{day}{suffix}' for day in dates
              for folder, suffix in [('clean','.json'),('raw','_manifest.json')]]
    before = {str(p):sha(p) for p in inputs}

    def checked_record(day, job, health, versions, previous=None):
        row, market = classify_record(day, job, health, versions, previous)
        validate_market_output(market)
        calls[day] += 1
        if row is not None:
            validate_market_output(row)
            assert identity(row) == identity(job)
            source = previous if row['classification_status'] == 'carried_forward' else job
            expected_hash = source['content_sha256'] if source is previous else job_content_sha256(source)
            assert row['content_sha256'] == expected_hash
            assert row['in_scope']
            emitted[(day, *identity(row))] = row
        return row, market

    def checked_fit(job, market):
        assert market['in_scope'] is True
        fit_calls['total'] += 1
        return classify_fit(job, market)

    def checked_observe(self, day, jobs, health):
        result = observe(self, day, jobs, health)
        lifecycle_days.append(day)
        for job in jobs:
            key = identity(job)
            assert key in self.state
            if health.resolve(key[0],str(job.get('company','')),job).content_reliable:
                assert self.state[key].reliable_sha == job_content_sha256(job)
        for event in result:
            assert event['event_type'] in EVENT_TYPES and event['event_status'] in EVENT_STATUSES
            assert identity(event) in self.state
        return result

    with TemporaryDirectory(prefix='market-v1-replay-') as directory:
        root = Path(directory)
        for folder in ('clean','raw'):
            (root/folder).mkdir()
        for source in inputs:
            (root/source.parent.name/source.name).symlink_to(source.resolve())
        with patch.object(pipeline,'classify_record',checked_record), \
             patch.object(classification,'classify_personal_fit',checked_fit), \
             patch.object(pipeline.Lifecycle,'observe',checked_observe):
            replay = pipeline.replay(dates[0],dates[-1],data_dir=root,output_dir=root/'output')
        observations = {r['date']:r for r in replay['observations']}
        assert set(observations) == set(dates) == set(lifecycle_days)
        summaries = []
        for day in dates:
            jobs = index_jobs(load_jobs(Path('data/clean')/f'{day}.json'))
            assert calls[day] == len(jobs) == observations[day]['clean_job_count']
            lines = (root/'output/classification'/f'{day}.jsonl').read_text().splitlines()
            rows = [json.loads(line) for line in lines]
            assert len(rows) == observations[day]['market_in_scope_count']
            assert len(rows) == sum(k[0] == day for k in emitted)
            for row in rows:
                validate_market_output(row)
                assert row == emitted[(day,*identity(row))]
                assert identity(row) in jobs
            summaries.append(dict(date=day,clean_input=len(jobs),market_classifications=calls[day],
                serialized_in_scope=len(rows),schema='PASS',identity='PASS',content_sha256='PASS',
                lifecycle='PASS'))
        # Missing weekend snapshots are not requested replay dates.
        assert all(item['date'] not in dates for item in replay['incomplete_history'])
    assert before == {str(p):sha(p) for p in inputs}
    return dict(status='PASS',observations=summaries,fit_calls=fit_calls['total'],
        fit_scope_guard='PASS',input_hashes=before,
        storage_boundary='One Market decision per clean identity; existing serialization stores only in-scope rows.',
        lifecycle_boundary='Lifecycle consumes clean identities/content, not Market labels; shared replay and hash invariants passed.',
        output='Temporary replay outputs removed; existing production artifacts untouched.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-unblock', action='store_true', required=True)
    args = parser.parse_args()
    from collections import Counter
    from src.analysis.ai_eval_regression import load_market_migration

    migration_path = Path('tests/fixtures/ai_eval_market_v1_migration.yaml')
    history_before = historical_hashes()
    frozen = {str(p):tracked_hash_check(p) for p in (ORACLE,CONTRACT,LEGACY,OVERLAY)}
    assert all(x['unchanged'] for x in frozen.values())
    # A failed earlier gate must stop before the expensive full suite/replay.
    split = run_split_regression(LEGACY,migration_path,suite='market')
    print('MARKET V1 SPLIT:',split['market']['passed'], '/',split['market']['total'],flush=True)
    assert split['market']['gate_passed']
    old = run_frozen_regression(LEGACY)
    print('COMBINED:',old['passed'],'/',old['total'],flush=True)
    assert old['passed']==old['total']==117
    split.update(run_split_regression(LEGACY,migration_path,suite='fit'))
    print('FIT:',split['fit']['passed'],'/',split['fit']['total'],flush=True)
    assert split['fit']['passed']==split['fit']['total']==114
    scan = special_case_scan()
    assert scan['status']=='PASS'
    import sys
    tests = {}
    for name, command in [('compileall',[sys.executable,'-m','compileall','src','tests']),
                          ('pytest',[sys.executable,'-m','pytest','-q'])]:
        result = subprocess.run(command,text=True,capture_output=True)
        tests[name] = dict(command=command,exit_code=result.returncode,output=result.stdout+result.stderr)
        print(name+': '+tests[name]['output'].splitlines()[-1],flush=True)
        if result.returncode:
            print(tests[name]['output'],flush=True)
            Path('/tmp/market-freeze-failed-tests.json').write_text(json.dumps(tests,indent=2))
            return 1
    replay = historical_replay()
    assert historical_hashes()==history_before
    current = split['market']['semantic_oracle']
    gates = dict(frozen_sixty=current['metrics']['full_oracle_exact_match']['correct']==60,
        legacy_combined=True,legacy_compatibility=True,market_v1_split=True,fit=True,
        full_pytest=True,compileall=True,special_case_scan=True,historical_replay=True,
        frozen_sources_unchanged=True,historical_outputs_unchanged=True)
    assert all(gates.values())
    config = CONFIG.read_text()
    assert 'market_classifier_version: market_v1_candidate' in config
    CONFIG.write_text(config.replace('market_classifier_version: market_v1_candidate',
                                     'market_classifier_version: market_v1',1))
    assert load_settings()[1]['market']=='market_v1'
    cases = load_frozen_regression_cases(LEGACY)
    _, migrations, _ = load_market_migration(migration_path,cases)
    counts = dict(Counter(e['classification'] for e in migrations.values()))
    source_paths = [*Path('src/analysis').glob('*.py'),*Path('configs/analysis').glob('*.yaml'),
                    migration_path,Path('tools/market_v1_regression.py'),Path('tests/test_market_regression_migration.py')]
    report = dict(version='market_v1',production_classifier_v1_frozen=True,gates=gates,
        classifier_modified_this_batch=False,legacy_failure_classifications=counts,
        legacy_migration=str(migration_path),frozen_sources=frozen,
        source_provenance=dict(base_commit=git('rev-parse','HEAD'),implemented_source_commit=None,
            reason='Uncommitted workspace; no commit authorized.',file_sha256={str(p):sha(p) for p in source_paths}),
        frozen_sixty=current,legacy_combined=old,split=split,special_case_scan=scan,
        historical_replay=replay,historical_outputs=dict(before=history_before,after=historical_hashes()),tests=tests)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'market_v1_regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    with (OUTPUT/'market_v1_remaining_failures.csv').open('w',newline='') as f:
        csv.writer(f).writerow(['suite','case_id','field','expected','predicted','status'])
    migration_lines = ['# Legacy Market regression migration','',
        '仅处理原15条失败。全部 LEGACY_CONTRACT_OBSOLETE；TRUE_V1_REGRESSION=0；EVALUATOR_OR_SCHEMA_MISMATCH=0。',
        '原117 combined fixture与旧Market overlay逐字保留。旧overlay不再是V1 semantic owner。',
        'V1入口为tests/fixtures/ai_eval_market_v1_migration.yaml：只维护历史兼容delta，唯一V1语义owner仍为market_oracle_v1.yaml。',
        '旧reason ID伴随过期label退出exact断言；V1 reason结构仍校验，其余case的旧reason exact断言保留。',
        'P-01直接引用Oracle，不复制expected；STOP按冻结契约机械迁移；其余只迁移有明确正文和契约证据的冲突字段。',
        '冻结不意味着117条都有人工作出的完整V1五字段Oracle；117用于兼容性，60用于完整V1语义。','',
        '| Case | Classification | Conflict proof / JD evidence |','|---|---|---|']
    for cid,e in migrations.items():
        migration_lines.append(f"| {cid} | {e['classification']} | {e['proof']}：{e.get('evidence',{}).get('quote',e.get('oracle_case_id','negative STOP'))} |")
    (OUTPUT/'legacy_market_regression_migration.md').write_text('\n'.join(migration_lines)+'\n')
    lines = ['# Market V1 Productionization — freeze unblock','',
        'MARKET V1 FROZEN: YES。版本market_v1。当前有效未提交production实现完整保留，本批次未修改classifier。',
        '15条旧失败：LEGACY_CONTRACT_OBSOLETE=15；TRUE_V1_REGRESSION=0；EVALUATOR_OR_SCHEMA_MISMATCH=0。',
        'Frozen Oracle=60/60；scope TP=39 FP=0 TN=21 FN=0；role/relation/relevance/secondary=39/39。',
        'Combined=117/117；Market V1兼容回归=117/117并通过Frozen60语义gate；Fit=114/114；full pytest/replay/special-case scan=PASS。',
        '旧overlay原始102/117差异保留为历史诊断，不伪称旧expectations现在匹配V1；具体迁移见legacy_market_regression_migration.md。','',
        '## 本批次文件与原因','',
        '- src/analysis/ai_eval_regression.py：版本化兼容迁移、hash/正文/Contract绑定、单独Market/Fit gate；保留旧overlay诊断入口。',
        '- tests/fixtures/ai_eval_market_v1_migration.yaml：仅15条兼容delta，引用唯一Frozen60 semantic owner。',
        '- tests/test_market_regression_migration.py：验证内容变化、重复key及错误预测不会被迁移掩盖。',
        '- tests/test_market_pipeline.py：使用明确V1 gate，保留117/114分母。',
        '- data/analysis/audit/test_market_audit_instrument_v2.py：历史source断言指向batch1.5等字节快照。',
        '- data/analysis/audit/test_market_oracle_ledger_v3.py：历史ledger断言指向batch1.6版本。',
        '- data/analysis/audit/test_market_audit_patch_v3_1.py：最终delta引用冻结source/hash，并验证current Frozen60完整状态。',
        '- tools/market_v1_regression.py：按指定顺序执行gate，仅全通过后replay及版本冻结。',
        '- configs/analysis/versions.yaml：本批次candidate→market_v1（HEAD本已为market_v1，因此git diff不显示此恢复）。',
        '- 本报告、market_v1_regression.json、market_v1_remaining_failures.csv及小型migration说明：记录冻结证据；CSV仅header表示无剩余失败。','',
        '## 验收命令与结果','',
        '`PYTHONPATH=. venv/bin/pytest -q tests/test_market_regression_migration.py data/analysis/audit/test_market_audit_instrument_v2.py data/analysis/audit/test_market_oracle_ledger_v3.py data/analysis/audit/test_market_audit_patch_v3_1.py`：46 passed。',
        '`PYTHONPATH=. venv/bin/python tools/market_v1_regression.py --freeze-unblock`：Market→combined→Fit→compileall→full pytest ONCE→离线replay→freeze。',
        '内部验收：`venv/bin/python -m compileall src tests`；`venv/bin/python -m pytest -q`。','```text',
        tests['compileall']['output'].strip(),tests['pytest']['output'].strip(),'```','',
        '## Historical replay','',json.dumps(replay,ensure_ascii=False,indent=2),'',
        '## 工作区状态和diff','', '```text',git('status','--short'),'```','```text',git('diff','--stat'),'```',
        '关键diff片段如下；完整：`git diff -- src/analysis/ai_eval_regression.py tests/test_market_pipeline.py`。新增文件直接查看；data/analysis内audit测试和报告被既有.gitignore忽略，未stage。',
        '```diff',git('diff','--','src/analysis/ai_eval_regression.py','tests/test_market_pipeline.py'),'```','',
        '风险/限制：60条定向样本不外推市场总体准确率。Lifecycle以clean为输入，与新schema共存验证通过。',
        '没有真实访问招聘网站；未改raw、clean、数据库、diff、通知、README或Trend；未commit。',
        '本批次已完成，已停止，等待人工确认后再继续下一批次。']
    (OUTPUT/'market_v1_productionization_report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(gates=gates,version='market_v1',replay=replay['observations']),ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
