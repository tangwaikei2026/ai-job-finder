#!/usr/bin/env python3
"""Run the existing Daily Runner, then interpret its completed observation."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.daily_health import generate_daily_health  # noqa: E402
from src.operations.daily_ops import (  # noqa: E402
    DailyOperations,
    RecoveryOutcome,
    write_ops_failure_evidence,
)
from tools.run_daily import DEFAULT_CONFIG, run_daily  # noqa: E402


Runner = Callable[..., tuple[int, Path, dict[str, Any]]]
HealthGenerator = Callable[..., tuple[Path, dict[str, Any]]]
RUNNABLE_RUNNER_STATUSES = frozenset({'SUCCESS', 'DEGRADED'})


class OrchestrationBusyError(RuntimeError):
    """Another daily orchestration owns the project lock."""


@contextmanager
def _exclusive_lock(root: Path) -> Iterator[Path]:
    project_key = hashlib.sha256(str(root.resolve()).encode('utf-8')).hexdigest()[:24]
    lock_path = Path(tempfile.gettempdir()) / f'ai-job-finder-daily-{project_key}.lock'
    handle = lock_path.open('a+', encoding='utf-8')
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OrchestrationBusyError('daily orchestration is already running') from exc
        yield lock_path
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _read_final_status(path: Path, run_date: str, runner_status: str) -> None:
    try:
        persisted = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'runner status artifact is unavailable: {exc}') from exc
    if not isinstance(persisted, Mapping):
        raise ValueError('runner status artifact must contain an object')
    if persisted.get('date') != run_date or persisted.get('status') != runner_status:
        raise ValueError('runner status artifact does not match the completed run')


def _remove_health(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise ValueError(f'could not invalidate health artifact: {exc}') from exc


def _publish_ops(
    operations: DailyOperations,
    run_date: str,
    *,
    run: Mapping[str, Any],
    health: Mapping[str, Any] | None,
    recovery: RecoveryOutcome,
    summary: dict[str, Any],
    orchestration_error: str | None = None,
) -> None:
    """Publish Operations without changing the completed production result."""
    try:
        artifact = operations.publish(
            run_date,
            run=run,
            health=health,
            recovery=recovery,
            orchestration_error=orchestration_error,
        )
        summary.update(
            ops_status=artifact['ops_status'],
            ops_file=str(operations.ops_dir / 'latest.json'),
            human_summary_file=str(operations.ops_dir / 'latest.md'),
            gpt_review_required=artifact['gpt_review_required'],
        )
    except Exception as exc:
        summary['ops_error'] = str(exc)
        try:
            write_ops_failure_evidence(
                data_dir=operations.data_dir,
                run_date=run_date,
                error=str(exc),
                run=run,
            )
        except Exception as evidence_error:
            summary['ops_failure_evidence_error'] = str(evidence_error)


def _run_locked(
    run_date: str,
    *,
    config_path: Path,
    root: Path,
    resume_from: str | None,
    runner: Runner,
    health_generator: HealthGenerator,
) -> tuple[int, dict[str, Any]]:
    try:
        runner_code, status_path_value, status = runner(
            run_date,
            config_path=config_path,
            root=root,
            resume_from=resume_from,
        )
    except Exception as exc:
        summary = {'phase': 'runner', 'error': str(exc)}
        synthetic_run = {
            'date': run_date,
            'status': 'FAILED',
            'crawl': {'status': 'FAILED', 'error': str(exc)},
            'clean': {'status': 'SKIPPED'},
            'analysis': {'status': 'SKIPPED'},
        }
        operations = DailyOperations(
            data_dir=Path(root) / 'data',
            root=root,
            config_path=config_path,
            trigger=os.environ.get('AI_JOB_FINDER_TRIGGER', 'daily_wrapper'),
        )
        _publish_ops(
            operations,
            run_date,
            run=synthetic_run,
            health=None,
            recovery=RecoveryOutcome(),
            summary=summary,
            orchestration_error=f'runner raised an exception: {exc}',
        )
        return 1, summary

    if not isinstance(status, Mapping):
        summary = {'phase': 'runner', 'error': 'runner returned an invalid status'}
        write_ops_failure_evidence(
            data_dir=Path(root) / 'data',
            run_date=run_date,
            error=summary['error'],
        )
        return 1, summary
    runner_status = status.get('status')
    status_path = Path(status_path_value).resolve()
    data_root = status_path.parents[2]
    operations = DailyOperations(
        data_dir=data_root,
        root=root,
        config_path=config_path,
        trigger=os.environ.get('AI_JOB_FINDER_TRIGGER', 'daily_wrapper'),
    )
    recovery = RecoveryOutcome()
    summary: dict[str, Any] = {
        'runner_status': runner_status,
        'status_file': str(status_path),
    }
    try:
        _read_final_status(status_path, run_date, str(runner_status))
    except ValueError as exc:
        summary.update(phase='runner', error=str(exc))
        _publish_ops(
            operations,
            run_date,
            run=status,
            health=None,
            recovery=recovery,
            summary=summary,
            orchestration_error=str(exc),
        )
        return 1, summary

    if runner_code != 0 or runner_status not in RUNNABLE_RUNNER_STATUSES:
        if runner_code != 0 and runner_status == 'FAILED':
            recovery = operations.attempt_recovery(
                run_date,
                status,
                runner=runner,
            )
            summary['automatic_recovery'] = recovery.as_dict()
            if recovery.result == 'SUCCESS' and recovery.runner_result is not None:
                runner_code, recovered_path, recovered_status = recovery.runner_result
                status_path = Path(recovered_path).resolve()
                status = recovered_status
                runner_status = status.get('status')
                summary.update(
                    runner_status=runner_status,
                    status_file=str(status_path),
                )
            else:
                effective_status = status
                if recovery.runner_result is not None:
                    candidate = recovery.runner_result[2]
                    if isinstance(candidate, Mapping):
                        effective_status = candidate
                summary.update(phase='runner', error='runner did not complete successfully')
                _publish_ops(
                    operations,
                    run_date,
                    run=effective_status,
                    health=None,
                    recovery=recovery,
                    summary=summary,
                )
                return 1, summary
        else:
            summary.update(phase='runner', error='runner did not complete successfully')
            _publish_ops(
                operations,
                run_date,
                run=status,
                health=None,
                recovery=recovery,
                summary=summary,
                orchestration_error='inconsistent runner return code or status',
            )
            return 1, summary

    health_path = data_root / 'analysis' / 'health' / f'{run_date}.json'
    try:
        _remove_health(health_path)
        generated_path, health = health_generator(run_date, data_dir=data_root)
        if Path(generated_path).resolve() != health_path.resolve() or not health_path.is_file():
            raise ValueError('Daily Health did not write the expected dated artifact')
        if not isinstance(health, Mapping):
            raise ValueError('Daily Health returned an invalid artifact')
        overall_action = health.get('overall_action')
        if overall_action not in {'NO_NEW_ACTION', 'ACTION_REQUIRED'}:
            raise ValueError('Daily Health returned an invalid overall_action')
    except Exception as exc:
        try:
            _remove_health(health_path)
        except ValueError:
            pass
        summary.update(phase='health', error=str(exc))
        _publish_ops(
            operations,
            run_date,
            run=status,
            health=None,
            recovery=recovery,
            summary=summary,
            orchestration_error=f'Daily Health generation failed: {exc}',
        )
        return 1, summary

    summary.update(
        phase='complete',
        health_file=str(health_path),
        overall_action=overall_action,
    )
    _publish_ops(
        operations,
        run_date,
        run=status,
        health=health,
        recovery=recovery,
        summary=summary,
    )
    return (0 if overall_action == 'NO_NEW_ACTION' else 2), summary


def run_daily_with_health(
    run_date: str,
    *,
    config_path: Path = DEFAULT_CONFIG,
    root: Path = ROOT,
    resume_from: str | None = None,
    runner: Runner = run_daily,
    health_generator: HealthGenerator = generate_daily_health,
) -> tuple[int, dict[str, Any]]:
    """Coordinate the two existing owners without changing either contract."""
    try:
        with _exclusive_lock(root):
            return _run_locked(
                run_date,
                config_path=Path(config_path),
                root=Path(root),
                resume_from=resume_from,
                runner=runner,
                health_generator=health_generator,
            )
    except (OSError, OrchestrationBusyError) as exc:
        return 1, {'phase': 'lock', 'error': str(exc)}


def _date_arg(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError('date must use YYYY-MM-DD') from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True, type=_date_arg)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--resume-from', choices=('clean', 'analysis'))
    args = parser.parse_args(argv)
    return_code, summary = run_daily_with_health(
        args.date,
        config_path=args.config,
        resume_from=args.resume_from,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return return_code


if __name__ == '__main__':
    raise SystemExit(main())
