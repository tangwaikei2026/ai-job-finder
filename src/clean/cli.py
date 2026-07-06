from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from src.clean.audit import run_audit


def _date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raw job data quality tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser(
        "audit",
        help="audit a RawJobPosting JSON file",
    )
    audit_parser.add_argument("--input", type=Path, required=True)
    audit_parser.add_argument("--date", type=_date, required=True)
    audit_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/audit"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "audit":
        json_path, markdown_path, report = run_audit(
            args.input,
            audit_date=args.date,
            output_dir=args.output_dir,
        )
        print(f"Audited {report['manifest']['job_count']} jobs")
        print(f"Wrote {json_path}")
        print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    main()

