from __future__ import annotations

import json
import subprocess
import sys


def test_src_main_imports() -> None:
    import src.main

    assert src.main is not None


def test_src_main_exposes_raw_main() -> None:
    import src.main
    import src.raw.main

    assert src.main.main is src.raw.main.main


def test_importing_src_main_does_not_import_old_components() -> None:
    script = """
import json
import sys

import src.main

old_components = {"scrapers", "pipeline", "db", "report", "notifiers"}
loaded = sorted(
    name
    for name in sys.modules
    if len(name.split(".")) > 1
    and name.split(".")[0] == "src"
    and name.split(".")[1] in old_components
)
print(json.dumps(loaded))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == []
