"""Offline Trend V1 gates: historical assertions, compile, one full pytest, freeze.

Run after targeted tests: python -m tools.trend_v1_validation --freeze
Only Trend artifacts and the Trend version setting may be written.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import yaml

from src.analysis import pipeline
from src.analysis.lifecycle import identity
from src.analysis.trends import (
    DIMENSIONS, FLOW_FIELDS, NON_ADDITIVE, compare_trends, trend_snapshot,
    validate_comparison, validate_snapshot,
)
from src.models import write_json_atomic

DATES = ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04', '2026-09-07']
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/analysis/trends'
SOURCE_FILES = ['src/analysis/trends.py', 'src/analysis/pipeline.py',
                'tests/test_trend_v1.py', 'tools/trend_v1_validation.py']
ALLOWED_CHANGES = {'src/analysis/trends.py', 'src/analysis/pipeline.py', 'configs/analysis/versions.yaml'}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def preserved_hashes():
    roots = ('src', 'configs', 'tests/fixtures', 'docs', 'data/raw', 'data/clean',
             'data/analysis/classification', 'data/analysis/events')
    files = {p for root in roots for p in (ROOT / root).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts}
    files.update(p for p in OUTPUT.glob('????-??-??.json') if p.is_file())
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)
            if str(p.relative_to(ROOT)) not in ALLOWED_CHANGES}


def check_integration_baseline():
    path = OUTPUT / 'integration_baseline.json'
    if not path.exists():
        return {'status': 'NO_SESSION_BASELINE', 'changed': []}
    baseline = json.loads(path.read_text())['hashes']
    changed = [name for name, value in baseline.items() if name not in ALLOWED_CHANGES
               and (not (ROOT / name).exists() or digest(ROOT / name) != value)]
    if changed:
        raise ValueError(f'UPSTREAM_HASH_CHANGED: {changed}')
    return {'status': 'PASS', 'checked_files': len(baseline) - len(ALLOWED_CHANGES), 'changed': []}


def verify_snapshot(history, **kwargs):
    snapshot = trend_snapshot(history, **kwargs)
    current = history[-1]
    # Independent calculations from identity-indexed source labels.
    all_rows = {identity(r): r for r in current['classifications']}
    rows = [r for r in all_rows.values() if r['in_scope'] and (
        r['classification_status'] == 'fresh' or (
            r['classification_status'] == 'carried_forward'
            and 'CONTENT_CARRIED_FORWARD' in r['reason_codes']['market']
            and r['career_pool'] in {'P1', 'P2', 'REF', 'X'}))]
    assert snapshot['active_jobs'] == len(rows)
    for dimension, field in DIMENSIONS.items():
        actual = Counter(snapshot[dimension])
        expected = Counter(r[field] for r in rows)
        assert actual == expected
        assert sum(actual.values()) == len(rows)
    assert Counter(snapshot['by_role_family_any']) == Counter(
        family for r in rows for family in set([r['role_family']] + r['secondary_role_families']))
    assert Counter(snapshot['by_skill_tag']) == Counter(tag for r in rows for tag in set(r['skill_tags']))
    assert snapshot['hybrid_role_count'] == len([r for r in rows if len(r['secondary_role_families']) >= 1])
    assert snapshot['hybrid_role_share']['denominator'] == len(rows)
    expected_share = snapshot['hybrid_role_count'] / len(rows) if rows else None
    assert snapshot['hybrid_role_share']['share'] == expected_share
    assert snapshot['unique_content_versions'] == len({r['content_sha256'] for r in rows})
    assert snapshot['metric_semantics'] == {**{key: 'NON_ADDITIVE' for key in NON_ADDITIVE},
                                           'unique_content_versions': 'DIAGNOSTIC_ONLY'}
    labels = {}
    for obs in history:
        for key in obs['present_keys']:
            labels.pop(key, None)
        labels.update({identity(r): r for r in obs['classifications'] if r['in_scope'] and (
            r['classification_status'] == 'fresh' or (
                r['classification_status'] == 'carried_forward'
                and 'CONTENT_CARRIED_FORWARD' in r['reason_codes']['market']))})
    flows = Counter()
    company_flows = Counter()
    for e in current['events']:
        r = labels.get(identity(e))
        if e['event_type'] not in FLOW_FIELDS or e['event_status'] != 'confirmed' or r is None or r['versions'] != current['versions']:
            continue
        health = current['health'].resolve(e['platform'], r['company'], current['jobs_by_identity'].get(identity(e)))
        if e['event_type'] == 'UPDATED':
            reliable = (health.content_reliable and r['classification_status'] == 'fresh'
                        and bool(e['previous_sha256']) and e['previous_sha256'] != e['current_sha256']
                        and e['current_sha256'] == r['content_sha256'])
        else:
            reliable = health.presence_reliable
        if reliable:
            flows[e['event_type']] += 1
            company_flows[(r['company'], e['event_type'])] += 1
    for kind, field in FLOW_FIELDS.items():
        assert snapshot[field] == flows[kind]
        assert sum(c[field] for c in snapshot['by_company'].values()) == flows[kind]
        for company, counts in snapshot['by_company'].items():
            assert counts[field] == company_flows[(company, kind)]
    validate_snapshot(snapshot)
    return snapshot


def historical_validation():
    with patch.object(pipeline, 'trend_snapshot', verify_snapshot), \
         patch.object(pipeline.Lifecycle, 'observe', side_effect=AssertionError('LIFECYCLE_RECOMPUTATION_FORBIDDEN')):
        result = pipeline.replay(DATES[0], DATES[-1], data_dir=ROOT / 'data', trend_only=True)
    assert [row['date'] for row in result['observations']] == DATES
    assert not any(row['date'] in DATES for row in result['incomplete_history'])
    snapshots = [json.loads((OUTPUT / 'snapshots' / f'{day}.json').read_text()) for day in DATES]
    comparisons = []
    for a, b in zip(snapshots, snapshots[1:]):
        path = OUTPUT / 'comparisons' / f"{a['snapshot_date']}_{b['snapshot_date']}.json"
        result = json.loads(path.read_text())
        assert result == compare_trends(a, b)
        validate_comparison(result)
        for family, info in result['comparability'].items():
            expected = set(a['platforms']) & set(b['platforms'])
            expected = {p for p in expected if a['platforms'][p]['reliability'][family]['reliable']
                        and b['platforms'][p]['reliability'][family]['reliable']
                        and a['platforms'][p]['source_scope'] == b['platforms'][p]['source_scope']}
            assert set(info['included_platforms']) == expected
            if info['comparable']:
                for side, snap in (('from', a), ('to', b)):
                    assert result['comparable_subset'][family][side]['active_jobs'] == sum(
                        snap['platforms'][p]['metrics']['active_jobs'] for p in expected)
        comparisons.append({'from_date': result['from_date'], 'to_date': result['to_date'],
                            'comparability': result['comparability']})
    return {'dates': DATES, 'warmup_dates': result_warmup(), 'snapshot_aggregation': 'PASS',
            'lifecycle_flow': 'PASS', 'comparability': 'PASS', 'invariants': 'PASS',
            'snapshots': [{key: snap[key] for key in ('snapshot_date', 'active_jobs', 'hybrid_role_count',
                                                    'unique_content_versions', *FLOW_FIELDS.values())}
                          for snap in snapshots], 'comparisons': comparisons}


def result_warmup():
    return sorted(p.stem for p in (ROOT / 'data/clean').glob('????-??-??.json') if p.stem < DATES[0]
                  and (ROOT / 'data/analysis/events' / f'{p.stem}.jsonl').exists())


def run_gate(name, command):
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    path = OUTPUT / f'{name}.log'
    path.write_text(completed.stdout)
    print(f'{name}: {"PASS" if completed.returncode == 0 else "FAIL"}', flush=True)
    if completed.returncode:
        raise RuntimeError(f'{name} failed; see {path}')
    return {'status': 'PASS', 'command': command, 'exit_code': completed.returncode,
            'log': str(path.relative_to(ROOT)), 'sha256': digest(path),
            'summary': completed.stdout.strip().splitlines()[-1]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true', help='After history, run compile/full pytest once and freeze on PASS.')
    args = parser.parse_args(argv)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = preserved_hashes()
    session = check_integration_baseline()
    frozen_market = ROOT / 'data/analysis/audit/market_v1_regression.json'
    market_evidence = json.loads(frozen_market.read_text())
    assert market_evidence['production_classifier_v1_frozen']
    assert all(market_evidence['gates'].values())
    # Only the downstream graph changed. Reuse frozen upstream evidence by hash.
    for name in ('src/analysis/market_rules.py', 'src/analysis/ai_eval_jobs.py',
                 'src/analysis/classification.py', 'src/analysis/lifecycle.py', 'src/analysis/source_health.py'):
        assert digest(ROOT / name) == market_evidence['source_provenance']['file_sha256'][name], name
    print('Historical validation started (local clean + canonical events).', flush=True)
    report = historical_validation()
    print('Historical validation: PASS', flush=True)
    report.update(trend_version='trend_v1_candidate', frozen=False, session_baseline=session,
                  upstream_versions=pipeline.load_settings()[1],
                  upstream_frozen_evidence={'path': str(frozen_market.relative_to(ROOT)), 'sha256': digest(frozen_market)},
                  source_sha256={name: digest(ROOT / name) for name in SOURCE_FILES})
    if args.freeze:
        report['compileall'] = run_gate('compileall', [sys.executable, '-m', 'compileall', 'src', 'tests'])
        report['full_pytest'] = run_gate('full_pytest', [sys.executable, '-m', 'pytest', '-q'])
    assert preserved_hashes() == before, 'UPSTREAM_OR_HISTORICAL_DATA_CHANGED'
    report['upstream_hashes'] = {'before': before, 'after': preserved_hashes(), 'unchanged': True}
    if args.freeze:
        settings_path = ROOT / 'configs/analysis/versions.yaml'
        text = settings_path.read_text()
        settings = yaml.safe_load(text)
        assert settings['trend']['version'] in {'trend_v1_candidate', 'trend_v1'}
        # Version activation only: no upstream setting changes and no rule edits.
        settings_path.write_text(text.replace('version: trend_v1_candidate', 'version: trend_v1'))
        for folder in ('snapshots', 'comparisons'):
            for path in sorted((OUTPUT / folder).glob('*.json')):
                artifact = json.loads(path.read_text())
                if artifact.get('snapshot_date') in DATES or (
                    artifact.get('from_date') in DATES and artifact.get('to_date') in DATES):
                    artifact['trend_version'] = 'trend_v1'
                    write_json_atomic(path, artifact)
        report.update(trend_version='trend_v1', frozen=True)
    write_json_atomic(OUTPUT / 'validation_v1.json', report)
    print(json.dumps({'dates': DATES, 'invariants': 'PASS', 'trend_version': report['trend_version'],
                      'frozen': report['frozen'], 'upstream_modified': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
