"""Synthetic absence/recovery contracts; never read or rewrite production history."""
import json
from copy import deepcopy

import pytest

from src.analysis.ai_eval_jobs import job_content_sha256
from src.analysis.lifecycle import Lifecycle
from src.analysis.pipeline import replay
from src.analysis.source_health import SourceHealth
from src.models import CollectionManifest, RawJobPosting
from test_market_pipeline import job, observe, write_day

UNRELIABLE = dict(status='error', complete=False, stopped_by='worker_budget_exhausted',
                  error='meituan worker: budget_exhausted')


@pytest.mark.parametrize('reliable_gap', [False, True])
@pytest.mark.parametrize('reliable_return', [False, True])
def test_reappearance_requires_reliable_absence(reliable_gap, reliable_return):
    life = Lifecycle()
    observe(life, '2026-01-01', [job()])
    gap = observe(life, '2026-01-02', [], **({} if reliable_gap else UNRELIABLE))
    saved_audit = deepcopy(gap)
    assert gap[0]['event_type'] == 'MISSING'
    # The first reliable absence is also provisional: event_status alone is not proof.
    assert gap[0]['event_status'] == 'provisional'
    assert ('RELIABLE_ABSENCE' in gap[0]['reason_codes']) is reliable_gap
    assert life.state[('test', 'a')].missing_streak == int(reliable_gap)
    returned = observe(life, '2026-01-03', [job()], **({} if reliable_return else UNRELIABLE))
    if reliable_gap:
        assert [e['event_type'] for e in returned] == ['REAPPEARED']
        assert returned[0]['event_status'] == ('confirmed' if reliable_return else 'provisional')
    else:
        assert returned == []
    assert gap == saved_audit
    state = life.state[('test', 'a')]
    assert not state.missing and not state.removed and state.missing_streak == 0
    assert observe(life, '2026-01-04', [job()]) == []


@pytest.mark.parametrize('changed', [False, True])
@pytest.mark.parametrize('reliable_return', [False, True])
def test_content_changes_still_follow_existing_reliability(changed, reliable_return):
    life = Lifecycle()
    original = job()
    current = dict(original, requirements='Python 与 RAG') if changed else original
    observe(life, '2026-01-01', [original])
    prior_sha = life.state[('test', 'a')].reliable_sha
    observe(life, '2026-01-02', [], **UNRELIABLE)
    events = observe(life, '2026-01-03', [current], **({} if reliable_return else UNRELIABLE))
    assert [e['event_type'] for e in events] == (['UPDATED'] if changed and reliable_return else [])
    if events:
        assert events[0]['event_status'] == 'confirmed'
        assert events[0]['previous_sha256'] == prior_sha
        assert events[0]['current_sha256'] == job_content_sha256(current)
    assert not life.state[('test', 'a')].missing
    if not reliable_return:
        assert life.state[('test', 'a')].reliable_sha == prior_sha
    later = observe(life, '2026-01-04', [current])
    assert [e['event_type'] for e in later] == (['UPDATED'] if changed and not reliable_return else [])
    assert observe(life, '2026-01-05', [current]) == []


def test_repeated_unreliable_gaps_do_not_accumulate_changes():
    life = Lifecycle()
    observe(life, '2026-01-01', [job()])
    for day in range(2, 7):
        events = observe(life, f'2026-01-{day:02}', [], **UNRELIABLE)
        assert len(events) == 1 and events[0]['event_type'] == 'MISSING'
        assert events[0]['event_status'] == 'provisional'
        assert 'SOURCE_UNRELIABLE' in events[0]['reason_codes']
        assert life.state[('test', 'a')].missing_streak == 0
    assert observe(life, '2026-01-07', [job()], **UNRELIABLE) == []
    assert observe(life, '2026-01-08', [job()]) == []
    observe(life, '2026-01-09', [], **UNRELIABLE)
    assert observe(life, '2026-01-10', [job()]) == []
    assert not life.state[('test', 'a')].missing


@pytest.mark.parametrize('gaps', [(True, False), (False, True), (False, True, False), (True, True)])
def test_reliable_absence_evidence_is_not_erased_by_unreliable_gaps(gaps):
    life = Lifecycle()
    observe(life, '2026-01-01', [job()])
    for day, reliable in enumerate(gaps, 2):
        observe(life, f'2026-01-{day:02}', [], **({} if reliable else UNRELIABLE))
    events = observe(life, '2026-01-08', [job()])
    assert [e['event_type'] for e in events] == ['REAPPEARED']
    assert events[0]['event_status'] == 'confirmed'
    assert not life.state[('test', 'a')].removed


@pytest.mark.parametrize('reliable_return', [False, True])
def test_original_worker_merge_gate_synthetic_fixture(reliable_return):
    # Exact RawJobPosting and manifest inputs from the original merge-gate probe.
    # Keep the old MISSING audit/hash; only the newly approved recovery rule changes.
    row = RawJobPosting(platform='meituan', job_id='offline-1', title='工程师', company='美团',
                        description='offline confirmed content', scraped_at='2026-01-01 10:00:00').to_dict()
    def health(rows, complete):
        manifest = CollectionManifest(platform='meituan', name='美团',
            status='success' if complete else 'error', complete=complete, source_total=1,
            expected_pages=1, pages_fetched=int(bool(rows)), records_fetched=len(rows),
            jobs_mapped=len(rows), jobs_in_scope=len(rows),
            stopped_by='source_total_reached' if complete else 'worker_budget_exhausted',
            error='' if complete else 'meituan worker: budget_exhausted')
        return SourceHealth({'platforms': [manifest.to_dict()], 'job_count': len(rows)}, rows)
    life = Lifecycle()
    life.observe('2026-01-01', [row], health([row], True))
    gap = life.observe('2026-01-02', [], health([], False))
    assert gap[0]['event_type'] == 'MISSING' and gap[0]['event_status'] == 'provisional'
    assert gap[0]['previous_sha256'] == 'e581f7df089e024d084a7efe998b50c20b360ea4eb95c20f6ffdaeb57875ed1e'
    assert gap[0]['reason_codes'] == [
        'SOURCE_UNRELIABLE', 'SOURCE_ERROR', 'LIST_PAGES_INCOMPLETE',
        'LIST_RECORDS_INCOMPLETE', 'SOURCE_INCOMPLETE', 'UNVERIFIED_STOP_REASON']
    assert life.observe('2026-01-03', [row], health([row], reliable_return)) == []
    assert not life.state[('meituan', 'offline-1')].missing


@pytest.mark.parametrize('reliable_gap', [False, True])
@pytest.mark.parametrize('changed', [False, True])
def test_warmup_and_canonical_trends_agree(tmp_path, reliable_gap, changed):
    target, anchor = job(), job('anchor')
    current = dict(target, requirements='Python 与 RAG') if changed else target
    write_day(tmp_path, '2026-01-01', [target, anchor])
    write_day(tmp_path, '2026-01-02', [anchor], **({} if reliable_gap else UNRELIABLE))
    write_day(tmp_path, '2026-01-03', [current, anchor])
    source_files = list((tmp_path/'raw').glob('*')) + list((tmp_path/'clean').glob('*'))
    before = {p: p.read_bytes() for p in source_files}
    replay('2026-01-01', '2026-01-03', data_dir=tmp_path)
    event_path = tmp_path/'analysis/events/2026-01-03.jsonl'
    events = [json.loads(line) for line in event_path.read_text().splitlines()]
    expected = (['REAPPEARED'] if reliable_gap else []) + (['UPDATED'] if changed else [])
    assert [e['event_type'] for e in events] == expected
    assert all(e['event_status'] == 'confirmed' for e in events)
    gap_path = tmp_path/'analysis/events/2026-01-02.jsonl'
    gap_bytes = gap_path.read_bytes()
    assert json.loads(gap_bytes)['event_type'] == 'MISSING'
    warm = replay('2026-01-03', '2026-01-03', data_dir=tmp_path, output_dir=tmp_path/'warm')
    assert warm['warmup_dates'] == ['2026-01-01', '2026-01-02']
    assert (tmp_path/'warm/events/2026-01-03.jsonl').read_bytes() == event_path.read_bytes()
    relative = 'trends/snapshots/2026-01-03.json'
    snapshot = json.loads((tmp_path/'analysis'/relative).read_text())
    assert json.loads((tmp_path/'warm'/relative).read_text()) == snapshot
    metrics = snapshot['platforms']['test']['metrics']
    assert metrics['reappeared_jobs'] == int(reliable_gap)
    assert metrics['updated_jobs'] == int(changed)
    assert metrics['new_jobs'] == metrics['removed_jobs'] == 0
    # Trend-only consumes the newly generated synthetic ledger; never rewrites it.
    replay('2026-01-01', '2026-01-03', data_dir=tmp_path,
           output_dir=tmp_path/'trend-only', trend_only=True)
    assert json.loads((tmp_path/'trend-only'/relative).read_text()) == snapshot
    assert gap_path.read_bytes() == gap_bytes
    assert before == {p: p.read_bytes() for p in source_files}
