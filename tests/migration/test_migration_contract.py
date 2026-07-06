from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from src import main as app_main
from src.collectors.liepin import LiepinRawCollector
from src.models import (
    CollectionManifest,
    CollectionResult,
    RawJobPosting,
    write_json_atomic,
)


ROOT = Path(__file__).parents[2]
OUTPUT_DATE = "2026-07-06"


def _job(platform: str = "target", job_id: str = "job-1") -> RawJobPosting:
    return RawJobPosting(
        job_id=job_id,
        platform=platform,
        title="AI 测试工程师",
        company="示例公司",
        location="上海",
        scraped_at="2026-07-06 09:00:00",
    )


def _manifest(
    platform: str = "target",
    *,
    status: str = "success",
    complete: bool = True,
) -> CollectionManifest:
    return CollectionManifest(
        platform=platform,
        name=f"{platform} platform",
        status=status,
        complete=complete,
        source_total=1,
        expected_pages=1,
        pages_fetched=1,
        records_fetched=1,
        jobs_mapped=1,
        jobs_in_scope=1,
        stopped_by="source_total_reached" if complete else "error",
        error="" if complete else "fake failure",
        started_at="2026-07-06 09:00:00",
        finished_at="2026-07-06 09:00:01",
        duration_seconds=1.0,
    )


def _write_config(
    path: Path,
    *,
    output_dir: str | None = "output",
) -> Path:
    output_line = f'output_dir: "{output_dir}"\n' if output_dir is not None else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            f"{output_line}"
            "cities:\n"
            "  - 上海\n"
            "platforms:\n"
            "  target:\n"
            "    enabled: true\n"
            "    name: target platform\n"
        ),
        encoding="utf-8",
    )
    return path


def _install_main_run(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    *,
    jobs: list[RawJobPosting] | None = None,
    manifests: list[CollectionManifest] | None = None,
) -> None:
    monkeypatch.setattr(app_main, "COLLECTOR_REGISTRY", {"target": object()})
    monkeypatch.setattr(
        app_main,
        "collect_all",
        lambda config, selected: (
            [_job()] if jobs is None else jobs,
            [_manifest()] if manifests is None else manifests,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["src.main", *argv])


def _output_paths(base: Path, output_dir: str = "output") -> tuple[Path, Path]:
    directory = base / output_dir
    return (
        directory / f"{OUTPUT_DATE}.json",
        directory / f"{OUTPUT_DATE}_manifest.json",
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_module_help_uses_canonical_entrypoint() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.main", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--platform" in completed.stdout
    assert "--merge-existing" in completed.stdout


def test_repository_has_no_old_namespace_imports() -> None:
    banned = "src" + ".raw"
    python_files = [*ROOT.joinpath("src").rglob("*.py"), *ROOT.joinpath("tests").rglob("*.py")]

    offenders = [
        str(path.relative_to(ROOT))
        for path in python_files
        if banned in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_old_module_entrypoint_is_removed() -> None:
    old_module = "src" + ".raw.main"
    assert importlib.util.find_spec("src" + ".raw") is None

    completed = subprocess.run(
        [sys.executable, "-m", old_module, "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0


def test_top_level_config_loads_and_legacy_wrapper_is_rejected(
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    assert app_main.load_config(config_path)["platforms"]["target"]["enabled"] is True

    legacy_path = tmp_path / "legacy.yaml"
    legacy_path.write_text(
        "raw_collection:\n  platforms: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="legacy raw_collection wrapper"):
        app_main.load_config(legacy_path)


def test_default_config_and_output_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_config(tmp_path / "config.yaml", output_dir=None)
    monkeypatch.chdir(tmp_path)
    _install_main_run(monkeypatch, ["--date", OUTPUT_DATE])

    app_main.main()

    jobs_path, manifest_path = _output_paths(tmp_path, "data/raw")
    assert jobs_path.exists()
    assert manifest_path.exists()


def test_relative_config_resolves_output_from_config_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_config(tmp_path / "settings" / "custom.yaml")
    monkeypatch.chdir(tmp_path)
    _install_main_run(
        monkeypatch,
        ["--config", "settings/custom.yaml", "--date", OUTPUT_DATE],
    )

    app_main.main()

    jobs_path, manifest_path = _output_paths(tmp_path / "settings")
    assert jobs_path.exists()
    assert manifest_path.exists()


def test_collect_all_supports_full_and_single_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCollector:
        def __init__(self, platform_config, collection_config):
            self.platform = platform_config["platform"]

        def collect(self) -> CollectionResult:
            return CollectionResult(
                jobs=[_job(self.platform)],
                manifest=_manifest(self.platform),
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        app_main,
        "COLLECTOR_REGISTRY",
        {"alpha": FakeCollector, "beta": FakeCollector},
    )
    config = {
        "platforms": {
            "alpha": {"enabled": True, "platform": "alpha"},
            "beta": {"enabled": True, "platform": "beta"},
        }
    }

    all_jobs, all_manifests = app_main.collect_all(config)
    selected_jobs, selected_manifests = app_main.collect_all(config, "beta")

    assert [job.platform for job in all_jobs] == ["alpha", "beta"]
    assert [item.platform for item in all_manifests] == ["alpha", "beta"]
    assert [job.platform for job in selected_jobs] == ["beta"]
    assert [item.platform for item in selected_manifests] == ["beta"]


def test_merge_existing_replaces_only_selected_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    jobs_path, manifest_path = _output_paths(tmp_path)
    kept_job = _job("other", "keep-1")
    _write_json(jobs_path, [_job("target", "old-1").to_dict(), kept_job.to_dict()])
    _write_json(
        manifest_path,
        {"platforms": [_manifest("target").to_dict(), _manifest("other").to_dict()]},
    )
    _install_main_run(
        monkeypatch,
        [
            "--config",
            str(config_path),
            "--date",
            OUTPUT_DATE,
            "--platform",
            "target",
            "--merge-existing",
        ],
    )

    app_main.main()

    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    assert [(item["platform"], item["job_id"]) for item in jobs] == [
        ("other", "keep-1"),
        ("target", "job-1"),
    ]


def test_merge_existing_rejects_missing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    _install_main_run(
        monkeypatch,
        [
            "--config",
            str(config_path),
            "--date",
            OUTPUT_DATE,
            "--platform",
            "target",
            "--merge-existing",
        ],
    )

    with pytest.raises(ValueError, match="requires existing dated output files"):
        app_main.main()


def test_merge_existing_rejects_incomplete_run_without_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    jobs_path, manifest_path = _output_paths(tmp_path)
    _write_json(jobs_path, [_job("target", "old-1").to_dict()])
    _write_json(manifest_path, {"platforms": [_manifest().to_dict()]})
    jobs_before = jobs_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    _install_main_run(
        monkeypatch,
        [
            "--config",
            str(config_path),
            "--date",
            OUTPUT_DATE,
            "--platform",
            "target",
            "--merge-existing",
        ],
        jobs=[_job()],
        manifests=[_manifest(status="partial", complete=False)],
    )

    with pytest.raises(RuntimeError, match="incomplete platform run"):
        app_main.main()

    assert jobs_path.read_bytes() == jobs_before
    assert manifest_path.read_bytes() == manifest_before


def test_total_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    jobs_path, manifest_path = _output_paths(tmp_path)
    _write_json(jobs_path, [_job("target", "old-1").to_dict()])
    _write_json(manifest_path, {"platforms": [_manifest().to_dict()]})
    jobs_before = jobs_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    _install_main_run(
        monkeypatch,
        ["--config", str(config_path), "--date", OUTPUT_DATE],
        jobs=[],
        manifests=[_manifest(status="error", complete=False)],
    )

    with pytest.raises(RuntimeError, match="total failure"):
        app_main.main()

    assert jobs_path.read_bytes() == jobs_before
    assert manifest_path.read_bytes() == manifest_before


def test_partial_failure_writes_manifest_and_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    _install_main_run(
        monkeypatch,
        ["--config", str(config_path), "--date", OUTPUT_DATE],
        jobs=[_job("healthy")],
        manifests=[
            _manifest("healthy"),
            _manifest("broken", status="error", complete=False),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        app_main.main()

    assert exc_info.value.code == 1
    jobs_path, manifest_path = _output_paths(tmp_path)
    assert json.loads(jobs_path.read_text(encoding="utf-8"))[0]["platform"] == "healthy"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["complete"] is False
    assert [item["status"] for item in manifest["platforms"]] == ["success", "error"]


def test_atomic_write_replaces_target_and_removes_temp_file(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    path.write_text('{"old": true}\n', encoding="utf-8")

    write_json_atomic(path, {"new": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}
    assert not path.with_suffix(".json.tmp").exists()


def test_liepin_uses_migrated_additional_output_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = app_main.load_config(ROOT / "config.yaml")
    output_file = config["platforms"]["liepin"]["output_file"]
    collector = object.__new__(LiepinRawCollector)
    collector.platform_config = {"output_file": output_file}
    written_paths: list[Path] = []
    monkeypatch.setattr(
        "src.collectors.liepin.write_json_atomic",
        lambda path, data: written_paths.append(path),
    )

    collector._write_output_safely([_job("liepin")], [])

    assert output_file == "data/liepin/raw_job.json"
    assert written_paths == [ROOT / "data/liepin/raw_job.json"]


def test_workflow_keeps_canonical_command_and_current_artifact_path() -> None:
    workflow = (ROOT / ".github/workflows/daily-scrape.yml").read_text(
        encoding="utf-8"
    )
    old_command = "python -m " + "src" + ".raw.main"

    assert "python -m src.main" in workflow
    assert old_command not in workflow
    assert "path: data/raw/" in workflow


def test_mock_output_matches_pre_migration_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 6, 9, 30, 0)

    config_path = _write_config(tmp_path / "config.yaml")
    monkeypatch.setattr(app_main, "datetime", FrozenDateTime)
    _install_main_run(
        monkeypatch,
        ["--config", str(config_path), "--date", OUTPUT_DATE],
    )

    app_main.main()

    jobs_path, manifest_path = _output_paths(tmp_path)
    assert json.loads(jobs_path.read_text(encoding="utf-8")) == [
        {
            "job_id": "job-1",
            "platform": "target",
            "title": "AI 测试工程师",
            "company": "示例公司",
            "department": "",
            "location": "上海",
            "experience": "",
            "education": "",
            "salary": "",
            "description": "",
            "requirements": "",
            "url": "",
            "scraped_at": "2026-07-06 09:00:00",
        }
    ]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest == {
        "generated_at": "2026-07-06 09:30:00",
        "config": str(config_path),
        "cities": ["上海"],
        "job_count": 1,
        "complete": True,
        "platforms": [_manifest().to_dict()],
    }
