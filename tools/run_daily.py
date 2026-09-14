#!/usr/bin/env python3
"""Run the existing production stages in order for one explicit date."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config.yaml"
MIN_PYTHON = (3, 10)
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
        if row["complete"] != (row["status"] == "success"):
            raise ValueError(
                f"manifest status/complete mismatch for {row['platform']}"
            )
    return manifest


def _validate_raw(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("raw artifact must contain a JSON array")
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"raw artifact row {row_number} must be an object")
        if not isinstance(row.get("platform"), str) or not row["platform"]:
            raise ValueError(
                f"raw artifact row {row_number} has an invalid platform"
            )
        if not isinstance(row.get("job_id"), str) or not row["job_id"]:
            raise ValueError(f"raw artifact row {row_number} has an invalid job_id")
    return rows


def _validate_platform_counts(
    rows: list[dict[str, Any]], manifest: dict[str, Any], *, artifact: str
) -> None:
    counts = Counter(row["platform"] for row in rows)
    manifest_platforms = {row["platform"] for row in manifest["platforms"]}
    unknown_platforms = sorted(set(counts) - manifest_platforms)
    if unknown_platforms:
        raise ValueError(
            f"{artifact} contains platforms absent from manifest: {unknown_platforms}"
        )
    for platform in manifest["platforms"]:
        expected = platform.get("jobs_in_scope")
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
            raise ValueError(
                f"manifest contains invalid jobs_in_scope for {platform['platform']}"
            )
        actual = counts.get(platform["platform"], 0)
        if actual != expected:
            raise ValueError(
                f"{artifact}/manifest count mismatch for {platform['platform']}: "
                f"{actual} != {expected}"
            )


def _validate_existing_observation(
    raw_path: Path,
    manifest_path: Path,
    config_path: Path,
    *,
    require_usable: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _validate_raw(raw_path)
    manifest = _read_manifest(manifest_path)
    recorded_config = manifest.get("config")
    if not isinstance(recorded_config, str) or not recorded_config:
        raise ValueError("manifest does not identify its config")
    if Path(recorded_config).resolve() != config_path.resolve():
        raise ValueError(
            f"manifest config mismatch: {recorded_config} != {config_path}"
        )
    manifest_job_count = manifest.get("job_count")
    if (
        isinstance(manifest_job_count, bool)
        or not isinstance(manifest_job_count, int)
        or manifest_job_count < 0
    ):
        raise ValueError("manifest contains an invalid job_count")
    if manifest_job_count != len(rows):
        raise ValueError(
            f"raw/manifest job_count mismatch: {len(rows)} != {manifest_job_count}"
        )
    manifest_complete = manifest.get("complete")
    expected_complete = all(row["complete"] for row in manifest["platforms"])
    if not isinstance(manifest_complete, bool) or manifest_complete != expected_complete:
        raise ValueError("manifest complete flag is inconsistent with platform results")
    _validate_platform_counts(rows, manifest, artifact="raw artifact")
    if require_usable and all(
        row["status"] == "error" for row in manifest["platforms"]
    ):
        raise ValueError("all platforms failed; no usable crawl result")
    return rows, manifest


def _validate_clean_artifact(
    path: Path,
    manifest: dict[str, Any],
    raw_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("clean artifact must contain a JSON array")
    required_lists = (
        "locations_norm",
        "location_level",
        "province_norm",
        "city_norm",
    )
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"clean artifact row {row_number} must be an object")
        if not isinstance(row.get("platform"), str) or not row["platform"]:
            raise ValueError(
                f"clean artifact row {row_number} has an invalid platform"
            )
        if not isinstance(row.get("job_id"), str) or not row["job_id"]:
            raise ValueError(
                f"clean artifact row {row_number} has an invalid job_id"
            )
        if any(not isinstance(row.get(field), list) for field in required_lists):
            raise ValueError(
                f"clean artifact row {row_number} lacks normalization fields"
            )
    if len(rows) != manifest["job_count"]:
        raise ValueError(
            f"clean/manifest job_count mismatch: {len(rows)} != "
            f"{manifest['job_count']}"
        )
    _validate_platform_counts(rows, manifest, artifact="clean artifact")
    raw_identities = Counter(
        (row["platform"], row["job_id"]) for row in raw_rows
    )
    clean_identities = Counter((row["platform"], row["job_id"]) for row in rows)
    if clean_identities != raw_identities:
        raise ValueError("clean/raw job identities do not match")
    return rows


def _python_version() -> tuple[int, int, int]:
    return sys.version_info[:3]


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
    resume_from: str | None = None,
) -> tuple[int, Path, dict[str, Any]]:
    config_path = config_path.resolve()
    fallback_data_dir = root / "data"
    status_path = fallback_data_dir / "analysis" / "runs" / f"{run_date}.json"
    python_version = _python_version()
    status: dict[str, Any] = {
        "date": run_date,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "FAILED",
        "python_executable": sys.executable,
        "python_version": ".".join(str(part) for part in python_version),
        "crawl": {
            "status": "PENDING",
            "initial_failed_platforms": [],
            "retried_platforms": [],
            "final_failed_platforms": [],
        },
        "clean": {"status": "PENDING"},
        "analysis": {"status": "PENDING"},
    }
    if resume_from is not None:
        status["resume_from"] = resume_from

    def fail(
        stage: str,
        error: str,
        *,
        reason: str | None = None,
    ) -> tuple[int, Path, dict[str, Any]]:
        status[stage]["status"] = "FAILED"
        status[stage]["error"] = error
        if reason is not None:
            status["reason"] = reason
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

    if resume_from not in {None, "clean", "analysis"}:
        return fail("crawl", f"unsupported resume stage: {resume_from}")
    if python_version[:2] < MIN_PYTHON:
        required = ".".join(str(part) for part in MIN_PYTHON)
        actual = ".".join(str(part) for part in python_version)
        return fail(
            "crawl",
            f"Python {required}+ is required; runner uses {actual} at {sys.executable}",
            reason="unsupported_python",
        )

    raw_path = raw_dir / f"{run_date}.json"
    manifest_path = raw_dir / f"{run_date}_manifest.json"
    clean_path = data_dir / "clean" / f"{run_date}.json"

    if resume_from is None:
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
            raw_rows, manifest = _validate_existing_observation(
                raw_path,
                manifest_path,
                config_path,
                require_usable=False,
            )
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
                status["crawl"].setdefault("retry_errors", {})[platform] = str(
                    error
                )
            status["crawl"]["retried_platforms"].append(platform)
        status["crawl"]["retry_return_codes"] = retry_return_codes

        try:
            raw_rows, manifest = _validate_existing_observation(
                raw_path,
                manifest_path,
                config_path,
                require_usable=False,
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return fail("crawl", str(error))
    else:
        try:
            raw_rows, manifest = _validate_existing_observation(
                raw_path,
                manifest_path,
                config_path,
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return fail("crawl", f"resume validation failed: {error}")
        status["crawl"]["reused_artifacts"] = True
        status["crawl"]["retry_skipped"] = True

    final_failed = _failed_platforms(manifest)
    incomplete = _incomplete_platforms(manifest)
    status["crawl"]["final_failed_platforms"] = final_failed
    status["crawl"]["final_incomplete_platforms"] = incomplete
    status["crawl"]["final_platform_errors"] = _platform_errors(manifest)
    if len(final_failed) == len(manifest["platforms"]):
        return fail("crawl", "all platforms failed; no usable crawl result")
    status["crawl"]["status"] = "DEGRADED" if incomplete else "SUCCESS"

    if resume_from == "analysis":
        try:
            _validate_clean_artifact(clean_path, manifest, raw_rows)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return fail("clean", f"resume validation failed: {error}")
        status["clean"]["status"] = "SUCCESS"
        status["clean"]["reused_artifact"] = True
    else:
        before_clean = _artifact_marker(clean_path)
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
        if before_clean == _artifact_marker(clean_path):
            return fail("clean", "clean did not replace its dated artifact")
        try:
            _validate_clean_artifact(clean_path, manifest, raw_rows)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return fail("clean", str(error))
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
    parser.add_argument("--resume-from", choices=("clean", "analysis"))
    args = parser.parse_args(argv)
    return_code, status_path, status = run_daily(
        args.date,
        config_path=args.config,
        resume_from=args.resume_from,
    )
    print(json.dumps({"status": status["status"], "status_file": str(status_path)}, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
