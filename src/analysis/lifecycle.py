"""Identity lifecycle from clean presence, independent of all classifiers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.analysis.ai_eval_jobs import job_content_sha256
from src.analysis.source_health import SourceHealth

EVENT_TYPES = frozenset({'NEW', 'FIRST_SEEN', 'UPDATED', 'MISSING', 'REMOVED', 'REAPPEARED'})
EVENT_STATUSES = frozenset({'confirmed', 'provisional'})


def identity(job: Mapping[str, Any]) -> tuple[str, str]:
    return str(job.get('platform', '')), str(job.get('job_id', ''))


def index_jobs(jobs: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    result = {}
    for job in jobs:
        key = identity(job)
        if not all(key):
            raise ValueError('CLEAN_IDENTITY_MISSING')
        if key in result and result[key] != job:
            raise ValueError(f'CLEAN_IDENTITY_CONFLICT: {key}')
        result[key] = job
    return result


@dataclass
class Observation:
    company: str
    title: str
    reliable_sha: str | None
    cities: tuple[str, ...]
    missing_streak: int = 0
    missing: bool = False
    removed: bool = False


class Lifecycle:
    def __init__(self, confirmation_runs: int = 2):
        if confirmation_runs < 2:
            raise ValueError('removal_confirmation_runs must be >= 2')
        self.confirmation_runs = confirmation_runs
        self.state: dict[tuple[str, str], Observation] = {}
        self.previous_health: SourceHealth | None = None
        self.previous_date: str | None = None

    def observe(self, day: str, jobs: Sequence[Mapping[str, Any]], health: SourceHealth) -> list[dict]:
        if self.previous_date and day <= self.previous_date:
            raise ValueError('OBSERVATIONS_MUST_BE_STRICTLY_CHRONOLOGICAL')
        current = index_jobs(jobs)
        events = []
        scope_changed = self.previous_health is not None and health.cities != self.previous_health.cities

        def emit(key, observation, event_type, confirmed, previous=None, sha=None, reasons=()):
            events.append(dict(event_date=day, platform=key[0], job_id=key[1],
                               company=observation.company, title=observation.title,
                               event_type=event_type,
                               event_status='confirmed' if confirmed else 'provisional',
                               previous_sha256=previous, current_sha256=sha, reason_codes=list(reasons)))

        for key, job in current.items():
            company = str(job.get('company', ''))
            reliability = health.resolve(key[0], company, job)
            sha = job_content_sha256(job) if reliability.content_reliable else None
            old = self.state.get(key)
            if old is None:
                previous_reliable = (self.previous_health is not None and not scope_changed
                                     and self.previous_health.resolve(key[0], company).presence_reliable)
                confirmed = bool(previous_reliable and reliability.presence_reliable)
                old = Observation(company, str(job.get('title', '')), sha, health.cities)
                emit(key, old, 'NEW' if confirmed else 'FIRST_SEEN', confirmed, sha=sha,
                     reasons=['RELIABLE_ABSENCE_TO_PRESENCE'] if confirmed else ['NO_COMPARABLE_PRIOR_ABSENCE'])
                self.state[key] = old
            else:
                previous_sha = old.reliable_sha
                if old.missing:
                    emit(key, old, 'REAPPEARED', reliability.presence_reliable and not scope_changed,
                         previous_sha, sha, ['PREVIOUSLY_MISSING'])
                if sha is not None and previous_sha is not None and sha != previous_sha:
                    emit(key, old, 'UPDATED', True, previous_sha, sha, ['RELIABLE_CONTENT_CHANGED'])
                if sha is not None:
                    old.reliable_sha = sha
                old.company, old.title = company, str(job.get('title', ''))
                old.cities = health.cities
                old.missing_streak = 0
                old.missing = old.removed = False

        for key, old in self.state.items():
            if key in current or old.removed:
                continue
            reliability = health.resolve(key[0], old.company)
            old.missing = True
            absence_scope_changed = scope_changed or old.cities != health.cities
            if reliability.presence_reliable and not absence_scope_changed:
                old.missing_streak += 1
                old.removed = old.missing_streak >= self.confirmation_runs
                emit(key, old, 'REMOVED' if old.removed else 'MISSING', old.removed,
                     old.reliable_sha, reasons=['RELIABLE_ABSENCE'])
            else:
                emit(key, old, 'MISSING', False, old.reliable_sha,
                     reasons=['SOURCE_UNRELIABLE', *reliability.reason_codes,
                              *(['SOURCE_SCOPE_CHANGED'] if absence_scope_changed else [])])
        self.previous_health, self.previous_date = health, day
        return events
