from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.base import RawCollector
from src.models import CollectionManifest, CollectionResult, RawJobPosting


class DidiRawCollector(RawCollector):
    platform = "didi"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 16)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "滴滴")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        detail_targets: list[tuple[dict[str, Any], RawJobPosting]] = []

        try:
            self.request("GET", str(cfg["list_url"]))
            page = 1
            while True:
                payload = self.request_json(
                    "GET",
                    str(cfg["list_api"]),
                    params={"page": page, "recruitType": 1, "size": page_size},
                    headers={"Referer": str(cfg["list_url"])},
                )
                if (payload.get("meta") or {}).get("code") != 0:
                    raise RuntimeError(
                        f"Didi list API failed: {(payload.get('meta') or {}).get('message')}"
                    )
                data = payload.get("data") or {}
                records = data.get("items") or []
                # This is a live list and its total can change while the run is
                # paging. Use the latest value instead of freezing page 1.
                manifest.source_total = int(data.get("total") or 0)
                manifest.expected_pages = math.ceil(
                    manifest.source_total / page_size
                )
                if not records:
                    break

                manifest.pages_fetched += 1
                manifest.records_fetched += len(records)
                for item in records:
                    basic_job = self._map_list_job(item)
                    if not basic_job.job_id:
                        manifest.missing_job_id += 1
                        continue
                    if basic_job.job_id in jobs_by_id:
                        manifest.duplicate_records += 1
                        continue
                    manifest.jobs_mapped += 1
                    if not basic_job.location:
                        manifest.unknown_location += 1
                    if not self.location_in_scope(basic_job.location):
                        manifest.outside_city_scope += 1
                        continue
                    jobs_by_id[basic_job.job_id] = basic_job
                    detail_targets.append((item, basic_job))

                if manifest.records_fetched >= manifest.source_total:
                    break
                page += 1

            workers = max(1, int(cfg.get("detail_workers", 4)))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(self._fetch_detail, item): job
                    for item, job in detail_targets
                }
                for future in as_completed(future_map):
                    job = future_map[future]
                    try:
                        detail = future.result()
                        self._apply_detail(job, detail)
                        manifest.details_fetched += 1
                    except Exception:
                        manifest.detail_failed += 1
                        manifest.detail_failed_job_ids.append(job.job_id)

            manifest.jobs_in_scope = len(jobs_by_id)
            list_complete = (
                manifest.records_fetched >= manifest.source_total
                and manifest.pages_fetched >= manifest.expected_pages
            )
            manifest.complete = list_complete and manifest.detail_failed == 0
            manifest.status = "success" if manifest.complete else "partial"
            manifest.stopped_by = (
                "source_total_reached"
                if manifest.complete
                else "detail_errors" if manifest.detail_failed else "incomplete_list"
            )
        except Exception as exc:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = "error"
            manifest.error = str(exc)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _map_list_job(self, item: dict[str, Any]) -> RawJobPosting:
        source_job_id = str(item.get("jdId") or "")
        job_id = str(item.get("jdNo") or source_job_id)
        detail_url = str(self.platform_config.get("detail_url") or "")
        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=str(item.get("jobName") or ""),
            company=str(self.platform_config.get("name") or "滴滴"),
            department=str(item.get("deptName") or ""),
            location=str(item.get("workArea") or ""),
            url=(
                detail_url.format(job_id=source_job_id)
                if detail_url and source_job_id
                else ""
            ),
        )

    def _fetch_detail(self, item: dict[str, Any]) -> dict[str, Any]:
        job_id = str(item.get("jdId") or "")
        detail_api = str(self.platform_config["detail_api"]).format(
            job_id=job_id
        )
        payload = self.request_json(
            "GET",
            detail_api,
            headers={"Referer": str(self.platform_config["list_url"])},
        )
        if (payload.get("meta") or {}).get("code") != 0:
            raise RuntimeError(
                f"Didi detail API failed for {job_id}: "
                f"{(payload.get('meta') or {}).get('message')}"
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"Didi detail API returned no data for {job_id}")
        return data

    @staticmethod
    def _apply_detail(job: RawJobPosting, detail: dict[str, Any]) -> None:
        job.title = str(detail.get("jobName") or job.title)
        job.department = str(detail.get("deptName") or job.department)
        job.location = str(detail.get("workArea") or job.location)
        job.description = str(detail.get("jobDesc") or "")
        job.requirements = str(detail.get("qualification") or "")
