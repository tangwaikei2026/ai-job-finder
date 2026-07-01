from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.raw.collectors import COLLECTOR_REGISTRY
from src.raw.models import CollectionManifest, RawJobPosting, write_json_atomic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("raw-job-collector")
logging.getLogger("httpx").setLevel(logging.WARNING)


def load_raw_config(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    config = loaded.get("raw_collection")
    if not isinstance(config, dict):
        raise ValueError("raw_config.yaml must contain a raw_collection mapping")
    if not isinstance(config.get("platforms"), dict):
        raise ValueError("raw_collection.platforms must be a mapping")
    return config


def collect_all(
    config: dict[str, Any],
    selected_platform: str | None = None,
) -> tuple[list[RawJobPosting], list[CollectionManifest]]:
    all_jobs: list[RawJobPosting] = []
    manifests: list[CollectionManifest] = []

    for platform, platform_config in config["platforms"].items():
        if selected_platform and platform != selected_platform:
            continue
        if not platform_config.get("enabled", False):
            continue
        collector_class = COLLECTOR_REGISTRY.get(platform)
        if collector_class is None:
            logger.warning("No raw collector registered for %s", platform)
            continue

        logger.info("Collecting unfiltered jobs from %s", platform)
        collector = collector_class(platform_config, config)
        try:
            result = collector.collect()
        finally:
            collector.close()
        all_jobs.extend(result.jobs)
        manifests.append(result.manifest)
        logger.info(
            "[%s] status=%s source=%d in_scope=%d pages=%d/%d",
            platform,
            result.manifest.status,
            result.manifest.source_total,
            result.manifest.jobs_in_scope,
            result.manifest.pages_fetched,
            result.manifest.expected_pages,
        )

    if selected_platform and not manifests:
        raise ValueError(f"platform is disabled, unknown, or unsupported: {selected_platform}")
    return all_jobs, manifests


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect unfiltered raw job listings")
    parser.add_argument("--config", default="raw_config.yaml")
    parser.add_argument("--platform", choices=sorted(COLLECTOR_REGISTRY))
    parser.add_argument("--date", help="Output date in YYYY-MM-DD format")
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Replace selected platform in an existing dated output",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_raw_config(config_path)

    output_date = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = Path(config.get("output_dir", "data/raw"))
    if not output_dir.is_absolute():
        output_dir = config_path.parent / output_dir

    jobs_path = output_dir / f"{output_date}.json"
    manifest_path = output_dir / f"{output_date}_manifest.json"
    jobs, manifests = collect_all(config, args.platform)

    if args.merge_existing:
        if not args.platform:
            raise ValueError("--merge-existing requires --platform")
        if not manifests or any(not item.complete for item in manifests):
            raise RuntimeError(
                "refusing to replace existing data with an incomplete platform run"
            )
        if not jobs_path.exists() or not manifest_path.exists():
            raise ValueError("--merge-existing requires existing dated output files")
        with open(jobs_path, encoding="utf-8") as f:
            existing_jobs = json.load(f)
        with open(manifest_path, encoding="utf-8") as f:
            existing_manifest = json.load(f)
        jobs = [
            RawJobPosting(**item)
            for item in existing_jobs
            if item.get("platform") != args.platform
        ] + jobs
        previous_manifests = [
            CollectionManifest(**item)
            for item in existing_manifest.get("platforms", [])
            if item.get("platform") != args.platform
        ]
        manifests = previous_manifests + manifests

    write_json_atomic(jobs_path, [job.to_dict() for job in jobs])
    write_json_atomic(
        manifest_path,
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": str(config_path),
            "cities": config.get("cities", []),
            "job_count": len(jobs),
            "complete": bool(manifests) and all(item.complete for item in manifests),
            "platforms": [item.to_dict() for item in manifests],
        },
    )

    logger.info("Wrote %d jobs to %s", len(jobs), jobs_path)
    logger.info("Wrote collection manifest to %s", manifest_path)
    if any(not item.complete for item in manifests):
        sys.exit(1)


if __name__ == "__main__":
    main()
