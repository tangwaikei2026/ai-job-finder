from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import tools.backfill_history as backfill


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _input_triplet(data_dir: Path, day: str) -> None:
    raw = [{"platform": "example", "job_id": f"job-{day}", "company": "Example", "title": "AI测试", "description": "Eval", "requirements": "Python"}]
    clean = [{**raw[0], "locations_norm": [], "location_level": [], "province_norm": [], "city_norm": []}]
    manifest = {
        "date": day,
        "generated_at": f"{day}T09:00:00+08:00",
        "config": "/historical/config.yaml",
        "job_count": 1,
        "complete": True,
        "cities": ["北京"],
        "platforms": [{
            "platform": "example",
            "status": "success",
            "complete": True,
            "source_total": 1,
            "expected_pages": 1,
            "pages_fetched": 1,
            "records_fetched": 1,
            "jobs_mapped": 1,
            "jobs_in_scope": 1,
            "detail_failed": 0,
            "stopped_by": "source_total_reached",
        }],
    }
    _write_json(data_dir / "raw" / f"{day}.json", raw)
    _write_json(data_dir / "raw" / f"{day}_manifest.json", manifest)
    _write_json(data_dir / "clean" / f"{day}.json", clean)


def _classification(day: str) -> dict:
    return {
        "snapshot_date": day,
        "platform": "example",
        "job_id": f"job-{day}",
        "company": "Example",
        "title": "AI测试",
        "city_norm": [],
        "in_scope": True,
        "market_relevance": "core",
        "role_family": "qa_test",
        "secondary_role_families": [],
        "ai_relation": "ai_product_quality",
        "seniority_level": "regular",
        "career_pool": "P1",
        "reason_codes": {"market": [], "fit": []},
        "evidence": {},
        "skill_tags": ["Python"],
        "classification_status": "fresh",
        "versions": {"market": "market_v1", "fit": "fit_v1", "skills": "skills_v1"},
        "content_sha256": "abc",
        "url": "",
    }


def _snapshot(day: str) -> dict:
    reliable = {name: {"reliable": True, "reason_codes": []} for name in ("inventory", "presence_flow", "content_flow")}
    return {
        "artifact_type": "trend_snapshot_v1",
        "snapshot_date": day,
        "trend_version": "trend_v1",
        "lifecycle_contract": {"owner": "src/analysis/lifecycle.py"},
        "platforms": {"example": {"reliability": reliable}},
    }


def _fake_replay(start, end, *, output_dir, **_kwargs):
    assert start == end
    day = start
    output_dir = Path(output_dir)
    classification = output_dir / "classification" / f"{day}.jsonl"
    classification.parent.mkdir(parents=True, exist_ok=True)
    classification.write_text(json.dumps(_classification(day), ensure_ascii=False) + "\n", encoding="utf-8")
    events = output_dir / "events" / f"{day}.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text("", encoding="utf-8")
    _write_json(output_dir / "trends" / "snapshots" / f"{day}.json", _snapshot(day))
    _write_json(output_dir / "audit" / f"{day}_bundle.json", {"snapshot_date": day, "jobs": []})
    _write_json(output_dir / "audit" / f"{day}_{day}_replay.json", {"from_date": day, "to_date": day})
    return {"historical_replay_verified": True}


def _install_existing_chain(data_dir: Path, day: str) -> None:
    stage = data_dir / "stage"
    _fake_replay(day, day, output_dir=stage)
    for source in stage.rglob("*"):
        if source.is_file():
            destination = data_dir / "analysis" / source.relative_to(stage)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    _write_json(data_dir / "analysis" / "runs" / f"{day}.json", {"date": day, "status": "SUCCESS"})
    _write_json(data_dir / "analysis" / "health" / f"{day}.json", {
        "date": day,
        "sources": {"example": {"source_health": {}, "limitation_state": "NORMAL"}},
    })
    db = data_dir / "ops" / "ops.sqlite3"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE runs(run_date TEXT)")
        connection.execute("INSERT INTO runs VALUES (?)", (day,))


def _tree_hashes(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(path)): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def test_backfill_handles_complete_recoverable_and_unrecoverable_idempotently(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    complete = "2026-01-03"
    recoverable = "2026-01-02"
    unrecoverable = "2026-01-01"
    _input_triplet(data_dir, complete)
    _input_triplet(data_dir, recoverable)
    _install_existing_chain(data_dir, complete)
    _write_json(data_dir / "raw" / f"{unrecoverable}.json", [])
    config = tmp_path / "config.yaml"
    settings = tmp_path / "versions.yaml"
    config.write_text("output_dir: data/raw\n", encoding="utf-8")
    settings.write_text("unused: true\n", encoding="utf-8")
    monkeypatch.setattr(backfill, "replay", _fake_replay)
    monkeypatch.setattr(backfill, "render_snapshot", lambda _value: "# report\n")

    first = backfill.run_backfill(
        data_dir=data_dir,
        root=tmp_path,
        config_path=config,
        settings_path=settings,
        base_sha="taxonomy-sha",
    )
    assert first["summary"] == {
        "total_historical_dates": 3,
        "already_complete": 1,
        "fully_backfilled": 0,
        "partially_backfilled": 1,
        "not_recoverable": 1,
        "failed": 0,
    }
    by_date = {row["date"]: row for row in first["dates"]}
    assert by_date[complete]["result"] == "ALREADY_COMPLETE"
    assert by_date[recoverable]["result"] == "PARTIAL_BACKFILL"
    assert by_date[unrecoverable]["result"] == "NOT_RECOVERABLE"
    assert not by_date[recoverable]["final"]["daily_status_present"]
    assert (data_dir / "analysis" / "classification" / f"{recoverable}.jsonl").is_file()
    before = _tree_hashes(data_dir)

    second = backfill.run_backfill(
        data_dir=data_dir,
        root=tmp_path,
        config_path=config,
        settings_path=settings,
        base_sha="taxonomy-sha",
    )
    assert second["summary"] == first["summary"]
    assert _tree_hashes(data_dir) == before


def test_dependency_map_names_the_production_reliability_gate():
    trend = backfill.dependency_map()["Trend"]
    assert trend["entrypoint"] == "src.analysis.trends.trend_snapshot / compare_trends"
    assert trend["reliability_gate"] == "src.analysis.trends.trend_comparability"
