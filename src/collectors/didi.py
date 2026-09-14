from __future__ import annotations

import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.base import RawCollector
from src.models import CollectionManifest, CollectionResult, RawJobPosting


class DidiRawCollector(RawCollector):
    platform = "didi"
    DEFAULT_MAX_PAGES = 1000
    REASON_PRECEDENCE = (
        "request_error",
        "dynamic_total",
        "dynamic_page1",
        "duplicate_pagination",
        "unique_deficit",
        "incomplete_list",
        "detail_errors",
    )

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 16)))
        max_pages = max(1, int(cfg.get("max_pages", self.DEFAULT_MAX_PAGES)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "滴滴")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        detail_targets: list[tuple[dict[str, Any], RawJobPosting]] = []
        seen_job_ids: set[str] = set()
        totals: list[int] = []
        page_ledger: list[dict[str, Any]] = []
        start_page1_ids: list[str] | None = None
        end_page1_ids: list[str] | None = None
        terminal_page: int | None = None
        terminal_page_count: int | None = None
        list_error = False

        try:
            self.request("GET", str(cfg["list_url"]))
            for page in range(1, max_pages + 1):
                total, records = self._fetch_list_page(page, page_size)
                totals.append(total)
                manifest.source_total = total
                manifest.expected_pages = math.ceil(total / page_size)

                ordered_ids = [self._list_job_id(item) for item in records]
                if page == 1:
                    start_page1_ids = ordered_ids

                page_seen_ids: set[str] = set()
                duplicate_seen_before_count = 0
                for job_id in ordered_ids:
                    if not job_id:
                        continue
                    if job_id in seen_job_ids:
                        duplicate_seen_before_count += 1
                    page_seen_ids.add(job_id)

                page_ledger.append(
                    {
                        "page": page,
                        "items_count": len(records),
                        "reported_total": total,
                        "unique_ids_on_page": len(page_seen_ids),
                        "duplicate_seen_before_count": duplicate_seen_before_count,
                        "ordered_ids_hash": self._ordered_ids_hash(ordered_ids),
                    }
                )

                if not records:
                    terminal_page = page
                    terminal_page_count = 0
                    break

                manifest.pages_fetched += 1
                manifest.records_fetched += len(records)
                for item, job_id in zip(records, ordered_ids):
                    if not job_id:
                        manifest.missing_job_id += 1
                        continue
                    if job_id in seen_job_ids:
                        manifest.duplicate_records += 1
                        continue
                    seen_job_ids.add(job_id)

                    basic_job = self._map_list_job(item)
                    manifest.jobs_mapped += 1
                    if not basic_job.location:
                        manifest.unknown_location += 1
                    if not self.location_in_scope(basic_job.location):
                        manifest.outside_city_scope += 1
                        continue
                    jobs_by_id[job_id] = basic_job
                    detail_targets.append((item, basic_job))

            # Didi exposes dynamic offset pagination without a snapshot/cursor.
            # A complete observation therefore requires a stable page-1 reread;
            # it does not claim database-level snapshot consistency.
            end_total, end_records = self._fetch_list_page(1, page_size)
            totals.append(end_total)
            manifest.source_total = end_total
            manifest.expected_pages = math.ceil(end_total / page_size)
            end_page1_ids = [self._list_job_id(item) for item in end_records]

            list_reasons = self._list_completeness_reasons(
                totals=totals,
                start_page1_ids=start_page1_ids,
                end_page1_ids=end_page1_ids,
                unique_job_ids=len(seen_job_ids),
                duplicate_records=manifest.duplicate_records,
                missing_job_id=manifest.missing_job_id,
                terminal_page=terminal_page,
            )
            list_complete = not list_reasons

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
            completeness_reasons = list(list_reasons)
            if manifest.detail_failed:
                completeness_reasons.append("detail_errors")
            manifest.complete = list_complete and manifest.detail_failed == 0
            manifest.status = "success" if manifest.complete else "partial"
            manifest.stopped_by = (
                "source_total_reached"
                if manifest.complete
                else self._primary_reason(completeness_reasons)
            )
        except Exception as exc:
            list_error = True
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = "request_error"
            manifest.error = str(exc)
            observed_reasons = self._list_completeness_reasons(
                totals=totals,
                start_page1_ids=start_page1_ids,
                end_page1_ids=end_page1_ids,
                unique_job_ids=len(seen_job_ids),
                duplicate_records=manifest.duplicate_records,
                missing_job_id=manifest.missing_job_id,
                terminal_page=terminal_page,
            )
            completeness_reasons = [
                reason
                for reason in self.REASON_PRECEDENCE
                if reason == "request_error" or reason in observed_reasons
            ]
            list_complete = False
        finally:
            self._set_pagination_metadata(
                manifest=manifest,
                page_size=page_size,
                totals=totals,
                seen_job_ids=seen_job_ids,
                start_page1_ids=start_page1_ids,
                end_page1_ids=end_page1_ids,
                terminal_page=terminal_page,
                terminal_page_count=terminal_page_count,
                page_ledger=page_ledger,
                list_complete=list_complete,
                completeness_reasons=completeness_reasons,
                list_error=list_error,
            )
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _fetch_list_page(
        self, page: int, page_size: int
    ) -> tuple[int, list[dict[str, Any]]]:
        payload = self.request_json(
            "GET",
            str(self.platform_config["list_api"]),
            params={"page": page, "recruitType": 1, "size": page_size},
            headers={"Referer": str(self.platform_config["list_url"])},
        )
        meta = payload.get("meta")
        if not isinstance(meta, dict) or meta.get("code") != 0:
            message = meta.get("message") if isinstance(meta, dict) else None
            raise RuntimeError(f"Didi list API failed: {message or 'invalid meta'}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Didi list API returned invalid data")
        total = data.get("total")
        if isinstance(total, bool):
            raise RuntimeError("Didi list API returned invalid total")
        try:
            parsed_total = int(total)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Didi list API returned invalid total") from exc
        if parsed_total < 0:
            raise RuntimeError("Didi list API returned invalid total")
        records = data.get("items")
        if not isinstance(records, list) or not all(
            isinstance(item, dict) for item in records
        ):
            raise RuntimeError("Didi list API returned invalid items")
        return parsed_total, records

    @staticmethod
    def _list_job_id(item: dict[str, Any]) -> str:
        source_job_id = str(item.get("jdId") or "")
        return str(item.get("jdNo") or source_job_id)

    @staticmethod
    def _ordered_ids_hash(ordered_ids: list[str]) -> str:
        encoded = json.dumps(
            ordered_ids, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _list_completeness_reasons(
        cls,
        *,
        totals: list[int],
        start_page1_ids: list[str] | None,
        end_page1_ids: list[str] | None,
        unique_job_ids: int,
        duplicate_records: int,
        missing_job_id: int,
        terminal_page: int | None,
    ) -> list[str]:
        reasons: list[str] = []
        stable_total = totals[0] if totals and min(totals) == max(totals) else None
        if totals and stable_total is None:
            reasons.append("dynamic_total")
        if (
            start_page1_ids is not None
            and end_page1_ids is not None
            and start_page1_ids != end_page1_ids
        ):
            reasons.append("dynamic_page1")
        if duplicate_records:
            reasons.append("duplicate_pagination")
        # When totals move there is no stable coverage target, but falling short
        # of the largest observed source total is still an independently useful
        # deficit signal for the audit trail.
        if totals and unique_job_ids < max(totals):
            reasons.append("unique_deficit")
        if (
            not totals
            or start_page1_ids is None
            or end_page1_ids is None
            or terminal_page is None
            or missing_job_id
            or (stable_total is not None and unique_job_ids > stable_total)
        ):
            reasons.append("incomplete_list")
        return [reason for reason in cls.REASON_PRECEDENCE if reason in reasons]

    @classmethod
    def _primary_reason(cls, reasons: list[str]) -> str:
        return next(
            (reason for reason in cls.REASON_PRECEDENCE if reason in reasons),
            "incomplete_list",
        )

    @classmethod
    def _set_pagination_metadata(
        cls,
        *,
        manifest: CollectionManifest,
        page_size: int,
        totals: list[int],
        seen_job_ids: set[str],
        start_page1_ids: list[str] | None,
        end_page1_ids: list[str] | None,
        terminal_page: int | None,
        terminal_page_count: int | None,
        page_ledger: list[dict[str, Any]],
        list_complete: bool,
        completeness_reasons: list[str],
        list_error: bool,
    ) -> None:
        manifest.metadata = {
            "pagination_mode": "offset_dynamic",
            "page_size": page_size,
            "source_total_semantics": "final_valid_api_reported_total",
            "first_total": totals[0] if totals else None,
            "last_total": totals[-1] if totals else None,
            "min_total": min(totals) if totals else None,
            "max_total": max(totals) if totals else None,
            "total_changed": bool(totals and min(totals) != max(totals)),
            "records_fetched": manifest.records_fetched,
            "unique_job_ids": len(seen_job_ids),
            "duplicate_records": manifest.duplicate_records,
            "start_page1_ids_hash": (
                cls._ordered_ids_hash(start_page1_ids)
                if start_page1_ids is not None
                else None
            ),
            "end_page1_ids_hash": (
                cls._ordered_ids_hash(end_page1_ids)
                if end_page1_ids is not None
                else None
            ),
            "page1_changed": (
                start_page1_ids != end_page1_ids
                if start_page1_ids is not None and end_page1_ids is not None
                else None
            ),
            "terminal_page": terminal_page,
            "terminal_page_count": terminal_page_count,
            "terminal_condition": "next_page_empty",
            "terminal_condition_proven": terminal_page is not None,
            "stable_snapshot_mechanism": False,
            "completeness_scope": (
                "observation_complete_under_available_source_contract"
            ),
            "list_complete": list_complete,
            "completeness_reasons": completeness_reasons,
            "list_error": list_error,
            "page_ledger": page_ledger,
        }

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
