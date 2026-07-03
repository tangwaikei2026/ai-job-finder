from __future__ import annotations

import importlib.util


def test_legacy_main_remains_available_for_rollback() -> None:
    assert importlib.util.find_spec("src.legacy.main") is not None


def test_legacy_main_imports() -> None:
    import src.legacy.main

    assert callable(src.legacy.main.main)
