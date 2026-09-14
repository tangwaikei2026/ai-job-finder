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


# Trend V1 is the canonical machine contract. aggregate_trends above is retained
# solely for the existing seven-day audit compatibility interface.
TREND_VERSION = 'trend_v1_candidate'
SNAPSHOT_CONTRACT = 'trend_snapshot_v1'
COMPARISON_CONTRACT = 'trend_comparison_v1'
COMPARABILITY_CONTRACT = 'trend_comparability_v1'
FLOW_FIELDS = {'NEW': 'new_jobs', 'UPDATED': 'updated_jobs',
               'REMOVED': 'removed_jobs', 'REAPPEARED': 'reappeared_jobs'}
DIMENSIONS = {'by_market_relevance': 'market_relevance',
              'by_role_family': 'role_family', 'by_ai_relation': 'ai_relation',
              'by_career_pool': 'career_pool'}
NON_ADDITIVE = ('by_role_family_any', 'by_skill_tag')
METRIC_FAMILIES = ('inventory', 'presence_flow', 'content_flow')


def _share(count, denominator):
    return dict(count=count, denominator=denominator,
                share=count / denominator if denominator else None)


def _inventory(rows):
    """Rows are already unique official identities with usable classifications."""
    result = {'active_jobs': len(rows)}
    for output, field in DIMENSIONS.items():
        result[output] = _counts(rows, field)
    for key in ('core', 'adjacent'):
        result['by_market_relevance'].setdefault(key, 0)
    for key in ('P1', 'P2', 'REF', 'X'):
        result['by_career_pool'].setdefault(key, 0)
    result['by_role_family_any'] = dict(sorted(Counter(
        family for row in rows for family in {row['role_family'], *row['secondary_role_families']}
    ).items()))
    result['by_skill_tag'] = dict(sorted(Counter(
        tag for row in rows for tag in set(row['skill_tags'])).items()))
    result['hybrid_role_count'] = sum(bool(row['secondary_role_families']) for row in rows)
    result['hybrid_role_share'] = _share(result['hybrid_role_count'], len(rows))
    result['shares'] = {dimension: {name: _share(count, len(rows)) for name, count in result[dimension].items()}
                        for dimension in (*DIMENSIONS, *NON_ADDITIVE)}
    result['unique_content_versions'] = len({row['content_sha256'] for row in rows})
    result['metric_semantics'] = {**{key: 'NON_ADDITIVE' for key in NON_ADDITIVE},
                                  'unique_content_versions': 'DIAGNOSTIC_ONLY'}
    return result


def _usable(row):
    status = row.get('classification_status')
    if status == 'fresh':
        return True
    return status == 'carried_forward' and (
        'CONTENT_CARRIED_FORWARD' in row.get('reason_codes', {}).get('market', [])
        and row.get('career_pool') in {'P1', 'P2', 'REF', 'X'})


def _validate_row(row):
    # Consume the frozen field contract, without classifying or extending enums.
    from src.analysis.market_rules import AI_RELATIONS, ROLE_FAMILIES
    if type(row.get('in_scope')) is not bool:
        raise ValueError('TREND_SCHEMA_REPLAY_REQUIRED: in_scope')
    if not row['in_scope'] or not _usable(row):
        return
    if row.get('market_relevance') not in {'core', 'adjacent'}:
        raise ValueError('TREND_INVALID_MARKET_RELEVANCE')
    if row.get('role_family') not in ROLE_FAMILIES or row.get('ai_relation') not in AI_RELATIONS:
        raise ValueError('TREND_INVALID_MARKET_DIMENSION')
    if row.get('career_pool') not in {'P1', 'P2', 'REF', 'X'}:
        raise ValueError('TREND_FIT_INVARIANT_FAILED')
    for field in ('secondary_role_families', 'skill_tags'):
        if not isinstance(row.get(field), list) or not all(isinstance(x, str) and x for x in row[field]):
            raise ValueError(f'TREND_INVALID_LIST: {field}')
    if not set(row['secondary_role_families']) <= ROLE_FAMILIES:
        raise ValueError('TREND_INVALID_SECONDARY_ROLE')
    if not row.get('content_sha256') or not isinstance(row.get('company'), str):
        raise ValueError('TREND_CLASSIFICATION_INCOMPLETE')
    if not all(row.get('versions', {}).get(key) for key in ('market', 'fit', 'skills')):
        raise ValueError('TREND_CLASSIFICATION_VERSION_MISSING')


def _company_metrics(rows, flows):
    names = {row['company'] for row in rows} | {event['company'] for event in flows}
    result = {}
    for name in sorted(names):
        jobs = [row for row in rows if row['company'] == name]
        result[name] = dict(active_jobs=len(jobs),
                            core=sum(row['market_relevance'] == 'core' for row in jobs),
                            adjacent=sum(row['market_relevance'] == 'adjacent' for row in jobs),
                            P1=sum(row['career_pool'] == 'P1' for row in jobs),
                            **{field: sum(e['event_type'] == kind and e['company'] == name for e in flows)
                               for kind, field in FLOW_FIELDS.items()})
    return result


def _metrics(rows, flows):
    return {**_inventory(rows),
            **{field: sum(e['event_type'] == kind for e in flows) for kind, field in FLOW_FIELDS.items()},
            'by_company': _company_metrics(rows, flows)}


def trend_snapshot(history, *, trend_version=TREND_VERSION, removal_confirmation_runs=2):
    """Aggregate the latest observation; consume canonical events without inference.

    Earlier labels supply market membership for removals. present_keys contains
    ALL clean identities, allowing present out-of-scope jobs to invalidate labels.
    SourceHealth owns reliability; Trend only combines its booleans and scope.
    """
    from src.analysis.lifecycle import index_jobs
    from pathlib import Path
    from hashlib import sha256
    if not history:
        raise ValueError('HISTORICAL_SOURCE_INCOMPLETE')
    if removal_confirmation_runs < 2:
        raise ValueError('INVALID_LIFECYCLE_CONTRACT')
    dates = [obs['date'] for obs in history]
    if dates != sorted(set(dates)):
        raise ValueError('OBSERVATIONS_MUST_BE_STRICTLY_CHRONOLOGICAL')
    labels, known_out_of_scope = {}, set()
    for obs in history:
        indexed = index_jobs(obs['classifications'])
        for row in indexed.values():
            _validate_row(row)
        if 'present_keys' not in obs:
            raise ValueError('TREND_PRESENCE_CONTEXT_REQUIRED')
        for key in obs['present_keys']:
            labels.pop(key, None)
            known_out_of_scope.discard(key)
            row = indexed.get(key)
            job = obs.get('jobs_by_identity', {}).get(key)
            if (row is not None and not row['in_scope']) or (
                row is None and job is not None
                and obs['health'].resolve(key[0], str(job.get('company', '')), job).content_reliable
            ):
                known_out_of_scope.add(key)
        labels.update({key: row for key, row in indexed.items() if row['in_scope'] and _usable(row)})
    current = history[-1]
    health, versions = current['health'], current['versions']
    rows = [row for row in indexed.values() if row['in_scope'] and _usable(row)]
    jobs = current.get('jobs_by_identity', {})
    platforms = (set(health.platforms) | {p for p, _ in health.scopes()}
                 | {identity(row)[0] for row in indexed.values()}
                 | {identity(event)[0] for event in current['events']})
    per_platform, reliable_flows = {}, []
    diagnostics = Counter()
    for platform in sorted(platforms):
        scopes = sorted(c for p, c in health.scopes() if p == platform) or ['']
        resolved = [health.resolve(platform, company) for company in scopes]
        reasons = {family: set() for family in METRIC_FAMILIES}
        if not all(item.presence_reliable for item in resolved):
            for family in ('inventory', 'presence_flow'):
                reasons[family].add('SOURCE_PRESENCE_UNRELIABLE')
                reasons[family].update(code for item in resolved if not item.presence_reliable
                                       for code in item.reason_codes)
        if not all(item.content_reliable for item in resolved):
            reasons['content_flow'].add('SOURCE_CONTENT_UNRELIABLE')
        platform_rows = [row for row in rows if row['platform'] == platform]
        candidates = [row for row in indexed.values() if row['platform'] == platform]
        for row in candidates:
            if not _usable(row):
                reasons['inventory'].add('CLASSIFICATION_REVIEW_REQUIRED')
                diagnostics['excluded_classification_identities'] += 1
            elif row['in_scope'] and row['versions'] != versions:
                reasons['inventory'].update({'CLASSIFIER_VERSION_MISMATCH', 'REPLAY_REQUIRED'})
        # A failed detail may conceal an in-scope job that never produced a row.
        # Carry-forward is accepted only for the exact identity under its contract.
        for key, job in jobs.items():
            if key[0] != platform:
                continue
            if not health.resolve(platform, str(job.get('company', '')), job).content_reliable:
                row = indexed.get(key)
                if not row or row.get('classification_status') != 'carried_forward' or not _usable(row):
                    reasons['inventory'].add('CLASSIFICATION_COVERAGE_INCOMPLETE')
        if not jobs and not all(item.content_reliable for item in resolved):
            reasons['inventory'].add('CLASSIFICATION_COVERAGE_UNVERIFIED')
        events, seen = [], set()
        for event in current['events']:
            if event['platform'] != platform:
                continue
            kind, key = event['event_type'], identity(event)
            if kind not in FLOW_FIELDS or event['event_status'] != 'confirmed':
                diagnostics[f'{kind.lower()}_diagnostic_events'] += 1
                continue
            event_key = (key, kind)
            if event_key in seen:
                raise ValueError('TREND_DUPLICATE_CANONICAL_EVENT')
            seen.add(event_key)
            row = labels.get(key)
            family = 'content_flow' if kind == 'UPDATED' else 'presence_flow'
            if row is None:
                if key in known_out_of_scope:
                    diagnostics['out_of_scope_flow_events'] += 1
                else:
                    diagnostics['unclassified_flow_events'] += 1
                    reasons[family].add('FLOW_CLASSIFICATION_UNAVAILABLE')
                continue
            if row['versions'] != versions:
                reasons[family].update({'CLASSIFIER_VERSION_MISMATCH', 'REPLAY_REQUIRED'})
                continue
            resolved_event = health.resolve(platform, row['company'], jobs.get(key))
            allowed = resolved_event.content_reliable if kind == 'UPDATED' else resolved_event.presence_reliable
            if kind == 'UPDATED':
                allowed = allowed and row['classification_status'] == 'fresh' and bool(
                    event.get('previous_sha256') and event.get('current_sha256')
                    and event['previous_sha256'] != event['current_sha256']
                    and event['current_sha256'] == row['content_sha256'])
            if not allowed:
                reasons[family].add('UNRELIABLE_CANONICAL_EVENT_EXCLUDED')
                diagnostics[f'excluded_{kind.lower()}_events'] += 1
                continue
            events.append({**event, 'company': row['company']})
        reliable_flows.extend(events)
        per_platform[platform] = {
            'metrics': _metrics(platform_rows, events),
            'content_versions': sorted({row['content_sha256'] for row in platform_rows}),
            'source_scope': {'cities': list(health.cities), 'companies': scopes},
            'reliability': {family: {'reliable': not reasons[family], 'reason_codes': sorted(reasons[family])}
                            for family in METRIC_FAMILIES},
        }
    result = dict(artifact_type=SNAPSHOT_CONTRACT, snapshot_date=current['date'],
                  trend_version=trend_version, versions=dict(versions),
                  trend_code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                  lifecycle_contract={'owner': 'src/analysis/lifecycle.py',
                                      'code_sha256': sha256(Path(__file__).with_name('lifecycle.py').read_bytes()).hexdigest(),
                                      'removal_confirmation_runs': removal_confirmation_runs},
                  counting_unit=['platform', 'job_id'], market_universe='market.in_scope == true',
                  active_jobs_basis='observed_usable_classified_identities_including_valid_carried_forward',
                  **_metrics(rows, reliable_flows), platforms=per_platform,
                  diagnostics=dict(sorted(diagnostics.items())))
    validate_snapshot(result)
    return result


def validate_snapshot(snapshot):
    """Fail closed on additive/denominator errors, including empty snapshots."""
    for metrics in [snapshot, *(p['metrics'] for p in snapshot['platforms'].values())]:
        n = metrics['active_jobs']
        if any(sum(metrics[key].values()) != n for key in DIMENSIONS):
            raise ValueError('TREND_ADDITIVE_INVARIANT_FAILED')
        if sum(metrics['by_role_family_any'].values()) < n:
            raise ValueError('TREND_ROLE_DIFFUSION_INVARIANT_FAILED')
        if not 0 <= metrics['hybrid_role_count'] <= n or metrics['hybrid_role_share'] != _share(metrics['hybrid_role_count'], n):
            raise ValueError('TREND_HYBRID_INVARIANT_FAILED')
        for dimension in (*DIMENSIONS, *NON_ADDITIVE):
            if metrics['shares'][dimension] != {key: _share(count, n) for key, count in metrics[dimension].items()}:
                raise ValueError('TREND_SHARE_DENOMINATOR_FAILED')
        if sum(row['active_jobs'] for row in metrics['by_company'].values()) != n:
            raise ValueError('TREND_COMPANY_INVARIANT_FAILED')
    if sum(p['metrics']['active_jobs'] for p in snapshot['platforms'].values()) != snapshot['active_jobs']:
        raise ValueError('TREND_PLATFORM_INVARIANT_FAILED')


def trend_comparability(before, after, family):
    if family not in METRIC_FAMILIES:
        raise ValueError('TREND_UNKNOWN_METRIC_FAMILY')
    included, excluded, details = [], [], {}
    for platform in sorted(before['platforms'].keys() | after['platforms'].keys()):
        a, b = before['platforms'].get(platform), after['platforms'].get(platform)
        reasons = set()
        if a is None or b is None:
            reasons.add('PLATFORM_NOT_OBSERVED_BOTH_DAYS')
        else:
            for side in (a, b):
                reasons.update(side['reliability'][family]['reason_codes'])
                if not side['reliability'][family]['reliable']:
                    reasons.add('METRIC_SOURCE_UNRELIABLE')
            if a['source_scope'] != b['source_scope']:
                reasons.add('SOURCE_SCOPE_CHANGED')
        if before['versions'] != after['versions']:
            reasons.update({'CLASSIFIER_VERSION_MISMATCH', 'REPLAY_REQUIRED'})
        if (before['trend_version'] != after['trend_version']
                or before['trend_code_sha256'] != after['trend_code_sha256']
                or before['lifecycle_contract'] != after['lifecycle_contract']):
            reasons.add('TREND_OR_LIFECYCLE_VERSION_MISMATCH')
        if reasons:
            excluded.append(platform)
            details[platform] = sorted(reasons)
        else:
            included.append(platform)
    codes = {code for reasons in details.values() for code in reasons}
    if not included:
        codes.add('NO_COMPARABLE_PLATFORMS')
    return dict(artifact_type=COMPARABILITY_CONTRACT, metric_family=family,
                comparable=bool(included), included_platforms=included, excluded_platforms=excluded,
                reason_codes=sorted(codes), excluded_platform_reasons=details)


def _subset(snapshot, platforms):
    # All additive counts are summed by platform; diagnostic hashes use a union.
    result = _metrics([], [])
    companies = defaultdict(Counter)
    versions = set()
    for platform in platforms:
        item = snapshot['platforms'][platform]
        metrics = item['metrics']
        for field in ('active_jobs', 'hybrid_role_count', *FLOW_FIELDS.values()):
            result[field] += metrics[field]
        for dimension in (*DIMENSIONS, *NON_ADDITIVE):
            for key, count in metrics[dimension].items():
                result[dimension][key] = result[dimension].get(key, 0) + count
        for company, counts in metrics['by_company'].items():
            companies[company].update(counts)
        versions.update(item['content_versions'])
    result['unique_content_versions'] = len(versions)
    result['hybrid_role_share'] = _share(result['hybrid_role_count'], result['active_jobs'])
    result['shares'] = {dimension: {key: _share(count, result['active_jobs']) for key, count in result[dimension].items()}
                        for dimension in (*DIMENSIONS, *NON_ADDITIVE)}
    result['by_company'] = {company: dict(counts) for company, counts in sorted(companies.items())}
    return result


def _change(a, b, comparable):
    return {'from': a if comparable else None, 'to': b if comparable else None,
            'delta': b - a if comparable else None,
            'pct_change': (b - a) / a if comparable and a else None, 'comparable': comparable}


def _share_change(a, b, comparable):
    valid = comparable and a['share'] is not None and b['share'] is not None
    return {'from': a if comparable else None, 'to': b if comparable else None,
            'delta': b['share'] - a['share'] if valid else None,
            'share_change': b['share'] - a['share'] if valid else None,
            'pct_change': (b['share'] - a['share']) / a['share'] if valid and a['share'] else None,
            'comparable': bool(valid)}


def compare_trends(before, after):
    """Compare daily observations over one stable platform set per metric family."""
    if before['snapshot_date'] >= after['snapshot_date']:
        raise ValueError('COMPARISON_DATES_MUST_INCREASE')
    for snapshot in (before, after):
        validate_snapshot(snapshot)
    comparability = {family: trend_comparability(before, after, family) for family in METRIC_FAMILIES}
    subsets = {family: {side: _subset(snapshot, info['included_platforms']) if info['comparable'] else None
                        for side, snapshot in (('from', before), ('to', after))}
               for family, info in comparability.items()}
    valid = comparability['inventory']['comparable']
    a, b = (subsets['inventory'][side] or _metrics([], []) for side in ('from', 'to'))
    market = {'active_jobs': _change(a['active_jobs'], b['active_jobs'], valid),
              'core_jobs': _change(a['by_market_relevance']['core'], b['by_market_relevance']['core'], valid),
              'adjacent_jobs': _change(a['by_market_relevance']['adjacent'], b['by_market_relevance']['adjacent'], valid),
              'hybrid_role_share': _share_change(a['hybrid_role_share'], b['hybrid_role_share'], valid)}
    dimensions = {}
    for dimension in (*DIMENSIONS, *NON_ADDITIVE):
        keys = before[dimension].keys() | after[dimension].keys()
        dimensions[dimension] = {key: {**_change(a[dimension].get(key, 0), b[dimension].get(key, 0), valid),
            'share': _share_change(_share(a[dimension].get(key, 0), a['active_jobs']),
                                   _share(b[dimension].get(key, 0), b['active_jobs']), valid)} for key in sorted(keys)}
    lifecycle = {}
    for kind, field in FLOW_FIELDS.items():
        family = 'content_flow' if kind == 'UPDATED' else 'presence_flow'
        allowed = comparability[family]['comparable']
        pair = subsets[family]
        lifecycle[kind] = _change(pair['from'][field] if allowed else 0,
                                  pair['to'][field] if allowed else 0, allowed)
    company_changes = {}
    for company in sorted(before['by_company'].keys() | after['by_company'].keys()):
        changes = {}
        for field in ('active_jobs', 'core', 'adjacent', 'P1', *FLOW_FIELDS.values()):
            family = ('content_flow' if field == 'updated_jobs' else 'presence_flow') if field in FLOW_FIELDS.values() else 'inventory'
            allowed = comparability[family]['comparable']
            pair = subsets[family]
            values = [pair[side]['by_company'].get(company, {}).get(field, 0) if allowed else 0 for side in ('from', 'to')]
            changes[field] = _change(*values, allowed)
        company_changes[company] = changes
    result = dict(artifact_type=COMPARISON_CONTRACT, trend_version=after['trend_version'],
                  from_date=before['snapshot_date'], to_date=after['snapshot_date'],
                  versions=dict(after['versions']), lifecycle_contract=after['lifecycle_contract'],
                  comparability=comparability,
                  observed_full_snapshot={side: {key: snapshot[key] for key in _metrics([], [])}
                                          for side, snapshot in (('from', before), ('to', after))},
                  comparable_subset=subsets, market=market, **dimensions,
                  lifecycle=lifecycle, company_changes=company_changes,
                  lifecycle_comparison_basis='daily_canonical_event_counts_not_interval_totals')
    validate_comparison(result)
    return result


def validate_comparison(comparison):
    for family, info in comparison['comparability'].items():
        if bool(info['included_platforms']) != info['comparable'] or set(info['included_platforms']) & set(info['excluded_platforms']):
            raise ValueError('TREND_COMPARABLE_PLATFORM_INVARIANT_FAILED')
        if not info['comparable'] and any(v is not None for v in comparison['comparable_subset'][family].values()):
            raise ValueError('TREND_NOT_COMPARABLE_SUBSET_FAILED')
    def check(value):
        if isinstance(value, dict):
            if value.get('comparable') is False and ('delta' in value or 'pct_change' in value):
                if value.get('delta') is not None or value.get('pct_change') is not None:
                    raise ValueError('TREND_NOT_COMPARABLE_DELTA_FAILED')
            for child in value.values():
                check(child)
    check(comparison)
