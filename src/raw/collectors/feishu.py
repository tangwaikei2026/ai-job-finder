from __future__ import annotations

import math
import time
from typing import Any

from src.raw.base import RawCollector
from src.raw.models import CollectionManifest, CollectionResult, RawJobPosting
from src.raw.portal import bootstrap_portal, fetch_portal_page


class FeishuRawCollector(RawCollector):
    platform = "feishu"

    def collect(self) -> CollectionResult:
        from playwright.sync_api import sync_playwright

        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 50)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "飞书招聘")),
        )
        jobs_by_key: dict[str, RawJobPosting] = {}
        company_errors: list[str] = []

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    for company in cfg.get("companies", []):
                        context = browser.new_context(
                            user_agent=(
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 Chrome/126 Safari/537.36"
                            )
                        )
                        page = context.new_page()
                        try:
                            self._collect_company(
                                page,
                                company,
                                page_size,
                                jobs_by_key,
                                manifest,
                            )
                        except Exception as exc:
                            company_errors.append(
                                f"{company.get('name', 'unknown')}: {exc}"
                            )
                        finally:
                            context.close()
                finally:
                    browser.close()

            manifest.jobs_in_scope = len(jobs_by_key)
            manifest.complete = not company_errors
            manifest.status = "success" if manifest.complete else "partial"
            manifest.stopped_by = (
                "all_companies_complete" if manifest.complete else "company_error"
            )
            manifest.error = "; ".join(company_errors)
        except Exception as exc:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = "error"
            manifest.error = str(exc)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_key.values()), manifest)

    def _collect_company(
        self,
        page: Any,
        company: dict[str, Any],
        page_size: int,
        jobs_by_key: dict[str, RawJobPosting],
        manifest: CollectionManifest,
    ) -> None:
        bootstrap = bootstrap_portal(page, str(company["list_url"]))
        offset = 0
        company_total = 0
        company_fetched = 0
        seen_pages: set[tuple[str, ...]] = set()

        while True:
            payload = fetch_portal_page(
                page,
                bootstrap,
                offset=offset,
                limit=page_size,
            )
            data = payload.get("data") or {}
            records = data.get("job_post_list") or []
            if offset == 0:
                company_total = int(data.get("count") or 0)
                manifest.source_total += company_total
                manifest.expected_pages += math.ceil(company_total / page_size)
            if not records:
                if company_fetched < company_total:
                    raise RuntimeError(
                        f"empty page after {company_fetched}/{company_total} records"
                    )
                break

            page_ids = tuple(str(item.get("id") or "") for item in records)
            if page_ids in seen_pages:
                raise RuntimeError("repeated page")
            seen_pages.add(page_ids)
            manifest.pages_fetched += 1
            manifest.records_fetched += len(records)
            company_fetched += len(records)

            for item in records:
                job = self._map_job(item, company)
                if not job.job_id:
                    manifest.missing_job_id += 1
                    continue
                key = f"{company.get('name', '')}:{job.job_id}"
                if key in jobs_by_key:
                    manifest.duplicate_records += 1
                    continue
                manifest.jobs_mapped += 1
                if not job.location:
                    manifest.unknown_location += 1
                if not self.location_in_scope(job.location):
                    manifest.outside_city_scope += 1
                    continue
                jobs_by_key[key] = job

            if company_fetched >= company_total:
                break
            offset += len(records)

    def _map_job(
        self,
        item: dict[str, Any],
        company: dict[str, Any],
    ) -> RawJobPosting:
        job_id = str(item.get("id") or "")
        city_list = item.get("city_list") or []
        location = ", ".join(
            str(city.get("name") or "")
            for city in city_list
            if isinstance(city, dict) and city.get("name")
        )
        detail_url = str(company.get("detail_url") or "")
        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=str(item.get("title") or "").strip(),
            company=str(company.get("name") or ""),
            location=location,
            description=str(item.get("description") or ""),
            requirements=str(item.get("requirement") or ""),
            url=detail_url.format(job_id=job_id) if detail_url and job_id else "",
        )
