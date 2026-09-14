"""Compact market classifications. Existing clean snapshots remain the JD source."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from src.analysis.ai_eval_jobs import (
    classify_market, classify_personal_fit, classify_skills, job_content_sha256,
)
from src.analysis.source_health import Health
from src.analysis.market_rules import validate_market_output

CLASSIFICATION_STATUSES = frozenset({'fresh', 'carried_forward', 'review_required'})


def market_classification_reliable(row: Mapping[str, Any]) -> bool:
    """Fit/skill replay needs must not erase a reliable inherited market fact."""
    return row['classification_status'] != 'review_required' or (
        'CONTENT_CARRIED_FORWARD' in row['reason_codes']['market']
        and row['reason_codes']['fit'] == ['REPLAY_REQUIRED']
    )


def classify_record(day: str, job: Mapping[str, Any], health: Health,
                    versions: Mapping[str, str], previous: Mapping[str, Any] | None = None):
    market = classify_market(job)
    previous_schema_valid = False
    if previous:
        try:
            validate_market_output(previous)
            previous_schema_valid = True
        except ValueError:
            pass  # A same-version legacy row must not bypass the current schema.
    failure = bool({'DETAIL_FAILED_JOB_ID', 'PROBABLE_DETAIL_FAILURE'} & set(health.reason_codes))
    if not health.content_reliable and failure and previous_schema_valid and previous['versions']['market'] == versions['market']:
        if previous['classification_status'] in {'fresh', 'carried_forward'}:
            row = deepcopy(previous)
            row['snapshot_date'] = day
            # Hash/evidence describe the inherited reliable JD, not today's broken body.
            row['classification_status'] = 'carried_forward'
            row['reason_codes']['market'] = list(dict.fromkeys([
                *row['reason_codes']['market'], 'CONTENT_CARRIED_FORWARD']))
            if previous['versions']['fit'] != versions['fit']:
                row['classification_status'] = 'review_required'
                row['career_pool'] = None
                row['reason_codes']['fit'] = ['REPLAY_REQUIRED']
            return row, market
    if not market['in_scope']:
        return None, market
    reliable = health.content_reliable
    fit = classify_personal_fit(job, market) if reliable else {
        'career_pool': None, 'fit_reason_codes': ['INSUFFICIENT_CONTENT'],
    }
    row = {
        'snapshot_date': day,
        **{key: job.get(key, '') for key in ('platform', 'job_id', 'company', 'title', 'url')},
        'city_norm': job.get('city_norm', []),
        'content_sha256': job_content_sha256(job),
        **{key: market[key] for key in ('in_scope', 'market_relevance', 'role_family', 'secondary_role_families', 'ai_relation', 'seniority_level')},
        'career_pool': fit['career_pool'],
        'reason_codes': {'market': market['reason_codes']['market'], 'fit': fit['fit_reason_codes']},
        'evidence': market['evidence'],
        'skill_tags': classify_skills(job) if reliable else [],
        'classification_status': 'fresh' if reliable else 'review_required',
        'versions': dict(versions),
    }
    return row, market
