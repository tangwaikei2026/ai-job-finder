"""Resolve observation reliability from existing manifests; never mutate inputs."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Health:
    presence_reliable: bool
    content_reliable: bool
    reason_codes: tuple[str, ...] = ()


class SourceHealth:
    def __init__(self, manifest: Mapping[str, Any], jobs: Sequence[Mapping[str, Any]]):
        self.manifest = manifest
        self.platforms = {row['platform']: row for row in manifest.get('platforms', [])}
        self.counts = Counter(str(job.get('platform', '')) for job in jobs)
        self.companies: dict[str, set[str]] = {}
        for job in jobs:
            self.companies.setdefault(str(job.get('platform', '')), set()).add(str(job.get('company', '')))
        self.cities = tuple(sorted(manifest.get('cities', [])))
        self.global_mismatch = manifest.get('job_count') != len(jobs)

    def failed_companies(self, platform: str) -> set[str]:
        row = self.platforms.get(platform, {})
        if 'failed_companies' in row:
            return set(row['failed_companies'])
        # Legacy Feishu writes exactly "company: error; company: error".
        # Reject ambiguous chunks instead of treating arbitrary text as a company.
        if platform == 'feishu' and row.get('stopped_by') == 'company_error':
            chunks = str(row.get('error', '')).split('; ')
            names = [re.match(r'^([^:;\n/]{1,80}):\s+.+', chunk) for chunk in chunks]
            if names and all(names):
                return {match.group(1) for match in names if match}
        return set()

    def scopes(self) -> set[tuple[str, str]]:
        result = set()
        for platform, row in self.platforms.items():
            if platform == 'feishu':
                names = (set(row.get('attempted_companies', []))
                         | self.companies.get(platform, set()) | self.failed_companies(platform))
                result.update((platform, name) for name in (names or {''}))
            else:
                result.add((platform, ''))
        result.update((platform, '') for platform in self.counts if platform not in self.platforms)
        return result

    def resolve(self, platform: str, company: str = '', job: Mapping[str, Any] | None = None) -> Health:
        row = self.platforms.get(platform)
        if row is None:
            return Health(False, False, ('MANIFEST_SCOPE_MISSING',))
        reasons: list[str] = []
        status, stopped = row.get('status'), row.get('stopped_by')
        required = ('source_total', 'expected_pages', 'pages_fetched', 'records_fetched',
                    'jobs_mapped', 'jobs_in_scope', 'detail_failed')
        if any(not isinstance(row.get(key), int) or row[key] < 0 for key in required):
            return Health(False, False, ('MANIFEST_COUNTERS_INVALID',))
        if self.global_mismatch or self.counts[platform] != row['jobs_in_scope']:
            reasons.append('SNAPSHOT_COUNT_MISMATCH')
        if status not in {'success', 'partial'}:
            reasons.append('SOURCE_ERROR')
        if row.get('missing_job_id', 0):
            reasons.append('MISSING_JOB_IDS')
        if row['jobs_mapped'] < row['jobs_in_scope']:
            reasons.append('MAPPING_INCOMPLETE')
        if row['jobs_mapped'] + row.get('duplicate_records', 0) < row['records_fetched']:
            reasons.append('MAPPING_INCOMPLETE')

        failed = self.failed_companies(platform)
        company_partial = platform == 'feishu' and stopped == 'company_error' and bool(failed)
        known = set(row.get('attempted_companies', [])) | self.companies.get(platform, set())
        if platform == 'feishu' and company not in known:
            reasons.append('COMPANY_SCOPE_UNOBSERVED')
        if company_partial:
            if company in failed:
                reasons.append('COMPANY_ERROR')
            # The adapter catches errors per company and completes all other
            # attempted companies. Aggregate page deficits belong to failed ones.
            if 'failed_companies' not in row:
                legacy_reason = 'LEGACY_COMPANY_ERROR_PARSED'
            else:
                legacy_reason = ''
        else:
            legacy_reason = ''
            if row['pages_fetched'] < row['expected_pages']:
                reasons.append('LIST_PAGES_INCOMPLETE')
            if row['records_fetched'] < row['source_total']:
                reasons.append('LIST_RECORDS_INCOMPLETE')
            if stopped in {'empty_page', 'incomplete_list', 'repeated_page', 'company_error'}:
                reasons.append('LIST_INCOMPLETE')
            if not row.get('complete') and stopped != 'detail_errors':
                reasons.append('SOURCE_INCOMPLETE')
            if row.get('error'):
                reasons.append('SOURCE_ERROR')
            if stopped not in {'source_total_reached', 'all_city_totals_reached',
                               'all_companies_complete', 'detail_errors'}:
                reasons.append('UNVERIFIED_STOP_REASON')
        presence = not reasons
        if legacy_reason:
            reasons.append(legacy_reason)
        content = status in {'success', 'partial'}
        if job is None:
            content = content and row['detail_failed'] == 0
        else:
            fields = [str(job.get(key) or '').strip() for key in ('title', 'description', 'requirements')]
            if str(job.get('job_id')) in set(row.get('detail_failed_job_ids', [])):
                content = False
                reasons.append('DETAIL_FAILED_JOB_ID')
            elif fields[0] and not fields[1] and not fields[2] and (
                row['detail_failed'] > 0 or stopped == 'detail_errors'
            ):
                content = False
                reasons.append('PROBABLE_DETAIL_FAILURE')
            if not fields[0] or not (fields[1] or fields[2]):
                content = False
                reasons.append('INSUFFICIENT_CONTENT')
        return Health(presence, content, tuple(dict.fromkeys(reasons)))
