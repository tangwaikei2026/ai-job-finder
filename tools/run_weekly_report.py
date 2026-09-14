#!/usr/bin/env python3
"""Create one endpoint comparison and render it with Report V1."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.trends import compare_trends  # noqa: E402
from src.models import write_json_atomic  # noqa: E402


TREND_ROOT = ROOT / "data" / "analysis" / "trends"
REPORT_ROOT = ROOT / "data" / "analysis" / "reports"
CommandRunner = Callable[[Sequence[str], Path], int]


def _run(command: Sequence[str], cwd: Path) -> int:
    return subprocess.run(list(command), cwd=cwd, check=False).returncode


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"trend artifact must contain an object: {path}")
    return value


def run_weekly_report(
    from_date: str,
    to_date: str,
    *,
    trend_root: Path = TREND_ROOT,
    output_dir: Path = REPORT_ROOT,
    root: Path = ROOT,
    command_runner: CommandRunner = _run,
) -> tuple[int, Path]:
    if from_date >= to_date:
        raise ValueError("from date must be earlier than to date")
    before = _read(trend_root / "snapshots" / f"{from_date}.json")
    after = _read(trend_root / "snapshots" / f"{to_date}.json")
    if before.get("snapshot_date") != from_date or after.get("snapshot_date") != to_date:
        raise ValueError("snapshot date does not match requested endpoint")
    comparison = compare_trends(before, after)
    comparison_path = trend_root / "comparisons" / f"{from_date}_{to_date}.json"
    write_json_atomic(comparison_path, comparison)
    command = [
        sys.executable,
        str(root / "tools" / "generate_market_report.py"),
        "--from",
        from_date,
        "--to",
        to_date,
        "--trend-root",
        str(trend_root),
        "--output-dir",
        str(output_dir),
    ]
    return_code = command_runner(command, root)
    return return_code, output_dir / f"market_report_{from_date}_{to_date}.md"


def _date_arg(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_date", required=True, type=_date_arg)
    parser.add_argument("--to", dest="to_date", required=True, type=_date_arg)
    args = parser.parse_args(argv)
    if args.from_date >= args.to_date:
        parser.error("--from must be earlier than --to")
    try:
        return_code, report_path = run_weekly_report(args.from_date, args.to_date)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(1, f"{error}\n")
    if return_code == 0:
        print(report_path)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
