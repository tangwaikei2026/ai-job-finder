from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from threading import Lock, Event
from typing import Any

import httpx

from src.base import RawCollector, request_error_fields
from src.models import CollectionManifest, CollectionResult, RawJobPosting


logger = logging.getLogger(__name__)


class MeituanRawCollector(RawCollector):
    platform = "meituan"

    def collect(self) -> CollectionResult:
        # Optional worker hooks; pure request/parse unit tests use the same loop.
        emit = getattr(self, "worker_emit", lambda *args, **kwargs: None)
        stop = getattr(self, "worker_stop", Event())
        started = time.monotonic()
        wall_started = time.time()
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
        phase = "list"
        phase_started = started
        progress_lock = Lock()
        progress = {
            "list_complete": False, "detail_targets": 0, "detail_submitted": 0,
            "detail_started": 0, "detail_succeeded": 0, "detail_failed": 0,
            "list_seconds": 0.0, "detail_seconds": 0.0,
            "last_success_at": None, "last_success_elapsed_seconds": None,
        }
        manifest.metadata["progress"] = progress

        def success() -> None:
            progress["last_success_at"] = datetime.now(timezone.utc).isoformat()
            progress["last_success_elapsed_seconds"] = round(time.monotonic() - started, 3)

        def observe(event: str) -> None:
            with progress_lock:
                progress["detail_targets"] = len(detail_targets)
                progress["detail_not_started"] = len(detail_targets) - progress["detail_started"]
                progress["detail_in_flight"] = (
                    progress["detail_started"] - progress["detail_succeeded"] - progress["detail_failed"]
                )
                progress["detail_unfinished"] = (
                    len(detail_targets) - progress["detail_succeeded"] - progress["detail_failed"]
                )
                snapshot = dict(progress)
            logger.info(
                "[meituan] event=%s phase=%s status=%s elapsed_seconds=%.3f "
                "wall_seconds=%.3f pages=%d progress=%s",
                event, phase, manifest.status, time.monotonic() - started,
                time.time() - wall_started, manifest.pages_fetched, snapshot,
                extra={"collection_event": event, "collection_phase": phase,
                       "collection_progress": snapshot},
            )

        def fetch_detail(item: dict[str, Any]) -> dict[str, Any]:
            if stop.is_set():
                raise InterruptedError("worker stopping")
            emit("attempt", job_id=str(item["jobUnionId"]))
            if stop.is_set():
                raise InterruptedError("worker stopping")
            with progress_lock:
                progress["detail_started"] += 1
            return self._fetch_detail(item)

        observe("enter")

        try:
            while True:
                if stop.is_set():
                    raise InterruptedError("worker stopping")
                payload = self.request_json(
                    "POST",
                    str(cfg["list_api"]),
                    request_stage="list",
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

                success()
                emit("list", manifest=manifest.to_dict(),
                     jobs=[job.to_dict() for job in jobs_by_id.values()])
                observe("list_progress")

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

            progress["list_complete"] = manifest.complete
            progress["list_seconds"] = round(time.monotonic() - phase_started, 3)
            phase = "detail"
            phase_started = time.monotonic()
            observe("detail_enter")
            emit("list_end", manifest=manifest.to_dict())
            workers = max(1, int(cfg.get("detail_workers", 4)))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                targets = iter(detail_targets)
                future_map = {}

                def submit() -> None:
                    if stop.is_set():
                        return
                    target = next(targets, None)
                    if target is not None:
                        item, job = target
                        future_map[executor.submit(fetch_detail, item)] = job
                        progress["detail_submitted"] += 1

                for _ in range(workers):
                    submit()
                while future_map:
                    if stop.is_set():
                        raise InterruptedError("worker stopping")
                    done, _ = wait(future_map, timeout=0.1, return_when=FIRST_COMPLETED)
                    for future in done:
                        job = future_map.pop(future)
                        try:
                            self._apply_detail(job, future.result())
                            manifest.details_fetched += 1
                            progress["detail_succeeded"] += 1
                            success()
                            emit("success", job=job.to_dict())
                        except Exception as exc:
                            # Fixed type buckets only: no messages, URLs, headers or response bodies.
                            error_type = next((kind.__name__ for kind in (
                                httpx.TimeoutException, TimeoutError, httpx.HTTPStatusError,
                                httpx.RequestError, ValueError, TypeError, KeyError, RuntimeError,
                            ) if isinstance(exc, kind)), "Exception")
                            counts = manifest.metadata.setdefault("detail_error_types", {})
                            counts[error_type] = counts.get(error_type, 0) + 1
                            fields = request_error_fields(exc)
                            logger.warning(
                                "[meituan] detail_failed stage=detail error_type=%s error_category=%s",
                                fields["error_type"], fields["error_category"], extra=fields,
                            )
                            manifest.detail_failed += 1
                            progress["detail_failed"] += 1
                            manifest.detail_failed_job_ids.append(job.job_id)
                            emit("failure", job_id=job.job_id)
                        if (manifest.details_fetched + manifest.detail_failed) % 50 == 0:
                            observe("detail_progress")
                        submit()

            manifest.jobs_in_scope = len(jobs_by_id)
            manifest.complete = manifest.complete and manifest.detail_failed == 0
            manifest.status = "success" if manifest.complete else "partial"
            if manifest.detail_failed:
                manifest.stopped_by = "detail_errors"
        except Exception as exc:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = "error"
            fields = request_error_fields(exc)
            manifest.metadata["collection_error"] = {"stage": phase, **fields}
            manifest.error = (
                f"stage={phase} error_type={fields['error_type']} "
                f"error_category={fields['error_category']}"
            )
            logger.warning("[meituan] collection_failed %s", manifest.error,
                           extra={"request_stage": phase, **fields})
        finally:
            progress[f"{phase}_seconds"] = round(time.monotonic() - phase_started, 3)
            observe("exit")
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
            request_stage="detail",
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
