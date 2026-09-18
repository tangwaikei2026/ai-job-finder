from __future__ import annotations

import hashlib
import json
from pathlib import Path

import tools.sourcehealth_v2_backfill as backfill


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _inputs(data_dir: Path, day: str) -> None:
    job = {
        "platform": "example", "job_id": f"job-{day}", "company": "Example",
        "title": "AI测试", "description": "Eval", "requirements": "Python",
        "locations_norm": [], "location_level": [], "province_norm": [], "city_norm": [],
    }
    _write_json(data_dir / "raw" / f"{day}.json", [job])
    _write_json(data_dir / "raw" / f"{day}_manifest.json", {
        "date": day, "job_count": 1, "complete": True, "cities": ["北京"],
        "platforms": [{
            "platform": "example", "status": "success", "complete": True,
            "source_total": 1, "expected_pages": 1, "pages_fetched": 1,
            "records_fetched": 1, "jobs_mapped": 1, "jobs_in_scope": 1,
            "detail_failed": 0, "stopped_by": "source_total_reached",
        }],
    })
    _write_json(data_dir / "clean" / f"{day}.json", [job])


def _snapshot(day: str, *, version: str, unknown: int = 0) -> dict:
    metrics = {
        "active_jobs": 1, "unknown_classification_count": unknown,
        "observed_inventory_count": 1 + unknown,
        "new_jobs": 0, "removed_jobs": 0, "reappeared_jobs": 0, "updated_jobs": 0,
        "unknown_new_jobs": 0, "unknown_removed_jobs": 0,
        "unknown_reappeared_jobs": 0, "unknown_updated_jobs": 0,
        "by_career_pool": {"P1": 1}, "by_skill_tag": {"Python": 1},
    }
    reliability = {family: {"reliable": True, "reason_codes": []}
                   for family in ("inventory", "presence_flow", "content_flow")}
    return {
        "artifact_type": "trend_snapshot_v1", "snapshot_date": day,
        "trend_version": version, **metrics,
        "platforms": {"example": {"metrics": metrics, "reliability": reliability}},
    }


def _fake_replay(calls: list[tuple[str, str]]):
    def run(start, end, *, output_dir, **_kwargs):
        calls.append((start, end))
        stage = Path(output_dir)
        row = {
            "snapshot_date": start, "platform": "example", "job_id": f"job-{start}",
            "company": "Example", "title": "AI测试", "in_scope": True,
            "market_relevance": "core", "role_family": "qa_test",
            "secondary_role_families": [], "ai_relation": "ai_product_quality",
            "seniority_level": "regular", "career_pool": "P1",
            "reason_codes": {"market": [], "fit": []}, "skill_tags": ["Python"],
            "classification_status": "fresh",
        }
        classification = stage / "classification" / f"{start}.jsonl"
        classification.parent.mkdir(parents=True, exist_ok=True)
        classification.write_text(json.dumps(row) + "\n", encoding="utf-8")
        events = stage / "events" / f"{start}.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        events.write_text("", encoding="utf-8")
        _write_json(stage / "trends" / "snapshots" / f"{start}.json",
                    _snapshot(start, version="trend_v2", unknown=2))
        _write_json(stage / "audit" / f"{start}_bundle.json", {"snapshot_date": start})
        return {"historical_replay_verified": True}
    return run


def _tree_hashes(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(path)): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*")) if item.is_file()
    }


def test_coverage_distinguishes_v1_v2_and_missing_inputs(tmp_path):
    data = tmp_path / "data"
    _inputs(data, "2026-01-01")
    _inputs(data, "2026-01-02")
    (data / "raw" / "2026-01-03.json").write_text("[]", encoding="utf-8")
    for day, version in (("2026-01-01", "trend_v1"), ("2026-01-02", "trend_v2")):
        _write_json(data / "analysis" / "trends" / "snapshots" / f"{day}.json",
                    _snapshot(day, version=version))
        for folder, suffix in (("classification", ".jsonl"), ("events", ".jsonl")):
            path = data / "analysis" / folder / f"{day}{suffix}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        _write_json(data / "analysis" / "audit" / f"{day}_bundle.json", {})
    rows = {row["date"]: row for row in backfill.coverage_audit(data)}
    assert rows["2026-01-01"]["coverage_status"] == "CAN_REPLAY_V2"
    assert rows["2026-01-02"]["coverage_status"] == "ALREADY_V2"
    assert rows["2026-01-03"]["coverage_status"] == "NOT_RECOVERABLE"


def test_v2_backfill_replaces_only_derived_and_is_idempotent(tmp_path, monkeypatch):
    data = tmp_path / "data"
    day = "2026-01-01"
    _inputs(data, day)
    _write_json(data / "analysis" / "trends" / "snapshots" / f"{day}.json",
                _snapshot(day, version="trend_v1"))
    health = data / "analysis" / "health" / f"{day}.json"
    _write_json(health, {"date": day, "overall_action": "ACTION_REQUIRED"})
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(backfill, "replay", _fake_replay(calls))
    monkeypatch.setattr(backfill, "validate_snapshot", lambda _snapshot: None)
    settings = tmp_path / "versions.yaml"
    settings.write_text("unused: true\n", encoding="utf-8")
    audit = data / "analysis" / "audit"
    source_before = _tree_hashes(data / "raw") | _tree_hashes(data / "clean")
    health_before = health.read_bytes()

    first = backfill.run_v2_backfill(
        data_dir=data, root=tmp_path, settings_path=settings, audit_dir=audit,
    )
    assert first["summary"]["partial_v2"] == 1
    assert first["dates"][0]["validation"]["unattributed_legacy_unknown"] == 2
    assert _read_version(data, day) == "trend_v2"
    derived_before_second = _derived_hashes(data)

    second = backfill.run_v2_backfill(
        data_dir=data, root=tmp_path, settings_path=settings, audit_dir=audit,
    )
    assert calls == [(day, day)]
    assert second["idempotency"] == {
        "verified": True, "derived_artifacts_changed_on_second_run": False,
    }
    assert _derived_hashes(data) == derived_before_second
    assert (_tree_hashes(data / "raw") | _tree_hashes(data / "clean")) == source_before
    assert health.read_bytes() == health_before


def test_before_after_keeps_frozen_v1_baseline_and_uses_observed_v2_values():
    reliability = {family: {"reliable": True, "reason_codes": []}
                   for family in ("inventory", "presence_flow", "content_flow")}
    delta = backfill._before_after({
        "tencent_2026_09_17": {
            "metrics": {"active_jobs": 127, "unknown_classification_count": 1,
                        "observed_inventory_count": 128, "new_jobs": 3,
                        "unknown_new_jobs": 1},
            "reliability": reliability,
        },
    })
    assert delta["tencent_2026_09_17"]["before_v1"]["content_flow_reliable"] is False
    assert delta["tencent_2026_09_17"]["after_v2"]["unknown"] == 1
    assert delta["tencent_2026_09_17"]["after_v2"]["unknown_new"] == 1


def _read_version(data: Path, day: str) -> str:
    return json.loads((data / "analysis" / "trends" / "snapshots" / f"{day}.json").read_text())["trend_version"]


def _derived_hashes(data: Path) -> dict[str, str]:
    result = _tree_hashes(data / "analysis")
    return {key: value for key, value in result.items()
            if not key.startswith("audit/sourcehealth_v2_backfill_")}
