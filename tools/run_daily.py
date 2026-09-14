#!/usr/bin/env python3
"""Run the existing production stages in order for one explicit date."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config.yaml"
CommandRunner = Callable[[Sequence[str], Path], int]


def _run(command: Sequence[str], cwd: Path) -> int:
    return subprocess.run(list(command), cwd=cwd, check=False).returncode


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)


def _load_config(config_path: Path) -> tuple[Path, Path]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError("config must contain a mapping")
    output_dir = Path(config.get("output_dir", "data/raw"))
    raw_dir = output_dir if output_dir.is_absolute() else config_path.parent / output_dir
    raw_dir = raw_dir.resolve()
    if raw_dir.name != "raw":
        raise ValueError("configured output_dir must be the raw directory of a data root")
    return raw_dir, raw_dir.parent


def _read_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("platforms"), list):
        raise ValueError("manifest must contain a platforms list")
    platforms = manifest["platforms"]
    if not platforms:
        raise ValueError("manifest contains no platform results")
    names: set[str] = set()
    for row in platforms:
        if not isinstance(row, dict) or not isinstance(row.get("platform"), str) or not row["platform"]:
            raise ValueError("manifest contains an invalid platform result")
        if row["platform"] in names:
            raise ValueError(f"manifest contains duplicate platform: {row['platform']}")
        names.add(row["platform"])
        if row.get("status") not in {"success", "partial", "error"}:
            raise ValueError(f"manifest contains invalid status for {row['platform']}")
        if not isinstance(row.get("complete"), bool):
            raise ValueError(f"manifest contains invalid complete flag for {row['platform']}")
    return manifest


def _validate_raw(path: Path) -> None:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("raw artifact must contain a JSON array")


def _failed_platforms(manifest: dict[str, Any]) -> list[str]:
    return [row["platform"] for row in manifest["platforms"] if row["status"] == "error"]


def _incomplete_platforms(manifest: dict[str, Any]) -> list[str]:
    return [
        row["platform"]
        for row in manifest["platforms"]
        if row["status"] != "success" or not row["complete"]
    ]


def _platform_errors(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        row["platform"]: row["error"]
        for row in manifest["platforms"]
        if isinstance(row.get("error"), str) and row["error"]
    }


def _artifact_marker(path: Path) -> tuple[int, int, int] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_ino, stat.st_mtime_ns, stat.st_size


def run_daily(
    run_date: str,
    *,
    config_path: Path = DEFAULT_CONFIG,
    root: Path = ROOT,
    command_runner: CommandRunner = _run,
) -> tuple[int, Path, dict[str, Any]]:
    config_path = config_path.resolve()
    fallback_data_dir = root / "data"
    status_path = fallback_data_dir / "analysis" / "runs" / f"{run_date}.json"
    status: dict[str, Any] = {
        "date": run_date,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "FAILED",
        "crawl": {
            "status": "PENDING",
            "initial_failed_platforms": [],
            "retried_platforms": [],
            "final_failed_platforms": [],
        },
        "clean": {"status": "PENDING"},
        "analysis": {"status": "PENDING"},
    }

    def fail(stage: str, error: str) -> tuple[int, Path, dict[str, Any]]:
        status[stage]["status"] = "FAILED"
        status[stage]["error"] = error
        for later in ("clean", "analysis"):
            if status[later]["status"] == "PENDING":
                status[later]["status"] = "SKIPPED"
        status["status"] = "FAILED"
        _write_json_atomic(status_path, status)
        return 1, status_path, status

    try:
        raw_dir, data_dir = _load_config(config_path)
        status_path = data_dir / "analysis" / "runs" / f"{run_date}.json"
    except (OSError, ValueError, yaml.YAMLError) as error:
        return fail("crawl", str(error))

    raw_path = raw_dir / f"{run_date}.json"
    manifest_path = raw_dir / f"{run_date}_manifest.json"
    before_raw = _artifact_marker(raw_path)
    before_manifest = _artifact_marker(manifest_path)
    crawl_command = [
        sys.executable,
        "-m",
        "src.main",
        "--config",
        str(config_path),
        "--date",
        run_date,
    ]
    try:
        initial_return_code = command_runner(crawl_command, root)
    except OSError as error:
        return fail("crawl", f"could not start crawl: {error}")
    status["crawl"]["initial_return_code"] = initial_return_code
    raw_replaced = before_raw != _artifact_marker(raw_path)
    manifest_replaced = before_manifest != _artifact_marker(manifest_path)
    if not raw_replaced or not manifest_replaced:
        return fail(
            "crawl",
            "crawl did not replace both raw and manifest artifacts for this run",
        )
    try:
        _validate_raw(raw_path)
        manifest = _read_manifest(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return fail("crawl", str(error))

    initial_failed = _failed_platforms(manifest)
    status["crawl"]["initial_failed_platforms"] = initial_failed
    status["crawl"]["initial_platform_errors"] = _platform_errors(manifest)
    retry_return_codes: dict[str, int] = {}
    for platform in initial_failed:
        retry_command = [
            sys.executable,
            "-m",
            "src.main",
            "--config",
            str(config_path),
            "--platform",
            platform,
            "--date",
            run_date,
            "--merge-existing",
        ]
        try:
            retry_return_codes[platform] = command_runner(retry_command, root)
        except OSError as error:
            retry_return_codes[platform] = -1
            status["crawl"].setdefault("retry_errors", {})[platform] = str(error)
        status["crawl"]["retried_platforms"].append(platform)
    status["crawl"]["retry_return_codes"] = retry_return_codes

    try:
        _validate_raw(raw_path)
        manifest = _read_manifest(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return fail("crawl", str(error))
    final_failed = _failed_platforms(manifest)
    incomplete = _incomplete_platforms(manifest)
    status["crawl"]["final_failed_platforms"] = final_failed
    status["crawl"]["final_incomplete_platforms"] = incomplete
    status["crawl"]["final_platform_errors"] = _platform_errors(manifest)
    if len(final_failed) == len(manifest["platforms"]):
        return fail("crawl", "all platforms failed; no usable crawl result")
    status["crawl"]["status"] = "DEGRADED" if incomplete else "SUCCESS"

    clean_command = [
        sys.executable,
        "-m",
        "src.clean.cli",
        "clean-jobs",
        "--input",
        str(raw_path),
        "--date",
        run_date,
        "--output-dir",
        str(data_dir / "clean"),
    ]
    try:
        clean_return_code = command_runner(clean_command, root)
    except OSError as error:
        return fail("clean", f"could not start clean: {error}")
    status["clean"]["return_code"] = clean_return_code
    if clean_return_code != 0:
        return fail("clean", f"clean exited with code {clean_return_code}")
    clean_path = data_dir / "clean" / f"{run_date}.json"
    if not clean_path.exists():
        return fail("clean", f"clean artifact not found: {clean_path}")
    status["clean"]["status"] = "SUCCESS"

    analysis_command = [
        sys.executable,
        "-m",
        "src.analysis.pipeline",
        "run",
        "--date",
        run_date,
        "--data-dir",
        str(data_dir),
    ]
    try:
        analysis_return_code = command_runner(analysis_command, root)
    except OSError as error:
        return fail("analysis", f"could not start analysis: {error}")
    status["analysis"]["return_code"] = analysis_return_code
    if analysis_return_code != 0:
        return fail("analysis", f"analysis exited with code {analysis_return_code}")
    required_outputs = [
        data_dir / "analysis" / "classification" / f"{run_date}.jsonl",
        data_dir / "analysis" / "events" / f"{run_date}.jsonl",
        data_dir / "analysis" / "trends" / "snapshots" / f"{run_date}.json",
    ]
    missing_outputs = [str(path) for path in required_outputs if not path.exists()]
    if missing_outputs:
        return fail("analysis", f"analysis artifacts not found: {missing_outputs}")
    status["analysis"]["status"] = "SUCCESS"
    status["status"] = "DEGRADED" if status["crawl"]["status"] == "DEGRADED" else "SUCCESS"
    _write_json_atomic(status_path, status)
    return 0, status_path, status


def _date_arg(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=_date_arg)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    return_code, status_path, status = run_daily(args.date, config_path=args.config)
    print(json.dumps({"status": status["status"], "status_file": str(status_path)}, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
