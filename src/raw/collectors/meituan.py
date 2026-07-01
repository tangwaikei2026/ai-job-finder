from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.raw.base import RawCollector
from src.raw.models import CollectionManifest, CollectionResult, RawJobPosting


class MeituanRawCollector(RawCollector):
    platform = "meituan"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 50)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "美团")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        seen_job_ids: set[str] = set()
        seen_page_ids: set[tuple[str, ...]] = set()
        detail_targets: list[tuple[dict[str, Any], RawJobPosting]] = []
        page = 1

        try:
            while True:
                payload = self.request_json(
                    "POST",
                    str(cfg["list_api"]),
                    json={
                        "page": {"pageNo": page, "pageSize": page_size},
                        "jobShareType": "1",
                        "keywords": "",
                        "cityList": [],
                        "department": [],
                        "jfJgList": [],
                        "jobType": [{"code": "3", "subCode": []}],
                        "typeCode": [],
                        "specialCode": [],
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Referer": str(cfg["list_url"]),
                        "Origin": "https://zhaopin.meituan.com",
                    },
                )
                if payload.get("status") != 1:
                    raise RuntimeError(
                        "Meituan list API returned "
                        f"status={payload.get('status')}: {payload.get('message', '')}"
                    )

                data = payload.get("data") or {}
                records = data.get("list") or []
                page_data = data.get("page") or {}
                manifest.source_total = int(page_data.get("totalCount") or 0)
                manifest.expected_pages = int(
                    page_data.get("totalPage")
                    or math.ceil(manifest.source_total / page_size)
                )

                if not records:
                    manifest.stopped_by = "empty_page"
                    manifest.complete = (
                        manifest.records_fetched >= manifest.source_total
                    )
                    break

                page_ids = tuple(
                    str(item.get("jobUnionId") or "") for item in records
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
                    detail_targets.append((item, job))

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

            workers = max(1, int(cfg.get("detail_workers", 4)))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(self._fetch_detail, item): job
                    for item, job in detail_targets
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
            manifest.stopped_by = "error"
            manifest.error = str(exc)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _map_job(self, item: dict[str, Any]) -> RawJobPosting:
        job_id = str(item.get("jobUnionId") or "")
        detail_url = str(self.platform_config.get("detail_url") or "")
        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=str(item.get("name") or ""),
            company=str(self.platform_config.get("name") or "美团"),
            department=self._names(item.get("department")),
            location=self._names(item.get("cityList")),
            experience=str(item.get("workYear") or ""),
            description=self._description(item),
            requirements=str(item.get("jobRequirement") or ""),
            url=detail_url.format(job_id=job_id) if detail_url and job_id else "",
        )

    def _fetch_detail(self, item: dict[str, Any]) -> dict[str, Any]:
        job_id = str(item.get("jobUnionId") or "")
        payload = self.request_json(
            "POST",
            str(self.platform_config["detail_api"]),
            json={"jobUnionId": job_id, "jobShareType": "1"},
            headers={
                "Content-Type": "application/json",
                "Referer": str(self.platform_config["list_url"]),
                "Origin": "https://zhaopin.meituan.com",
            },
        )
        if payload.get("status") != 1:
            raise RuntimeError(
                f"Meituan detail API failed for {job_id}: "
                f"{payload.get('message', '')}"
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"Meituan detail API returned no data for {job_id}")
        return data

    def _apply_detail(
        self,
        job: RawJobPosting,
        detail: dict[str, Any],
    ) -> None:
        job.title = str(detail.get("name") or job.title)
        job.department = self._names(detail.get("department")) or job.department
        job.location = self._names(detail.get("cityList")) or job.location
        job.experience = str(detail.get("workYear") or job.experience)
        job.description = self._description(detail) or job.description
        job.requirements = str(
            detail.get("jobRequirement") or job.requirements
        )

    @staticmethod
    def _names(value: Any) -> str:
        if not isinstance(value, list):
            return str(value or "")
        return ",".join(
            str(item.get("name") or "")
            for item in value
            if isinstance(item, dict) and item.get("name")
        )

    @staticmethod
    def _description(item: dict[str, Any]) -> str:
        duty = str(item.get("jobDuty") or "")
        highlight = str(item.get("highLight") or "")
        if duty and highlight:
            return f"{duty}\n岗位亮点\n{highlight}"
        return duty or highlight
