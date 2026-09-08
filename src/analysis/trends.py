"""Derived metrics only. Block comparisons when coverage or versions differ."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Sequence

from src.analysis.classification import market_classification_reliable
from src.analysis.lifecycle import identity


def _counts(rows, field):
    return dict(sorted(Counter(row[field] for row in rows).items()))


def _skills(rows):
    mentions = Counter()
    companies = defaultdict(set)
    for row in rows:
        for tag in set(row['skill_tags']):
            mentions[tag] += 1
            companies[tag].add(row['company'])
    return mentions, companies


def aggregate_trends(history: Sequence[dict[str, Any]], window_days: int = 7) -> dict:
    if not history:
        raise ValueError('HISTORICAL_SOURCE_INCOMPLETE')
    if window_days != 7:
        raise ValueError('The fixed *_7d schema requires window_days=7')
    current = history[-1]
    as_of = date.fromisoformat(current['date'])
    baseline_date = (as_of - timedelta(days=window_days)).isoformat()
    window = [obs for obs in history if baseline_date <= obs['date'] <= current['date']]
    baseline = next((obs for obs in window if obs['date'] == baseline_date), None)
    versions = current['versions']
    reasons: set[str] = set()
    blocked: dict[tuple[str, str], set[str]] = defaultdict(set)
    expected_dates = {(as_of - timedelta(days=i)).isoformat() for i in range(window_days + 1)}
    if not expected_dates.issubset({obs['date'] for obs in window}):
        reasons.add('OBSERVATION_GAPS')
    if baseline is None:
        reasons.add('INSUFFICIENT_WINDOW_HISTORY')
    all_scopes = set().union(*(obs['health'].scopes() for obs in window))
    if any(not obs['health'].platforms for obs in window):
        reasons.add('MANIFEST_SCOPE_MISSING')
    cities = {obs['health'].cities for obs in window}
    if len(cities) > 1:
        reasons.add('SOURCE_SCOPE_CHANGED')
    for obs in window:
        health = obs['health']
        for platform, company in all_scopes:
            resolved = health.resolve(platform, company)
            if not resolved.presence_reliable or not resolved.content_reliable:
                codes = set(resolved.reason_codes)
                if not resolved.content_reliable:
                    codes.add('SOURCE_CONTENT_UNRELIABLE')
                blocked[(platform, company)].update(codes)
        if obs.get('content_unreliable_count', 0):
            reasons.add('CONTENT_COVERAGE_INCOMPLETE')
        if any(not market_classification_reliable(row) for row in obs['classifications']):
            reasons.add('CLASSIFICATION_REVIEW_REQUIRED')
    if blocked:
        reasons.add('SOURCE_COVERAGE_INCOMPARABLE')
    market_mismatch = any(obs['versions']['market'] != versions['market'] for obs in window)
    fit_mismatch = any(obs['versions']['fit'] != versions['fit'] for obs in window)
    skills_mismatch = any(obs['versions']['skills'] != versions['skills'] for obs in window)
    # Validate row versions too: a carried classification must not be relabelled.
    for obs in window:
        for row in obs['classifications']:
            market_mismatch |= row['versions']['market'] != versions['market']
            fit_mismatch |= row['versions']['fit'] != versions['fit']
            skills_mismatch |= row['versions']['skills'] != versions['skills']
    totals = Counter()
    # Labels are looked up at the event's observation, or the last prior JD for
    # removals. Leaving market scope removes the cached label even while present.
    labels = {}
    for obs in history:
        missing_keys = {identity(event) for event in obs['events']
                        if event['event_type'] in {'MISSING', 'REMOVED'}}
        current_keys = {identity(row) for row in obs['classifications']}
        for key in set(labels) - missing_keys - current_keys:
            labels.pop(key, None)
        labels.update({identity(row): row for row in obs['classifications']
                       if market_classification_reliable(row)})
        if not baseline_date < obs['date'] <= current['date']:
            continue
        for event in obs['events']:
            kind = event['event_type']
            row = labels.get(identity(event))
            if kind not in {'NEW', 'REMOVED'} or event['event_status'] != 'confirmed' or row is None:
                continue
            market_mismatch |= row['versions']['market'] != versions['market']
            fit_mismatch |= row['versions']['fit'] != versions['fit']
            totals[('market', kind)] += 1
            if row['career_pool'] == 'P1':
                totals[('qa_bridge', kind)] += 1

    if market_mismatch:
        reasons.update({'CLASSIFIER_VERSION_MISMATCH', 'REPLAY_REQUIRED'})
    comparable = not reasons
    qa_comparable = comparable and not fit_mismatch
    skill_comparable = comparable and not skills_mismatch
    active = [row for row in current['classifications'] if market_classification_reliable(row)]
    qa = [row for row in active if row['career_pool'] == 'P1']

    def metrics(rows, name, allowed):
        return dict(active_jobs=len(rows), new_7d=totals[(name, 'NEW')] if allowed else None,
                    removed_7d=totals[(name, 'REMOVED')] if allowed else None,
                    company_count=len({row['company'] for row in rows}))

    current_skills, breadth = _skills(active)
    old_rows = [] if baseline is None else [row for row in baseline['classifications']
                                           if market_classification_reliable(row)]
    old_skills, old_breadth = _skills(old_rows)
    previously_seen = {tag for obs in history[:-1] for row in obs['classifications'] for tag in row['skill_tags']}
    skill_rows = []
    for skill, count in sorted(current_skills.items(), key=lambda item: (-item[1], item[0])):
        share = count / len(active) if active else 0
        old_share = old_skills[skill] / len(old_rows) if old_rows else 0
        skill_rows.append(dict(skill=skill, count=count, mention_share=round(share, 6),
                               company_breadth=len(breadth[skill]),
                               change_7d=count - old_skills[skill] if skill_comparable else None,
                               mention_share_change_7d=round(share - old_share, 6) if skill_comparable else None,
                               company_breadth_change_7d=(len(breadth[skill]) - len(old_breadth[skill])) if skill_comparable else None))
    return {
        'as_of': current['date'], 'window_days': window_days, 'versions': dict(versions),
        'coverage': {
            'comparable': comparable, 'qa_bridge_comparable': qa_comparable,
            'skills_comparable': skill_comparable,
            'reason_codes': sorted(reasons),
            'qa_bridge_reason_codes': ['FIT_VERSION_MISMATCH', 'REPLAY_REQUIRED'] if fit_mismatch else [],
            'skills_reason_codes': ['SKILL_VERSION_MISMATCH', 'REPLAY_REQUIRED'] if skills_mismatch else [],
            'blocked_scopes': [dict(platform=p, company=c, reason_codes=sorted(codes))
                               for (p, c), codes in sorted(blocked.items())],
            'active_jobs_basis': 'observed_classified_identities_including_carried_forward',
        },
        'market': {**metrics(active, 'market', comparable),
                   'by_role_family': _counts(active, 'role_family'),
                   'by_ai_relation': _counts(active, 'ai_relation'), 'by_company': _counts(active, 'company')},
        'qa_bridge': {**metrics(qa, 'qa_bridge', qa_comparable),
                      'share': round(len(qa) / len(active), 6) if active else 0,
                      'by_ai_relation': _counts(qa, 'ai_relation')},
        'skills': {'top': skill_rows,
                   'rising': [row for row in skill_rows if skill_comparable and row['change_7d'] > 0
                              and row['mention_share_change_7d'] > 0 and row['company_breadth_change_7d'] > 0
                              and row['company_breadth'] > 1],
                   'newly_observed': [row for row in skill_rows if not skills_mismatch and not market_mismatch
                                      and row['skill'] not in previously_seen]},
    }
