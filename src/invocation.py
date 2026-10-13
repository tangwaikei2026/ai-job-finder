"""Evidence gates for new Daily invocations; no source-health interpretation."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID


def digest(value) -> str:
    """Bind JSON content, independent of indentation and object-key ordering."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def timestamp(value, timezone):
    if not isinstance(value, str) or len(value) < 19 or value[10] not in {'T', ' '}:
        raise ValueError('MANIFEST_DATE_MISMATCH: timestamp needs date and time')
    try:
        result = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('MANIFEST_DATE_MISMATCH: invalid timestamp') from exc
    return result.replace(tzinfo=timezone) if result.tzinfo is None else result.astimezone(timezone)


def validate_context(context, run_date, expected_id=None):
    if not isinstance(context, dict):
        raise ValueError('INVOCATION_PROOF_MISSING')
    try:
        identifier = context['id']
        if str(UUID(identifier)) != identifier:
            raise ValueError()
        started = datetime.fromisoformat(context['started_at'])
        if started.tzinfo is None:
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError('INVOCATION_PROOF_INVALID') from exc
    if expected_id is not None and identifier != expected_id:
        raise ValueError('INVOCATION_ID_MISMATCH')
    if context.get('run_date') != run_date or started.date().isoformat() != run_date:
        raise ValueError('MANIFEST_DATE_MISMATCH: invocation start')
    return started


def validate_manifest(run_date, manifest, expected_id):
    if not isinstance(manifest, dict):
        raise ValueError('MANIFEST_INVALID')
    context = manifest.get('invocation')
    started = validate_context(context, run_date, expected_id)
    if manifest.get('date') != run_date:
        raise ValueError('MANIFEST_DATE_MISMATCH: logical date')
    generated = timestamp(manifest.get('generated_at'), started.tzinfo)
    end = (started.replace(hour=0, minute=0, second=0, microsecond=0)
           + timedelta(days=2))
    if not started <= generated < end:
        raise ValueError('MANIFEST_DATE_MISMATCH: outside invocation window')
    return started, generated


def validate_raw(run_date, manifest, jobs, expected_id, config_path=None):
    started, generated = validate_manifest(run_date, manifest, expected_id)
    if manifest.get('raw_sha256') != digest(jobs):
        raise ValueError('RAW_DIGEST_MISMATCH')
    if config_path is not None:
        expected = hashlib.sha256(Path(config_path).read_bytes()).hexdigest()
        if manifest.get('config_sha256') != expected:
            raise ValueError('INVOCATION_CONFIG_MISMATCH')
    if (not isinstance(jobs, list) or type(manifest.get('job_count')) is not int
            or manifest['job_count'] != len(jobs)):
        raise ValueError('RAW_MANIFEST_COUNT_MISMATCH')
    platforms = manifest.get('platforms')
    if not isinstance(platforms, list) or not platforms:
        raise ValueError('MANIFEST_PLATFORMS_MISSING')
    if any(not isinstance(job, dict) or not isinstance(job.get('platform'), str)
           or not job['platform'] or not isinstance(job.get('job_id'), str)
           or not job['job_id'] for job in jobs):
        raise ValueError('RAW_ROWS_INVALID')
    counts = Counter(job.get('platform') for job in jobs)
    windows = {}
    for row in platforms:
        if not isinstance(row, dict):
            raise ValueError('MANIFEST_PLATFORM_INVALID')
        begin = timestamp(row.get('started_at'), started.tzinfo)
        finish = timestamp(row.get('finished_at'), started.tzinfo)
        if not started <= begin <= finish <= generated:
            raise ValueError('MANIFEST_DATE_MISMATCH: platform window')
        name = row.get('platform')
        if not isinstance(name, str) or not name or name in windows:
            raise ValueError('MANIFEST_PLATFORM_INVALID')
        if (row.get('status') not in {'success', 'partial', 'error'}
                or type(row.get('complete')) is not bool
                or row['complete'] != (row['status'] == 'success')
                or type(row.get('jobs_in_scope')) is not int
                or row['jobs_in_scope'] < 0 or row['jobs_in_scope'] != counts.get(name, 0)):
            raise ValueError('RAW_MANIFEST_PLATFORM_MISMATCH')
        windows[name] = (begin, finish)
    if (type(manifest.get('complete')) is not bool
            or manifest['complete'] != all(row['complete'] for row in platforms)):
        raise ValueError('MANIFEST_COMPLETE_MISMATCH')
    for job in jobs:
        observed = timestamp(job.get('scraped_at'), started.tzinfo)
        window = windows.get(job.get('platform'))
        if window is None or not window[0] <= observed <= window[1]:
            raise ValueError('MANIFEST_DATE_MISMATCH: job window')
    return manifest['invocation']


def clean_proof(manifest, jobs):
    return {'invocation': manifest['invocation'], 'raw_sha256': manifest['raw_sha256'],
            'manifest_sha256': digest(manifest), 'clean_sha256': digest(jobs)}


def validate_clean(data_dir, run_date, expected_id):
    data_dir = Path(data_dir)
    manifest = read(data_dir / 'raw' / f'{run_date}_manifest.json')
    raw = read(data_dir / 'raw' / f'{run_date}.json')
    validate_raw(run_date, manifest, raw, expected_id)
    jobs = read(data_dir / 'clean' / f'{run_date}.json')
    report = read(data_dir / 'clean' / f'{run_date}_report.json')
    started, collected = validate_manifest(run_date, manifest, expected_id)
    generated = timestamp(report.get('manifest', {}).get('generated_at'), started.tzinfo)
    validate_clock(manifest['invocation'], generated)
    if generated < collected:
        raise ValueError('MANIFEST_DATE_MISMATCH: clean precedes raw')
    if report.get('provenance') != clean_proof(manifest, jobs):
        raise ValueError('CLEAN_PROVENANCE_MISMATCH')
    # Normalization can add fields, but cannot change raw identity/content/time.
    if len(jobs) != len(raw) or any(
        any(job.get(key) != value for key, value in source.items())
        for source, job in zip(raw, jobs)
    ):
        raise ValueError('CLEAN_RAW_CONTENT_MISMATCH')
    return manifest, jobs


def validate_clock(context, now=None):
    started = validate_context(context, context['run_date'])
    current = now or datetime.now().astimezone()
    end = started.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2)
    if not started <= current < end:
        raise ValueError('MANIFEST_DATE_MISMATCH: invocation elapsed beyond window')


def analysis_proof(data_dir, run_date, expected_id, *, completed_at=None):
    manifest, jobs = validate_clean(data_dir, run_date, expected_id)
    paths = [f'classification/{run_date}.jsonl', f'events/{run_date}.jsonl',
             f'trends/snapshots/{run_date}.json', f'audit/{run_date}_bundle.json']
    completed_at = completed_at or datetime.now().astimezone().isoformat(timespec='seconds')
    started = validate_context(manifest['invocation'], run_date)
    completed = timestamp(completed_at, started.tzinfo)
    validate_clock(manifest['invocation'], completed)
    clean_time = timestamp(read(Path(data_dir) / 'clean' / f'{run_date}_report.json')
                           ['manifest']['generated_at'], started.tzinfo)
    if completed < clean_time:
        raise ValueError('MANIFEST_DATE_MISMATCH: analysis precedes clean')
    return {**clean_proof(manifest, jobs), 'completed_at': completed_at, 'artifacts': {
        p: hashlib.sha256((Path(data_dir) / 'analysis' / p).read_bytes()).hexdigest()
        for p in paths}}


def validate_analysis(data_dir, run_date, expected_id):
    proof = read(Path(data_dir) / 'analysis' / 'audit' / f'{run_date}_invocation.json')
    if not isinstance(proof.get('completed_at'), str):
        raise ValueError('ANALYSIS_PROVENANCE_MISSING')
    if proof != analysis_proof(data_dir, run_date, expected_id, completed_at=proof['completed_at']):
        raise ValueError('ANALYSIS_PROVENANCE_MISMATCH')
