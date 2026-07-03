from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from src.raw import main as raw_main
from src.raw.models import CollectionManifest, RawJobPosting


OUTPUT_DATE = "2026-07-03"
TARGET_PLATFORM = "target"
OTHER_PLATFORM = "other"


def _job(platform: str, job_id: str, title: str) -> RawJobPosting:
    return RawJobPosting(
        job_id=job_id,
        platform=platform,
        title=title,
        company=f"{platform} company",
        scraped_at="2026-07-03 12:00:00",
    )


def _manifest(
    platform: str,
    *,
    complete: bool = True,
    source_total: int = 1,
) -> CollectionManifest:
    return CollectionManifest(
        platform=platform,
        name=f"{platform} platform",
        status="success" if complete else "partial",
        complete=complete,
        source_total=source_total,
        records_fetched=source_total,
        jobs_mapped=source_total,
        jobs_in_scope=source_total,
        stopped_by="source_total_reached" if complete else "error",
        error="" if complete else "fake incomplete run",
        started_at="2026-07-03 12:00:00",
        finished_at="2026-07-03 12:00:01",
        duration_seconds=1.0,
    )


def _write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "raw_config.yaml"
    config_path.write_text(
        """
raw_collection:
  output_dir: output
  cities:
    - 上海
  platforms:
    target:
      enabled: true
      name: target platform
""",
        encoding="utf-8",
    )
    return config_path


def _output_paths(tmp_path: Path) -> tuple[Path, Path]:
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


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as input_file:
        return json.load(input_file)


def _install_fake_run(
    monkeypatch,
    config_path: Path,
    *,
    jobs: list[RawJobPosting],
    manifests: list[CollectionManifest],
    selected_platform: str | None = TARGET_PLATFORM,
) -> list[tuple[dict[str, Any], str | None]]:
    calls: list[tuple[dict[str, Any], str | None]] = []

    def fake_collect_all(
        config: dict[str, Any],
        selected: str | None,
    ) -> tuple[list[RawJobPosting], list[CollectionManifest]]:
        calls.append((config, selected))
        return jobs, manifests

    monkeypatch.setattr(
        raw_main,
        "COLLECTOR_REGISTRY",
        {TARGET_PLATFORM: object()},
    )
    monkeypatch.setattr(raw_main, "collect_all", fake_collect_all)

    argv = [
        "raw-main",
        "--config",
        str(config_path),
        "--date",
        OUTPUT_DATE,
        "--merge-existing",
    ]
    if selected_platform is not None:
        argv.extend(["--platform", selected_platform])
    monkeypatch.setattr(sys, "argv", argv)
    return calls


def test_merge_existing_requires_selected_platform(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    calls = _install_fake_run(
        monkeypatch,
        config_path,
        jobs=[],
        manifests=[_manifest(TARGET_PLATFORM)],
        selected_platform=None,
    )

    with pytest.raises(
        ValueError,
        match="--merge-existing requires --platform",
    ):
        raw_main.main()

    assert len(calls) == 1
    assert calls[0][1] is None
    assert not any((tmp_path / "output").glob("*.json"))


def test_merge_existing_requires_existing_jobs_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _output_paths(tmp_path)
    old_manifest = {
        "platforms": [_manifest(OTHER_PLATFORM).to_dict()],
    }
    _write_json(manifest_path, old_manifest)
    _install_fake_run(
        monkeypatch,
        config_path,
        jobs=[_job(TARGET_PLATFORM, "new-1", "new target job")],
        manifests=[_manifest(TARGET_PLATFORM)],
    )

    with pytest.raises(
        ValueError,
        match="--merge-existing requires existing dated output files",
    ):
        raw_main.main()

    assert not jobs_path.exists()
    assert _read_json(manifest_path) == old_manifest


def test_merge_existing_requires_existing_manifest_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _output_paths(tmp_path)
    old_jobs = [_job(OTHER_PLATFORM, "keep-1", "kept job").to_dict()]
    _write_json(jobs_path, old_jobs)
    _install_fake_run(
        monkeypatch,
        config_path,
        jobs=[_job(TARGET_PLATFORM, "new-1", "new target job")],
        manifests=[_manifest(TARGET_PLATFORM)],
    )

    with pytest.raises(
        ValueError,
        match="--merge-existing requires existing dated output files",
    ):
        raw_main.main()

    assert _read_json(jobs_path) == old_jobs
    assert not manifest_path.exists()


def test_merge_existing_replaces_only_selected_platform(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _output_paths(tmp_path)
    kept_job = _job(OTHER_PLATFORM, "keep-1", "kept other job")
    old_jobs = [
        _job(TARGET_PLATFORM, "old-1", "old target job").to_dict(),
        kept_job.to_dict(),
        _job(TARGET_PLATFORM, "old-2", "another old target job").to_dict(),
    ]
    kept_manifest = _manifest(OTHER_PLATFORM, source_total=3)
    old_manifest = {
        "generated_at": "2026-07-02 12:00:00",
        "platforms": [
            _manifest(TARGET_PLATFORM, source_total=2).to_dict(),
            kept_manifest.to_dict(),
        ],
    }
    _write_json(jobs_path, old_jobs)
    _write_json(manifest_path, old_manifest)

    new_job = _job(TARGET_PLATFORM, "new-1", "new target job")
    new_manifest = _manifest(TARGET_PLATFORM)
    calls = _install_fake_run(
        monkeypatch,
        config_path,
        jobs=[new_job],
        manifests=[new_manifest],
    )

    raw_main.main()

    merged_jobs = _read_json(jobs_path)
    assert [(job["platform"], job["job_id"]) for job in merged_jobs] == [
        (OTHER_PLATFORM, "keep-1"),
        (TARGET_PLATFORM, "new-1"),
    ]
    assert merged_jobs[0] == kept_job.to_dict()

    merged_manifest = _read_json(manifest_path)
    assert [
        (manifest["platform"], manifest["source_total"])
        for manifest in merged_manifest["platforms"]
    ] == [
        (OTHER_PLATFORM, 3),
        (TARGET_PLATFORM, 1),
    ]
    assert merged_manifest["platforms"][0] == kept_manifest.to_dict()
    assert merged_manifest["platforms"][1] == new_manifest.to_dict()
    assert merged_manifest["job_count"] == 2
    assert merged_manifest["complete"] is True
    assert len(calls) == 1
    assert calls[0][1] == TARGET_PLATFORM


def test_merge_existing_rejects_incomplete_collection_without_overwrite(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config(tmp_path)
    jobs_path, manifest_path = _output_paths(tmp_path)
    old_jobs = [_job(TARGET_PLATFORM, "old-1", "old target job").to_dict()]
    old_manifest = {
        "generated_at": "2026-07-02 12:00:00",
        "platforms": [_manifest(TARGET_PLATFORM).to_dict()],
    }
    _write_json(jobs_path, old_jobs)
    _write_json(manifest_path, old_manifest)
    jobs_before = jobs_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    _install_fake_run(
        monkeypatch,
        config_path,
        jobs=[_job(TARGET_PLATFORM, "new-1", "incomplete new job")],
        manifests=[_manifest(TARGET_PLATFORM, complete=False)],
    )

    with pytest.raises(
        RuntimeError,
        match="refusing to replace existing data with an incomplete platform run",
    ):
        raw_main.main()

    assert jobs_path.read_bytes() == jobs_before
    assert manifest_path.read_bytes() == manifest_before
