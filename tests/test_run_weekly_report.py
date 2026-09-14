from __future__ import annotations

import json

import pytest

from tools import run_weekly_report


def test_weekly_wrapper_creates_endpoint_comparison_and_delegates_report(tmp_path, monkeypatch):
    trend_root = tmp_path / "data" / "analysis" / "trends"
    snapshots = trend_root / "snapshots"
    snapshots.mkdir(parents=True)
    snapshots.joinpath("2026-09-01.json").write_text(json.dumps({"snapshot_date": "2026-09-01"}))
    snapshots.joinpath("2026-09-07.json").write_text(json.dumps({"snapshot_date": "2026-09-07"}))
    comparison_path = trend_root / "comparisons" / "2026-09-01_2026-09-07.json"
    comparison_path.parent.mkdir(parents=True)
    comparison_path.write_text(json.dumps({"old": True}))
    monkeypatch.setattr(
        run_weekly_report,
        "compare_trends",
        lambda before, after: {
            "artifact_type": "trend_comparison_v1",
            "from_date": before["snapshot_date"],
            "to_date": after["snapshot_date"],
        },
    )
    calls = []

    def runner(command, cwd):
        calls.append(list(command))
        return 0

    output_dir = tmp_path / "data" / "analysis" / "reports"
    code, report = run_weekly_report.run_weekly_report(
        "2026-09-01",
        "2026-09-07",
        trend_root=trend_root,
        output_dir=output_dir,
        root=tmp_path,
        command_runner=runner,
    )
    comparison = json.loads(
        (trend_root / "comparisons" / "2026-09-01_2026-09-07.json").read_text()
    )
    assert code == 0
    assert comparison["artifact_type"] == "trend_comparison_v1"
    assert report == output_dir / "market_report_2026-09-01_2026-09-07.md"
    assert len(calls) == 1
    assert calls[0][1].endswith("tools/generate_market_report.py")


def test_weekly_wrapper_requires_increasing_dates(tmp_path):
    with pytest.raises(ValueError, match="earlier"):
        run_weekly_report.run_weekly_report(
            "2026-09-07", "2026-09-01", trend_root=tmp_path
        )


def test_weekly_wrapper_requires_exact_endpoint_snapshots(tmp_path):
    trend_root = tmp_path / "trends"
    snapshots = trend_root / "snapshots"
    snapshots.mkdir(parents=True)
    snapshots.joinpath("2026-09-01.json").write_text(
        json.dumps({"snapshot_date": "2026-08-31"})
    )
    snapshots.joinpath("2026-09-07.json").write_text(
        json.dumps({"snapshot_date": "2026-09-07"})
    )
    with pytest.raises(ValueError, match="does not match"):
        run_weekly_report.run_weekly_report(
            "2026-09-01", "2026-09-07", trend_root=trend_root
        )


def test_weekly_wrapper_does_not_substitute_a_missing_endpoint(tmp_path):
    trend_root = tmp_path / "trends"
    snapshots = trend_root / "snapshots"
    snapshots.mkdir(parents=True)
    snapshots.joinpath("2026-09-01.json").write_text(
        json.dumps({"snapshot_date": "2026-09-01"})
    )
    with pytest.raises(FileNotFoundError):
        run_weekly_report.run_weekly_report(
            "2026-09-01", "2026-09-07", trend_root=trend_root
        )
