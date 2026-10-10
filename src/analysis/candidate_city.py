"""Personal city candidates, independent of occupational Fit and city statistics."""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from src.clean.jobs import CITY_ALIASES

_CITY = re.compile('|'.join(sorted(CITY_ALIASES, key=len, reverse=True)))
_SHENZHEN = re.compile(r'深圳(?:市)?')
_NEGATIVE = re.compile(
    r'(?:非|不在|不含|不包括|不包含|不招|不考虑|排除|除)\s*深圳(?:市)?'
    r'|深圳(?:市)?\s*(?:除外|以外|不招聘|不招人|不招|无岗位|没有岗位|无名额|不设岗位|不提供岗位)'
)
_NON_LOCATION = re.compile(r'深圳(?:市)?(?:大学|客户|市场|业务)')


def match_shenzhen_candidate(job: Mapping[str, Any]) -> dict[str, Any]:
    """Either source can admit a candidate; explicit negation vetoes both.

    This is evidence of a possible workplace, never confirmation of an opening.
    Raw fields and city_norm are not altered; body text is not a city source.
    """
    evidence = {f: job.get(f, '') for f in ('location', 'title')}
    positive, negative = [], []
    cities = {}
    for field, raw in evidence.items():
        text = raw if isinstance(raw, str) else ''
        negatives = list(_NEGATIVE.finditer(text))
        ignored = negatives + list(_NON_LOCATION.finditer(text))
        if negatives:
            negative.append(field)
        if any(not any(n.start() <= m.start() < n.end() for n in ignored)
               for m in _SHENZHEN.finditer(text)):
            positive.append(field)
        cities[field] = {CITY_ALIASES[m.group()] for m in _CITY.finditer(text)}
    conflict = bool(positive and negative) or bool(
        cities['location'] and cities['title']
        and cities['location'] != cities['title']
    )
    matches = bool(positive) and not negative
    return {
        'matches': matches,
        'positive_fields': positive,
        'negative_fields': negative,
        'location_conflict': conflict,
        'needs_verification': matches or bool(positive and negative),
        'confirmed_openings': None,
        'evidence': evidence,
    }


def select_shenzhen_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Select P1/P2 rows with original title/location available, without reclassifying."""
    result = []
    for row in rows:
        match = match_shenzhen_candidate(row)
        if row.get('career_pool') in {'P1', 'P2'} and match['matches']:
            result.append({**row, 'candidate_city_match': match})
    return result
