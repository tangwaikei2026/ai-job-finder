from __future__ import annotations

import hashlib
import hmac
import math
import time
from typing import Any
from urllib.parse import quote

from src.base import RawCollector
from src.models import CollectionManifest, CollectionResult, RawJobPosting


DEFAULT_SIGNING_KEY = "652f962a-0575-4575-98d2-f04e2291bee2"
DICTIONARY_TYPES = "workLocation,positionCategory,positionExperience"


class KuaishouRawCollector(RawCollector):
    platform = "kuaishou"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 100)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "快手")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        seen_job_ids: set[str] = set()
        seen_page_ids: set[tuple[str, ...]] = set()
        page = 1

        try:
            self.request("GET", str(cfg["list_url"]))
            dictionaries = self._fetch_dictionaries()

            while True:
                params: dict[str, Any] = {
                    "pageNum": page,
                    "pageSize": page_size,
                    "positionNatureCode": "C001",
                    "recruitProject": "socialr",
                }
                timestamp = int(time.time() * 1000)
                signature = self._generate_signature(
                    params,
                    timestamp,
                    str(cfg.get("signing_key") or DEFAULT_SIGNING_KEY),
                )
                payload = self.request_json(
                    "GET",
                    str(cfg["list_api"]),
                    params=params,
                    headers={
                        "Referer": str(cfg["list_url"]),
                        "Origin": "https://zhaopin.kuaishou.cn",
                        "sign": signature,
                        "signTimestamp": str(timestamp),
                    },
                )
                if payload.get("code") != 0:
                    raise RuntimeError(
                        "Kuaishou API returned "
                        f"code={payload.get('code')}: "
                        f"{payload.get('message', '')}"
                    )

                data = payload.get("result") or {}
                records = data.get("list") or []
                manifest.source_total = int(data.get("total") or 0)
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
                    job = self._map_job(item, dictionaries)
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

            manifest.jobs_in_scope = len(jobs_by_id)
            manifest.status = "success" if manifest.complete else "partial"
        except Exception as exc:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = "error"
            manifest.error = str(exc)
        finally:
            self.finish_manifest(manifest, started)

        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _fetch_dictionaries(self) -> dict[str, dict[str, str]]:
        payload = self.request_json(
            "GET",
            str(self.platform_config["dictionary_api"]),
            params={"types": DICTIONARY_TYPES},
            headers={
                "Referer": str(self.platform_config["list_url"]),
                "Origin": "https://zhaopin.kuaishou.cn",
            },
        )
        if payload.get("code") != 0:
            raise RuntimeError(
                "Kuaishou dictionary API returned "
                f"code={payload.get('code')}: {payload.get('message', '')}"
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Kuaishou dictionary API returned no result")

        dictionaries: dict[str, dict[str, str]] = {}
        for dictionary_name in DICTIONARY_TYPES.split(","):
            entries = result.get(dictionary_name) or []
            dictionaries[dictionary_name] = {
                str(entry.get("code")): str(entry.get("name"))
                for entry in entries
                if (
                    isinstance(entry, dict)
                    and entry.get("code")
                    and entry.get("name")
                )
            }
        return dictionaries

    def _map_job(
        self,
        item: dict[str, Any],
        dictionaries: dict[str, dict[str, str]] | None = None,
    ) -> RawJobPosting:
        dictionaries = dictionaries or {}
        job_id = str(item.get("id") or "")
        detail_url = str(self.platform_config.get("detail_url") or "")
        location = self._map_codes(
            item.get("workLocationsCode") or item.get("workLocationCode"),
            dictionaries.get("workLocation", {}),
        )
        department = str(item.get("departmentName") or "")
        if not department:
            department = self._map_codes(
                item.get("positionCategoryCode"),
                dictionaries.get("positionCategory", {}),
            )

        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=str(item.get("name") or ""),
            company=str(self.platform_config.get("name") or "快手"),
            department=department,
            location=location,
            experience=self._map_codes(
                item.get("workExperienceCode"),
                dictionaries.get("positionExperience", {}),
            ),
            education=str(item.get("educationLimitCode") or ""),
            salary=self._format_salary(
                item.get("salaryMin"),
                item.get("salaryMax"),
            ),
            description=str(item.get("description") or ""),
            requirements=str(item.get("positionDemand") or ""),
            url=(
                detail_url.format(job_id=job_id)
                if detail_url and job_id
                else ""
            ),
        )

    @classmethod
    def _generate_signature(
        cls,
        params: dict[str, Any],
        timestamp: int,
        signing_key: str,
        body: str = "",
    ) -> str:
        message = (
            f"{timestamp}{cls._canonical_params(params)}{body}{signing_key}"
        )
        return hmac.new(
            signing_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _canonical_params(params: dict[str, Any]) -> str:
        pairs: list[str] = []
        for key in sorted(params):
            raw_value = params[key]
            values = raw_value if isinstance(raw_value, list) else [raw_value]
            values = sorted(
                str(value)
                for value in values
                if value is not None and str(value) != ""
            )
            if not values:
                continue
            encoded_values = ",".join(
                quote(value, safe="-_.!~*'()").replace("%20", "+")
                for value in values
            )
            pairs.append(f"{key}={encoded_values}")
        return "&".join(pairs)

    @staticmethod
    def _map_codes(value: Any, dictionary: dict[str, str]) -> str:
        if value is None or value == "":
            return ""
        values = value if isinstance(value, list) else [value]
        return ", ".join(
            dictionary.get(str(code), str(code))
            for code in values
            if code is not None and str(code)
        )

    @staticmethod
    def _format_salary(lower: Any, upper: Any) -> str:
        if lower is not None and upper is not None:
            return f"{lower}-{upper}"
        if lower is not None:
            return f"{lower}以上"
        if upper is not None:
            return f"{upper}以下"
        return ""
