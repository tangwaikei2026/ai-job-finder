from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.analysis.known_limitations import DEFAULT_REGISTRY, load_known_limitations


LIMITATION_ID = 'didi_dynamic_offset_pagination_v1'
ALLOWED_REASONS = {
    'dynamic_total',
    'dynamic_page1',
    'duplicate_pagination',
    'unique_deficit',
}
REFERENCE = '964eeb8d3b482a3c9921c04ab77d75e3dc829943'


def test_didi_known_limitation_registry_contract():
    registry = load_known_limitations()

    assert registry['version'] == 1
    matches = [row for row in registry['limitations'] if row['id'] == LIMITATION_ID]
    assert len(matches) == 1
    limitation = matches[0]
    assert limitation['platform'] == 'didi'
    assert limitation['category'] == 'SOURCE_DYNAMIC_PAGINATION_LIMITATION'
    assert limitation['status'] == 'active'
    assert set(limitation['allowed_reasons']) == ALLOWED_REASONS
    assert limitation['review_cadence_days'] == 90
    assert limitation['review_after'] == '2026-12-13'
    assert limitation['reference'] == {'type': 'git_commit', 'value': REFERENCE}
    assert not {'request_error', 'incomplete_list', 'detail_errors'} & set(limitation['allowed_reasons'])


def _write_registry(path: Path, registry: dict) -> None:
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding='utf-8')


@pytest.mark.parametrize(
    'mutation',
    [
        lambda registry: registry['limitations'][0].pop('platform'),
        lambda registry: registry['limitations'][0].pop('id'),
        lambda registry: registry['limitations'][0].update(allowed_reasons=[]),
        lambda registry: registry['limitations'][0].update(allowed_reasons=['future_unknown_reason']),
        lambda registry: registry['limitations'][0].update(allowed_reasons=['request_error']),
        lambda registry: registry['limitations'][0].update(allowed_reasons=['incomplete_list']),
        lambda registry: registry['limitations'][0].update(allowed_reasons=['detail_errors']),
        lambda registry: registry['limitations'][0].update(review_after='2026-02-30'),
        lambda registry: registry['limitations'][0].pop('reference'),
        lambda registry: registry['limitations'][0]['reference'].update(value='964eeb8'),
        lambda registry: registry['limitations'].append(deepcopy(registry['limitations'][0])),
    ],
    ids=[
        'missing-platform',
        'missing-id',
        'empty-reasons',
        'unknown-reason',
        'request-error',
        'incomplete-list',
        'detail-errors',
        'invalid-review-date',
        'missing-reference',
        'malformed-commit',
        'duplicate-id',
    ],
)
def test_invalid_registry_fails_closed(tmp_path, mutation):
    registry = yaml.safe_load(DEFAULT_REGISTRY.read_text(encoding='utf-8'))
    mutation(registry)
    path = tmp_path / 'known_limitations.yaml'
    _write_registry(path, registry)

    with pytest.raises(ValueError, match='INVALID_KNOWN_LIMITATION_REGISTRY'):
        load_known_limitations(path)
