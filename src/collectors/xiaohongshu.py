from __future__ import annotations

import math
import time
from typing import Any

from src.base import RawCollector
from src.models import CollectionManifest, CollectionResult, RawJobPosting


class XiaohongshuRawCollector(RawCollector):
    platform = "xiaohongshu"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 50)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "小红书")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        seen_job_ids: set[str] = set()
        seen_page_ids: set[tuple[str, ...]] = set()
        page = 1

        try:
            while True:
                payload = self.request_json(
                    "POST",
                    str(cfg["list_api"]),
                    json={
                        "pageNum": page,
                        "pageSize": page_size,
                        "recruitType": "social",
                        "positionName": "",
                        "jobTypes": [],
                        "workplaces": [],
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Referer": str(cfg["list_url"]),
                        "Origin": "https://job.xiaohongshu.com",
                    },
                )
                if payload.get("statusCode") != 200:
                    raise RuntimeError(
                        "Xiaohongshu API returned "
                        f"statusCode={payload.get('statusCode')}: "
                        f"{payload.get('alertMsg', '')}"
                    )

                data = payload.get("data") or {}
                records = data.get("list") or []
                manifest.source_total = int(data.get("total") or 0)
                manifest.expected_pages = int(
                    data.get("totalPage")
                    or math.ceil(manifest.source_total / page_size)
                )

                if not records:
                    manifest.stopped_by = "empty_page"
                    manifest.complete = (
                        manifest.records_fetched >= manifest.source_total
                    )
                    break

                page_ids = tuple(
                    str(item.get("positionId") or "") for item in records
                )
                if page_ids in seen_page_ids:
                    manifest.stopped_by = "repeated_page"
                    manifest.complete = False
                    break
                seen_page_ids.add(page_ids)
                manifest.pages_fetched += 1
                manifest.records_fetched += len(records)

                for item in records:
                    job = self._map_job(item)
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

                if (
                    manifest.records_fetched >= manifest.source_total
                    or page >= manifest.expected_pages
                ):
                    manifest.stopped_by = "source_total_reached"
                    manifest.complete = (
                        manifest.records_fetched >= manifest.source_total
                    )
                    break
                page += 1

            manifest.jobs_in_scope = len(jobs_by_id)
            manifest.status = "success" if manifest.complete else "partial"
        except Exception as exc:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = "error"
            manifest.error = str(exc)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _map_job(self, item: dict[str, Any]) -> RawJobPosting:
        job_id = str(item.get("positionId") or "")
        detail_url = str(self.platform_config.get("detail_url") or "")
        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=str(item.get("positionName") or ""),
            company=str(self.platform_config.get("name") or "小红书"),
            department=str(item.get("jobType") or ""),
            location=str(item.get("workplace") or ""),
            description=str(item.get("duty") or ""),
            requirements=str(item.get("qualification") or ""),
            url=(
                detail_url.format(job_id=job_id)
                if detail_url and job_id
                else ""
            ),
        )
