from __future__ import annotations

from pathlib import Path

import pytest

from src.raw import main as raw_main


def _write_config(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_load_raw_config_reads_platforms_mapping(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "raw_config.yaml",
        """
raw_collection:
  cities:
    - 上海
  platforms:
    example:
      enabled: false
""",
    )

    config = raw_main.load_raw_config(config_path)

    assert config["cities"] == ["上海"]
    assert config["platforms"] == {
        "example": {
            "enabled": False,
        }
    }


def test_load_raw_config_rejects_missing_raw_collection(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "raw_config.yaml",
        "platforms: {}\n",
    )

    with pytest.raises(
        ValueError,
        match="must contain a raw_collection mapping",
    ):
        raw_main.load_raw_config(config_path)


def test_load_raw_config_rejects_missing_platforms(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path / "raw_config.yaml",
        "raw_collection:\n  cities: []\n",
    )

    with pytest.raises(
        ValueError,
        match=r"raw_collection\.platforms must be a mapping",
    ):
        raw_main.load_raw_config(config_path)
