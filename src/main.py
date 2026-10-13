from __future__ import annotations

import argparse
import json
import hashlib
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.invocation import digest, read, validate_context, validate_raw
from src.collectors import COLLECTOR_REGISTRY
from src.models import (
    CollectionManifest,
    CollectionResult,
    RawJobPosting,
    write_json_atomic,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("raw-job-collector")
logging.getLogger("httpx").setLevel(logging.WARNING)


def load_config(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    if not isinstance(loaded, dict):
        raise ValueError("config.yaml must contain a mapping")
    if "raw_collection" in loaded:
        raise ValueError(
            "config.yaml no longer accepts the legacy raw_collection wrapper"
        )
    if not isinstance(loaded.get("platforms"), dict):
        raise ValueError("config.yaml platforms must be a mapping")
    return loaded


def _error_manifest(
    platform: str,
    platform_config: dict[str, Any],
    error: str,
    *,
    stopped_by: str = "error",
) -> CollectionManifest:
    return CollectionManifest(
        platform=platform,
        name=str(platform_config.get("name") or platform),
        status="error",
        complete=False,
        stopped_by=stopped_by,
        error=error,
        finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


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
            error = f"No raw collector registered for {platform}"
            logger.error(error)
            manifests.append(
                _error_manifest(
                    platform,
                    platform_config,
                    error,
                    stopped_by="unregistered",
                )
            )
            continue

        logger.info("Collecting unfiltered jobs from %s", platform)
        collector = None
        result: CollectionResult | None = None
        try:
            collector = collector_class(platform_config, config)
            result = collector.collect()
        except Exception as exc:
            logger.exception("[%s] raw collector failed", platform)
            result = CollectionResult(
                jobs=[],
                manifest=_error_manifest(platform, platform_config, str(exc)),
            )
        finally:
            if collector is not None:
                try:
                    collector.close()
                except Exception as exc:
                    logger.exception("[%s] raw collector close failed", platform)
                    if result is None:
                        result = CollectionResult(
                            jobs=[],
                            manifest=_error_manifest(
                                platform,
                                platform_config,
                                str(exc),
                                stopped_by="close_error",
                            ),
                        )
                    else:
                        result.manifest.complete = False
                        result.manifest.status = (
                            "partial" if result.jobs else "error"
                        )
                        result.manifest.stopped_by = "close_error"
                        result.manifest.error = "; ".join(
                            part
                            for part in (result.manifest.error, str(exc))
                            if part
                        )
        assert result is not None
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
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--invocation-id")
    parser.add_argument("--started-at")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--platform", choices=sorted(COLLECTOR_REGISTRY))
    parser.add_argument("--date", help="Output date in YYYY-MM-DD format")
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Replace selected platform in an existing dated output",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    config_fingerprint = hashlib.sha256(config_path.read_bytes()).hexdigest()

    output_date = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = args.output_dir or Path(config.get("output_dir", "data/raw"))
    if not output_dir.is_absolute():
        output_dir = config_path.parent / output_dir

    jobs_path = output_dir / f"{output_date}.json"
    manifest_path = output_dir / f"{output_date}_manifest.json"
    context = None
    if args.invocation_id or args.started_at:
        context = dict(id=args.invocation_id, run_date=output_date, started_at=args.started_at)
        validate_context(context, output_date, args.invocation_id)
        if args.merge_existing:
            previous = read(manifest_path)
            validate_raw(output_date, previous, read(jobs_path), args.invocation_id, config_path)
            if previous['invocation'] != context:
                raise ValueError('INVOCATION_CONTEXT_MISMATCH')
    jobs, manifests = collect_all(config, args.platform)

    if args.merge_existing:
        if not args.platform:
            raise ValueError("--merge-existing requires --platform")
        incomplete_manifests = [item for item in manifests if not item.complete]
        if not manifests or incomplete_manifests:
            retry_errors = "; ".join(
                f"{item.platform}: {item.error or item.stopped_by or item.status}"
                for item in incomplete_manifests
            )
            detail = f": {retry_errors}" if retry_errors else ""
            raise RuntimeError(
                "refusing to replace existing data with an incomplete platform run"
                f"{detail}"
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

    all_failed = not manifests or all(
        item.status == "error"
        for item in manifests
    )
    if (
        not args.merge_existing
        and all_failed
        and (jobs_path.exists() or manifest_path.exists())
    ):
        raise RuntimeError(
            "refusing to overwrite existing raw output after total failure"
        )

    raw_rows = [job.to_dict() for job in jobs]
    provenance = ({'date': output_date, 'invocation': context,
                   'raw_sha256': digest(raw_rows),
                   'config_sha256': config_fingerprint}
                  if context is not None else {})
    write_json_atomic(jobs_path, raw_rows)
    write_json_atomic(
        manifest_path,
        {
            **provenance,
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
    if all_failed or any(not item.complete for item in manifests):
        sys.exit(1)


if __name__ == "__main__":
    main()
