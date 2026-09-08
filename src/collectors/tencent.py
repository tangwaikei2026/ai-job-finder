from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any

from src.base import RawCollector
from src.models import (
    CollectionManifest,
    CollectionResult,
    RawJobPosting,
)

logger = logging.getLogger(__name__)


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
                self._detail_request_lock = Lock()
                self._last_detail_request_at = 0.0
                selected_detail_targets = self._select_detail_targets(detail_targets)
                logger.info(
                    "[tencent] detail_targets total=%d strategy=%s limit=%d",
                    len(selected_detail_targets),
                    str(cfg.get("detail_strategy", "all")),
                    max(0, int(cfg.get("detail_limit", 0))),
                )
                workers = max(1, int(cfg.get("detail_workers", 2)))
                detail_done = 0
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    future_map = {
                        executor.submit(self._fetch_detail, job): job
                        for job in selected_detail_targets
                    }
                    for future in as_completed(future_map):
                        job = future_map[future]
                        try:
                            self._apply_detail(job, future.result())
                            manifest.details_fetched += 1
                        except Exception:
                            manifest.detail_failed += 1
                            manifest.detail_failed_job_ids.append(job.job_id)
                        detail_done += 1
                        if (
                            detail_done % 50 == 0
                            or detail_done == len(selected_detail_targets)
                        ):
                            logger.info(
                                "[tencent] detail progress total=%d done=%d "
                                "details_fetched=%d detail_failed=%d",
                                len(selected_detail_targets),
                                detail_done,
                                manifest.details_fetched,
                                manifest.detail_failed,
                            )

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

    def _select_detail_targets(
        self,
        jobs: list[RawJobPosting],
    ) -> list[RawJobPosting]:
        cfg = self.platform_config
        strategy = str(cfg.get("detail_strategy", "all")).strip().lower()
        if strategy != "all":
            raise ValueError(f"unsupported Tencent detail_strategy: {strategy}")

        limit = max(0, int(cfg.get("detail_limit", 0)))
        if limit:
            return jobs[:limit]
        return jobs

    def _fetch_detail(self, job: RawJobPosting) -> dict[str, Any]:
        cfg = self.platform_config
        max_attempts = max(1, int(cfg.get("detail_max_retries", 1)))
        timeout = max(0.1, float(cfg.get("detail_timeout_seconds", 8)))
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                self._wait_for_detail_request()
                response = self.client.request(
                    "GET",
                    str(cfg["detail_api"]),
                    params={
                        "timestamp": "careers",
                        "postId": job.job_id,
                        "language": "zh-cn",
                    },
                    headers={
                        "Referer": job.url,
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
                        ),
                    },
                    timeout=timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError(
                        "Tencent detail API returned non-object JSON "
                        f"for {job.job_id}"
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
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    logger.warning(
                        "[tencent] detail request failed for %s (%d/%d): %s; "
                        "retrying",
                        job.job_id,
                        attempt,
                        max_attempts,
                        exc,
                    )

        assert last_error is not None
        raise last_error

    def _wait_for_detail_request(self) -> None:
        delay = max(
            0.0,
            float(self.platform_config.get("detail_delay_seconds", 0.3)),
        )
        with self._detail_request_lock:
            elapsed = time.monotonic() - self._last_detail_request_at
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_detail_request_at = time.monotonic()

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
