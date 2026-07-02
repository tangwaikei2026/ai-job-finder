from __future__ import annotations

import time

from src.raw.base import RawCollector
from src.raw.models import CollectionManifest, CollectionResult


class JDRawCollector(RawCollector):
    """Raw collector for JD's official social-recruitment site.

    This first-stage skeleton only establishes the raw collector contract.
    List requests, parsing, pagination, mapping, and JD-specific city handling
    will be added in the next implementation step.
    """

    platform = "jd"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(self.platform_config.get("name", "京东")),
            status="partial",
            complete=False,
            stopped_by="not_implemented",
            error="JD raw list collection is not implemented yet",
        )
        self.finish_manifest(manifest, started)
        return CollectionResult(jobs=[], manifest=manifest)
