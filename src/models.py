from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class RawJobPosting:
    job_id: str
    platform: str
    title: str
    company: str
    department: str = ""
    location: str = ""
    experience: str = ""
    education: str = ""
    salary: str = ""
    description: str = ""
    requirements: str = ""
    url: str = ""
    scraped_at: str = field(default_factory=_now)

    @property
    def unique_key(self) -> str:
        return f"{self.platform}:{self.job_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionManifest:
    platform: str
    name: str
    status: str = "pending"
    complete: bool = False
    source_total: int = 0
    expected_pages: int = 0
    pages_fetched: int = 0
    records_fetched: int = 0
    jobs_mapped: int = 0
    jobs_in_scope: int = 0
    outside_city_scope: int = 0
    unknown_location: int = 0
    duplicate_records: int = 0
    missing_job_id: int = 0
    details_fetched: int = 0
    detail_failed: int = 0
    failed_companies: list[str] = field(default_factory=list)
    attempted_companies: list[str] = field(default_factory=list)
    detail_failed_job_ids: list[str] = field(default_factory=list)
    stopped_by: str = ""
    error: str = ""
    started_at: str = field(default_factory=_now)
    finished_at: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionResult:
    jobs: list[RawJobPosting]
    manifest: CollectionManifest


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)
