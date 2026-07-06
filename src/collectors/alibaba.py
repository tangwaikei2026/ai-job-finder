from __future__ import annotations

import math
import time
from typing import Any

import httpx

from src.base import RawCollector
from src.models import CollectionManifest, CollectionResult, RawJobPosting


DEGREE_MAP = {
    "bachelor": "本科",
    "master": "硕士",
    "doctor": "博士",
    "phd": "博士",
    "college": "大专",
    "high_school": "高中",
}


class AlibabaBaseCollector(RawCollector):
    """Shared list collector for Alibaba recruitment portals."""

    platform = "alibaba"
    DEGREE_MAP = DEGREE_MAP

    def __init__(
        self,
        platform_config: dict[str, Any],
        collection_config: dict[str, Any],
        client: httpx.Client | None = None,
    ):
        super().__init__(platform_config, collection_config, client)
        self.platform = str(platform_config.get("platform_key") or self.platform)

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 50)))
        platform_key = self._platform_key()
        manifest = CollectionManifest(
            platform=platform_key,
            name=str(cfg.get("name") or "阿里巴巴"),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        seen_job_ids: set[str] = set()
        seen_page_ids: set[tuple[str, ...]] = set()
        page = 1

        try:
            self.request("GET", str(cfg["list_url"]))
            csrf_token = self.client.cookies.get("XSRF-TOKEN")
            if not csrf_token:
                raise RuntimeError(
                    f"{platform_key} list page did not set XSRF-TOKEN"
                )

            while True:
                payload = self.request_json(
                    "POST",
                    str(cfg["list_api"]),
                    json=self._build_payload(page, page_size),
                    headers={
                        "Content-Type": "application/json",
                        "Referer": str(cfg["list_url"]),
                        "X-XSRF-TOKEN": csrf_token,
                    },
                )
                if payload.get("success") is not True:
                    raise RuntimeError(
                        f"{platform_key} API failed: "
                        f"{payload.get('errorCode')} "
                        f"{payload.get('errorMsg', '')}"
                    )

                records, total_count = self._extract_records(payload)
                if page == 1:
                    manifest.source_total = total_count
                    manifest.expected_pages = math.ceil(
                        manifest.source_total / page_size
                    )

                if not records:
                    manifest.stopped_by = "empty_page"
                    manifest.complete = (
                        manifest.records_fetched >= manifest.source_total
                    )
                    break

                page_ids = tuple(str(item.get("id") or "") for item in records)
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

                if manifest.records_fetched >= manifest.source_total:
                    manifest.stopped_by = "source_total_reached"
                    manifest.complete = True
                    break
                page += 1

            manifest.jobs_in_scope = len(jobs_by_id)
            manifest.status = "success" if manifest.complete else "partial"
        except Exception as exc:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = manifest.stopped_by or "error"
            manifest.error = str(exc)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _build_payload(self, page: int, page_size: int) -> dict[str, Any]:
        return {
            "channel": "group_official_site",
            "language": "zh",
            "batchId": "",
            "categories": "",
            "deptCodes": [],
            "key": "",
            "pageIndex": page,
            "pageSize": page_size,
            "regions": "",
            "subCategories": "",
            "shareType": "",
            "shareId": "",
            "myReferralShareCode": "",
        }

    def _extract_records(
        self,
        payload: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], int]:
        content = payload.get("content")
        if content is None:
            content = {}
        if not isinstance(content, dict):
            raise ValueError("Alibaba API content must be an object")
        records = content.get("datas")
        if records is None:
            records = []
        if not isinstance(records, list) or not all(
            isinstance(item, dict) for item in records
        ):
            raise ValueError("Alibaba API content.datas must be a list of objects")
        return records, int(content.get("totalCount") or 0)

    def _map_job(self, item: dict[str, Any]) -> RawJobPosting:
        job_id = str(item.get("id") or "")
        locations = item.get("workLocations") or []
        if isinstance(locations, list):
            location = ", ".join(str(place) for place in locations if place)
        else:
            location = str(locations)

        detail_url = str(self.platform_config.get("detail_url") or "")
        url = detail_url.format(job_id=job_id) if detail_url and job_id else ""
        return RawJobPosting(
            job_id=job_id,
            platform=self._platform_key(),
            title=str(item.get("name") or ""),
            company=str(self.platform_config.get("name") or "阿里巴巴"),
            department=str(
                item.get("department") or item.get("departmentName") or ""
            ),
            location=location,
            experience=self._format_experience(item.get("experience")),
            education=self._format_degree(item.get("degree")),
            salary="",
            description=str(item.get("description") or ""),
            requirements=str(item.get("requirement") or ""),
            url=url,
        )

    def _platform_key(self) -> str:
        return str(self.platform_config.get("platform_key") or self.platform)

    @staticmethod
    def _format_experience(value: Any) -> str:
        if not value or value == "None":
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            lower = value.get("from")
            upper = value.get("to")
            if lower and upper:
                return f"{lower}-{upper}年"
            if lower:
                return f"{lower}年以上"
        return str(value)

    @staticmethod
    def _format_degree(value: Any) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            return DEGREE_MAP.get(value.lower(), value)
        return str(value)
