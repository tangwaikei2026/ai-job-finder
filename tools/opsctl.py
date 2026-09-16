#!/usr/bin/env python3
"""Human-facing Daily Operations command line interface."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.operations.daily_ops import DailyOperations, DailyOperationsError  # noqa: E402
from src.operations.notifications import NotificationService  # noqa: E402
from src.operations.presentation import build_presentation, render_status  # noqa: E402


def _date_arg(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError('date must use YYYY-MM-DD') from exc


def _operations(args: argparse.Namespace) -> DailyOperations:
    root = Path(args.root).resolve()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else root / 'data'
    config = Path(args.config).resolve() if args.config else root / 'config.yaml'
    return DailyOperations(
        data_dir=data_dir,
        root=root,
        config_path=config,
        trigger='opsctl',
    )


def _status(args: argparse.Namespace, operations: DailyOperations) -> int:
    machine = operations.machine_status(args.date)
    if machine is None:
        print('No Operations status is available for that date.', file=sys.stderr)
        return 1
    print(render_status(build_presentation(machine)), end='')
    return 0


def _history(args: argparse.Namespace, operations: DailyOperations) -> int:
    rows = operations.history(args.days)
    print('DATE        RESULT             ACTION')
    for row in rows:
        outcome = str(row['human_outcome']).replace('_', ' ')
        action = 'GPT REVIEW' if row['human_action_required'] else 'NONE'
        print(f"{row['run_date']:<10}  {outcome:<17}  {action}")
    if not rows:
        print('(no history)')
    return 0


def _incidents(args: argparse.Namespace, operations: DailyOperations) -> int:
    rows = operations.incidents(open_only=args.open)
    print('INCIDENT        DATE        STATUS          PROBLEM')
    for row in rows:
        problem = row['platform'] or row['failed_phase'] or row['error_type']
        print(
            f"{row['incident_id']:<15} {row['run_id']:<10}  "
            f"{row['status']:<15} {problem}"
        )
    if not rows:
        print('(none)')
    return 0


def _recover(args: argparse.Namespace, operations: DailyOperations) -> int:
    if not args.dry_run:
        print('opsctl only supports deferred recovery inspection; use --dry-run.', file=sys.stderr)
        return 2
    as_of = args.as_of or date.today().isoformat()
    candidates = operations.deferred_recovery_candidates(as_of)
    print('ELIGIBLE DEFERRED RECOVERY')
    print('DATE        RESUME FROM')
    for candidate in candidates:
        print(f'{candidate.run_date:<10}  {candidate.recovery_type}')
    if not candidates:
        print('(none)')
    print('\nNo recovery was executed.')
    return 0


def _incident(args: argparse.Namespace, operations: DailyOperations) -> int:
    if args.format != 'gpt':
        print('only --format gpt is supported', file=sys.stderr)
        return 2
    try:
        print(operations.render_incident_gpt(), end='')
    except DailyOperationsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _notify(args: argparse.Namespace, operations: DailyOperations) -> int:
    service = NotificationService(operations)
    if args.dry_run:
        if not args.date:
            print('--date is required with --dry-run', file=sys.stderr)
            return 2
        try:
            subject, body = service.render(args.date)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f'Subject: {subject}\n\n{body}', end='')
        return 0
    if args.pending:
        if not service.adapter.configured:
            print('Email adapter is not configured; pending notifications were unchanged.')
            return 1
        results = service.send_pending()
        for result in results:
            print(
                f"{result['date']} {result['notification_type']} "
                f"{result['delivery_status']}"
            )
        if not results:
            print('No eligible pending notifications.')
        return 0 if all(row['delivery_status'] == 'DELIVERED' for row in results) else 1
    if not args.date:
        print('use --date or --pending', file=sys.stderr)
        return 2
    service.queue(args.date)
    if not service.adapter.configured:
        print('Email adapter is not configured; notification remains pending.')
        return 1
    results = service.send_pending(run_date=args.date, limit=1)
    return 0 if results and results[0]['delivery_status'] == 'DELIVERED' else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--config', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)

    status = commands.add_parser('status', help='show one human-readable result')
    status.add_argument('--date', type=_date_arg)

    history = commands.add_parser('history', help='show recent human outcomes')
    history.add_argument('--days', type=int, default=7)

    incidents = commands.add_parser('incidents', help='list incidents')
    incidents.add_argument('--open', action='store_true')

    recover = commands.add_parser('recover', help='inspect deferred recovery')
    recover.add_argument('--dry-run', action='store_true')
    recover.add_argument('--as-of', type=_date_arg, help=argparse.SUPPRESS)

    incident = commands.add_parser('incident', help='generate an incident handoff')
    incident.add_argument('--latest', action='store_true', required=True)
    incident.add_argument('--format', choices=('gpt',), required=True)

    notify = commands.add_parser('notify', help='render or deliver email notifications')
    notify_target = notify.add_mutually_exclusive_group()
    notify_target.add_argument('--date', type=_date_arg)
    notify_target.add_argument('--pending', action='store_true')
    notify.add_argument('--dry-run', action='store_true')
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    operations = _operations(args)
    handlers = {
        'status': _status,
        'history': _history,
        'incidents': _incidents,
        'recover': _recover,
        'incident': _incident,
        'notify': _notify,
    }
    try:
        return handlers[args.command](args, operations)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
