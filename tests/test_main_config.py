from __future__ import annotations

from pathlib import Path

import pytest

from src import main as raw_main


def _write_config(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_load_config_reads_platforms_mapping(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "config.yaml",
        """
cities:
  - 上海
platforms:
  example:
    enabled: false
""",
    )

    config = raw_main.load_config(config_path)

    assert config["cities"] == ["上海"]
    assert config["platforms"] == {
        "example": {
            "enabled": False,
        }
    }


def test_load_config_rejects_legacy_raw_collection(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "config.yaml",
        "raw_collection:\n  platforms: {}\n",
    )

    with pytest.raises(
        ValueError,
        match="no longer accepts the legacy raw_collection wrapper",
    ):
        raw_main.load_config(config_path)


def test_load_config_rejects_missing_platforms(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "config.yaml",
        "cities: []\n",
    )

    with pytest.raises(
        ValueError,
        match="config.yaml platforms must be a mapping",
    ):
        raw_main.load_config(config_path)


def test_sensetime_uses_current_official_portal_urls() -> None:
    config = raw_main.load_config(Path(__file__).parents[1] / "config.yaml")
    companies = {
        company["name"]: company
        for company in config["platforms"]["feishu"]["companies"]
    }

    assert companies["商汤科技"] == {
        "name": "商汤科技",
        "list_url": "https://hr-jobs.sensetime.com/exp/position/list",
        "detail_url": "https://hr-jobs.sensetime.com/exp/position/{job_id}/detail",
    }
    assert companies["MiniMax"]["list_url"] == "https://vrfi1sk8a0.jobs.feishu.cn/index/"
    assert companies["智谱AI"]["list_url"] == "https://zhipu-ai.jobs.feishu.cn/index/"
    assert companies["零一万物"]["list_url"] == "https://01ai.jobs.feishu.cn/index/position/list"
    assert companies["百川智能"]["list_url"] == (
        "https://cq6qe6bvfr6.jobs.feishu.cn/baichuanzhaopin/"
    )
