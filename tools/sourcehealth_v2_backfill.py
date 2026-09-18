#!/usr/bin/env python3
"""Offline SourceHealth Reliability V2 backfill over frozen historical inputs.

The tool discovers dates, validates raw/manifest/clean inputs, stages one
chronological production replay, validates V2 invariants, and only then replaces
old derived artifacts atomically.  Raw, clean, Daily Health, and operations
history are never written.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.analysis.ai_eval_jobs import _write_text_atomic
from src.analysis.classification import classification_unknown
from src.analysis.pipeline import DEFAULT_VERSION_CONFIG, replay
from src.analysis.trends import compare_trends, validate_snapshot
from src.models import write_json_atomic
from tools.backfill_history import (
    DEFAULT_DATA_DIR,
    ROOT,
    _atomic_copy,
    _git,
    _read_json,
    _relative,
    _sha256,
    _validate_historical_inputs,
    artifact_paths,
    discover_dates,
)
from tools.generate_market_report import render_comparison, render_snapshot


AUDIT_MANIFEST = "sourcehealth_v2_backfill_manifest.json"
AUDIT_REPORT = "sourcehealth_v2_backfill_report.md"
FINAL_STATES = {"ALREADY_V2", "REPLAYED_V2", "PARTIAL_V2", "NOT_RECOVERABLE", "FAILED"}
FROZEN_WEEKLY_PAIRS = (
    ("2026-09-16", "2026-09-17"),
    ("2026-09-01", "2026-09-07"),
    ("2026-09-03", "2026-09-04"),
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _trend_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        value = _read_json(path)
        return value.get("trend_version") if isinstance(value, Mapping) else None
    except (OSError, json.JSONDecodeError):
        return None


def _hash_if_file(path: Path) -> str | None:
    return _sha256(path) if path.is_file() else None


def coverage_audit(data_dir: Path) -> list[dict[str, Any]]:
    """Classify every discovered historical date before any replay is run."""
    rows = []
    for run_date in discover_dates(data_dir):
        paths = artifact_paths(run_date, data_dir)
        errors = _validate_historical_inputs(run_date, data_dir)
        version = _trend_version(paths["trend_snapshot"])
        core = all(paths[name].is_file() for name in ("classification", "events", "trend_snapshot", "audit"))
        if errors:
            status = "NOT_RECOVERABLE"
        elif version == "trend_v2" and core:
            status = "ALREADY_V2"
        else:
            status = "CAN_REPLAY_V2"
        rows.append({
            "date": run_date,
            "raw": paths["raw"].is_file(),
            "manifest": paths["manifest"].is_file(),
            "clean": paths["clean"].is_file(),
            "classification": paths["classification"].is_file(),
            "events": paths["events"].is_file(),
            "trend_snapshot": paths["trend_snapshot"].is_file(),
            "trend_version": version,
            "audit_bundle": paths["audit"].is_file(),
            "daily_health": paths["daily_health"].is_file(),
            "market_report": paths["trend_report"].is_file(),
            "weekly_dependencies": paths["trend_snapshot"].is_file(),
            "coverage_status": status,
            "missing_inputs": errors,
        })
    return rows


def _validate_unknown_rows(rows: Sequence[Mapping[str, Any]]) -> int:
    unknown = 0
    for row in rows:
        if not classification_unknown(row):
            continue
        unknown += 1
        if (row.get("in_scope") is not None
                or any(row.get(field) is not None for field in (
                    "ai_relation", "role_family", "career_pool", "market_relevance", "seniority_level"
                ))
                or row.get("skill_tags") != []):
            raise ValueError("UNKNOWN_CLASSIFICATION_NOT_DISJOINT")
    return unknown


def _date_validation(run_date: str, stage: Path) -> dict[str, Any]:
    classification = stage / "classification" / f"{run_date}.jsonl"
    events = stage / "events" / f"{run_date}.jsonl"
    snapshot_path = stage / "trends" / "snapshots" / f"{run_date}.json"
    audit = stage / "audit" / f"{run_date}_bundle.json"
    missing = [str(path) for path in (classification, events, snapshot_path, audit) if not path.is_file()]
    if missing:
        raise ValueError(f"STAGED_ARTIFACT_MISSING: {', '.join(missing)}")
    rows = _jsonl(classification)
    explicit_unknown = _validate_unknown_rows(rows)
    snapshot = _read_json(snapshot_path)
    if snapshot.get("snapshot_date") != run_date or snapshot.get("trend_version") != "trend_v2":
        raise ValueError(f"EXPECTED_TREND_V2: {run_date}")
    validate_snapshot(snapshot)
    unknown = snapshot["unknown_classification_count"]
    return {
        "confirmed_active": snapshot["active_jobs"],
        "unknown_inventory": unknown,
        "observed_inventory": snapshot["observed_inventory_count"],
        "explicit_unknown_rows": explicit_unknown,
        "unattributed_legacy_unknown": max(unknown - explicit_unknown, 0),
        "unknown_flows": {
            field: snapshot[field]
            for field in (
                "unknown_new_jobs", "unknown_removed_jobs",
                "unknown_reappeared_jobs", "unknown_updated_jobs",
            )
        },
    }


def _prepare_reports_and_weekly(stage: Path) -> list[tuple[str, str]]:
    reports = stage / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    snapshots = stage / "trends" / "snapshots"
    for path in sorted(snapshots.glob("????-??-??.json")):
        (reports / f"market_report_{path.stem}.md").write_text(
            render_snapshot(_read_json(path)), encoding="utf-8"
        )
    comparisons = stage / "trends" / "comparisons"
    comparisons.mkdir(parents=True, exist_ok=True)
    for before, after in FROZEN_WEEKLY_PAIRS:
        before_path = snapshots / f"{before}.json"
        after_path = snapshots / f"{after}.json"
        if before_path.is_file() and after_path.is_file():
            write_json_atomic(comparisons / f"{before}_{after}.json", compare_trends(
                _read_json(before_path), _read_json(after_path)
            ))
    pairs = []
    for path in sorted(comparisons.glob("????-??-??_????-??-??.json")):
        comparison = _read_json(path)
        pair = (comparison["from_date"], comparison["to_date"])
        pairs.append(pair)
        (reports / f"market_report_{pair[0]}_{pair[1]}.md").write_text(
            render_comparison(comparison), encoding="utf-8"
        )
    return pairs


def _platform(snapshot: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    return snapshot["platforms"][name]


def _frozen_acceptance(stage: Path) -> dict[str, Any]:
    snapshots = stage / "trends" / "snapshots"
    comparisons = stage / "trends" / "comparisons"
    result: dict[str, Any] = {}

    t_path = snapshots / "2026-09-17.json"
    if t_path.is_file():
        snap = _read_json(t_path)
        item = _platform(snap, "tencent")
        metrics, reliability = item["metrics"], item["reliability"]
        failed = [row for row in _jsonl(stage / "classification" / "2026-09-17.jsonl")
                  if row.get("platform") == "tencent"
                  and str(row.get("job_id")) == "2093528517592662016"]
        passed = (
            metrics["active_jobs"] == 127
            and metrics["unknown_classification_count"] == 1
            and metrics["observed_inventory_count"] == 128
            and metrics["new_jobs"] == 3
            and metrics["unknown_new_jobs"] == 1
            and all(reliability[family]["reliable"] for family in (
                "inventory", "presence_flow", "content_flow"
            ))
            and len(failed) == 1 and classification_unknown(failed[0])
            and failed[0].get("career_pool") is None and failed[0].get("skill_tags") == []
        )
        result["tencent_2026_09_17"] = {"passed": passed, "metrics": metrics,
                                          "reliability": reliability, "failed_job": failed}

    meituan = {}
    for run_date, confirmed, unknown in (("2026-07-07", 121, 1194), ("2026-09-07", 147, 829)):
        path = snapshots / f"{run_date}.json"
        if not path.is_file():
            continue
        item = _platform(_read_json(path), "meituan")
        metrics = item["metrics"]
        pool_sum = sum(metrics["by_career_pool"].values())
        meituan[run_date] = {
            "passed": metrics["active_jobs"] == confirmed
                      and metrics["unknown_classification_count"] == unknown
                      and metrics["observed_inventory_count"] == confirmed + unknown
                      and pool_sum == confirmed and bool(metrics["by_skill_tag"]),
            "confirmed": metrics["active_jobs"], "unknown": metrics["unknown_classification_count"],
            "observed": metrics["observed_inventory_count"], "career_pool_sum": pool_sum,
            "skill_categories": len(metrics["by_skill_tag"]),
        }
    if meituan:
        result["meituan_severe"] = {"passed": all(row["passed"] for row in meituan.values()),
                                      "dates": meituan}

    d_path = snapshots / "2026-09-04.json"
    if d_path.is_file():
        item = _platform(_read_json(d_path), "didi")
        metrics, reliability = item["metrics"], item["reliability"]
        expected_reasons = {"LIST_RECORDS_INCOMPLETE", "SOURCE_PRESENCE_UNRELIABLE"}
        passed = (
            metrics["active_jobs"] == 43
            and metrics["unknown_classification_count"] == 9
            and metrics["observed_inventory_count"] == 52
            and not reliability["inventory"]["reliable"]
            and not reliability["presence_flow"]["reliable"]
            and reliability["content_flow"]["reliable"]
            and expected_reasons <= set(reliability["inventory"]["reason_codes"])
            and expected_reasons <= set(reliability["presence_flow"]["reason_codes"])
        )
        result["didi_2026_09_04"] = {"passed": passed, "metrics": metrics,
                                      "reliability": reliability}

    weekly = {}
    for before, after in FROZEN_WEEKLY_PAIRS:
        path = comparisons / f"{before}_{after}.json"
        if not path.is_file():
            continue
        value = _read_json(path)
        weekly[f"{before}_{after}"] = value
    weekly_pass = True
    if "2026-09-16_2026-09-17" in weekly:
        value = weekly["2026-09-16_2026-09-17"]
        weekly_pass &= all("tencent" in value["comparability"][family]["included_platforms"]
                           for family in ("inventory", "presence_flow", "content_flow"))
        weekly_pass &= value["lifecycle"]["UNKNOWN_NEW"]["to"] >= 1
    if "2026-09-01_2026-09-07" in weekly:
        value = weekly["2026-09-01_2026-09-07"]
        weekly_pass &= all("meituan" in value["comparability"][family]["included_platforms"]
                           for family in ("inventory", "presence_flow", "content_flow"))
        weekly_pass &= value["comparable_subset"]["inventory"]["to"]["unknown_classification_count"] >= 829
        weekly_pass &= bool(value["comparable_subset"]["inventory"]["to"]["by_skill_tag"])
    if "2026-09-03_2026-09-04" in weekly:
        value = weekly["2026-09-03_2026-09-04"]
        weekly_pass &= "didi" in value["comparability"]["inventory"]["excluded_platforms"]
        weekly_pass &= "didi" in value["comparability"]["presence_flow"]["excluded_platforms"]
        weekly_pass &= "didi" in value["comparability"]["content_flow"]["included_platforms"]
    if weekly:
        result["weekly"] = {"passed": weekly_pass, "pairs": sorted(weekly)}
    return result


def _assert_acceptance(result: Mapping[str, Any]) -> None:
    failed = [name for name, value in result.items() if not value.get("passed")]
    if failed:
        raise ValueError(f"FROZEN_V2_ACCEPTANCE_FAILED: {', '.join(failed)}")


def _source_hashes(rows: Sequence[Mapping[str, Any]], data_dir: Path) -> dict[str, str]:
    hashes = {}
    for row in rows:
        for name in ("raw", "manifest", "clean"):
            path = artifact_paths(row["date"], data_dir)[name]
            if path.is_file():
                hashes[_relative(path, ROOT)] = _sha256(path)
    return dict(sorted(hashes.items()))


def _daily_health_hashes(rows: Sequence[Mapping[str, Any]], data_dir: Path) -> dict[str, str]:
    return {
        _relative(path, ROOT): _sha256(path)
        for row in rows
        if (path := artifact_paths(row["date"], data_dir)["daily_health"]).is_file()
    }


def _promote(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"PROMOTION_SOURCE_MISSING: {source}")
    _atomic_copy(source, destination)


def _artifact_hashes(run_date: str, data_dir: Path) -> dict[str, str | None]:
    paths = artifact_paths(run_date, data_dir)
    return {name: _hash_if_file(paths[name]) for name in (
        "classification", "events", "trend_snapshot", "audit", "trend_report"
    )}


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row["status"]) for row in rows)
    return {
        "total_dates": len(rows),
        "already_v2": counts["ALREADY_V2"],
        "replayed_v2": counts["REPLAYED_V2"],
        "partial_v2": counts["PARTIAL_V2"],
        "not_recoverable": counts["NOT_RECOVERABLE"],
        "failed": counts["FAILED"],
    }


def _before_after(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    """Human-readable migration delta for the frozen historical acceptance cases."""
    result: dict[str, Any] = {}
    if "tencent_2026_09_17" in acceptance:
        after = acceptance["tencent_2026_09_17"]
        metrics, reliability = after["metrics"], after["reliability"]
        result["tencent_2026_09_17"] = {
            "before_v1": {
                "confirmed_active": 127, "unknown": 0, "observed": 127,
                "confirmed_new": 3, "unknown_new": 0,
                "inventory_reliable": False, "presence_flow_reliable": False,
                "content_flow_reliable": False,
            },
            "after_v2": {
                "confirmed_active": metrics["active_jobs"],
                "unknown": metrics["unknown_classification_count"],
                "observed": metrics["observed_inventory_count"],
                "confirmed_new": metrics["new_jobs"],
                "unknown_new": metrics["unknown_new_jobs"],
                "inventory_reliable": reliability["inventory"]["reliable"],
                "presence_flow_reliable": reliability["presence_flow"]["reliable"],
                "content_flow_reliable": reliability["content_flow"]["reliable"],
            },
        }
    if "meituan_severe" in acceptance:
        result["meituan_severe"] = acceptance["meituan_severe"]["dates"]
    if "didi_2026_09_04" in acceptance:
        after = acceptance["didi_2026_09_04"]
        metrics, reliability = after["metrics"], after["reliability"]
        result["didi_2026_09_04"] = {
            "after_v2": {
                "confirmed_active": metrics["active_jobs"],
                "unknown": metrics["unknown_classification_count"],
                "observed": metrics["observed_inventory_count"],
                "inventory_reliable": reliability["inventory"]["reliable"],
                "presence_flow_reliable": reliability["presence_flow"]["reliable"],
                "content_flow_reliable": reliability["content_flow"]["reliable"],
                "inventory_reason_codes": reliability["inventory"]["reason_codes"],
                "presence_flow_reason_codes": reliability["presence_flow"]["reason_codes"],
            },
        }
    return result


def render_audit_report(manifest: Mapping[str, Any]) -> str:
    summary = manifest["summary"]
    lines = [
        "# SourceHealth Reliability V2 Historical Backfill",
        "",
        f"- taxonomy SHA: `{manifest['taxonomy_sha']}`",
        f"- replay generated_at: `{manifest['replay_generated_at']}`",
        f"- date range: {manifest['date_range']['earliest']} → {manifest['date_range']['latest']}",
        f"- total dates: {summary['total_dates']}",
        f"- already V2: {summary['already_v2']}",
        f"- replayed V2: {summary['replayed_v2']}",
        f"- partial V2: {summary['partial_v2']}",
        f"- not recoverable: {summary['not_recoverable']}",
        f"- failed: {summary['failed']}",
        "- live recrawl: NO",
        "- raw / clean rewritten: NO",
        "- Daily Health rewritten: NO",
        "",
        "## Per-date coverage",
        "",
        "| Date | Raw | Manifest | Clean | Prior trend | Status | UNKNOWN | Unattributed legacy UNKNOWN | Reason |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in manifest["dates"]:
        lines.append(
            f"| {row['date']} | {row['coverage']['raw']} | {row['coverage']['manifest']} | "
            f"{row['coverage']['clean']} | {row['coverage']['trend_version']} | {row['status']} | "
            f"{row.get('validation', {}).get('unknown_inventory', 0)} | "
            f"{row.get('validation', {}).get('unattributed_legacy_unknown', 0)} | "
            f"{'; '.join(row.get('reasons', []))} |"
        )
    lines.extend(["", "## Artifact counts", ""])
    for key, value in manifest["artifact_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## UNKNOWN totals", ""])
    lines.append(f"- inventory: {manifest['unknown_totals']['inventory']}")
    for key, value in manifest["unknown_totals"]["flows"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Frozen regression", ""])
    for key, value in manifest["acceptance"].items():
        lines.append(f"- {key}: {'PASS' if value.get('passed') else 'FAIL'}")
    lines.extend(["", "## V1 → V2 before / after", ""])
    delta = manifest.get("before_after", {})
    if "tencent_2026_09_17" in delta:
        item = delta["tencent_2026_09_17"]
        lines.append(f"- Tencent 2026-09-17 V1: `{json.dumps(item['before_v1'], ensure_ascii=False, sort_keys=True)}`")
        lines.append(f"- Tencent 2026-09-17 V2: `{json.dumps(item['after_v2'], ensure_ascii=False, sort_keys=True)}`")
    if "meituan_severe" in delta:
        for run_date, item in delta["meituan_severe"].items():
            lines.append(
                f"- Meituan {run_date} V2: confirmed={item['confirmed']}, unknown={item['unknown']}, "
                f"observed={item['observed']}, skill_categories={item['skill_categories']}"
            )
    if "didi_2026_09_04" in delta:
        lines.append(
            f"- Didi 2026-09-04 V2: `{json.dumps(delta['didi_2026_09_04']['after_v2'], ensure_ascii=False, sort_keys=True)}`"
        )
    lines.extend(["", "## Idempotency", ""])
    lines.append(f"- verified: {manifest['idempotency']['verified']}")
    lines.append("- semantic derived artifacts are hash-stable across the second run")
    lines.extend(["", "## Provenance", ""])
    lines.append("Each replayable date records frozen input hashes, before/after derived hashes, source date, taxonomy SHA, trend_v2, and replay generated_at in the JSON manifest.")
    lines.append("")
    return "\n".join(lines)


def _existing_is_current(manifest: Mapping[str, Any], *, taxonomy_sha: str, data_dir: Path) -> bool:
    if manifest.get("taxonomy_sha") != taxonomy_sha:
        return False
    for row in manifest.get("dates", []):
        if row.get("status") not in {"REPLAYED_V2", "PARTIAL_V2", "ALREADY_V2"}:
            continue
        for name, expected in row.get("after_artifact_sha256", {}).items():
            if expected is None:
                continue
            actual = _hash_if_file(artifact_paths(row["date"], data_dir)[name])
            if actual != expected:
                return False
    return True


def run_v2_backfill(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    root: Path = ROOT,
    settings_path: Path = DEFAULT_VERSION_CONFIG,
    audit_dir: Path | None = None,
    base_branch: str = "taxonomy",
) -> dict[str, Any]:
    data_dir = Path(data_dir).resolve()
    root = Path(root).resolve()
    settings_path = Path(settings_path).resolve()
    audit_dir = Path(audit_dir).resolve() if audit_dir else data_dir / "analysis" / "audit"
    taxonomy_sha = _git(root, "rev-parse", base_branch)
    manifest_path = audit_dir / AUDIT_MANIFEST
    report_path = audit_dir / AUDIT_REPORT
    if manifest_path.is_file():
        existing = _read_json(manifest_path)
        if _existing_is_current(existing, taxonomy_sha=taxonomy_sha, data_dir=data_dir):
            changed = False
            if "before_after" not in existing:
                existing["before_after"] = _before_after(existing.get("acceptance", {}))
                changed = True
            if not existing.get("idempotency", {}).get("verified"):
                existing["idempotency"] = {"verified": True, "derived_artifacts_changed_on_second_run": False}
                changed = True
            if changed:
                write_json_atomic(manifest_path, existing)
                _write_text_atomic(report_path, render_audit_report(existing))
            return existing

    coverage = coverage_audit(data_dir)
    if not coverage:
        raise ValueError("NO_HISTORICAL_DATES_DISCOVERED")
    source_before = _source_hashes(coverage, data_dir)
    health_before = _daily_health_hashes(coverage, data_dir)
    replay_dates = [row["date"] for row in coverage if row["coverage_status"] == "CAN_REPLAY_V2"]
    already_dates = [row["date"] for row in coverage if row["coverage_status"] == "ALREADY_V2"]
    validation: dict[str, dict[str, Any]] = {}
    before_hashes = {day: _artifact_hashes(day, data_dir) for day in replay_dates}
    acceptance: dict[str, Any] = {}
    weekly_pairs: list[tuple[str, str]] = []
    if replay_dates:
        with tempfile.TemporaryDirectory(prefix="sourcehealth-v2-backfill-") as temporary:
            stage = Path(temporary) / "analysis"
            replay(replay_dates[0], replay_dates[-1], data_dir=data_dir, output_dir=stage,
                   settings_path=settings_path)
            for run_date in replay_dates:
                validation[run_date] = _date_validation(run_date, stage)
            weekly_pairs = _prepare_reports_and_weekly(stage)
            acceptance = _frozen_acceptance(stage)
            _assert_acceptance(acceptance)
            for run_date in replay_dates:
                paths = artifact_paths(run_date, data_dir)
                for name, relative in (
                    ("classification", Path("classification") / f"{run_date}.jsonl"),
                    ("events", Path("events") / f"{run_date}.jsonl"),
                    ("trend_snapshot", Path("trends") / "snapshots" / f"{run_date}.json"),
                    ("audit", Path("audit") / f"{run_date}_bundle.json"),
                    ("trend_report", Path("reports") / f"market_report_{run_date}.md"),
                ):
                    _promote(stage / relative, paths[name])
            for comparison in sorted((stage / "trends" / "comparisons").glob("*.json")):
                _promote(comparison, data_dir / "analysis" / "trends" / "comparisons" / comparison.name)
            for report in sorted((stage / "reports").glob("market_report_????-??-??_????-??-??.md")):
                _promote(report, data_dir / "analysis" / "reports" / report.name)

    source_after = _source_hashes(coverage, data_dir)
    health_after = _daily_health_hashes(coverage, data_dir)
    if source_after != source_before:
        raise ValueError("FROZEN_RAW_OR_CLEAN_INPUT_CHANGED")
    if health_after != health_before:
        raise ValueError("DAILY_HEALTH_CHANGED")
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for item in coverage:
        run_date = item["date"]
        reasons = list(item["missing_inputs"])
        if item["coverage_status"] == "NOT_RECOVERABLE":
            status = "NOT_RECOVERABLE"
        elif run_date in already_dates:
            status = "ALREADY_V2"
        else:
            partial = validation[run_date]["unattributed_legacy_unknown"] > 0
            status = "PARTIAL_V2" if partial else "REPLAYED_V2"
            if partial:
                reasons.append("LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE")
        after = _artifact_hashes(run_date, data_dir) if status != "NOT_RECOVERABLE" else {}
        rows.append({
            "date": run_date, "status": status, "coverage": item,
            "reasons": reasons, "validation": validation.get(run_date, {}),
            "source_historical_date": run_date, "taxonomy_sha": taxonomy_sha,
            "trend_version": "trend_v2" if status != "NOT_RECOVERABLE" else None,
            "replay_generated_at": generated_at if run_date in replay_dates else None,
            "input_sha256": {
                name: _hash_if_file(artifact_paths(run_date, data_dir)[name])
                for name in ("raw", "manifest", "clean")
            },
            "before_artifact_sha256": before_hashes.get(run_date, {}),
            "after_artifact_sha256": after,
        })
    unknown_inventory = sum(row.get("validation", {}).get("unknown_inventory", 0) for row in rows)
    flow_totals = Counter()
    for row in rows:
        flow_totals.update(row.get("validation", {}).get("unknown_flows", {}))
    manifest = {
        "schema_version": 1,
        "taxonomy_sha": taxonomy_sha,
        "base_branch": base_branch,
        "backfill_branch": _git(root, "branch", "--show-current"),
        "backfill_start_sha": _git(root, "rev-parse", "HEAD"),
        "replay_generated_at": generated_at,
        "date_range": {"earliest": coverage[0]["date"], "latest": coverage[-1]["date"]},
        "no_live_recrawl": True,
        "raw_clean_modified": False,
        "daily_health_modified": False,
        "existing_v1_derived_artifacts_replaced": bool(replay_dates),
        "summary": _summary(rows),
        "artifact_counts": {
            "classification": len(replay_dates), "events": len(replay_dates),
            "trend": len(replay_dates), "audit_bundle": len(replay_dates),
            "daily_market_report": len(replay_dates), "weekly": len(weekly_pairs),
        },
        "unknown_totals": {"inventory": unknown_inventory, "flows": dict(sorted(flow_totals.items()))},
        "acceptance": acceptance,
        "before_after": _before_after(acceptance),
        "idempotency": {"verified": False, "derived_artifacts_changed_on_second_run": None},
        "source_input_sha256": source_after,
        "daily_health_sha256": health_after,
        "dates": rows,
    }
    if any(row["status"] not in FINAL_STATES for row in rows):
        raise ValueError("INVALID_FINAL_BACKFILL_STATUS")
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(manifest_path, manifest)
    _write_text_atomic(report_path, render_audit_report(manifest))
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--settings", type=Path, default=DEFAULT_VERSION_CONFIG)
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--coverage-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.coverage_only:
            print(json.dumps(coverage_audit(args.data_dir), ensure_ascii=False, indent=2))
            return 0
        result = run_v2_backfill(data_dir=args.data_dir, settings_path=args.settings,
                                 audit_dir=args.audit_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps({"date_range": result["date_range"], "summary": result["summary"],
                      "artifact_counts": result["artifact_counts"],
                      "idempotency": result["idempotency"]}, ensure_ascii=False, indent=2))
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
