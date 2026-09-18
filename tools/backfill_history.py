#!/usr/bin/env python3
"""Backfill deterministic derived artifacts from saved historical observations.

This tool never invokes a collector.  It validates saved raw/manifest/clean
triples, delegates derivation to the current production analysis functions, and
preserves every pre-existing artifact byte-for-byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.ai_eval_jobs import _write_text_atomic, load_jobs
from src.analysis.daily_health import generate_daily_health
from src.analysis.pipeline import DEFAULT_VERSION_CONFIG, replay
from src.analysis.source_health import SourceHealth
from src.models import write_json_atomic
from src.operations.daily_ops import DailyOperations
from tools.generate_market_report import render_snapshot
from tools.run_daily import (
    DEFAULT_CONFIG,
    _read_manifest,
    _validate_clean_artifact,
    _validate_platform_counts,
    _validate_raw,
)


DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_AUDIT_DIR = DEFAULT_DATA_DIR / "analysis" / "audit"
DATE_PATTERN = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
RESULTS = {
    "ALREADY_COMPLETE",
    "BACKFILLED",
    "PARTIAL_BACKFILL",
    "NOT_RECOVERABLE",
    "FAILED",
}
CORE_FIELDS = ("classification_present", "events_present", "trend_snapshot_present", "audit_present")
OPS_FIELDS = ("daily_status_present", "daily_health_present", "historical_db_present_or_registered")


def dependency_map() -> dict[str, dict[str, Any]]:
    """Document the current production dependency graph with code owners."""
    return {
        "Production AI job analysis": {
            "entrypoint": "src.analysis.ai_eval_jobs.run_analysis",
            "inputs": ["dated clean jobs", "config.yaml company scope"],
            "outputs": ["*_ai_eval_analysis.json", "*_ai_eval_report.md", "*_ai_eval_hits.jsonl"],
            "backfill_role": "reference-only; not required by the current derived pipeline",
        },
        "Classification / Personal Fit": {
            "entrypoint": "src.analysis.pipeline.replay -> src.analysis.classification.classify_record",
            "inputs": ["dated clean jobs", "SourceHealth", "classifier versions", "prior reliable classification"],
            "outputs": ["analysis/classification/YYYY-MM-DD.jsonl"],
        },
        "SourceHealth": {
            "entrypoint": "src.analysis.source_health.SourceHealth",
            "inputs": ["crawl manifest", "dated clean jobs"],
            "outputs": ["in-memory reliability used by lifecycle, trend, audit, and Daily Health"],
        },
        "Lifecycle / Events": {
            "entrypoint": "src.analysis.lifecycle.Lifecycle.observe",
            "inputs": ["strictly chronological clean observations", "SourceHealth", "prior lifecycle state"],
            "outputs": ["analysis/events/YYYY-MM-DD.jsonl"],
        },
        "Trend": {
            "entrypoint": "src.analysis.trends.trend_snapshot / compare_trends",
            "inputs": ["classification", "canonical events", "SourceHealth", "present clean identities", "prior history"],
            "outputs": ["analysis/trends/snapshots/YYYY-MM-DD.json", "optional comparisons"],
            "reliability_gate": "src.analysis.trends.trend_comparability",
        },
        "Trend report": {
            "entrypoint": "tools.generate_market_report.render_snapshot",
            "inputs": ["canonical trend snapshot"],
            "outputs": ["analysis/reports/market_report_YYYY-MM-DD.md"],
        },
        "Audit": {
            "entrypoint": "src.analysis.audit_bundle.export_bundle",
            "inputs": ["clean jobs", "classification", "SourceHealth", "events", "trend", "prior observation"],
            "outputs": ["analysis/audit/YYYY-MM-DD_bundle.json"],
        },
        "Daily Health": {
            "entrypoint": "src.analysis.daily_health.generate_daily_health",
            "inputs": ["actual daily run status", "crawl manifest", "clean jobs", "known-limitations registry"],
            "outputs": ["analysis/health/YYYY-MM-DD.json"],
        },
        "Daily run status": {
            "entrypoint": "tools.run_daily.run_daily",
            "inputs": ["actual crawl/clean/analysis execution results"],
            "outputs": ["analysis/runs/YYYY-MM-DD.json"],
            "backfill_policy": "never synthesize from artifacts after the fact",
        },
        "History registration": {
            "entrypoint": "src.operations.daily_ops.DailyOperations.publish",
            "inputs": ["actual daily run status", "Daily Health"],
            "outputs": ["ops/ops.sqlite3 runs and sources rows"],
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _git(root: Path, *args: str, fallback: str = "UNKNOWN") -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return fallback


def _db_dates(data_dir: Path) -> set[str]:
    path = data_dir / "ops" / "ops.sqlite3"
    if not path.is_file():
        return set()
    try:
        uri = f"file:{path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            return {str(row[0]) for row in connection.execute("SELECT run_date FROM runs")}
    except sqlite3.Error:
        return set()


def discover_dates(data_dir: Path) -> list[str]:
    """Discover dates from files and the history DB rather than assuming a range."""
    found = set(_db_dates(data_dir))
    for path in data_dir.rglob("*"):
        if not path.is_file():
            continue
        match = DATE_PATTERN.search(path.name)
        if match:
            try:
                found.add(date.fromisoformat(match.group(1)).isoformat())
            except ValueError:
                continue
    return sorted(found)


def artifact_paths(run_date: str, data_dir: Path) -> dict[str, Path]:
    analysis = data_dir / "analysis"
    return {
        "raw": data_dir / "raw" / f"{run_date}.json",
        "manifest": data_dir / "raw" / f"{run_date}_manifest.json",
        "clean": data_dir / "clean" / f"{run_date}.json",
        "clean_report": data_dir / "clean" / f"{run_date}_report.json",
        "production_ai_analysis": analysis / f"{run_date}_ai_eval_analysis.json",
        "production_ai_hits": analysis / f"{run_date}_ai_eval_hits.jsonl",
        "production_ai_report": analysis / f"{run_date}_ai_eval_report.md",
        "classification": analysis / "classification" / f"{run_date}.jsonl",
        "events": analysis / "events" / f"{run_date}.jsonl",
        "trend_snapshot": analysis / "trends" / "snapshots" / f"{run_date}.json",
        "trend_report": analysis / "reports" / f"market_report_{run_date}.md",
        "audit": analysis / "audit" / f"{run_date}_bundle.json",
        "replay_audit": analysis / "audit" / f"{run_date}_{run_date}_replay.json",
        "daily_status": analysis / "runs" / f"{run_date}.json",
        "daily_health": analysis / "health" / f"{run_date}.json",
    }


def _trend_has_reliability(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        value = _read_json(path)
        platforms = value.get("platforms")
        return isinstance(platforms, Mapping) and all(
            isinstance(row, Mapping) and isinstance(row.get("reliability"), Mapping)
            for row in platforms.values()
        )
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def _health_has_source_health(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        sources = _read_json(path).get("sources")
        return isinstance(sources, Mapping) and all(
            isinstance(row, Mapping) and isinstance(row.get("source_health"), Mapping)
            for row in sources.values()
        )
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def _validate_historical_inputs(run_date: str, data_dir: Path) -> list[str]:
    paths = artifact_paths(run_date, data_dir)
    missing = [name for name in ("raw", "manifest", "clean") if not paths[name].is_file()]
    if missing:
        return [f"MISSING_{name.upper()}" for name in missing]
    try:
        raw_rows = _validate_raw(paths["raw"])
        manifest = _read_manifest(paths["manifest"])
        _validate_platform_counts(raw_rows, manifest, artifact="raw artifact")
        clean_rows = _validate_clean_artifact(paths["clean"], manifest, raw_rows)
        health = SourceHealth(manifest, clean_rows)
        for platform, company in health.scopes():
            health.resolve(platform, company)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return [f"HISTORICAL_INPUT_VALIDATION_FAILED: {exc}"]
    return []


def inventory_date(run_date: str, data_dir: Path, *, db_dates: set[str] | None = None) -> dict[str, Any]:
    paths = artifact_paths(run_date, data_dir)
    database_dates = db_dates if db_dates is not None else _db_dates(data_dir)
    validation_errors = _validate_historical_inputs(run_date, data_dir)
    classification = paths["classification"].is_file()
    production_ai = paths["production_ai_analysis"].is_file()
    trend = paths["trend_snapshot"].is_file()
    events = paths["events"].is_file()
    health = paths["daily_health"].is_file()
    run_status = paths["daily_status"].is_file()
    replayable = not validation_errors
    missing_inputs = list(validation_errors)
    if not run_status:
        missing_inputs.append("MISSING_ACTUAL_DAILY_RUN_STATUS")
    result = {
        "date": run_date,
        "crawl_present": paths["raw"].is_file(),
        "crawl_manifest_present": paths["manifest"].is_file(),
        "clean_present": paths["clean"].is_file(),
        "clean_report_present": paths["clean_report"].is_file(),
        "analysis_present": production_ai or classification,
        "production_ai_analysis_present": production_ai,
        "production_ai_hits_present": paths["production_ai_hits"].is_file(),
        "classification_present": classification,
        "personal_fit_present": classification,
        "source_health_present": _health_has_source_health(paths["daily_health"]),
        "reliability_present": _trend_has_reliability(paths["trend_snapshot"]),
        "lifecycle_present": events and trend,
        "events_present": events,
        "trend_snapshot_present": trend,
        "trend_report_present": paths["trend_report"].is_file(),
        "audit_present": paths["audit"].is_file(),
        "daily_status_present": run_status,
        "daily_health_present": health,
        "historical_db_present_or_registered": run_date in database_dates,
        "can_backfill_source_health": replayable,
        "can_backfill_lifecycle": replayable,
        "can_backfill_events": replayable,
        "can_backfill_trend": replayable,
        "can_backfill_audit": replayable,
        "can_backfill_daily_status": False,
        "can_backfill_daily_health": replayable and run_status,
        "missing_inputs": missing_inputs,
        "notes": [],
    }
    if not production_ai:
        result["notes"].append("No legacy/full *_ai_eval_analysis.json artifact; current pipeline does not require it")
    if not run_status:
        result["notes"].append("Daily run status is execution evidence and cannot be reconstructed honestly")
    return result


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".backfill.tmp")
    shutil.copyfile(source, temporary)
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, destination)


def _promote_or_verify(
    source: Path,
    destination: Path,
    *,
    root: Path,
    generated: list[str],
    preserved: list[str],
    mismatches: list[str],
) -> None:
    label = _relative(destination, root)
    if destination.exists():
        preserved.append(label)
        if _sha256(source) != _sha256(destination):
            mismatches.append(label)
        return
    _atomic_copy(source, destination)
    generated.append(label)


def _stable_generated_at(paths: Mapping[str, Path]) -> str | None:
    for name in ("daily_status", "manifest"):
        path = paths[name]
        if not path.is_file():
            continue
        try:
            value = _read_json(path).get("generated_at")
            if isinstance(value, str) and value:
                return value
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    return None


def _register_history_if_possible(
    run_date: str,
    *,
    data_dir: Path,
    root: Path,
    config_path: Path,
) -> bool:
    if run_date in _db_dates(data_dir):
        return False
    paths = artifact_paths(run_date, data_dir)
    if not paths["daily_status"].is_file() or not paths["daily_health"].is_file():
        return False
    run = _read_json(paths["daily_status"])
    health = _read_json(paths["daily_health"])
    stable = _stable_generated_at(paths) or run_date
    operations = DailyOperations(
        data_dir=data_dir,
        root=root,
        config_path=config_path,
        trigger="historical_backfill",
        generated_at=lambda: stable,
    )
    operations.publish(run_date, run=run, health=health, write_latest=False)
    return True


def _backfill_date(
    run_date: str,
    *,
    data_dir: Path,
    root: Path,
    config_path: Path,
    settings_path: Path,
) -> dict[str, Any]:
    generated: list[str] = []
    preserved: list[str] = []
    mismatches: list[str] = []
    failed_stage: str | None = None
    error: str | None = None
    paths = artifact_paths(run_date, data_dir)
    errors = _validate_historical_inputs(run_date, data_dir)
    if errors:
        return {
            "generated_artifacts": generated,
            "preserved_artifacts": preserved,
            "existing_artifact_mismatches": mismatches,
            "failed_stage": None,
            "error": None,
            "skip_reasons": errors,
        }
    try:
        with tempfile.TemporaryDirectory(prefix=f"ai-job-backfill-{run_date}-") as temporary:
            stage = Path(temporary) / "analysis"
            replay(
                run_date,
                run_date,
                data_dir=data_dir,
                output_dir=stage,
                settings_path=settings_path,
            )
            for name, relative in (
                ("classification", Path("classification") / f"{run_date}.jsonl"),
                ("events", Path("events") / f"{run_date}.jsonl"),
                ("trend_snapshot", Path("trends") / "snapshots" / f"{run_date}.json"),
                ("audit", Path("audit") / f"{run_date}_bundle.json"),
                ("replay_audit", Path("audit") / f"{run_date}_{run_date}_replay.json"),
            ):
                _promote_or_verify(
                    stage / relative,
                    paths[name],
                    root=root,
                    generated=generated,
                    preserved=preserved,
                    mismatches=mismatches,
                )
    except Exception as exc:  # continue other historical dates with evidence
        failed_stage = "analysis_replay"
        error = f"{type(exc).__name__}: {exc}"

    if failed_stage is None and paths["trend_snapshot"].is_file():
        try:
            rendered = render_snapshot(_read_json(paths["trend_snapshot"]))
            with tempfile.TemporaryDirectory(prefix=f"ai-job-report-{run_date}-") as temporary:
                staged_report = Path(temporary) / paths["trend_report"].name
                staged_report.write_text(rendered, encoding="utf-8")
                _promote_or_verify(
                    staged_report,
                    paths["trend_report"],
                    root=root,
                    generated=generated,
                    preserved=preserved,
                    mismatches=mismatches,
                )
        except Exception as exc:
            failed_stage = "trend_report"
            error = f"{type(exc).__name__}: {exc}"

    if failed_stage is None and paths["daily_status"].is_file() and not paths["daily_health"].is_file():
        try:
            with tempfile.TemporaryDirectory(prefix=f"ai-job-health-{run_date}-") as temporary:
                generated_path, _ = generate_daily_health(
                    run_date,
                    data_dir=data_dir,
                    output_dir=Path(temporary),
                    generated_at=_stable_generated_at(paths),
                )
                _promote_or_verify(
                    generated_path,
                    paths["daily_health"],
                    root=root,
                    generated=generated,
                    preserved=preserved,
                    mismatches=mismatches,
                )
        except Exception as exc:
            failed_stage = "daily_health"
            error = f"{type(exc).__name__}: {exc}"

    if failed_stage is None:
        try:
            if _register_history_if_possible(
                run_date, data_dir=data_dir, root=root, config_path=config_path
            ):
                generated.append(_relative(data_dir / "ops" / "ops.sqlite3", root) + f"#run_date={run_date}")
        except Exception as exc:
            failed_stage = "history_registration"
            error = f"{type(exc).__name__}: {exc}"
    return {
        "generated_artifacts": sorted(generated),
        "preserved_artifacts": sorted(preserved),
        "existing_artifact_mismatches": sorted(mismatches),
        "failed_stage": failed_stage,
        "error": error,
        "skip_reasons": [],
    }


def _is_complete(row: Mapping[str, Any]) -> bool:
    return all(bool(row.get(field)) for field in (*CORE_FIELDS, *OPS_FIELDS))


def _result(initial: Mapping[str, Any], final: Mapping[str, Any], action: Mapping[str, Any]) -> str:
    if action.get("failed_stage"):
        return "FAILED"
    if _is_complete(initial):
        return "ALREADY_COMPLETE"
    if _is_complete(final):
        return "BACKFILLED"
    if action.get("generated_artifacts") or all(bool(final.get(field)) for field in CORE_FIELDS):
        return "PARTIAL_BACKFILL"
    return "NOT_RECOVERABLE"


def _reason(row: Mapping[str, Any]) -> str:
    if row["result"] == "ALREADY_COMPLETE":
        return "Canonical daily derived chain and operations history already existed; preserved"
    if row["result"] == "BACKFILLED":
        return "All canonical derived and operational artifacts are now present"
    if row["result"] == "PARTIAL_BACKFILL":
        if not row["final"]["daily_status_present"]:
            return "Derived analysis recovered; actual historical daily run status is unavailable, so Daily Health/DB history were not fabricated"
        return "Only the stages supported by preserved historical evidence were recovered"
    if row["result"] == "FAILED":
        return f"{row.get('failed_stage')}: {row.get('error')}"
    return "; ".join(row.get("skip_reasons") or row["final"].get("missing_inputs", []))


def _file_hashes(run_date: str, data_dir: Path, root: Path) -> dict[str, str]:
    hashes = {}
    for path in artifact_paths(run_date, data_dir).values():
        if path.is_file() and data_dir / "ops" not in path.parents:
            hashes[_relative(path, root)] = _sha256(path)
    return dict(sorted(hashes.items()))


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row["result"]) for row in rows)
    return {
        "total_historical_dates": len(rows),
        "already_complete": counts["ALREADY_COMPLETE"],
        "fully_backfilled": counts["BACKFILLED"],
        "partially_backfilled": counts["PARTIAL_BACKFILL"],
        "not_recoverable": counts["NOT_RECOVERABLE"],
        "failed": counts["FAILED"],
    }


def _matrix_value(value: bool) -> str:
    return "YES" if value else "NO"


def render_report(manifest: Mapping[str, Any]) -> str:
    summary = manifest["summary"]
    lines = [
        "# Historical Derived Artifact Backfill Audit",
        "",
        "## Summary",
        "",
        f"- date range: {manifest['date_range']['earliest']} → {manifest['date_range']['latest']}",
        f"- total historical dates: {summary['total_historical_dates']}",
        f"- already complete: {summary['already_complete']}",
        f"- fully backfilled: {summary['fully_backfilled']}",
        f"- partially backfilled: {summary['partially_backfilled']}",
        f"- not recoverable: {summary['not_recoverable']}",
        f"- failed: {summary['failed']}",
        "- live recrawl: NO",
        "- preservation policy: existing artifacts were never overwritten",
        "- SourceHealth column meaning: standalone Daily Health SourceHealth evidence; older Trend snapshots still embed the SourceHealth-derived reliability gate",
        "",
        "## Derived Artifact Dependency Map",
        "",
    ]
    for name, item in manifest["derived_artifact_dependency_map"].items():
        lines.extend([f"### {name}", "", f"- entrypoint: `{item['entrypoint']}`"])
        lines.append(f"- inputs: {', '.join(item['inputs'])}")
        if item.get("outputs"):
            lines.append(f"- outputs: {', '.join(item['outputs'])}")
        if item.get("reliability_gate"):
            lines.append(f"- reliability gate: `{item['reliability_gate']}`")
        if item.get("backfill_policy"):
            lines.append(f"- backfill policy: {item['backfill_policy']}")
        lines.append("")
    lines.extend([
        "## Per-date matrix",
        "",
        "| Date | Crawl | Clean | Analysis | SourceHealth | Reliability | Lifecycle/Events | Trend | Audit | Daily status/health | DB | Result | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for row in manifest["dates"]:
        final = row["final"]
        lines.append(
            "| {date} | {crawl} | {clean} | {analysis} | {source} | {reliability} | {events} | {trend} | {audit} | {daily} | {db} | {result} | {reason} |".format(
                date=row["date"],
                crawl=_matrix_value(final["crawl_present"] and final["crawl_manifest_present"]),
                clean=_matrix_value(final["clean_present"]),
                analysis=_matrix_value(final["analysis_present"]),
                source=_matrix_value(final["source_health_present"]),
                reliability=_matrix_value(final["reliability_present"]),
                events=_matrix_value(final["lifecycle_present"] and final["events_present"]),
                trend=_matrix_value(final["trend_snapshot_present"]),
                audit=_matrix_value(final["audit_present"]),
                daily=_matrix_value(final["daily_status_present"] and final["daily_health_present"]),
                db=_matrix_value(final["historical_db_present_or_registered"]),
                result=row["result"],
                reason=str(row["reason"]).replace("|", "\\|"),
            )
        )
    lines.extend(["", "## Unrecoverable dates", ""])
    unrecoverable = [row for row in manifest["dates"] if row["result"] == "NOT_RECOVERABLE"]
    if not unrecoverable:
        lines.append("None.")
    for row in unrecoverable:
        lines.append(f"- {row['date']}: {row['reason']}. Reconstructing the missing observation would require inventing or recrawling historical evidence.")
    lines.extend(["", "## Recomputed artifacts", ""])
    recomputed = manifest["recomputed_artifacts"]
    if not recomputed:
        lines.append("No historical production AI analysis was overwritten or regenerated.")
    for item in recomputed:
        lines.append(
            f"- {item['date']}: `{item['artifact']}` from `{item['historical_input']}`; "
            f"taxonomy SHA `{item['taxonomy_sha']}`; {item['reason']}"
        )
    lines.extend(["", "## Remaining gaps", ""])
    for gap in manifest["remaining_gaps"]:
        lines.append(f"- {gap}")
    lines.extend(["", "## Trend reliability finding", ""])
    lines.append(manifest["trend_reliability_finding"])
    lines.extend(["", "## REQUIRES_USER_DECISION", ""])
    lines.append(manifest["requires_user_decision"])
    lines.append("")
    return "\n".join(lines)


def render_chatgpt_index(manifest: Mapping[str, Any], *, data_dir: Path, root: Path) -> str:
    lines = [
        "# ChatGPT AI Eval Job Analysis Package Index",
        "",
        "Join key: `(platform, job_id)`. Structured classification is PRIMARY; clean JD text is SECONDARY because the current classification contract intentionally omits full description/requirements.",
        "",
        "## PRIMARY — AI Job classification and personal fit",
        "",
    ]
    usable_dates = []
    for row in manifest["dates"]:
        paths = artifact_paths(row["date"], data_dir)
        if paths["classification"].is_file():
            usable_dates.append(row["date"])
            lines.append(f"- {row['date']}: `{_relative(paths['classification'], root)}`")
    lines.extend([
        "",
        "Fields: `job_id`, `platform`, `company`, `title`, `city_norm`, `role_family`, `secondary_role_families`, `ai_relation`, `seniority_level`, `career_pool`, `reason_codes`, `evidence`, `skill_tags`, `classification_status`, and versions.",
        "",
        "## SECONDARY — JD content and trend/lifecycle context",
        "",
    ])
    for run_date in usable_dates:
        paths = artifact_paths(run_date, data_dir)
        if paths["clean"].is_file():
            lines.append(f"- {run_date} JD text: `{_relative(paths['clean'], root)}`")
        for name, label in (
            ("trend_snapshot", "trend snapshot + reliability"),
            ("trend_report", "human-readable trend report"),
            ("events", "event ledger"),
        ):
            if paths[name].is_file():
                lines.append(f"- {run_date} {label}: `{_relative(paths[name], root)}`")
    lines.extend([
        "",
        "Clean fields include `job_id`, `platform`, `company`, `location`, `title`, `description`, and `requirements`; join them to PRIMARY for complete JD analysis.",
        "",
        "## SECONDARY — Reliability",
        "",
    ])
    for row in manifest["dates"]:
        paths = artifact_paths(row["date"], data_dir)
        for name, label in (
            ("daily_health", "Daily Health + SourceHealth"),
            ("daily_status", "daily run status"),
            ("manifest", "crawl manifest"),
        ):
            if paths[name].is_file():
                lines.append(f"- {row['date']} {label}: `{_relative(paths[name], root)}`")
    lines.extend(["", "## DEBUG_ONLY — recall/precision investigation", ""])
    for row in manifest["dates"]:
        paths = artifact_paths(row["date"], data_dir)
        if paths["raw"].is_file():
            lines.append(f"- {row['date']} raw jobs: `{_relative(paths['raw'], root)}`")
        if paths["audit"].is_file():
            lines.append(f"- {row['date']} bounded audit bundle: `{_relative(paths['audit'], root)}`")
    lines.extend([
        "",
        "## Three-date sufficiency check",
        "",
    ])
    for item in manifest["ai_eval_validation"]:
        state = "PASS" if item["sufficient"] else "GAP"
        lines.append(f"- {item['date']} ({item['position']}): {state} — {item['note']}")
    lines.extend([
        "",
        "The package can answer P1/P2/REF/X inventory, new/missing/reappeared/updated roles, source-reliability caveats, and skill-tag trends. Exact requirement wording changes require joining successive clean files by `(platform, job_id)`; events provide change detection but only content hashes, not a field-level textual diff.",
        "",
        f"Lifecycle caveat: {manifest['requires_user_decision']}",
        "",
    ])
    return "\n".join(lines)


def _validate_ai_eval_dates(rows: Sequence[Mapping[str, Any]], data_dir: Path) -> list[dict[str, Any]]:
    candidates = [row["date"] for row in rows if row["final"]["classification_present"]]
    if not candidates:
        return []
    selected = [candidates[0], candidates[len(candidates) // 2], candidates[-1]]
    result = []
    for position, run_date in zip(("early", "middle", "recent"), selected):
        paths = artifact_paths(run_date, data_dir)
        try:
            clean = load_jobs(paths["clean"])
            clean_keys = {(str(row.get("platform", "")), str(row.get("job_id", ""))) for row in clean}
            classifications = [
                json.loads(line)
                for line in paths["classification"].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            required = {
                "job_id", "platform", "company", "title", "role_family", "ai_relation",
                "seniority_level", "career_pool", "reason_codes", "evidence", "skill_tags",
            }
            schema_ok = all(required <= set(row) for row in classifications)
            joined = all((str(row["platform"]), str(row["job_id"])) in clean_keys for row in classifications)
            events_ok = paths["events"].is_file()
            reliability_ok = _trend_has_reliability(paths["trend_snapshot"])
            sufficient = schema_ok and joined and events_ok and reliability_ok
            note = (
                f"{len(classifications)} classified jobs; classification→clean join complete={joined}; "
                f"events={events_ok}; reliability gate={reliability_ok}"
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            sufficient = False
            note = f"validation failed: {exc}"
        result.append({"date": run_date, "position": position, "sufficient": sufficient, "note": note})
    return result


def _trend_reliability_finding(rows: Sequence[Mapping[str, Any]], data_dir: Path) -> str:
    unreliable = 0
    guarded = 0
    for row in rows:
        path = artifact_paths(row["date"], data_dir)["trend_snapshot"]
        if not path.is_file():
            continue
        try:
            snapshot = _read_json(path)
            for platform in snapshot.get("platforms", {}).values():
                reliability = platform.get("reliability", {})
                if any(not value.get("reliable", False) for value in reliability.values()):
                    unreliable += 1
                    if any(value.get("reason_codes") for value in reliability.values()):
                        guarded += 1
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    if unreliable and unreliable == guarded:
        return (
            f"PASS: {guarded} platform-date observations with an unreliable metric family carry explicit "
            "reason codes. `trend_comparability` excludes those platform/family pairs and emits null deltas "
            "when no comparable platform remains, so source failure is not reported as market movement."
        )
    if not unreliable:
        return "PASS within observed history: no unreliable platform-date metric family was found."
    return f"REQUIRES_USER_DECISION: {unreliable - guarded} unreliable platform-date observations lacked an explicit Trend guard."


def _observation_gap_finding(rows: Sequence[Mapping[str, Any]]) -> str:
    observed = [
        date.fromisoformat(str(row["date"]))
        for row in rows
        if row["final"]["events_present"]
    ]
    gaps = [
        f"{before.isoformat()}→{after.isoformat()} ({(after - before).days} days)"
        for before, after in zip(observed, observed[1:])
        if (after - before).days > 1
    ]
    if not gaps:
        return "NONE: derived lifecycle observations are calendar-consecutive."
    return (
        "Lifecycle currently advances by successive available observations rather than calendar-consecutive "
        f"runs. Gaps found: {', '.join(gaps)}. Boundary NEW/REMOVED events are valid observation-to-observation "
        "facts but must not be described as daily market movement without a production semantics decision."
    )


def run_backfill(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    root: Path = ROOT,
    config_path: Path = DEFAULT_CONFIG,
    settings_path: Path = DEFAULT_VERSION_CONFIG,
    audit_dir: Path | None = None,
    selected_dates: Sequence[str] | None = None,
    dry_run: bool = False,
    base_branch: str = "taxonomy",
    base_sha: str | None = None,
) -> dict[str, Any]:
    data_dir = Path(data_dir).resolve()
    root = Path(root).resolve()
    config_path = Path(config_path).resolve()
    settings_path = Path(settings_path).resolve()
    audit_dir = Path(audit_dir).resolve() if audit_dir is not None else data_dir / "analysis" / "audit"
    dates = discover_dates(data_dir)
    if selected_dates is not None:
        wanted = {date.fromisoformat(value).isoformat() for value in selected_dates}
        dates = [value for value in dates if value in wanted]
    if not dates:
        raise ValueError("NO_HISTORICAL_DATES_DISCOVERED")
    taxonomy_sha = base_sha or _git(root, "rev-parse", base_branch)
    branch = _git(root, "branch", "--show-current")
    start_sha = _git(root, "rev-parse", "HEAD")
    previous_manifest_path = audit_dir / "backfill_manifest.json"
    previous: Mapping[str, Any] = {}
    if previous_manifest_path.is_file() and not dry_run:
        try:
            loaded = _read_json(previous_manifest_path)
            if loaded.get("base_sha") == taxonomy_sha:
                previous = loaded
        except (OSError, json.JSONDecodeError, AttributeError):
            previous = {}
    previous_dates = {row["date"]: row for row in previous.get("dates", [])}
    initial_db_dates = _db_dates(data_dir)
    rows = []
    for run_date in dates:
        observed_initial = inventory_date(run_date, data_dir, db_dates=initial_db_dates)
        prior = previous_dates.get(run_date)
        initial = prior.get("initial", observed_initial) if prior else observed_initial
        if dry_run:
            action = {
                "generated_artifacts": [],
                "preserved_artifacts": [],
                "existing_artifact_mismatches": [],
                "failed_stage": None,
                "error": None,
                "skip_reasons": observed_initial["missing_inputs"] if not observed_initial["can_backfill_trend"] else [],
            }
            final = dict(observed_initial)
            if observed_initial["can_backfill_trend"]:
                final.update({field: True for field in CORE_FIELDS})
                final.update({
                    "analysis_present": True,
                    "personal_fit_present": True,
                    "reliability_present": True,
                    "lifecycle_present": True,
                    "trend_report_present": True,
                })
        else:
            action = _backfill_date(
                run_date,
                data_dir=data_dir,
                root=root,
                config_path=config_path,
                settings_path=settings_path,
            )
            final = inventory_date(run_date, data_dir)
        if prior:
            action["generated_artifacts"] = sorted(set(prior.get("generated_artifacts", [])) | set(action["generated_artifacts"]))
        action["preserved_artifacts"] = sorted(
            set(action["preserved_artifacts"]) | set(action["generated_artifacts"])
        )
        row = {
            "date": run_date,
            "initial": initial,
            "final": final,
            **action,
        }
        row["result"] = prior.get("result") if prior and prior.get("result") in RESULTS else _result(initial, final, action)
        if action.get("failed_stage"):
            row["result"] = "FAILED"
        row["reason"] = _reason(row)
        row["artifact_sha256"] = _file_hashes(run_date, data_dir, root) if not dry_run else {}
        rows.append(row)
    recomputed = []
    for row in rows:
        classification_path = _relative(artifact_paths(row["date"], data_dir)["classification"], root)
        if classification_path in row["generated_artifacts"]:
            recomputed.append({
                "date": row["date"],
                "artifact": classification_path,
                "historical_input": _relative(artifact_paths(row["date"], data_dir)["clean"], root),
                "original_artifact": None,
                "taxonomy_sha": taxonomy_sha,
                "reason": "RECOMPUTED_WITH_CURRENT_TAXONOMY because the structured classification artifact was missing",
            })
    remaining_gaps = []
    for row in rows:
        final = row["final"]
        if not final["daily_status_present"]:
            remaining_gaps.append(
                f"{row['date']}: actual daily run status / Daily Health / operations history unavailable"
            )
        if not final["production_ai_analysis_present"]:
            if final["classification_present"]:
                detail = "original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used"
            else:
                detail = "original full production AI job analysis and structured classification are unavailable"
            remaining_gaps.append(f"{row['date']}: {detail}")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "base_branch": base_branch,
        "base_sha": taxonomy_sha,
        "backfill_branch": branch,
        "backfill_start_sha": start_sha,
        "no_live_recrawl": True,
        "existing_artifacts_overwritten": False,
        "date_range": {"earliest": dates[0], "latest": dates[-1]},
        "summary": _summary(rows),
        "derived_artifact_dependency_map": dependency_map(),
        "dates": rows,
        "recomputed_artifacts": recomputed,
        "remaining_gaps": remaining_gaps,
    }
    if not dry_run:
        manifest["ai_eval_validation"] = _validate_ai_eval_dates(rows, data_dir)
        manifest["trend_reliability_finding"] = _trend_reliability_finding(rows, data_dir)
        manifest["requires_user_decision"] = _observation_gap_finding(rows)
        audit_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(audit_dir / "backfill_manifest.json", manifest)
        _write_text_atomic(audit_dir / "backfill_report.md", render_report(manifest))
        _write_text_atomic(
            audit_dir / "chatgpt_analysis_index.md",
            render_chatgpt_index(manifest, data_dir=data_dir, root=root),
        )
    else:
        manifest["ai_eval_validation"] = []
        manifest["trend_reliability_finding"] = "NOT_RUN_IN_DRY_RUN"
        manifest["requires_user_decision"] = "NOT_EVALUATED_IN_DRY_RUN"
    return manifest


def _date_arg(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--settings", type=Path, default=DEFAULT_VERSION_CONFIG)
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--dates", nargs="+", type=_date_arg)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = run_backfill(
            data_dir=args.data_dir,
            config_path=args.config,
            settings_path=args.settings,
            audit_dir=args.audit_dir,
            selected_dates=args.dates,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps({
        "date_range": manifest["date_range"],
        "summary": manifest["summary"],
        "dry_run": args.dry_run,
    }, ensure_ascii=False, indent=2))
    return 0 if manifest["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
