#!/usr/bin/env python3
"""Supply the runtime local date to the official daily production wrapper."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


PRODUCTION_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_PYTHON = PRODUCTION_ROOT / 'venv' / 'bin' / 'python'
PRODUCTION_WRAPPER = PRODUCTION_ROOT / 'tools' / 'run_daily_with_health.py'
LOG_DIR = PRODUCTION_ROOT / 'data' / 'logs'
LOG_PATHS = (
    LOG_DIR / 'launchd-daily.stdout.log',
    LOG_DIR / 'launchd-daily.stderr.log',
)
MAX_LOG_BYTES = 512 * 1024
LOG_BACKUPS = 3


def build_command(now: datetime | None = None) -> list[str]:
    """Build the production command without running it."""
    runtime_now = datetime.now().astimezone() if now is None else now
    run_date = runtime_now.date().isoformat()
    return [
        str(PRODUCTION_PYTHON),
        str(PRODUCTION_WRAPPER),
        '--date',
        run_date,
    ]


def rotate_log(path: Path, *, max_bytes: int = MAX_LOG_BYTES, backups: int = LOG_BACKUPS) -> bool:
    """Keep a small fixed set of launchd logs; never read or copy log content."""
    try:
        if path.stat().st_size <= max_bytes:
            return False
    except FileNotFoundError:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    for candidate in path.parent.glob(f'{path.name}.*'):
        suffix = candidate.name.removeprefix(f'{path.name}.')
        if suffix.isdigit() and int(suffix) > backups:
            candidate.unlink(missing_ok=True)
    oldest = path.with_name(f'{path.name}.{backups}')
    oldest.unlink(missing_ok=True)
    for index in range(backups - 1, 0, -1):
        source = path.with_name(f'{path.name}.{index}')
        if source.exists():
            os.replace(source, path.with_name(f'{path.name}.{index + 1}'))
    os.replace(path, path.with_name(f'{path.name}.1'))
    return True


def main() -> None:
    for log_path in LOG_PATHS:
        rotate_log(log_path)
    os.environ.setdefault('AI_JOB_FINDER_TRIGGER', 'launchd')
    command = build_command()
    os.execv(command[0], command)


if __name__ == '__main__':
    main()
