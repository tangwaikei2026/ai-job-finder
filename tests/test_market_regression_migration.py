"""Versioned legacy deltas cannot hide a changed JD or new classifier failure."""
from copy import deepcopy
from pathlib import Path

import pytest

from src.analysis import ai_eval_regression as regression
from src.analysis.ai_eval_jobs import classify_market

FIXTURE = Path('tests/fixtures/ai_eval_regression_set_v1_117_frozen.yaml')
MIGRATION = Path('tests/fixtures/ai_eval_market_v1_migration.yaml')


@pytest.fixture(scope='module')
def loaded():
    cases = regression.load_frozen_regression_cases(FIXTURE)
    return cases, regression.load_market_migration(MIGRATION, cases)


def test_versioned_owner_only_migrates_fifteen_existing_failures(loaded):
    cases, (legacy, migrations, oracle) = loaded
    assert len(migrations) == 15
    assert len(oracle) == 60
    assert len(cases) == 117
    assert sum('oracle' in e for e in migrations.values()) == 1
    assert sum(e['proof'] == 'FROZEN_CONTRACT_STOP_SEMANTICS' for e in migrations.values()) == 3
    assert legacy['source'] == FIXTURE.name


def test_content_change_rejected_before_scoring(loaded):
    cases, (_, migrations, _) = loaded
    damaged = deepcopy(cases)
    next(c for c in damaged if c['case_id'] in migrations)['description'] += 'changed'
    with pytest.raises(regression.RegressionDataIntegrityError, match='content binding'):
        regression.load_market_migration(MIGRATION, damaged)


def test_duplicate_migration_keys_rejected(tmp_path):
    path = tmp_path / 'duplicate.yaml'
    path.write_text('version: x\nversion: y\n')
    with pytest.raises(ValueError, match='DUPLICATE_YAML_KEY'):
        regression.load_market_migration(path, [])


def test_p01_references_oracle_and_stop_preserves_scope_assertion(loaded):
    _, (_, migrations, _) = loaded
    expected = dict(in_scope=False, role_family='qa_test', ai_relation='ai_context_only',
                    seniority_level='mid', reason_codes=['legacy'])
    stop = next(e for e in migrations.values() if e['proof'] == 'FROZEN_CONTRACT_STOP_SEMANTICS')
    actual = regression.migrate_market_expectation(expected, stop)
    assert actual == dict(in_scope=False, role_family=None, ai_relation=None,
                         seniority_level='mid', market_relevance=None, secondary_role_families=[])
    p01 = next(e for e in migrations.values() if 'oracle' in e)
    assert 'replace' not in p01
    assert regression.migrate_market_expectation(expected, p01)['role_family'] == 'evaluation_engineering'


def test_migrated_case_still_detects_wrong_label(monkeypatch, loaded):
    import src.analysis.ai_eval_jobs as jobs
    cases, (overlay, migrations, _) = loaded
    cid = next(cid for cid, entry in migrations.items() if 'replace' in entry)
    case = next(c for c in cases if c['case_id'] == cid)
    one = deepcopy(overlay)
    one['market_reason_cases'] = {code: [cid] for code, ids in one['market_reason_cases'].items() if cid in ids}
    monkeypatch.setattr(regression, 'load_frozen_regression_cases', lambda _: [case])
    monkeypatch.setattr(regression, 'load_market_migration', lambda *_: (one, {cid: migrations[cid]}, None))
    wrong = classify_market(case)
    wrong['ai_relation'] = 'core_ai_evaluation'
    monkeypatch.setattr(jobs, 'classify_market', lambda _: wrong)
    result = regression.run_split_regression(FIXTURE, MIGRATION, suite='market')['market']
    assert result['failed'] == 1
    assert 'ai_relation' in result['failures'][0]['differences']
