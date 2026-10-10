"""Offline authority/identity contracts for the official report entrypoint."""
import json
from pathlib import Path

import pytest

from src.analysis import ai_eval_jobs as report
from src.analysis.classification import classify_record
from src.analysis.source_health import Health

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
