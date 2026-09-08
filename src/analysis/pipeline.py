"""Offline, versioned analysis/replay CLI over the existing raw/clean artifacts.

Example: python -m src.analysis.pipeline replay --from 2026-09-01 --to 2026-09-07
Earlier available observations are warmed in memory; only requested dates are written.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

from src.analysis.ai_eval_jobs import _write_text_atomic, load_jobs
from src.analysis.audit_bundle import export_bundle
from src.analysis.classification import classify_record
from src.analysis.lifecycle import Lifecycle, identity, index_jobs
from src.analysis.source_health import SourceHealth
from src.analysis.trends import aggregate_trends
from src.models import write_json_atomic

DEFAULT_VERSION_CONFIG = Path(__file__).resolve().parents[2] / 'configs/analysis/versions.yaml'


def load_settings(path=DEFAULT_VERSION_CONFIG):
    settings = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    versions = {key: settings[field] for key, field in (
        ('market', 'market_classifier_version'), ('fit', 'fit_classifier_version'),
        ('skills', 'skill_ontology_version'))}
    if not all(isinstance(value, str) and value for value in versions.values()):
        raise ValueError('INVALID_CLASSIFIER_VERSION')
    if settings['trend']['window_days'] != 7:
        raise ValueError('The fixed *_7d schema requires window_days=7')
    return settings, versions


def _dates(start, end):
    current, last = date.fromisoformat(start), date.fromisoformat(end)
    while current <= last:
        yield current.isoformat()
        current += timedelta(days=1)


def replay(start, end, *, data_dir=Path('data'), output_dir=None, settings_path=DEFAULT_VERSION_CONFIG,
           market_version=None, fit_version=None):
    if start > end:
        raise ValueError('from date must be <= to date')
    settings, versions = load_settings(settings_path)
    for key, requested in (('market', market_version), ('fit', fit_version)):
        if requested is not None and requested != versions[key]:
            raise ValueError(f'UNSUPPORTED_{key.upper()}_VERSION: {requested}; checkout the matching rule revision. REPLAY_REQUIRED')
    data_dir = Path(data_dir)
    output_dir = Path(output_dir) if output_dir is not None else data_dir / 'analysis'
    clean_dir, raw_dir = data_dir / 'clean', data_dir / 'raw'
    # Refuse configurations that could overwrite the input or legacy data layer.
    if any(output_dir.resolve() == path.resolve() or path.resolve() in output_dir.resolve().parents
           for path in (clean_dir, raw_dir)):
        raise ValueError('OUTPUT_MUST_NOT_OVERLAP_SOURCE_DATA')
    available = {p.stem for p in clean_dir.glob('????-??-??.json') if p.stem <= end}
    provenance = {p.name[:10] for p in (data_dir / 'analysis').glob('*_ai_eval_hits.jsonl')}
    wanted = set(_dates(start, end)) | {day for day in provenance if start <= day <= end}
    lifecycle = Lifecycle(settings['trend']['removal_confirmation_runs'])
    history, summary, incomplete = [], [], []
    previous_classifications = {}
    for day in sorted(available | wanted):
        clean_path = clean_dir / f'{day}.json'
        manifest_path = raw_dir / f'{day}_manifest.json'
        missing = [str(path) for path in (clean_path, manifest_path) if not path.exists()]
        if missing:
            if start <= day <= end:
                incomplete.append(dict(date=day, reason_codes=['HISTORICAL_SOURCE_INCOMPLETE'], missing=missing))
            continue
        jobs = load_jobs(clean_path)
        indexed = index_jobs(jobs)
        # Exact duplicate identities are one posting; conflicting identities fail.
        jobs = list(indexed.values())
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        health = SourceHealth(manifest, jobs)
        events = lifecycle.observe(day, jobs, health)
        classifications, markets = [], {}
        content_unreliable_count = 0
        for key, job in indexed.items():
            resolved = health.resolve(key[0], str(job.get('company', '')), job)
            content_unreliable_count += int(not resolved.content_reliable)
            row, market = classify_record(day, job, resolved, versions, previous_classifications.get(key))
            markets[key] = market
            if row:
                classifications.append(row)
                if row['classification_status'] in {'fresh', 'carried_forward'}:
                    previous_classifications[key] = row
            if resolved.content_reliable and row is None:
                previous_classifications.pop(key, None)
        classifications.sort(key=identity)
        observation = dict(date=day, versions=dict(versions), classifications=classifications,
                           events=events, health=health,
                           content_unreliable_count=content_unreliable_count)
        history.append(observation)
        if day < start:
            continue
        if not jobs and not any(health.resolve(p, c).presence_reliable for p, c in health.scopes()):
            incomplete.append(dict(date=day, reason_codes=['ALL_SOURCES_UNRELIABLE', 'OUTPUT_PRESERVED'], missing=[]))
            continue
        trend = aggregate_trends(history, settings['trend']['window_days'])
        bundle = export_bundle(day, jobs, classifications, markets, health, events, trend,
                               history[-2] if len(history) > 1 else None, settings['audit'])
        for folder, rows in (('classification', classifications), ('events', events)):
            _write_text_atomic(output_dir / folder / f'{day}.jsonl',
                               ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows))
        write_json_atomic(output_dir / 'trends' / f'{day}.json', trend)
        write_json_atomic(output_dir / 'audit' / f'{day}_bundle.json', bundle)
        raw_path = raw_dir / f'{day}.json'
        raw_count = len(load_jobs(raw_path)) if raw_path.exists() else None
        current_blocked = [dict(platform=p, company=c, reason_codes=list(health.resolve(p, c).reason_codes))
                           for p, c in sorted(health.scopes()) if not health.resolve(p, c).presence_reliable]
        summary.append(dict(date=day, raw_job_count=raw_count, manifest_job_count=manifest.get('job_count'),
                            clean_job_count=len(jobs), market_in_scope_count=len(classifications),
                            career_pool_counts=dict(Counter(row['career_pool'] or 'UNRESOLVED' for row in classifications)),
                            classification_status_counts=dict(Counter(row['classification_status'] for row in classifications)),
                            content_unreliable_count=content_unreliable_count,
                            event_counts=dict(Counter(row['event_type'] for row in events)),
                            current_presence_blocked_scopes=current_blocked,
                            coverage=trend['coverage'], audit_jobs=len(bundle['jobs'])))
    report = dict(versions=versions, from_date=start, to_date=end, observations=summary,
                  warmup_dates=[obs['date'] for obs in history if obs['date'] < start],
                  incomplete_history=incomplete,
                  pipeline_implemented=True, historical_replay_verified=bool(summary),
                  trend_data_comparable=bool(summary) and not incomplete and all(row['coverage']['comparable'] for row in summary))
    if summary:
        write_json_atomic(output_dir / 'audit' / f'{start}_{end}_replay.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'replay'):
        command = sub.add_parser(name)
        if name == 'run':
            command.add_argument('--date', required=True, type=date.fromisoformat)
        else:
            command.add_argument('--from', dest='start', required=True, type=date.fromisoformat)
            command.add_argument('--to', dest='end', required=True, type=date.fromisoformat)
        command.add_argument('--data-dir', type=Path, default=Path('data'))
        command.add_argument('--output-dir', type=Path)
        command.add_argument('--settings', type=Path, default=DEFAULT_VERSION_CONFIG)
        command.add_argument('--market-version')
        command.add_argument('--fit-version')
    args = parser.parse_args(argv)
    start, end = (str(args.date), str(args.date)) if args.command == 'run' else (str(args.start), str(args.end))
    try:
        result = replay(start, end, data_dir=args.data_dir, output_dir=args.output_dir, settings_path=args.settings,
                        market_version=args.market_version, fit_version=args.fit_version)
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['historical_replay_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
