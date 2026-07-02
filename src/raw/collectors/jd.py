from __future__ import annotations

import html
import math
import re
import time
from collections.abc import Iterable
from typing import Any

from src.raw.base import RawCollector
from src.raw.models import CollectionManifest, CollectionResult, RawJobPosting


# JD exposes province-level locations for Guangdong and Zhejiang. These are the
# only province-to-city expansions approved for the configured collection scope.
PROVINCE_CITY_SCOPE = {
    "广东": {"广州", "深圳"},
    "浙江": {"杭州"},
}


class JDRawCollector(RawCollector):
    """Raw collector for JD's official social-recruitment site."""

    platform = "jd"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, min(int(cfg.get("page_size", 100)), 100))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "京东")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        seen_job_ids: set[str] = set()
        seen_page_ids: set[tuple[str, ...]] = set()
        list_complete = False

        try:
            manifest.source_total = self._fetch_count()
            manifest.expected_pages = math.ceil(
                manifest.source_total / page_size
            )
            page = 1

            while manifest.records_fetched < manifest.source_total:
                records = self._fetch_page(page, page_size)
                if not records:
                    manifest.stopped_by = "empty_page"
                    list_complete = (
                        manifest.records_fetched >= manifest.source_total
                    )
                    break

                page_ids = tuple(
                    self._text(item.get("requirementId")) for item in records
                )
                if page_ids in seen_page_ids:
                    manifest.stopped_by = "repeated_page"
                    break
                seen_page_ids.add(page_ids)

                manifest.pages_fetched += 1
                manifest.records_fetched += len(records)
                for item in records:
                    job_id = self._text(item.get("requirementId"))
                    if not job_id:
                        manifest.missing_job_id += 1
                        continue
                    if job_id in seen_job_ids:
                        manifest.duplicate_records += 1
                        continue
                    seen_job_ids.add(job_id)

                    manifest.jobs_mapped += 1
                    source_location = self._text(item.get("workCity"))
                    if not source_location:
                        manifest.unknown_location += 1
                    if not self.location_in_scope(source_location):
                        manifest.outside_city_scope += 1
                        continue
                    jobs_by_id[job_id] = self._map_job(item)

                if manifest.records_fetched >= manifest.source_total:
                    list_complete = True
                    manifest.stopped_by = "source_total_reached"
                    break
                page += 1

            if manifest.source_total == 0:
                list_complete = True
                manifest.stopped_by = "source_total_reached"

            if bool(cfg.get("fetch_details", False)):
                self._enrich_details(jobs_by_id.values(), manifest)

            for job in jobs_by_id.values():
                self._apply_fallbacks(job)

            manifest.jobs_in_scope = len(jobs_by_id)
            manifest.complete = list_complete and manifest.detail_failed == 0
            manifest.status = "success" if manifest.complete else "partial"
            if manifest.detail_failed:
                manifest.stopped_by = "detail_errors"
        except Exception as exc:
            manifest.jobs_in_scope = len(jobs_by_id)
            manifest.complete = False
            manifest.status = "partial" if manifest.pages_fetched else "error"
            manifest.stopped_by = "error"
            manifest.error = str(exc)
            for job in jobs_by_id.values():
                self._apply_fallbacks(job)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _fetch_count(self) -> int:
        response = self.request(
            "POST",
            str(self.platform_config["count_api"]),
            data=self._list_form(),
            headers=self._request_headers(),
        )
        try:
            count = int(response.text.strip())
        except ValueError as exc:
            raise ValueError("JD count API returned a non-integer response") from exc
        if count < 0:
            raise ValueError("JD count API returned a negative total")
        return count

    def _fetch_page(
        self,
        page: int,
        page_size: int,
    ) -> list[dict[str, Any]]:
        response = self.request(
            "POST",
            str(self.platform_config["list_api"]),
            data=self._list_form(page=page, page_size=page_size),
            headers=self._request_headers(),
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("JD list API returned invalid JSON") from exc
        if not isinstance(payload, list):
            raise ValueError(
                f"JD list API expected an array, got {type(payload).__name__}"
            )
        if any(not isinstance(item, dict) for item in payload):
            raise ValueError("JD list API array contains a non-object record")
        return payload

    def _map_job(self, item: dict[str, Any]) -> RawJobPosting:
        job_id = self._text(item.get("requirementId"))
        detail_url = str(self.platform_config.get("detail_url") or "")
        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=(
                self._text(item.get("positionNameOpen"))
                or self._text(item.get("positionName"))
            ),
            company=str(self.platform_config.get("name") or "京东"),
            department=(
                self._text(item.get("positionDeptName"))
                or self._text(item.get("jobType"))
            ),
            location=self._text(item.get("workCity")),
            description=self._text(item.get("workContent")),
            requirements=self._text(item.get("qualification")),
            url=(
                detail_url.format(job_id=job_id)
                if detail_url and job_id
                else ""
            ),
        )

    def location_in_scope(self, location: str) -> bool:
        """Apply shared city matching plus JD's approved province mappings."""
        if super().location_in_scope(location):
            return True
        province = location.strip().removesuffix("省")
        mapped_cities = PROVINCE_CITY_SCOPE.get(province)
        if not mapped_cities:
            return False
        configured_cities = {
            self._city_token(city) for city in self.cities
        }
        return bool(mapped_cities & configured_cities)

    def _enrich_details(
        self,
        jobs: Iterable[RawJobPosting],
        manifest: CollectionManifest,
    ) -> None:
        # Detail enrichment is optional because the list API normally includes
        # both JD sections. Failures preserve the list record.
        for job in jobs:
            try:
                response = self.request(
                    "GET",
                    job.url,
                    headers={"Referer": str(self.platform_config["list_url"])},
                )
                detail = self._parse_detail(response.text)
                if not detail:
                    raise ValueError(
                        f"JD detail page returned no JD sections for {job.job_id}"
                    )
                job.description = detail.get("description") or job.description
                job.requirements = detail.get("requirements") or job.requirements
                manifest.details_fetched += 1
            except Exception:
                manifest.detail_failed += 1

    @classmethod
    def _parse_detail(cls, source: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        for heading, field_name in (
            ("岗位描述", "description"),
            ("任职要求", "requirements"),
        ):
            match = re.search(
                rf"<h2[^>]*>\s*{heading}\s*</h2>\s*"
                r"<div[^>]*class=[\"'][^\"']*\bpart\b[^\"']*[\"'][^>]*>"
                r"(.*?)</div>",
                source,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match:
                text = re.sub(r"<br\s*/?>", "\n", match.group(1), flags=re.I)
                text = re.sub(r"<[^>]+>", "", text)
                text = html.unescape(text).strip()
                if text:
                    sections[field_name] = text
        return sections

    @staticmethod
    def _list_form(
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        form: dict[str, Any] = {
            "workCityJson": "[]",
            "jobTypeJson": "[]",
            "jobSearch": "",
            "depTypeJson": "[]",
        }
        if page is not None:
            form["pageIndex"] = page
        if page_size is not None:
            form["pageSize"] = page_size
        return form

    def _request_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": str(self.platform_config["list_url"]),
            "Origin": "https://zhaopin.jd.com",
        }

    @staticmethod
    def _apply_fallbacks(job: RawJobPosting) -> None:
        job.title = job.title or f"京东职位-{job.job_id}"
        job.location = job.location or "地点未披露"
        job.description = job.description or "岗位描述未披露"
        job.requirements = job.requirements or "任职要求未披露"

    @staticmethod
    def _text(value: Any) -> str:
        return str(value).strip() if value is not None else ""
