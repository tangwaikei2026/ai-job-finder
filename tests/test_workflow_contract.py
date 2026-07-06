from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "daily-scrape.yml"
)


def _workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_workflow_uses_supported_raw_commands() -> None:
    workflow = _workflow()

    assert "python -m src.main" in workflow
    assert 'python -m src.main --platform "${{ github.event.inputs.platform }}"' in workflow
    assert "--tier" not in workflow
    assert "--enrich-details" not in workflow
    assert "--dry-run" not in workflow


def test_workflow_has_single_raw_collection_job() -> None:
    workflow = _workflow()

    assert "collect-raw:" in workflow
    assert "scrape-tier1:" not in workflow
    assert "scrape-tier2:" not in workflow
    assert "merge-and-notify:" not in workflow


def test_workflow_uploads_raw_artifact_only() -> None:
    workflow = _workflow()

    assert "path: data/raw/" in workflow
    assert "data/jobs.json" not in workflow
    assert "data/daily/" not in workflow
