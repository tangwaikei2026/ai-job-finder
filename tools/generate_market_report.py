#!/usr/bin/env python3
"""Render deterministic Markdown from canonical Trend V1 artifacts only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPORT_VERSION = "report_v1"
ROOT = Path(__file__).resolve().parents[1]
TREND_ROOT = ROOT / "data" / "analysis" / "trends"
REPORT_ROOT = ROOT / "data" / "analysis" / "reports"


def _value(value: Any) -> str:
    return "null" if value is None else str(value)


def _lines_for_counts(values: dict[str, Any]) -> list[str]:
    return [f"| {key} | {_value(values[key])} |" for key in sorted(values)]


def _changes(values: dict[str, Any]) -> list[str]:
    lines = ["| Key | From | To | Delta | Comparable |", "| --- | ---: | ---: | ---: | --- |"]
    def entries(prefix: str, value: Any):
        if isinstance(value, dict) and "from" not in value:
            for child_key in sorted(value):
                yield from entries(f"{prefix}.{child_key}" if prefix else child_key, value[child_key])
        else:
            yield prefix, value
    for key, item in entries("", values):
        lines.append(
            f"| {key} | {_value(item.get('from'))} | {_value(item.get('to'))} | "
            f"{_value(item.get('delta'))} | {_value(item.get('comparable'))} |"
        )
    return lines


def _snapshot_section(title: str, values: dict[str, Any], *, non_additive: bool = False) -> list[str]:
    label = " — NON_ADDITIVE" if non_additive else ""
    return [f"## {title}{label}", "", "| Key | Count |", "| --- | ---:", *_lines_for_counts(values), ""]


def render_snapshot(snapshot: dict[str, Any]) -> str:
    if snapshot.get("artifact_type") != "trend_snapshot_v1":
        raise ValueError("EXPECTED_TREND_SNAPSHOT_V1")
    lines = [
        "# Market Report V1", "", f"- report_version: {REPORT_VERSION}",
        f"- trend_version: {snapshot.get('trend_version')}",
        f"- snapshot_date: {snapshot['snapshot_date']}", "",
        "## Market Universe", "", f"- active_jobs: {_value(snapshot.get('active_jobs'))}",
        f"- core: {_value(snapshot.get('by_market_relevance', {}).get('core'))}",
        f"- adjacent: {_value(snapshot.get('by_market_relevance', {}).get('adjacent'))}", "",
        *_snapshot_section("Primary Role Structure", snapshot.get("by_role_family", {})),
        *_snapshot_section("Role Responsibility Coverage", snapshot.get("by_role_family_any", {}), non_additive=True),
        "## Hybrid Roles", "", f"- hybrid_role_count: {_value(snapshot.get('hybrid_role_count'))}",
        f"- hybrid_role_share: {_value(snapshot.get('hybrid_role_share', {}).get('share'))}", "",
        *_snapshot_section("AI Relation", snapshot.get("by_ai_relation", {})),
        *_snapshot_section("Personal Fit", snapshot.get("by_career_pool", {})),
        *_snapshot_section("Skill Tags", snapshot.get("by_skill_tag", {}), non_additive=True),
    ]
    return "\n".join(lines) + "\n"


def _comparability(lines: list[str], name: str, info: dict[str, Any]) -> None:
    state = "COMPARABLE" if info.get("comparable") else "NOT COMPARABLE"
    lines.extend([
        f"### {name}: {state}", "",
        f"- reason_codes: {json.dumps(info.get('reason_codes', []), ensure_ascii=False)}",
        f"- included_platforms: {json.dumps(info.get('included_platforms', []), ensure_ascii=False)}",
        f"- excluded_platforms: {json.dumps(info.get('excluded_platforms', []), ensure_ascii=False)}", "",
    ])


def _comparison_section(lines: list[str], title: str, values: dict[str, Any], info: dict[str, Any], *, non_additive: bool = False) -> None:
    suffix = " — NON_ADDITIVE" if non_additive else ""
    state = "COMPARABLE" if info.get("comparable") else "NOT COMPARABLE"
    lines.extend([f"## {title}{suffix}: {state}", "", *_changes(values), ""])


def render_comparison(comparison: dict[str, Any]) -> str:
    if comparison.get("artifact_type") != "trend_comparison_v1":
        raise ValueError("EXPECTED_TREND_COMPARISON_V1")
    comparability = comparison.get("comparability", {})
    inventory = comparability.get("inventory", {})
    presence = comparability.get("presence_flow", {})
    content = comparability.get("content_flow", {})
    lines = [
        "# Market Report V1", "", f"- report_version: {REPORT_VERSION}",
        f"- trend_version: {comparison.get('trend_version')}",
        f"- from_date: {comparison['from_date']}", f"- to_date: {comparison['to_date']}", "",
        "## Comparability", "",
    ]
    _comparability(lines, "inventory", inventory)
    _comparability(lines, "presence_flow", presence)
    _comparability(lines, "content_flow", content)
    _comparison_section(lines, "Active Jobs Change", {"active_jobs": comparison.get("market", {}).get("active_jobs", {})}, inventory)
    _comparison_section(lines, "Core / Adjacent Change", {
        "core": comparison.get("market", {}).get("core_jobs", {}),
        "adjacent": comparison.get("market", {}).get("adjacent_jobs", {}),
    }, inventory)
    _comparison_section(lines, "Role Family Changes", comparison.get("by_role_family", {}), inventory)
    _comparison_section(lines, "Role Family Any Changes", comparison.get("by_role_family_any", {}), inventory, non_additive=True)
    _comparison_section(lines, "Hybrid Change", {"hybrid_role_share": comparison.get("market", {}).get("hybrid_role_share", {})}, inventory)
    _comparison_section(lines, "AI Relation Changes", comparison.get("by_ai_relation", {}), inventory)
    _comparison_section(lines, "Career Pool Changes", comparison.get("by_career_pool", {}), inventory)
    _comparison_section(lines, "Skill Changes", comparison.get("by_skill_tag", {}), inventory, non_additive=True)
    _comparison_section(lines, "Lifecycle", comparison.get("lifecycle", {}), presence)
    _comparison_section(lines, "Company Changes", comparison.get("company_changes", {}), content)
    return "\n".join(lines) + "\n"


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise ValueError(f"TREND_ARTIFACT_NOT_FOUND: {path}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date")
    group.add_argument("--from", dest="from_date")
    parser.add_argument("--to")
    parser.add_argument("--trend-root", type=Path, default=TREND_ROOT)
    parser.add_argument("--output-dir", type=Path, default=REPORT_ROOT)
    args = parser.parse_args()
    if bool(args.from_date) != bool(args.to):
        parser.error("--from and --to must be supplied together")
    if args.date:
        artifact = _read(args.trend_root / "snapshots" / f"{args.date}.json")
        report, filename = render_snapshot(artifact), f"market_report_{args.date}.md"
    else:
        artifact = _read(args.trend_root / "comparisons" / f"{args.from_date}_{args.to}.json")
        report, filename = render_comparison(artifact), f"market_report_{args.from_date}_{args.to}.md"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / filename
    destination.write_text(report)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
