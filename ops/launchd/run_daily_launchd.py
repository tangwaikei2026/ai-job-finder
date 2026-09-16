#!/usr/bin/env python3
"""Supply the runtime local date to the official daily production wrapper."""
from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Mapping


PRODUCTION_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_PYTHON = PRODUCTION_ROOT / 'venv' / 'bin' / 'python'
PRODUCTION_WRAPPER = PRODUCTION_ROOT / 'tools' / 'run_daily_with_health.py'
CAFFEINATE = Path('/usr/bin/caffeinate')
LOG_DIR = PRODUCTION_ROOT / 'data' / 'logs'
LOG_PATHS = (
    LOG_DIR / 'launchd-daily.stdout.log',
    LOG_DIR / 'launchd-daily.stderr.log',
)
MAX_LOG_BYTES = 512 * 1024
LOG_BACKUPS = 3
EMAIL_CONFIG_PATH = (
    Path.home() / 'Library' / 'Application Support' / 'ai-job-finder' / 'email.json'
)
EMAIL_ENVIRONMENT_KEYS = frozenset({
    'AI_JOB_FINDER_EMAIL_HOST',
    'AI_JOB_FINDER_EMAIL_PORT',
    'AI_JOB_FINDER_EMAIL_FROM',
    'AI_JOB_FINDER_EMAIL_TO',
    'AI_JOB_FINDER_EMAIL_USERNAME',
    'AI_JOB_FINDER_EMAIL_PASSWORD',
    'AI_JOB_FINDER_EMAIL_SECURITY',
})


class EmailEnvironmentError(ValueError):
    """The user-local Email configuration could not be loaded safely."""


def load_email_environment(
    path: Path = EMAIL_CONFIG_PATH,
    *,
    environment: dict[str, str] | None = None,
) -> bool:
    """Load a private, user-owned Email config without shell evaluation."""
    target = Path(path)
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise EmailEnvironmentError('Email config metadata is not readable') from exc
    try:
        parent_metadata = target.parent.lstat()
    except OSError as exc:
        raise EmailEnvironmentError('Email config directory metadata is not readable') from exc
    if parent_metadata.st_uid != os.getuid():
        raise EmailEnvironmentError('Email config directory must be owned by the current user')
    if stat.S_IMODE(parent_metadata.st_mode) & 0o077:
        raise EmailEnvironmentError('Email config directory permissions must not exceed 0700')
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise EmailEnvironmentError('Email config must be a regular, non-symlink file')
    if metadata.st_uid != os.getuid():
        raise EmailEnvironmentError('Email config must be owned by the current user')
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise EmailEnvironmentError('Email config permissions must not exceed 0600')
    try:
        document = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EmailEnvironmentError('Email config is not readable valid JSON') from exc
    if not isinstance(document, Mapping):
        raise EmailEnvironmentError('Email config must contain a JSON object')
    unknown = set(document) - EMAIL_ENVIRONMENT_KEYS
    if unknown:
        raise EmailEnvironmentError('Email config contains unsupported keys')
    if not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in document.items()
    ):
        raise EmailEnvironmentError('Email config keys and values must be strings')
    destination = os.environ if environment is None else environment
    for key, value in document.items():
        destination.setdefault(key, value)
    return True


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


def build_caffeinated_command(command: list[str]) -> list[str]:
    """Prevent idle system sleep only while the production command is running."""
    return [str(CAFFEINATE), '-i', *command]


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
    try:
        load_email_environment()
    except EmailEnvironmentError as exc:
        print(f'Email configuration was not loaded: {exc}', file=sys.stderr)
    os.environ.setdefault('AI_JOB_FINDER_TRIGGER', 'launchd')
    command = build_caffeinated_command(build_command())
    os.execv(command[0], command)


if __name__ == '__main__':
    main()
