"""Offline authority/identity contracts for the official report entrypoint."""
import json
from pathlib import Path

import pytest

from src.analysis import ai_eval_jobs as report
from src.analysis.classification import classify_record
from src.analysis.source_health import Health
from tests.test_invocation import execution  # noqa: F401

DAY = '2026-10-09'
VERSIONS = dict(market='market_v1', fit='fit_v2', skills='skills_v1')


def job(job_id='1', **updates):
    source = json.loads((Path(__file__).parent / 'fixtures/classification_targeted_20261009.json').read_text())[0]
    return dict(source, **dict(dict(platform='test', job_id=job_id, location='深圳',
                                   url=f'https://example.test/{job_id}'), **updates))


def canonical(j):
    row, _ = classify_record(DAY, j, Health(True, True, ()), VERSIONS)
    assert row['career_pool'] in {'P1', 'P2'}
    return row


def setup(tmp_path, jobs, rows):
    source = tmp_path / 'clean' / f'{DAY}.json'
    source.parent.mkdir(exist_ok=True)
    source.write_text(json.dumps(jobs))
    artifact = tmp_path / 'analysis' / 'classification' / f'{DAY}.jsonl'
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return source, artifact


def run(tmp_path, source, **kwargs):
    return report.run_analysis(source, output_dir=tmp_path / 'output',
                               config_path=tmp_path / 'unused.yaml', **kwargs)


def test_identity_grouping_authority_and_skill_denominator(tmp_path, monkeypatch):
    a, b = job(), job('2')
    # Same ID on another platform is also a separate identity.
    c = dict(a, platform='other', url='https://other.test/1')
    excluded = job('market-excluded')
    rows = [canonical(j) for j in (a, b, c)]
    source, _ = setup(tmp_path, [a, b, a, c, excluded], rows + [rows[0]])
    def forbidden(*args, **kwargs):
        raise AssertionError('Official reports must not call legacy selection/classification')
    for name in ('classify_body_primary_ai_evaluation', 'explain_job_selection', 'explain_job_exclusion'):
        monkeypatch.setattr(report, name, forbidden)
    _, md, result = run(tmp_path, source)
    assert result['manifest']['selected_job_count'] == 3
    assert result['manifest']['display_group_count'] == 1
    assert result['manifest']['source_unique_identity_count'] == 4
    assert len(result['shenzhen_candidates']) == 3
    assert len(result['display_groups'][0]['jobs']) == 3
    assert result['skills'] and all(r['count'] == 3 and r['share'] == 1 for r in result['skills'])
    assert {r['url'] for r in result['matched_jobs']} == {a['url'], b['url'], c['url']}
    for row in result['matched_jobs']:
        expected = next(r for r in rows if (r['platform'], r['job_id']) == (row['platform'], row['job_id']))
        for key in ('career_pool', 'role_family', 'reason_codes', 'classification_status'):
            assert row[key] == expected[key]
    assert '真实岗位数：3' in md.read_text() and '展示分组数：1' in md.read_text()
    hits = Path(result['manifest']['raw_matches_report_file']).read_text()
    for j in (a, b, c):
        assert j['url'] in hits and j['description'].splitlines()[0] in hits
    details = [json.loads(line) for line in Path(result['manifest']['raw_matches_jsonl_file']).read_text().splitlines()]
    assert all(row['description'] == a['description'] for row in details)


@pytest.mark.parametrize('location,title,count,conflict', [
    ('深圳', 'AI测试工程师', 1, False),
    ('北京', 'AI测试工程师（深圳）', 1, True),
    ('深圳', 'AI测试工程师（北京）', 1, True),
    ('北京', 'AI测试工程师', 0, False),
    ('非深圳', 'AI测试工程师（深圳）', 0, False),
])
def test_city_uses_frozen_matcher(tmp_path, location, title, count, conflict):
    j = job(location=location, title=title)
    source, _ = setup(tmp_path, [j], [canonical(j)])
    _, _, result = run(tmp_path, source)
    assert len(result['shenzhen_candidates']) == count
    if count:
        assert result['shenzhen_candidates'][0]['candidate_city_match']['location_conflict'] == conflict


@pytest.mark.parametrize('failure,expected', [
    ('missing', 'CANONICAL_MISSING'), ('date', 'CANONICAL_DATE_MISMATCH'),
    ('filename', 'CANONICAL_DATE_MISMATCH'), ('identity', 'CANONICAL_IDENTITY_UNLINKED'),
    ('content', 'CANONICAL_CONTENT_MISMATCH'), ('status', 'CANONICAL_STATUS_INVALID'),
    ('review', 'CANONICAL_CANDIDATE_UNRESOLVED'), ('conflict', 'CLEAN_IDENTITY_CONFLICT'),
])
def test_fail_closed_before_writing(tmp_path, failure, expected):
    j = job()
    row = canonical(j)
    if failure == 'date': row['snapshot_date'] = '2026-10-08'
    if failure == 'identity': row['job_id'] = 'absent'
    if failure == 'content': row['content_sha256'] = 'wrong'
    if failure == 'status': row['classification_status'] = 'invalid'
    if failure == 'review': row['classification_status'] = 'review_required'
    jobs = [j, dict(j, title='conflict')] if failure == 'conflict' else [j]
    source, artifact = setup(tmp_path, jobs, [row])
    if failure == 'missing': artifact.unlink()
    if failure == 'filename': artifact = artifact.rename(artifact.with_name('2026-10-08.jsonl'))
    with pytest.raises(ValueError, match=expected):
        run(tmp_path, source, canonical_path=artifact)
    assert not (tmp_path / 'output').exists()


def test_carried_forward_preserves_evidence_and_never_reclassifies(tmp_path):
    j = job()
    row = canonical(j)
    row['classification_status'] = 'carried_forward'
    row['reason_codes']['market'].append('CONTENT_CARRIED_FORWARD')
    row['reason_codes']['fit'].append('DETAIL_VERIFICATION_REQUIRED')
    source, _ = setup(tmp_path, [dict(j, description='', requirements='')], [row])
    result = run(tmp_path, source)[2]
    assert result['manifest']['selected_job_count'] == 1
    assert result['matched_jobs'][0]['content_sha256'] == row['content_sha256']
    assert result['matched_jobs'][0]['reason_codes'] == row['reason_codes']


def test_other_pools_unknown_and_empty_canonical_do_not_enter(tmp_path):
    jobs, rows = [], []
    for i, pool in enumerate(('REF', 'X', None)):
        j = job(str(i)); row = canonical(j)
        row['career_pool'] = pool
        if pool is None: row['classification_status'] = 'review_required'
        jobs.append(j); rows.append(row)
    source, artifact = setup(tmp_path, jobs, rows)
    assert run(tmp_path, source)[2]['manifest']['selected_job_count'] == 0
    artifact.write_text('')
    assert run(tmp_path, source)[2]['manifest']['selected_job_count'] == 0


def test_exploration_is_explicit_and_namespaced(tmp_path):
    source, _ = setup(tmp_path, [job()], [])
    config = tmp_path / 'config.yaml'
    config.write_text('platforms:\n  test:\n    enabled: true\n    name: test\n')
    path, _, result = report.run_analysis(source, config_path=config, output_dir=tmp_path / 'output', exploratory=True)
    assert '_exploratory_ai_eval_' in path.name
    assert result['manifest']['report_mode'] == 'exploratory_noncanonical'
    assert not (tmp_path / 'output' / f'{DAY}_ai_eval_analysis.json').exists()


@pytest.fixture
def published_candidates(execution, monkeypatch):
    """Two Shenzhen candidates with a consistent modern publication proof."""
    from dataclasses import fields
    from src import main as collector
    from src.invocation import read, validate_analysis
    from src.models import CollectionManifest, RawJobPosting
    from tests.test_invocation import DAY as day

    e = execution
    # Match the synthetic postings to the declared source scope before any
    # manifest/config digest is produced. Only this test's temporary config changes.
    e['config'].write_text(
        'output_dir: data/raw\ncities: [深圳]\nplatforms:\n'
        '  tencent:\n    enabled: true\n    name: tencent\n'
    )
    raw_fields = {field.name for field in fields(RawJobPosting)}

    def collect(_config, selected=None):
        assert selected is None
        assert _config['cities'] == ['深圳']
        assert _config['platforms']['tencent']['enabled'] is True
        begin = e['now']
        e['now'] = e['finish']
        rows = [RawJobPosting(**{
            key: value for key, value in job(str(index), platform='tencent',
                scraped_at=e['finish']).items() if key in raw_fields
        }) for index in (1, 2)]
        assert all(posting.location == '深圳' for posting in rows)
        manifest = CollectionManifest(
            platform='tencent', name='tencent', status='success', complete=True,
            source_total=2, expected_pages=1, pages_fetched=1, records_fetched=2,
            jobs_mapped=2, jobs_in_scope=2, details_fetched=2,
            stopped_by='source_total_reached', started_at=begin, finished_at=e['finish'],
        )
        return rows, [manifest]

    monkeypatch.setattr(collector, 'collect_all', collect)
    assert e['run']()[0] == 0
    data = e['root'] / 'data'
    status = read(data / 'analysis' / 'runs' / f'{day}.json')
    validate_analysis(data, day, status['invocation']['id'])
    assert read(data / 'raw' / f'{day}_manifest.json')['cities'] == ['深圳']
    canonical_path = data / 'analysis' / 'classification' / f'{day}.jsonl'
    rows = [json.loads(line) for line in canonical_path.read_text().splitlines()]
    assert len(rows) == 2 and all(row['career_pool'] in {'P1', 'P2'} for row in rows)
    return dict(execution=e, data=data, day=day, invocation=status['invocation']['id'],
                source=data / 'clean' / f'{day}.json', canonical=canonical_path)


def test_proven_modern_candidate_report_remains_usable(published_candidates, tmp_path):
    p = published_candidates
    result = report.run_analysis(p['source'], output_dir=tmp_path / 'report')[2]
    assert result['manifest']['selected_job_count'] == 2
    assert {(row['platform'], row['job_id']) for row in result['matched_jobs']} == {
        ('tencent', '1'), ('tencent', '2'),
    }


# Contract basis: Canonical authority plus the existing analysis_proof artifact
# digest. A damaged *modern published* observation is not a valid empty legacy
# Canonical input. Keep all prior legacy/empty/carried-forward tests unchanged.
@pytest.mark.parametrize('damage', [
    'truncated_classification', 'emptied_classification', 'stale_same_day_proof',
    'missing_proof', 'tampered_proof',
])
def test_modern_report_rejects_inconsistent_publication_and_preserves_output(
    published_candidates, tmp_path, damage, record_property,
):
    from src.invocation import read, validate_analysis

    p = published_candidates
    output = tmp_path / 'report'
    report.run_analysis(p['source'], output_dir=output)
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    proof_path = p['data'] / 'analysis' / 'audit' / f"{p['day']}_invocation.json"
    if damage == 'truncated_classification':
        p['canonical'].write_text(p['canonical'].read_text().splitlines()[0] + '\n')
    elif damage == 'emptied_classification':
        p['canonical'].write_text('')
    elif damage == 'stale_same_day_proof':
        # Generate a second proven same-day publication, then pair its complete
        # clean/classification with the previous invocation's stale proof. This
        # tests proof/observation mismatch, not mixed classification rows.
        from src import main as collector
        from unittest.mock import patch
        collect = collector.collect_all
        def changed_source(config, selected=None):
            jobs, manifests = collect(config, selected)
            jobs[0].url = 'https://example.test/second-invocation'
            return jobs, manifests
        prior_proof = proof_path.read_bytes()
        with patch.object(collector, 'collect_all', changed_source):
            assert p['execution']['run']()[0] == 0
        current = read(proof_path)
        assert current['invocation']['id'] != p['invocation']
        validate_analysis(p['data'], p['day'], current['invocation']['id'])
        # Simulate a partial same-date publication: keep the new classification
        # and clean, but restore the previous invocation's published proof.
        proof_path.write_bytes(prior_proof)
    elif damage == 'missing_proof':
        proof_path.unlink()
    else:
        value = read(proof_path)
        value['artifacts'][f"classification/{p['day']}.jsonl"] = '0' * 64
        proof_path.write_text(json.dumps(value))

    expected_id = read(p['data'] / 'raw' / f"{p['day']}_manifest.json")['invocation']['id']
    proof_error = (pytest.raises(FileNotFoundError) if damage == 'missing_proof'
                   else pytest.raises(ValueError, match='ANALYSIS_PROVENANCE_MISMATCH'))
    with proof_error:
        validate_analysis(p['data'], p['day'], expected_id)
    error, result = None, None
    try:
        result = report.run_analysis(p['source'], output_dir=output)[2]
    except (ValueError, OSError) as exc:
        error = str(exc)
    after = {path.name: path.read_bytes() for path in output.iterdir()}
    changed = sorted(name for name in before.keys() | after.keys()
                     if before.get(name) != after.get(name))
    record_property('damage', damage)
    record_property('report_error', error or 'NONE')
    record_property('selected_jobs', None if result is None else result['manifest']['selected_job_count'])
    record_property('changed_outputs', json.dumps(changed))
    assert error is not None and not changed, (
        f'Damaged modern publication accepted: damage={damage}, error={error!r}, '
        f'selected={None if result is None else result["manifest"]["selected_job_count"]}, '
        f'changed={changed}'
    )


def test_proven_modern_publication_without_market_rows_yields_zero_report(
    published_candidates, tmp_path, monkeypatch,
):
    """Nonempty, proven clean with no market classifications yields zero candidates.

    This is distinct from erasing classifications in a nonzero publication.
    """
    from src import main as collector
    from src.invocation import read, validate_analysis

    p = published_candidates
    collect = collector.collect_all

    def non_market_source(config, selected=None):
        jobs, manifests = collect(config, selected)
        for posting in jobs:
            posting.title = '行政助理'
            posting.description = '负责日常行政事务和办公用品采购'
            posting.requirements = '熟练使用办公软件'
        return jobs, manifests

    monkeypatch.setattr(collector, 'collect_all', non_market_source)
    assert p['execution']['run']()[0] == 0
    identifier = read(p['data'] / 'raw' / f"{p['day']}_manifest.json")['invocation']['id']
    validate_analysis(p['data'], p['day'], identifier)
    assert len(read(p['source'])) == 2
    assert p['canonical'].read_text() == ''
    result = report.run_analysis(p['source'], output_dir=tmp_path / 'report')[2]
    assert result['manifest']['selected_job_count'] == 0
