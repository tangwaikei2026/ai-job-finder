from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from src.raw import main as raw_main
from src.raw.models import CollectionManifest, RawJobPosting


OUTPUT_DATE = "2026-07-03"


def _write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "raw_config.yaml"
    config_path.write_text(
        """
raw_collection:
  output_dir: output
  platforms: {}
""",
        encoding="utf-8",
    )
    return config_path


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    output_dir = tmp_path / "output"
    return (
        output_dir / f"{OUTPUT_DATE}.json",
        output_dir / f"{OUTPUT_DATE}_manifest.json",
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _install_run(
    monkeypatch,
    config_path: Path,
    *,
    jobs: list[RawJobPosting],
    manifests: list[CollectionManifest],
) -> None:
    monkeypatch.setattr(
        raw_main,
        "collect_all",
        lambda config, selected: (jobs, manifests),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "raw-main",
            "--config",
            str(config_path),
            "--date",
            OUTPUT_DATE,
        ],
    )


def _manifest(
    *,
    status: str,
    complete: bool,
    platform: str = "example",
) -> CollectionManifest:
    return CollectionManifest(
        platform=platform,
        name=platform,
        status=status,
        complete=complete,
        stopped_by="source_total_reached" if complete else "error",
        error="" if complete else "fake failure",
    )


def test_total_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _paths(tmp_path)
    _write_json(jobs_path, [{"platform": "old", "job_id": "old-1"}])
    _write_json(manifest_path, {"platforms": [{"platform": "old"}]})
    jobs_before = jobs_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    _install_run(
        monkeypatch,
        config_path,
        jobs=[],
        manifests=[_manifest(status="error", complete=False)],
    )

    with pytest.raises(
        RuntimeError,
        match="refusing to overwrite existing raw output after total failure",
    ):
        raw_main.main()

    assert jobs_path.read_bytes() == jobs_before
    assert manifest_path.read_bytes() == manifest_before


def test_no_manifests_preserves_existing_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _paths(tmp_path)
    _write_json(jobs_path, [{"platform": "old", "job_id": "old-1"}])
    _write_json(manifest_path, {"platforms": [{"platform": "old"}]})
    jobs_before = jobs_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    _install_run(monkeypatch, config_path, jobs=[], manifests=[])

    with pytest.raises(
        RuntimeError,
        match="refusing to overwrite existing raw output after total failure",
    ):
        raw_main.main()

    assert jobs_path.read_bytes() == jobs_before
    assert manifest_path.read_bytes() == manifest_before


def test_no_manifests_on_first_run_writes_incomplete_and_exits_nonzero(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _paths(tmp_path)
    _install_run(monkeypatch, config_path, jobs=[], manifests=[])

    with pytest.raises(SystemExit) as exc_info:
        raw_main.main()

    assert exc_info.value.code == 1
    assert json.loads(jobs_path.read_text(encoding="utf-8")) == []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["complete"] is False
    assert manifest["platforms"] == []


def test_complete_empty_run_can_replace_existing_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _paths(tmp_path)
    _write_json(jobs_path, [{"platform": "old", "job_id": "old-1"}])
    _write_json(manifest_path, {"platforms": [{"platform": "old"}]})
    _install_run(
        monkeypatch,
        config_path,
        jobs=[],
        manifests=[_manifest(status="success", complete=True)],
    )

    raw_main.main()

    assert json.loads(jobs_path.read_text(encoding="utf-8")) == []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["complete"] is True
    assert manifest["job_count"] == 0


def test_partial_success_writes_output_and_exits_nonzero(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _paths(tmp_path)
    job = RawJobPosting(
        job_id="job-1",
        platform="healthy",
        title="AI 测试工程师",
        company="示例公司",
    )
    _install_run(
        monkeypatch,
        config_path,
        jobs=[job],
        manifests=[
            _manifest(
                status="success",
                complete=True,
                platform="healthy",
            ),
            _manifest(
                status="error",
                complete=False,
                platform="broken",
            ),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        raw_main.main()

    assert exc_info.value.code == 1
    assert json.loads(jobs_path.read_text(encoding="utf-8"))[0]["job_id"] == "job-1"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["complete"] is False
    assert [item["status"] for item in manifest["platforms"]] == [
        "success",
        "error",
    ]
