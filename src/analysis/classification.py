"""Compact market classifications. Existing clean snapshots remain the JD source."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from src.analysis.ai_eval_jobs import (
    classify_market, classify_personal_fit, classify_skills, job_content_sha256,
)
from src.analysis.source_health import Health

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
    failure = bool({'DETAIL_FAILED_JOB_ID', 'PROBABLE_DETAIL_FAILURE'} & set(health.reason_codes))
    if not health.content_reliable and failure and previous and previous['versions']['market'] == versions['market']:
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
        **{key: market[key] for key in ('role_family', 'ai_relation', 'seniority_level')},
        'career_pool': fit['career_pool'],
        'reason_codes': {'market': market['reason_codes'], 'fit': fit['fit_reason_codes']},
        'evidence': market['evidence'],
        'skill_tags': classify_skills(job) if reliable else [],
        'classification_status': 'fresh' if reliable else 'review_required',
        'versions': dict(versions),
    }
    return row, market
