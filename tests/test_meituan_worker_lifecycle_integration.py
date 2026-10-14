"""Offline real-worker timeout output carried through three daily observations."""
import json
from copy import deepcopy

import pytest

from src.analysis.lifecycle import Lifecycle
from src.analysis.pipeline import replay
from src.analysis.source_health import SourceHealth
from test_market_pipeline import job, manifest
from test_meituan_worker import run


@pytest.mark.parametrize('reliable_gap', [False, True])
def test_worker_absence_recovery_integrates_with_lifecycle_and_trend(tmp_path, reliable_gap):
    first = run(tmp_path/'first', 'normal')
    interrupted = run(tmp_path/'gap', 'list_hang', .65)
    restored = run(tmp_path/'restored', 'normal')
    assert interrupted.jobs == []
    assert interrupted.manifest.status == 'error'
    assert interrupted.manifest.complete is False
    audit = interrupted.manifest.metadata['worker']
    assert audit['budget_exhausted'] and audit['sigterm'] and audit['sigkill']
    # run() also proves PID disappearance, independent session, no descendants,
    # and an acquirable budget lock for every real subprocess above.
    gap_manifest = interrupted.manifest.to_dict()
    if reliable_gap:
        # Counterfactual control: verified complete list with no jobs.
        gap_manifest = manifest([], platform='meituan')['platforms'][0]
    anchor = job('anchor')
    life = Lifecycle()
    gap_health = None
    for day, result in enumerate((first, interrupted, restored), 1):
        # The transport fixture's terse JD is deliberately not market evidence.
        # Supply a realistic synthetic clean JD; pipeline.replay performs the
        # real canonical classification, without mocked labels or rule changes.
        rows = [dict(row.to_dict(), city_norm=['北京'],
                     description='负责大模型产品质量保障和评测体系建设。',
                     requirements='熟悉 Python，能够设计自动化测试与回归测试方案。')
                for row in result.jobs]
        rows.append(anchor)
        source = gap_manifest if day == 2 else result.manifest.to_dict()
        evidence = dict(job_count=len(rows), cities=['北京'], platforms=[
            source, manifest([anchor])['platforms'][0]])
        health = SourceHealth(evidence, rows)
        events = life.observe(f'2026-01-0{day}', rows, health)
        if day == 2:
            gap_health = deepcopy(health.resolve('meituan'))
            assert gap_health.presence_reliable is reliable_gap
            assert len(events) == 4
            assert all(e['event_type'] == 'MISSING' and e['event_status'] == 'provisional'
                       for e in events)
            assert all(s.missing_streak == int(reliable_gap)
                       for k, s in life.state.items() if k[0] == 'meituan')
        if day == 3:
            assert [e['event_type'] for e in events] == (['REAPPEARED']*4 if reliable_gap else [])
            assert all(e['event_status'] == 'confirmed' for e in events)
            assert all(not s.missing and not s.removed and s.missing_streak == 0
                       for s in life.state.values())
        for folder in ('clean', 'raw'):
            (tmp_path/folder).mkdir(exist_ok=True)
        (tmp_path/'clean'/f'2026-01-0{day}.json').write_text(json.dumps(rows))
        (tmp_path/'raw'/f'2026-01-0{day}_manifest.json').write_text(json.dumps(evidence))
    assert gap_health.presence_reliable is reliable_gap
    if not reliable_gap:
        assert 'SOURCE_ERROR' in gap_health.reason_codes
    replay('2026-01-01', '2026-01-03', data_dir=tmp_path)
    classified = [json.loads(line) for line in
                  (tmp_path/'analysis/classification/2026-01-03.jsonl').read_text().splitlines()]
    market_rows = [row for row in classified if row['platform'] == 'meituan']
    assert {row['job_id'] for row in market_rows} == {'0', '1', '2', '3'}
    assert all(row['in_scope'] is True and row['classification_status'] == 'fresh'
               for row in market_rows)
    events = [json.loads(line) for line in
              (tmp_path/'analysis/events/2026-01-03.jsonl').read_text().splitlines()]
    assert [e['event_type'] for e in events] == (['REAPPEARED']*4 if reliable_gap else [])
    snapshot = json.loads((tmp_path/'analysis/trends/snapshots/2026-01-03.json').read_text())
    metrics = snapshot['platforms']['meituan']['metrics']
    assert metrics['active_jobs'] == 4
    assert metrics['reappeared_jobs'] == (4 if reliable_gap else 0)
    assert metrics['new_jobs'] == metrics['removed_jobs'] == metrics['updated_jobs'] == 0
    saved = json.loads((tmp_path/'raw/2026-01-02_manifest.json').read_text())['platforms'][0]
    assert saved == gap_manifest
