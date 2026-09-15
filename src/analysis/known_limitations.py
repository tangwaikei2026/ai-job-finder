"""Validate the versioned known-limitation governance registry."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.collectors.didi import DidiRawCollector


DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / 'configs/analysis/known_limitations.yaml'
REGISTRY_VERSION = 1
LIMITATION_STATUSES = frozenset({'active', 'inactive'})
DIDI_CATEGORY = 'SOURCE_DYNAMIC_PAGINATION_LIMITATION'
NON_LIMITATION_REASONS = frozenset({'request_error', 'incomplete_list', 'detail_errors'})
ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_]*$')
COMMIT_PATTERN = re.compile(r'^[0-9a-f]{40}$')


def _fail(message: str) -> None:
    raise ValueError(f'INVALID_KNOWN_LIMITATION_REGISTRY: {message}')


def _validate_entry(entry: Any, seen_ids: set[str]) -> None:
    required = {
        'id', 'platform', 'category', 'status', 'allowed_reasons',
        'review_cadence_days', 'review_after', 'reference',
    }
    if not isinstance(entry, dict) or set(entry) != required:
        _fail('limitation fields must match the version 1 schema')

    limitation_id = entry['id']
    if not isinstance(limitation_id, str) or not ID_PATTERN.fullmatch(limitation_id):
        _fail('limitation id is missing or invalid')
    if limitation_id in seen_ids:
        _fail(f'duplicate limitation id: {limitation_id}')
    seen_ids.add(limitation_id)

    platform = entry['platform']
    if not isinstance(platform, str) or not ID_PATTERN.fullmatch(platform):
        _fail(f'{limitation_id} platform is missing or invalid')
    if entry['category'] != DIDI_CATEGORY or platform != 'didi':
        _fail(f'{limitation_id} uses an unsupported platform/category contract')
    if entry['status'] not in LIMITATION_STATUSES:
        _fail(f'{limitation_id} status is invalid')

    reasons = entry['allowed_reasons']
    if not isinstance(reasons, list) or not reasons:
        _fail(f'{limitation_id} allowed_reasons must be a non-empty list')
    if any(not isinstance(reason, str) for reason in reasons) or len(reasons) != len(set(reasons)):
        _fail(f'{limitation_id} allowed_reasons are invalid or duplicated')
    source_reasons = set(DidiRawCollector.REASON_PRECEDENCE)
    if set(reasons) - source_reasons:
        _fail(f'{limitation_id} contains an unknown source reason')
    if set(reasons) & NON_LIMITATION_REASONS:
        _fail(f'{limitation_id} contains a non-limitation reason')

    cadence = entry['review_cadence_days']
    if isinstance(cadence, bool) or not isinstance(cadence, int) or cadence <= 0:
        _fail(f'{limitation_id} review cadence is invalid')
    review_after = entry['review_after']
    if not isinstance(review_after, str):
        _fail(f'{limitation_id} review_after must be an ISO date string')
    try:
        if date.fromisoformat(review_after).isoformat() != review_after:
            _fail(f'{limitation_id} review_after is invalid')
    except ValueError:
        _fail(f'{limitation_id} review_after is invalid')

    reference = entry['reference']
    if not isinstance(reference, dict) or set(reference) != {'type', 'value'}:
        _fail(f'{limitation_id} reference is missing or invalid')
    if reference['type'] != 'git_commit':
        _fail(f'{limitation_id} reference type is invalid')
    if not isinstance(reference['value'], str) or not COMMIT_PATTERN.fullmatch(reference['value']):
        _fail(f'{limitation_id} git commit reference is malformed')


def load_known_limitations(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Load a registry only after its complete version 1 contract validates."""
    try:
        registry = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError) as exc:
        _fail(str(exc))
    if not isinstance(registry, dict) or set(registry) != {'version', 'limitations'}:
        _fail('root fields must be version and limitations')
    if isinstance(registry['version'], bool) or registry['version'] != REGISTRY_VERSION:
        _fail('unsupported version')
    limitations = registry['limitations']
    if not isinstance(limitations, list) or not limitations:
        _fail('limitations must be a non-empty list')
    seen_ids: set[str] = set()
    for entry in limitations:
        _validate_entry(entry, seen_ids)
    return registry
