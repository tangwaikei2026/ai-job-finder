"""Deterministic Daily Health V1 interpretation over existing artifacts."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.analysis.ai_eval_jobs import load_jobs
from src.analysis.known_limitations import DEFAULT_REGISTRY, load_known_limitations
from src.analysis.lifecycle import index_jobs
from src.analysis.source_health import SourceHealth
from src.models import write_json_atomic


HEALTH_CONTRACT_VERSION = 1
TECHNICAL_RUN_HEALTHS = frozenset({'SUCCESS', 'FAILED'})
SOURCE_COMPLETENESS_VALUES = frozenset({'COMPLETE', 'PARTIAL', 'UNKNOWN'})
LIMITATION_STATES = frozenset({'NORMAL', 'KNOWN_LIMITATION', 'NEW_REGRESSION'})
OVERALL_ACTIONS = frozenset({'NO_NEW_ACTION', 'ACTION_REQUIRED'})
RUNNER_STATUSES = frozenset({'SUCCESS', 'DEGRADED', 'FAILED'})
CRAWL_STATUSES = frozenset({'SUCCESS', 'DEGRADED', 'FAILED'})
STAGE_STATUSES = frozenset({'SUCCESS', 'FAILED', 'SKIPPED', 'PENDING'})
DIRECTLY_EXPLAINED_SOURCE_HEALTH_REASONS = frozenset({
    'SOURCE_INCOMPLETE',
    'UNVERIFIED_STOP_REASON',
})


class DailyHealthError(ValueError):
    """An input or contract failure that must not produce normal health."""


def _fail(code: str) -> None:
    raise DailyHealthError(code)


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(code)
    return value


def _read_json(path: Path, code: str) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise DailyHealthError(f'{code}: {exc}') from exc


def derive_technical_run_health(run_status: Mapping[str, Any]) -> str:
    """Derive technical execution health without interpreting source coverage."""
    status = run_status.get('status')
    if not isinstance(status, str) or status not in RUNNER_STATUSES:
        _fail('INVALID_RUNNER_STATUS')
    stages = {}
    for name, allowed in (
        ('crawl', CRAWL_STATUSES),
        ('clean', STAGE_STATUSES),
        ('analysis', STAGE_STATUSES),
    ):
        stage = _mapping(run_status.get(name), f'MISSING_{name.upper()}_STATUS')
        stage_status = stage.get('status')
        if not isinstance(stage_status, str) or stage_status not in allowed:
            _fail(f'INVALID_{name.upper()}_STATUS')
        stages[name] = stage_status
    success = (
        status in {'SUCCESS', 'DEGRADED'}
        and stages['crawl'] in {'SUCCESS', 'DEGRADED'}
        and stages['clean'] == 'SUCCESS'
        and stages['analysis'] == 'SUCCESS'
    )
    return 'SUCCESS' if success else 'FAILED'


def derive_source_completeness(source: Mapping[str, Any]) -> str:
    """Map the canonical manifest status/complete pair exactly."""
    status, complete = source.get('status'), source.get('complete')
    if (
        not isinstance(status, str)
        or status not in {'success', 'partial', 'error'}
        or not isinstance(complete, bool)
    ):
        _fail('INVALID_SOURCE_STATUS_OR_COMPLETE')
    mapping = {
        ('success', True): 'COMPLETE',
        ('partial', False): 'PARTIAL',
        ('error', False): 'UNKNOWN',
    }
    result = mapping.get((status, complete))
    if result is None:
        _fail('SOURCE_STATUS_COMPLETE_MISMATCH')
    return result


def _validate_artifact_date(value: Any, run_date: str, code: str) -> None:
    if not isinstance(value, str) or not value:
        _fail(code)
    try:
        observed = datetime.fromisoformat(value).date().isoformat()
    except ValueError as exc:
        raise DailyHealthError(code) from exc
    if observed != run_date:
        _fail(code)


def _validate_run(run_date: str, run_status: Any) -> Mapping[str, Any]:
    run = _mapping(run_status, 'MALFORMED_DAILY_RUN_STATUS')
    if run.get('date') != run_date:
        _fail('DAILY_RUN_DATE_MISMATCH')
    derive_technical_run_health(run)
    return run


def _validate_manifest(run_date: str, value: Any) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    manifest = _mapping(value, 'MALFORMED_COLLECTION_MANIFEST')
    if 'date' in manifest and manifest['date'] != run_date:
        _fail('MANIFEST_DATE_MISMATCH')
    _validate_artifact_date(manifest.get('generated_at'), run_date, 'MANIFEST_DATE_MISMATCH')
    job_count = manifest.get('job_count')
    if isinstance(job_count, bool) or not isinstance(job_count, int) or job_count < 0:
        _fail('INVALID_MANIFEST_JOB_COUNT')
    platforms = manifest.get('platforms')
    if not isinstance(platforms, list) or not platforms:
        _fail('MALFORMED_MANIFEST_PLATFORMS')
    rows: list[Mapping[str, Any]] = []
    names: set[str] = set()
    for value in platforms:
        row = _mapping(value, 'MALFORMED_MANIFEST_PLATFORM')
        platform = row.get('platform')
        if not isinstance(platform, str) or not platform or platform in names:
            _fail('INVALID_OR_DUPLICATE_MANIFEST_PLATFORM')
        names.add(platform)
        derive_source_completeness(row)
        rows.append(row)
    complete = manifest.get('complete')
    if not isinstance(complete, bool) or complete != all(row['complete'] for row in rows):
        _fail('MANIFEST_COMPLETE_MISMATCH')
    return manifest, rows


def _validate_jobs(jobs: Any, platforms: set[str]) -> list[Mapping[str, Any]]:
    if (
        not isinstance(jobs, Sequence)
        or isinstance(jobs, (str, bytes))
        or any(not isinstance(job, Mapping) for job in jobs)
    ):
        _fail('INVALID_CLEAN_OBSERVATION')
    try:
        indexed = index_jobs(jobs)
    except (KeyError, TypeError, ValueError) as exc:
        raise DailyHealthError(f'INVALID_CLEAN_OBSERVATION: {exc}') from exc
    unknown = sorted({platform for platform, _ in indexed} - platforms)
    if unknown:
        _fail(f'CLEAN_PLATFORM_MISSING_FROM_MANIFEST: {unknown}')
    return list(indexed.values())


def _resolve_source_health(
    manifest: Mapping[str, Any],
    jobs: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    try:
        health = SourceHealth(manifest, jobs)
        all_scopes = health.scopes()
        result = {}
        for row in rows:
            platform = str(row['platform'])
            scopes = sorted(company for source, company in all_scopes if source == platform)
            if not scopes:
                _fail(f'SOURCE_HEALTH_SCOPE_MISSING: {platform}')
            resolved_scopes = []
            for company in scopes:
                resolved = health.resolve(platform, company)
                if (
                    not isinstance(resolved.presence_reliable, bool)
                    or not isinstance(resolved.content_reliable, bool)
                    or any(not isinstance(code, str) for code in resolved.reason_codes)
                ):
                    _fail(f'INVALID_SOURCE_HEALTH_RESULT: {platform}')
                resolved_scopes.append({
                    'company': company or None,
                    'presence_reliable': resolved.presence_reliable,
                    'content_reliable': resolved.content_reliable,
                    'reason_codes': list(resolved.reason_codes),
                })
            result[platform] = {
                'presence_reliable': all(scope['presence_reliable'] for scope in resolved_scopes),
                'content_reliable': all(scope['content_reliable'] for scope in resolved_scopes),
                'reason_codes': sorted({
                    code for scope in resolved_scopes for code in scope['reason_codes']
                }),
                'scopes': resolved_scopes,
            }
        return result
    except DailyHealthError:
        raise
    except Exception as exc:
        raise DailyHealthError(f'SOURCE_HEALTH_EVALUATION_FAILED: {exc}') from exc


def _completeness_reasons(source: Mapping[str, Any]) -> list[str]:
    metadata = source.get('metadata', {})
    if not isinstance(metadata, Mapping):
        return []
    reasons = metadata.get('completeness_reasons', [])
    if not isinstance(reasons, list) or any(not isinstance(reason, str) for reason in reasons):
        return []
    return list(reasons)


def _strict_limitation_match(
    source: Mapping[str, Any],
    source_health: Mapping[str, Any],
    limitation: Mapping[str, Any],
) -> bool:
    if source.get('platform') != limitation['platform']:
        return False
    allowed_reasons = set(limitation['allowed_reasons'])
    if source.get('status') != 'partial' or source.get('complete') is not False:
        return False
    if source.get('error') != '':
        return False
    stopped_by = source.get('stopped_by')
    if stopped_by not in allowed_reasons:
        return False
    if source.get('failed_companies') != []:
        return False
    detail_failed = source.get('detail_failed')
    if isinstance(detail_failed, bool) or detail_failed != 0:
        return False
    if source.get('detail_failed_job_ids') != []:
        return False
    metadata = source.get('metadata')
    if not isinstance(metadata, Mapping):
        return False
    if metadata.get('pagination_mode') != 'offset_dynamic':
        return False
    if metadata.get('stable_snapshot_mechanism') is not False:
        return False
    if metadata.get('list_complete') is not False or metadata.get('list_error') is not False:
        return False
    reasons = metadata.get('completeness_reasons')
    if (
        not isinstance(reasons, list)
        or not reasons
        or any(not isinstance(reason, str) for reason in reasons)
        or len(reasons) != len(set(reasons))
        or not set(reasons).issubset(allowed_reasons)
        or stopped_by not in reasons
    ):
        return False
    if source_health.get('content_reliable') is not True:
        return False
    health_reasons = source_health.get('reason_codes')
    if not isinstance(health_reasons, list):
        return False
    unexplained = (
        set(health_reasons)
        - DIRECTLY_EXPLAINED_SOURCE_HEALTH_REASONS
        - {'LIST_RECORDS_INCOMPLETE'}
    )
    if unexplained:
        return False
    if 'UNVERIFIED_STOP_REASON' in health_reasons and (
        stopped_by not in allowed_reasons or stopped_by not in reasons
    ):
        return False
    if 'LIST_RECORDS_INCOMPLETE' in health_reasons and 'unique_deficit' not in reasons:
        return False
    return True


def _limitation_interpretation(
    run_date: str,
    source: Mapping[str, Any],
    completeness: str,
    source_health: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> tuple[str, Mapping[str, Any] | None, list[str]]:
    structural_matches = [
        limitation
        for limitation in registry['limitations']
        if limitation['status'] == 'active'
        and _strict_limitation_match(source, source_health, limitation)
    ]
    if len(structural_matches) > 1:
        _fail(f'DUPLICATE_LIMITATION_MATCH: {source["platform"]}')
    if structural_matches:
        limitation = structural_matches[0]
        if run_date >= limitation['review_after']:
            return 'NEW_REGRESSION', limitation, ['KNOWN_LIMITATION_REVIEW_DUE']
        return 'KNOWN_LIMITATION', limitation, []
    if (
        completeness == 'COMPLETE'
        and source_health['presence_reliable']
        and source_health['content_reliable']
    ):
        return 'NORMAL', None, []
    return 'NEW_REGRESSION', None, ['NO_ACTIVE_KNOWN_LIMITATION_MATCH']


def build_daily_health(
    run_date: str,
    run_status: Any,
    manifest_value: Any,
    jobs: Sequence[Mapping[str, Any]],
    *,
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Build the deterministic semantic body; this function performs no writes."""
    try:
        date.fromisoformat(run_date)
    except (TypeError, ValueError) as exc:
        raise DailyHealthError('INVALID_HEALTH_DATE') from exc
    run = _validate_run(run_date, run_status)
    manifest, rows = _validate_manifest(run_date, manifest_value)
    validated_jobs = _validate_jobs(jobs, {str(row['platform']) for row in rows})
    try:
        registry = load_known_limitations(registry_path)
    except ValueError as exc:
        raise DailyHealthError(str(exc)) from exc
    source_health = _resolve_source_health(manifest, validated_jobs, rows)
    sources = {}
    for row in sorted(rows, key=lambda value: str(value['platform'])):
        platform = str(row['platform'])
        completeness = derive_source_completeness(row)
        limitation_state, matched, governance_reasons = _limitation_interpretation(
            run_date, row, completeness, source_health[platform], registry,
        )
        sources[platform] = {
            'source_status': row['status'],
            'source_complete': row['complete'],
            'source_completeness': completeness,
            'completeness_reasons': _completeness_reasons(row),
            'source_health': source_health[platform],
            'limitation_state': limitation_state,
            'matched_limitation_id': matched['id'] if matched else None,
            'matched_limitation': ({
                'category': matched['category'],
                'review_after': matched['review_after'],
                'review_cadence_days': matched['review_cadence_days'],
                'reference': dict(matched['reference']),
            } if matched else None),
            'governance_reasons': governance_reasons,
        }
    technical = derive_technical_run_health(run)
    action = (
        'ACTION_REQUIRED'
        if technical == 'FAILED'
        or any(source['limitation_state'] == 'NEW_REGRESSION' for source in sources.values())
        else 'NO_NEW_ACTION'
    )
    return {
        'date': run_date,
        'health_contract_version': HEALTH_CONTRACT_VERSION,
        'registry_version': registry['version'],
        'runner_status': run['status'],
        'technical_run_health': technical,
        'overall_action': action,
        'sources': sources,
    }


def generate_daily_health(
    run_date: str,
    *,
    data_dir: Path = Path('data'),
    registry_path: Path = DEFAULT_REGISTRY,
    output_dir: Path | None = None,
    generated_at: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Read canonical inputs and atomically write one dated health artifact."""
    data_dir = Path(data_dir)
    run = _read_json(data_dir / 'analysis' / 'runs' / f'{run_date}.json', 'MISSING_OR_INVALID_DAILY_RUN')
    manifest = _read_json(data_dir / 'raw' / f'{run_date}_manifest.json', 'MISSING_OR_INVALID_MANIFEST')
    try:
        jobs = load_jobs(data_dir / 'clean' / f'{run_date}.json')
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise DailyHealthError(f'MISSING_OR_INVALID_CLEAN_OBSERVATION: {exc}') from exc
    semantic = build_daily_health(
        run_date, run, manifest, jobs, registry_path=registry_path,
    )
    artifact = {
        'date': run_date,
        'generated_at': generated_at or datetime.now().astimezone().isoformat(timespec='seconds'),
        **{key: value for key, value in semantic.items() if key != 'date'},
    }
    target_dir = Path(output_dir) if output_dir is not None else data_dir / 'analysis' / 'health'
    output_path = target_dir / f'{run_date}.json'
    write_json_atomic(output_path, artifact)
    return output_path, artifact


def _date_arg(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError('date must use YYYY-MM-DD') from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True, type=_date_arg)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--registry', type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    try:
        path, artifact = generate_daily_health(
            args.date,
            data_dir=args.data_dir,
            registry_path=args.registry,
            output_dir=args.output_dir,
        )
    except DailyHealthError as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps({
        'health_file': str(path),
        'overall_action': artifact['overall_action'],
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
