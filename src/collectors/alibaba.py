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
    SOURCE_RESULT_CAP = 500

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

        try:
            region_partitions = self._resolve_region_partitions()
            self.request("GET", str(cfg["list_url"]))
            csrf_token = self.client.cookies.get("XSRF-TOKEN")
            if not csrf_token:
                raise RuntimeError(
                    f"{platform_key} list page did not set XSRF-TOKEN"
                )

            if region_partitions:
                self._collect_region_partitions(
                    region_partitions,
                    page_size,
                    csrf_token,
                    jobs_by_id,
                    seen_job_ids,
                    manifest,
                )
            else:
                self._collect_unpartitioned(
                    page_size,
                    csrf_token,
                    jobs_by_id,
                    seen_job_ids,
                    manifest,
                )

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

    def _resolve_region_partitions(self) -> list[tuple[str, str]]:
        if self._platform_key() != "aliyun":
            return []
        configured = self.platform_config.get("region_codes")
        if not isinstance(configured, dict):
            raise ValueError("missing_region_mapping: aliyun region_codes must be a mapping")
        if not self.cities:
            raise ValueError("missing_region_mapping: aliyun requires target cities")

        missing = [city for city in self.cities if not configured.get(city)]
        if missing:
            raise ValueError(
                "missing_region_mapping: no Aliyun region code for "
                + ", ".join(missing)
            )
        return [(city, str(configured[city])) for city in self.cities]

    def _build_payload(
        self,
        page: int,
        page_size: int,
        *,
        region_code: str = "",
    ) -> dict[str, Any]:
        return {
            "channel": "group_official_site",
            "language": "zh",
            "batchId": "",
            "categories": "",
            "deptCodes": [],
            "key": "",
            "pageIndex": page,
            "pageSize": page_size,
            "regions": region_code,
            "subCategories": "",
            "shareType": "",
            "shareId": "",
            "myReferralShareCode": "",
        }

    def _request_page(
        self,
        page: int,
        page_size: int,
        csrf_token: str,
        *,
        region_code: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        cfg = self.platform_config
        payload = self.request_json(
            "POST",
            str(cfg["list_api"]),
            json=self._build_payload(
                page,
                page_size,
                region_code=region_code,
            ),
            headers={
                "Content-Type": "application/json",
                "Referer": str(cfg["list_url"]),
                "X-XSRF-TOKEN": csrf_token,
            },
        )
        if payload.get("success") is not True:
            raise RuntimeError(
                f"{self._platform_key()} API failed: "
                f"{payload.get('errorCode')} "
                f"{payload.get('errorMsg', '')}"
            )
        return self._extract_records(payload)

    def _collect_unpartitioned(
        self,
        page_size: int,
        csrf_token: str,
        jobs_by_id: dict[str, RawJobPosting],
        seen_job_ids: set[str],
        manifest: CollectionManifest,
    ) -> None:
        seen_page_ids: set[tuple[str, ...]] = set()
        page = 1
        while True:
            records, total_count = self._request_page(
                page,
                page_size,
                csrf_token,
            )
            if page == 1:
                manifest.source_total = total_count
                manifest.expected_pages = math.ceil(total_count / page_size)

            if not records:
                manifest.stopped_by = "empty_page"
                manifest.complete = manifest.records_fetched >= manifest.source_total
                break

            page_ids = tuple(str(item.get("id") or "") for item in records)
            if page_ids in seen_page_ids:
                manifest.stopped_by = "repeated_page"
                manifest.complete = False
                break
            seen_page_ids.add(page_ids)
            manifest.pages_fetched += 1
            manifest.records_fetched += len(records)
            self._map_new_records(
                records,
                jobs_by_id,
                seen_job_ids,
                manifest,
            )

            if manifest.records_fetched >= manifest.source_total:
                manifest.stopped_by = "source_total_reached"
                manifest.complete = True
                break
            page += 1

    def _collect_region_partitions(
        self,
        region_partitions: list[tuple[str, str]],
        page_size: int,
        csrf_token: str,
        jobs_by_id: dict[str, RawJobPosting],
        seen_job_ids: set[str],
        manifest: CollectionManifest,
    ) -> None:
        partition_details: list[dict[str, Any]] = []
        cross_partition_duplicates = 0

        for region_name, region_code in region_partitions:
            detail: dict[str, Any] = {
                "region_name": region_name,
                "region_code": region_code,
                "source_total": 0,
                "expected_pages": 0,
                "pages_fetched": 0,
                "records_fetched": 0,
                "unique_job_ids": 0,
                "duplicate_job_ids_within_partition": 0,
                "stopped_by": "",
                "complete": False,
                "error": "",
            }
            partition_seen_ids: set[str] = set()
            seen_page_ids: set[tuple[str, ...]] = set()
            page = 1

            try:
                while True:
                    records, total_count = self._request_page(
                        page,
                        page_size,
                        csrf_token,
                        region_code=region_code,
                    )
                    if page == 1:
                        detail["source_total"] = total_count
                        detail["expected_pages"] = math.ceil(total_count / page_size)
                    elif total_count != detail["source_total"]:
                        detail["stopped_by"] = "source_total_changed"
                        detail["error"] = (
                            f"source_total changed from {detail['source_total']} "
                            f"to {total_count} on page {page}"
                        )
                        break

                    if detail["source_total"] == 0:
                        if records:
                            detail["stopped_by"] = "source_total_mismatch"
                            detail["error"] = "source_total=0 but records were returned"
                        else:
                            detail["stopped_by"] = "empty_source"
                            detail["complete"] = True
                        break

                    if not records:
                        if detail["records_fetched"] >= detail["source_total"]:
                            if detail["pages_fetched"] >= detail["expected_pages"]:
                                detail["stopped_by"] = "source_total_reached"
                                detail["complete"] = True
                            else:
                                detail["stopped_by"] = "page_count_mismatch"
                                detail["error"] = (
                                    "source_total reached before all expected pages: "
                                    f"{detail['pages_fetched']}/"
                                    f"{detail['expected_pages']}"
                                )
                        elif (
                            detail["source_total"] > self.SOURCE_RESULT_CAP
                            and detail["records_fetched"] >= self.SOURCE_RESULT_CAP
                        ):
                            detail["stopped_by"] = "partition_limit"
                            detail["error"] = (
                                "Aliyun result cap reached before partition "
                                f"source_total: {detail['records_fetched']}/"
                                f"{detail['source_total']}"
                            )
                        else:
                            detail["stopped_by"] = "empty_page"
                            detail["error"] = (
                                f"empty page after {detail['records_fetched']}/"
                                f"{detail['source_total']} records"
                            )
                        break

                    page_ids = tuple(str(item.get("id") or "") for item in records)
                    if page_ids in seen_page_ids:
                        detail["stopped_by"] = "repeated_page"
                        detail["error"] = f"repeated page {page}"
                        break
                    seen_page_ids.add(page_ids)
                    detail["pages_fetched"] += 1
                    detail["records_fetched"] += len(records)
                    manifest.pages_fetched += 1
                    manifest.records_fetched += len(records)
                    within_duplicates, cross_duplicates = self._map_new_records(
                        records,
                        jobs_by_id,
                        seen_job_ids,
                        manifest,
                        partition_seen_ids=partition_seen_ids,
                    )
                    detail["duplicate_job_ids_within_partition"] += within_duplicates
                    cross_partition_duplicates += cross_duplicates

                    if detail["records_fetched"] >= detail["source_total"]:
                        if detail["pages_fetched"] >= detail["expected_pages"]:
                            detail["stopped_by"] = "source_total_reached"
                            detail["complete"] = True
                        else:
                            detail["stopped_by"] = "page_count_mismatch"
                            detail["error"] = (
                                "source_total reached before all expected pages: "
                                f"{detail['pages_fetched']}/"
                                f"{detail['expected_pages']}"
                            )
                        break
                    page += 1
            except Exception as exc:
                detail["stopped_by"] = "error"
                detail["error"] = str(exc)

            detail["unique_job_ids"] = len(partition_seen_ids)
            manifest.expected_pages += int(detail["expected_pages"])
            partition_details.append(detail)

        all_complete = all(detail["complete"] for detail in partition_details)
        manifest.complete = all_complete
        manifest.source_total = len(seen_job_ids)
        if all_complete:
            manifest.stopped_by = "all_partitions_complete"
        elif any(detail["stopped_by"] == "partition_limit" for detail in partition_details):
            manifest.stopped_by = "partition_limit"
        elif any(detail["stopped_by"] == "error" for detail in partition_details):
            manifest.stopped_by = "partition_error"
        else:
            manifest.stopped_by = "partition_incomplete"
        manifest.error = "; ".join(
            f"{detail['region_name']}({detail['region_code']}): {detail['error']}"
            for detail in partition_details
            if detail["error"]
        )
        manifest.metadata = {
            "partition_dimension": "regions",
            "source_total_semantics": "observed_unique_union_job_ids",
            "global_source_total_available": False,
            "required_partitions": [name for name, _ in region_partitions],
            "all_required_partitions_complete": all_complete,
            "partitions": partition_details,
            "sum_partition_records": manifest.records_fetched,
            "unique_union_jobs": len(seen_job_ids),
            "cross_partition_duplicates": cross_partition_duplicates,
        }

    def _map_new_records(
        self,
        records: list[dict[str, Any]],
        jobs_by_id: dict[str, RawJobPosting],
        seen_job_ids: set[str],
        manifest: CollectionManifest,
        *,
        partition_seen_ids: set[str] | None = None,
    ) -> tuple[int, int]:
        within_partition_duplicates = 0
        cross_partition_duplicates = 0
        for item in records:
            job = self._map_job(item)
            if not job.job_id:
                manifest.missing_job_id += 1
                continue
            if partition_seen_ids is not None:
                if job.job_id in partition_seen_ids:
                    within_partition_duplicates += 1
                    manifest.duplicate_records += 1
                    continue
                partition_seen_ids.add(job.job_id)
            if job.job_id in seen_job_ids:
                cross_partition_duplicates += 1
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
        return within_partition_duplicates, cross_partition_duplicates

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
        if "totalCount" not in content or content["totalCount"] is None:
            raise ValueError("Alibaba API content.totalCount is required")
        try:
            total_count = int(content["totalCount"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Alibaba API content.totalCount must be an integer") from exc
        if total_count < 0:
            raise ValueError("Alibaba API content.totalCount must be non-negative")
        return records, total_count

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
