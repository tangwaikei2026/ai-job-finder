#!/usr/bin/env python3
"""Hold a bounded idle-sleep assertion across the 10:00 daily launch."""
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


CAFFEINATE = Path('/usr/bin/caffeinate')
WAKE_GUARD_SECONDS = 10 * 60


def build_command() -> list[str]:
    """Build the bounded guard command without starting an assertion."""
    return [str(CAFFEINATE), '-i', '-t', str(WAKE_GUARD_SECONDS)]


def main() -> int:
    started_at = datetime.now().astimezone().isoformat(timespec='seconds')
    print(
        f'wake_guard started_at={started_at} '
        f'timeout_seconds={WAKE_GUARD_SECONDS}',
        flush=True,
    )
    completed = subprocess.run(build_command(), check=False)
    finished_at = datetime.now().astimezone().isoformat(timespec='seconds')
    print(
        f'wake_guard finished_at={finished_at} '
        f'return_code={completed.returncode}',
        flush=True,
    )
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())
