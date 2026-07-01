from __future__ import annotations

import math
import time
from typing import Any

from src.raw.base import RawCollector
from src.raw.models import CollectionManifest, CollectionResult, RawJobPosting
from src.raw.portal import bootstrap_portal, fetch_portal_page


class ByteDanceRawCollector(RawCollector):
    platform = "bytedance"

    def collect(self) -> CollectionResult:
        from playwright.sync_api import sync_playwright

        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 100)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "字节跳动")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 Chrome/126 Safari/537.36"
                    )
                )
                page = context.new_page()
                try:
                    bootstrap = bootstrap_portal(
                        page,
                        str(cfg["list_url"]),
                        filter_marker="/api/v1/config/job/filters/2",
                    )
                    city_codes = self._city_codes(bootstrap.filter_data)
                    for city in self.cities:
                        code = city_codes.get(self._city_token(city))
                        if not code:
                            raise RuntimeError(f"ByteDance city code not found: {city}")
                        self._collect_city(
                            page,
                            bootstrap,
                            code,
                            page_size,
                            jobs_by_id,
                            manifest,
                        )
                finally:
                    context.close()
                    browser.close()

            manifest.jobs_in_scope = len(jobs_by_id)
            manifest.complete = (
                manifest.pages_fetched >= manifest.expected_pages
                and manifest.records_fetched >= manifest.source_total
            )
            manifest.status = "success" if manifest.complete else "partial"
            manifest.stopped_by = (
                "all_city_totals_reached" if manifest.complete else "incomplete_city"
            )
        except Exception as exc:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = "error"
            manifest.error = str(exc)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _collect_city(
        self,
        page: Any,
        bootstrap: Any,
        city_code: str,
        page_size: int,
        jobs_by_id: dict[str, RawJobPosting],
        manifest: CollectionManifest,
    ) -> None:
        offset = 0
        city_total = 0
        city_fetched = 0
        seen_pages: set[tuple[str, ...]] = set()

        while True:
            payload = fetch_portal_page(
                page,
                bootstrap,
                offset=offset,
                limit=page_size,
                body_updates={"location_code_list": [city_code]},
            )
            data = payload.get("data") or {}
            records = data.get("job_post_list") or []
            if offset == 0:
                city_total = int(data.get("count") or 0)
                manifest.source_total += city_total
                manifest.expected_pages += math.ceil(city_total / page_size)
            if not records:
                if city_fetched < city_total:
                    raise RuntimeError(
                        f"empty ByteDance city page after "
                        f"{city_fetched}/{city_total} records"
                    )
                break

            page_ids = tuple(str(item.get("id") or "") for item in records)
            if page_ids in seen_pages:
                raise RuntimeError("repeated ByteDance city page")
            seen_pages.add(page_ids)
            manifest.pages_fetched += 1
            manifest.records_fetched += len(records)
            city_fetched += len(records)

            for item in records:
                job = self._map_job(item)
                if not job.job_id:
                    manifest.missing_job_id += 1
                    continue
                if job.job_id in jobs_by_id:
                    manifest.duplicate_records += 1
                    continue
                manifest.jobs_mapped += 1
                if not job.location:
                    manifest.unknown_location += 1
                if not self.location_in_scope(job.location):
                    manifest.outside_city_scope += 1
                    continue
                jobs_by_id[job.job_id] = job

            if city_fetched >= city_total:
                break
            offset += len(records)

    def _map_job(self, item: dict[str, Any]) -> RawJobPosting:
        job_id = str(item.get("id") or "")
        city_info = item.get("city_info") or {}
        city_list = item.get("city_list") or []
        location = str(city_info.get("name") or "")
        if not location and isinstance(city_list, list):
            location = ", ".join(
                str(city.get("name") or "")
                for city in city_list
                if isinstance(city, dict) and city.get("name")
            )

        category = item.get("job_category") or {}
        parent = category.get("parent") or {}
        department_parts = [
            str(parent.get("name") or ""),
            str(category.get("name") or ""),
        ]
        department = " - ".join(part for part in department_parts if part)
        detail_url = str(self.platform_config.get("detail_url") or "")
        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=str(item.get("title") or ""),
            company=str(self.platform_config.get("name") or "字节跳动"),
            department=department,
            location=location,
            description=str(item.get("description") or ""),
            requirements=str(item.get("requirement") or ""),
            url=detail_url.format(job_id=job_id) if detail_url and job_id else "",
        )

    @staticmethod
    def _city_codes(filter_data: dict[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        for city in filter_data.get("city_list") or []:
            if not isinstance(city, dict):
                continue
            name = str(city.get("name") or "").removesuffix("市")
            code = str(city.get("code") or "")
            if name and code:
                result[name] = code
        return result
