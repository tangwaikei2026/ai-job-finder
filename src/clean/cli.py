from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from src.clean.audit import run_audit
from src.clean.jobs import run_clean_jobs


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
    clean_parser = subparsers.add_parser(
        "clean-jobs",
        help="normalize job cities and summarize them by company",
    )
    clean_parser.add_argument("--input", type=Path, required=True)
    clean_parser.add_argument("--date", type=_date)
    clean_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/clean"),
    )
    clean_parser.add_argument("--output", type=Path)
    clean_parser.add_argument("--report-output", type=Path)
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
    elif args.command == "clean-jobs":
        if args.output is None:
            if args.date is None:
                raise SystemExit("clean-jobs requires --date when --output is omitted")
            output = args.output_dir / f"{args.date}.clean.json"
        else:
            output = args.output
        report_output = args.report_output
        if report_output is None and args.output is None:
            report_output = args.output_dir / f"{args.date}.clean_report.json"
        report = run_clean_jobs(
            args.input,
            output_path=output,
            report_path=report_output,
        )
        print(f"Cleaned {report['manifest']['job_count']} jobs")
        print(f"Wrote {output}")
        print(f"Wrote {report['manifest']['report_file']}")


if __name__ == "__main__":
    main()
