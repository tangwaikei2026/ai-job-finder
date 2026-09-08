"""Bounded offline evidence export. Suggestions never feed production facts."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from src.analysis.ai_eval_jobs import AI_CONTEXT_ONLY_PATTERN, SKILL_PATTERNS
from src.analysis.lifecycle import identity


def export_bundle(day, jobs, classifications, markets, health, events, trend, previous, config):
    rows = {identity(row): row for row in classifications}
    deltas = defaultdict(list)
    for event in events:
        deltas[identity(event)].append(event)
    selected = {}
    category_totals = Counter()
    category_emitted = Counter()
    candidates = defaultdict(list)
    stop_words = {'the', 'and', 'for', 'with', 'from', 'are', 'you', 'our', 'job', 'com',
                  'http', 'https', 'www', 'that', 'this', 'will', 'have', 'your'}
    for job in sorted(jobs, key=identity):
        key = identity(job)
        row, market = rows.get(key), markets[key]
        resolved = health.resolve(key[0], str(job.get('company', '')), job)
        categories = []
        event_types = {event['event_type'] for event in deltas[key]}
        if row and event_types & {'NEW', 'UPDATED'}:
            categories.append('NEW_OR_UPDATED_MARKET')
        if (row and row['classification_status'] == 'review_required') or not resolved.content_reliable:
            categories.append('REVIEW_REQUIRED')
        if row and (row['career_pool'] in {'X', 'REF'} or row['classification_status'] == 'carried_forward'):
            categories.append('RULE_BOUNDARY')
        if not market['in_scope'] and AI_CONTEXT_ONLY_PATTERN.search(str(job.get('title', ''))):
            categories.append('NEAR_MISS')
        if market['in_scope'] and resolved.content_reliable:
            body = '\n'.join(str(job.get(field, '')) for field in ('title', 'description', 'requirements'))
            # Remove recognized ontology spans before extracting candidate tokens.
            for _, pattern in SKILL_PATTERNS:
                body = pattern.sub(' ', body)
            tokens = {token.casefold() for token in re.findall(r'(?<!\w)[A-Za-z][A-Za-z0-9+.#-]{2,}(?!\w)', body)}
            for token in tokens - stop_words:
                candidates[token].append({'platform': key[0], 'job_id': key[1], 'company': job.get('company', '')})
        for category in categories:
            category_totals[category] += 1
            if category_emitted[category] >= config['max_per_category']:
                continue
            if key not in selected and len(selected) >= config['max_jobs']:
                continue
            if key not in selected:
                selected[key] = {
                    **{field: job.get(field, '') for field in ('platform', 'job_id', 'company', 'title', 'description', 'requirements')},
                    'categories': [], 'current_classification': row,
                    'reason_codes': row['reason_codes'] if row else {'market': market['reason_codes'], 'fit': []},
                    'evidence': row['evidence'] if row else market['evidence'],
                    'source_health_reason_codes': list(resolved.reason_codes),
                    'deterministic_delta': deltas[key],
                }
            selected[key]['categories'].append(category)
            category_emitted[category] += 1
    anomalies = []
    if previous:
        for field in ('company', 'role_family'):
            old = Counter(row[field] for row in previous['classifications'])
            new = Counter(row[field] for row in classifications)
            for key in sorted(old.keys() | new.keys()):
                delta = new[key] - old[key]
                if abs(delta) >= 3 and abs(delta) / max(old[key], 1) >= .25:
                    anomalies.append(dict(dimension=field, value=key, previous=old[key], current=new[key], delta=delta))
        old = Counter(tag for row in previous['classifications'] for tag in row['skill_tags'])
        new = Counter(tag for row in classifications for tag in row['skill_tags'])
        for key in sorted(old.keys() | new.keys()):
            if abs(new[key] - old[key]) >= 3 and abs(new[key] - old[key]) / max(old[key], 1) >= .25:
                anomalies.append(dict(dimension='skill', value=key, previous=old[key], current=new[key], delta=new[key]-old[key]))
    return dict(
        snapshot_date=day, versions=trend['versions'],
        policy='Suggestions only: human review -> accepted rule change -> regression update -> version bump -> replay. No automatic rule, taxonomy, ontology or KPI writes.',
        jobs=list(selected.values()), selection_totals=dict(category_totals), exported_by_category=dict(category_emitted),
        truncated=len(selected) >= config['max_jobs'] or any(category_totals[k] > category_emitted[k] for k in category_totals),
        skill_candidates=[dict(term=term, job_count=len(refs), company_breadth=len({ref['company'] for ref in refs}), examples=refs[:3])
                          for term, refs in sorted(candidates.items(), key=lambda item: (-len(item[1]), item[0]))
                          if len(refs) >= config['candidate_min_mentions']][:40],
        anomalies=anomalies[:40], anomaly_basis='observed counts; not validated market growth',
        trend_coverage=trend['coverage'],
    )
