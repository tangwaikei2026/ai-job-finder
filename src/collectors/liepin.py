from __future__ import annotations

import logging
import math
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote, urlencode, urljoin, urlparse

from src.base import RawCollector
from src.models import (
    CollectionManifest,
    CollectionResult,
    RawJobPosting,
    write_json_atomic,
)

logger = logging.getLogger(__name__)


class LiepinSchemaError(RuntimeError):
    """猎聘列表响应不再符合当前 adapter 的结构约定。"""


class LiepinRawCollector(RawCollector):
    """按配置关键词采集猎聘列表，并标准化为 RawJobPosting。

    猎聘列表接口依赖浏览器会话生成动态校验参数，直接通过 httpx 重放会
    返回业务风控错误。因此本 adapter 只使用浏览器加载搜索列表并捕获页面
    自己发出的 JSON 请求；不会访问岗位详情页。
    """

    platform = "liepin"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(self.platform_config.get("name", "猎聘")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        errors: list[str] = []
        keywords = self._keywords()
        max_pages = max(1, int(self.platform_config.get("max_pages", 1)))
        page_size = max(1, int(self.platform_config.get("page_size", 40)))
        manifest.expected_pages = len(keywords) * max_pages

        if not keywords:
            errors.append("keywords is empty")
        else:
            try:
                with self._browser_page() as page:
                    for keyword in keywords:
                        self._collect_keyword(
                            page,
                            keyword,
                            max_pages,
                            page_size,
                            jobs_by_id,
                            manifest,
                            errors,
                        )
            except Exception as exc:
                # 浏览器初始化失败也只影响猎聘，不向上击穿整个 raw pipeline。
                errors.append(f"browser: {self._error_summary(exc)}")
                logger.warning("[liepin] browser failed: %s", exc)

        manifest.jobs_in_scope = len(jobs_by_id)
        # 总失败时保留上一份人工复核文件；成功解析到空页面时仍可写入空列表。
        if manifest.pages_fetched:
            self._write_output_safely(list(jobs_by_id.values()), errors)
        manifest.error = "; ".join(errors)

        if errors and manifest.pages_fetched == 0:
            manifest.status = "error"
            manifest.complete = False
            manifest.stopped_by = "list_error"
        elif errors:
            manifest.status = "partial"
            manifest.complete = False
            manifest.stopped_by = "list_error"
        else:
            # complete 表示配置限定的 keyword × max_pages 均已成功处理，
            # 不表示猎聘搜索结果的所有后续页面都已采集。
            manifest.status = "success"
            manifest.complete = True
            manifest.stopped_by = "configured_max_pages"

        self.finish_manifest(manifest, started)
        return CollectionResult(jobs=list(jobs_by_id.values()), manifest=manifest)

    def _collect_keyword(
        self,
        page: Any,
        keyword: str,
        max_pages: int,
        page_size: int,
        jobs_by_id: dict[str, RawJobPosting],
        manifest: CollectionManifest,
        errors: list[str],
    ) -> None:
        """采集一个关键词；失败时记录原因并继续下一个关键词。"""

        keyword_records = 0
        keyword_total: int | None = None
        for current_page in range(max_pages):
            try:
                payload = self._fetch_list_page_with_retry(
                    page,
                    keyword,
                    current_page,
                    page_size,
                )
                records, source_total = self._parse_list_payload(payload)
            except Exception as exc:
                errors.append(
                    f"keyword={keyword!r} page={current_page}: "
                    f"{self._error_summary(exc)}"
                )
                logger.warning(
                    "[liepin] keyword=%r page=%d failed: %s",
                    keyword,
                    current_page,
                    exc,
                )
                break

            manifest.pages_fetched += 1
            manifest.records_fetched += len(records)
            keyword_records += len(records)
            if source_total is not None:
                keyword_total = source_total

            for item in records:
                job = self._map_list_job(item)
                if not job.job_id:
                    manifest.missing_job_id += 1
                    continue
                if job.job_id in jobs_by_id:
                    manifest.duplicate_records += 1
                    continue
                if self._is_hunter_job(item, job):
                    continue

                manifest.jobs_mapped += 1
                if not job.location:
                    manifest.unknown_location += 1
                    if not self.include_unknown_location:
                        continue
                    job.location = "地点未披露"
                elif not self.location_in_scope(job.location):
                    manifest.outside_city_scope += 1
                    continue
                jobs_by_id[job.job_id] = job

            if not records:
                break
            if keyword_total is not None and keyword_records >= keyword_total:
                break
            if len(records) < page_size:
                break

        if keyword_total is not None:
            # 多关键词总数可能包含同一岗位；source_total 表示各搜索结果总数之和。
            manifest.source_total += keyword_total
        else:
            manifest.source_total += keyword_records

    def _fetch_list_page_with_retry(
        self,
        page: Any,
        keyword: str,
        current_page: int,
        page_size: int,
    ) -> dict[str, Any]:
        retries = max(1, int(self.platform_config.get("list_max_retries", 3)))
        configured = self.platform_config.get(
            "list_retry_backoff_seconds",
            [2, 5, 10],
        )
        delays = configured if isinstance(configured, list) else [2, 5, 10]
        last_error: Exception | None = None

        for attempt in range(retries):
            try:
                return self._fetch_list_page(
                    page,
                    keyword,
                    current_page,
                    page_size,
                )
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= retries:
                    break
                try:
                    delay = max(
                        0.0,
                        float(delays[min(attempt, len(delays) - 1)]),
                    )
                except (IndexError, TypeError, ValueError):
                    delay = float(2**attempt)
                if delay:
                    time.sleep(delay)

        assert last_error is not None
        raise last_error

    @contextmanager
    def _browser_page(self) -> Iterator[Any]:
        """创建猎聘列表专用页面，并确保浏览器资源被释放。"""

        # 延迟导入，避免猎聘未运行时影响其他 raw adapter。
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=bool(self.platform_config.get("browser_headless", True))
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                ),
                locale="zh-CN",
            )
            page = context.new_page()
            try:
                yield page
            finally:
                context.close()
                browser.close()

    def _fetch_list_page(
        self,
        page: Any,
        keyword: str,
        current_page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """加载搜索页并捕获由猎聘前端发起的列表 API 响应。"""

        marker = str(self.platform_config["list_api_marker"])
        timeout_ms = max(
            1,
            int(
                float(self.platform_config.get("list_timeout_seconds", 30))
                * 1000
            ),
        )
        list_url = self._build_list_url(keyword, current_page, page_size)

        with page.expect_response(
            lambda response: (
                urlparse(response.url).path == marker
                and response.request.method == "POST"
            ),
            timeout=timeout_ms,
        ) as response_info:
            page.goto(list_url, wait_until="commit", timeout=timeout_ms)

        response = response_info.value
        if int(response.status) >= 400:
            raise RuntimeError(f"list API returned HTTP {response.status}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise LiepinSchemaError(
                f"list API returned {type(payload).__name__}, expected object"
            )
        return payload

    def _build_list_url(
        self,
        keyword: str,
        current_page: int,
        page_size: int,
    ) -> str:
        cfg = self.platform_config
        params = {
            "city": str(cfg.get("city", "")),
            "dq": str(cfg.get("dq", cfg.get("city", ""))),
            "pubTime": str(cfg.get("pub_time", "")),
            "currentPage": str(current_page),
            "pageSize": str(page_size),
            "key": keyword,
            "suggestTag": str(cfg.get("suggest_tag", "")),
            "workYearCode": str(cfg.get("work_year_code", "0")),
            "compId": str(cfg.get("company_id", "")),
            "compName": str(cfg.get("company_name", "")),
            "compTag": str(cfg.get("company_tag", "")),
            "industry": str(cfg.get("industry", "")),
            "salaryCode": str(cfg.get("salary_code", "")),
            "jobKind": str(cfg.get("job_kind", "2")),
            "compScale": str(cfg.get("company_scale", "")),
            "compKind": str(cfg.get("company_kind", "")),
            "compStage": str(cfg.get("company_stage", "")),
            "eduLevel": str(cfg.get("edu_level", "")),
            "otherCity": str(cfg.get("other_city", "")),
        }
        base_url = str(cfg["list_url"])
        separator = "&" if "?" in base_url else "?"
        # 空格编码成 %20，避免猎聘前端把 '+' 当成关键词字符。
        return f"{base_url}{separator}{urlencode(params, quote_via=quote)}"

    @staticmethod
    def _parse_list_payload(
        payload: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], int | None]:
        """严格校验响应；平台格式变化时显式失败，不静默产出空数据。"""

        code = payload.get("code")
        if code not in (None, 0, "0"):
            raise RuntimeError(
                f"list API returned code={code}: {payload.get('msg', '')}"
            )
        outer = payload.get("data")
        if not isinstance(outer, dict):
            raise LiepinSchemaError("list API missing object data")
        data = outer.get("data")
        if not isinstance(data, dict):
            raise LiepinSchemaError("list API missing object data.data")

        records = data.get("jobCardList")
        if not isinstance(records, list):
            raise LiepinSchemaError("list API missing array data.data.jobCardList")
        if any(not isinstance(item, dict) for item in records):
            raise LiepinSchemaError("list API jobCardList contains non-object record")

        total: int | None = None
        pagination = outer.get("pagination")
        containers = [
            data,
            pagination if isinstance(pagination, dict) else {},
            outer,
        ]
        for container in containers:
            for key in ("totalCounts", "totalCount", "total", "count"):
                value = container.get(key)
                if value in (None, ""):
                    continue
                try:
                    total = max(0, int(value))
                except (TypeError, ValueError) as exc:
                    raise LiepinSchemaError(
                        f"list API {key} is not an integer: {value!r}"
                    ) from exc
                break
            if total is not None:
                break
        return records, total

    def _map_list_job(self, item: dict[str, Any]) -> RawJobPosting:
        job_info = item.get("job")
        comp_info = item.get("comp")
        if not isinstance(job_info, dict):
            job_info = {}
        if not isinstance(comp_info, dict):
            comp_info = {}

        job_id = self._source_job_id(item)
        labels = self._text(job_info.get("labels"))
        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=(
                self._first_text(
                    job_info,
                    "title",
                    "jobTitle",
                    "positionName",
                )
                or (f"猎聘职位-{job_id}" if job_id else "猎聘职位")
            ),
            company=(
                self._first_text(
                    comp_info,
                    "compName",
                    "companyName",
                    "name",
                )
                or "公司未披露"
            ),
            department=self._first_text(
                job_info,
                "department",
                "departmentName",
                "deptName",
            ),
            location=self._first_text(job_info, "dq", "location", "city"),
            experience=self._first_text(
                job_info,
                "requireWorkYears",
                "workYear",
                "experience",
            ),
            education=self._first_text(
                job_info,
                "requireEduLevel",
                "eduLevel",
                "education",
            ),
            salary=self._first_text(
                job_info,
                "salary",
                "salaryText",
                "salaryInfo",
            ),
            description=labels or "详情页待人工查看",
            requirements="",
            url=self._detail_url(item, job_info, job_id),
        )

    def _detail_url(
        self,
        item: dict[str, Any],
        job_info: dict[str, Any],
        job_id: str,
    ) -> str:
        source_url = (
            self._first_text(job_info, "link", "url", "jobUrl")
            or self._first_text(item, "link", "url")
        )
        if source_url:
            return urljoin("https://www.liepin.com", source_url)
        template = str(self.platform_config.get("detail_url") or "")
        return template.format(job_id=job_id) if template and job_id else ""

    def _is_hunter_job(
        self,
        item: dict[str, Any],
        job: RawJobPosting,
    ) -> bool:
        """排除猎头来源及“从事猎头”的岗位，不涉及岗位池规则。"""

        source_text = " ".join(
            self._text(item.get(key))
            for key in ("jobKind", "sourceType", "recruiterType")
        )
        if "猎头" in source_text or "headhunter" in source_text.casefold():
            return True
        title = job.title.casefold()
        return any(
            str(value).strip().casefold() in title
            for value in self.platform_config.get("exclude_hunter_titles", [])
            if str(value).strip()
        )

    def _write_output_safely(
        self,
        jobs: list[RawJobPosting],
        errors: list[str],
    ) -> None:
        output = str(self.platform_config.get("output_file") or "").strip()
        if not output:
            return
        path = Path(output)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        try:
            # 这是猎聘人工复核用的附加文件，不改变 raw main 的既有日期输出。
            write_json_atomic(path, [job.to_dict() for job in jobs])
        except Exception as exc:
            errors.append(f"output: {exc}")
            logger.warning("[liepin] cannot write %s: %s", path, exc)

    def _keywords(self) -> list[str]:
        values = self.platform_config.get("keywords")
        if not isinstance(values, list):
            return []
        return list(
            dict.fromkeys(str(value).strip() for value in values if str(value).strip())
        )

    @staticmethod
    def _error_summary(exc: Exception) -> str:
        text = str(exc).strip()
        return text.splitlines()[0] if text else type(exc).__name__

    @classmethod
    def _source_job_id(cls, item: dict[str, Any]) -> str:
        job_info = item.get("job")
        if not isinstance(job_info, dict):
            job_info = {}
        data_info = job_info.get("dataInfo")
        if not isinstance(data_info, dict):
            data_info = {}
        return (
            cls._first_text(job_info, "jobId", "id")
            or cls._first_text(data_info, "jobId", "id")
            or cls._first_text(item, "jobId", "id")
        )

    @staticmethod
    def _first_text(mapping: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = LiepinRawCollector._text(mapping.get(key))
            if value:
                return value
        return ""

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            return ", ".join(
                text
                for text in (LiepinRawCollector._text(item) for item in value)
                if text
            )
        if isinstance(value, dict):
            return LiepinRawCollector._first_text(
                value,
                "name",
                "label",
                "text",
                "value",
            )
        return str(value).strip()
