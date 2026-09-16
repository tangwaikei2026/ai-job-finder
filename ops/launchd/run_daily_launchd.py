#!/usr/bin/env python3
"""Supply the runtime local date to the official daily production wrapper."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


PRODUCTION_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_PYTHON = PRODUCTION_ROOT / 'venv' / 'bin' / 'python'
PRODUCTION_WRAPPER = PRODUCTION_ROOT / 'tools' / 'run_daily_with_health.py'


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


def main() -> None:
    command = build_command()
    os.execv(command[0], command)


if __name__ == '__main__':
    main()
