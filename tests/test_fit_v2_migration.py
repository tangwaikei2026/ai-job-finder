"""The approved security-business delta must not rewrite other frozen labels."""
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.analysis.ai_eval_regression import (
    FIT_MIGRATION, RegressionDataIntegrityError, load_fit_migration,
    load_frozen_regression_cases,
)

FROZEN = Path('tests/fixtures/ai_eval_regression_set_v1_117_frozen.yaml')
CASE_ID = 'REG-fced04cbcd0cb744'


def test_only_authorized_case_changes_and_original_is_retained():
    cases = load_frozen_regression_cases(FROZEN)
    before = deepcopy(cases)
    delta = load_fit_migration(FROZEN, cases)
    assert cases == before
    assert sum(c['expected_career_pool'] == 'P1' for c in cases) == 66
    assert set(delta) == {CASE_ID}
    assert delta[CASE_ID] == dict(ai_relation='none', career_pool='X', reason_codes=['domain_security'])
    original = next(c for c in cases if c['case_id'] == CASE_ID)
    assert original['expected_career_pool'] == 'P1'
    assert original['expected_ai_relation'] == 'ai_for_testing'


@pytest.mark.parametrize('damage', ['content', 'before', 'identity', 'source', 'unauthorized'])
def test_migration_rejects_changed_content_or_unapproved_expectations(tmp_path, damage):
    cases = load_frozen_regression_cases(FROZEN)
    doc = yaml.safe_load(FIT_MIGRATION.read_text())
    if damage == 'content':
        next(c for c in cases if c['case_id'] == CASE_ID)['description'] += 'changed'
    elif damage == 'before':
        doc['migrations'][CASE_ID]['before']['career_pool'] = 'P2'
    elif damage == 'identity':
        doc['migrations'][CASE_ID]['job_id'] = 'other'
    elif damage == 'source':
        doc['legacy_fixture_sha256'] = 'changed'
    else:
        other = next(c for c in cases if c['case_id'] != CASE_ID)
        doc['migrations'][other['case_id']] = dict(
            job_id=other['job_id'], content_sha256=other['content_sha256'],
            evidence=other['description'], before={'career_pool': other['expected_career_pool']},
            after={'career_pool': 'X'})
    path = tmp_path / 'migration.yaml'
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(RegressionDataIntegrityError):
        load_fit_migration(FROZEN, cases, path)


def test_duplicate_migration_keys_rejected(tmp_path):
    path = tmp_path / 'duplicate.yaml'
    path.write_text('version: one\nversion: two\n')
    with pytest.raises(ValueError, match='DUPLICATE_YAML_KEY'):
        load_fit_migration(FROZEN, [], path)
