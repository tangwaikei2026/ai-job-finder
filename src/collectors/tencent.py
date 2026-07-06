from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.base import RawCollector
from src.models import (
    CollectionManifest,
    CollectionResult,
    RawJobPosting,
)


class TencentRawCollector(RawCollector):
    platform = "tencent"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 100)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "腾讯")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        seen_job_ids: set[str] = set()
        seen_page_ids: set[tuple[str, ...]] = set()
        detail_targets: list[RawJobPosting] = []
        page = 1

        try:
            while True:
                payload = self.request_json(
                    "GET",
                    str(cfg["list_api"]),
                    params={
                        "keyword": "",
                        "pageIndex": page,
                        "pageSize": page_size,
                        "language": "zh-cn",
                        "area": "",
                        "timestamp": "careers",
                    },
                )
                if payload.get("Code") != 200:
                    raise RuntimeError(
                        f"Tencent API returned Code={payload.get('Code')}"
                    )

                data = payload.get("Data") or {}
                posts = data.get("Posts") or []
                if page == 1:
                    manifest.source_total = int(data.get("Count") or 0)
                    manifest.expected_pages = math.ceil(
                        manifest.source_total / page_size
                    )

                if not posts:
                    manifest.stopped_by = "empty_page"
                    manifest.complete = (
                        manifest.records_fetched >= manifest.source_total
                    )
                    break

                page_ids = tuple(str(item.get("PostId", "")) for item in posts)
                if page_ids in seen_page_ids:
                    manifest.stopped_by = "repeated_page"
                    manifest.complete = False
                    break
                seen_page_ids.add(page_ids)
                manifest.pages_fetched += 1
                manifest.records_fetched += len(posts)

                for item in posts:
                    job = self._map_list_job(item)
                    if not job.job_id:
                        manifest.missing_job_id += 1
                        continue
                    if job.job_id in seen_job_ids:
                        manifest.duplicate_records += 1
                        continue
                    seen_job_ids.add(job.job_id)
                    manifest.jobs_mapped += 1
                    if not job.location:
                        manifest.unknown_location += 1
                    if not self.location_in_scope(job.location):
                        manifest.outside_city_scope += 1
                        continue
                    jobs_by_id[job.job_id] = job
                    detail_targets.append(job)

                if manifest.records_fetched >= manifest.source_total:
                    manifest.stopped_by = "source_total_reached"
                    manifest.complete = True
                    break
                page += 1

            if cfg.get("fetch_details", True) and cfg.get("detail_api"):
                workers = max(1, int(cfg.get("detail_workers", 4)))
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    future_map = {
                        executor.submit(self._fetch_detail, job): job
                        for job in detail_targets
                    }
                    for future in as_completed(future_map):
                        job = future_map[future]
                        try:
                            self._apply_detail(job, future.result())
                            manifest.details_fetched += 1
                        except Exception:
                            manifest.detail_failed += 1

            manifest.jobs_in_scope = len(jobs_by_id)
            manifest.complete = manifest.complete and manifest.detail_failed == 0
            manifest.status = "success" if manifest.complete else "partial"
            if manifest.detail_failed:
                manifest.stopped_by = "detail_errors"
        except Exception as exc:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = manifest.stopped_by or "error"
            manifest.error = str(exc)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _map_list_job(self, item: dict[str, Any]) -> RawJobPosting:
        job_id = str(item.get("PostId") or "")
        source_url = str(item.get("PostURL") or "")
        detail_url = str(self.platform_config.get("detail_url") or "")
        url = source_url or (
            detail_url.format(job_id=job_id) if detail_url and job_id else ""
        )
        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=str(item.get("RecruitPostName") or ""),
            company=str(item.get("ComName") or self.platform_config.get("name") or "腾讯"),
            department=str(item.get("BGName") or ""),
            location=str(item.get("LocationName") or ""),
            experience=str(item.get("RequireWorkYearsName") or ""),
            description=str(item.get("Responsibility") or ""),
            url=url,
        )

    def _fetch_detail(self, job: RawJobPosting) -> dict[str, Any]:
        payload = self.request_json(
            "GET",
            str(self.platform_config["detail_api"]),
            params={
                "timestamp": "careers",
                "postId": job.job_id,
                "language": "zh-cn",
            },
        )
        if payload.get("Code") != 200:
            raise RuntimeError(
                f"Tencent detail API failed for {job.job_id}: "
                f"Code={payload.get('Code')}"
            )
        data = payload.get("Data")
        if not isinstance(data, dict):
            raise RuntimeError(
                f"Tencent detail API returned no data for {job.job_id}"
            )
        return data

    @staticmethod
    def _apply_detail(
        job: RawJobPosting,
        detail: dict[str, Any],
    ) -> None:
        job.description = str(
            detail.get("Responsibility") or job.description
        )
        job.requirements = str(
            detail.get("Requirement") or job.requirements
        )
