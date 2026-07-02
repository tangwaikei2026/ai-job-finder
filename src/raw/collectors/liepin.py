from __future__ import annotations

import json
import logging
import math
import random
import re
import time
from contextlib import contextmanager
from html.parser import HTMLParser
from typing import Any, Iterator
from urllib.parse import quote, urlencode, urljoin, urlparse

import httpx

from src.raw.base import RawCollector
from src.raw.models import CollectionManifest, CollectionResult, RawJobPosting

logger = logging.getLogger(__name__)


class LiepinSchemaError(RuntimeError):
    """猎聘响应结构与 adapter 预期不一致。"""


class LiepinDetailError(RuntimeError):
    """猎聘详情无法解析。"""


class LiepinBlockedError(LiepinDetailError):
    """猎聘详情请求被限流或跳转到安全验证。"""


class _JsonLdScriptParser(HTMLParser):
    """使用标准库提取 JSON-LD，避免为一个平台增加 HTML 解析依赖。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._active = False
        self._parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "script":
            return
        attributes = {
            key.casefold(): (value or "").casefold() for key, value in attrs
        }
        if attributes.get("type") == "application/ld+json":
            self._active = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._active:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._active:
            self.scripts.append("".join(self._parts))
            self._active = False
            self._parts = []


class _HtmlTextParser(HTMLParser):
    """把详情 JSON-LD 中的 HTML JD 转为保留段落的纯文本。"""

    _BLOCK_TAGS = {
        "br",
        "div",
        "li",
        "p",
        "section",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized = tag.casefold()
        if normalized in {"script", "style"}:
            self._ignored_depth += 1
        elif normalized in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif normalized in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


class LiepinRawCollector(RawCollector):
    """采集猎聘企业职位并标准化为 RawJobPosting。

    猎聘列表接口依赖浏览器会话生成的动态校验参数，直接用 httpx 重放会
    返回业务错误。因此浏览器只用于让搜索页发起真实列表请求；列表响应的
    解析、字段映射和后续详情请求仍由 adapter 独立完成。
    """

    platform = "liepin"

    def collect(self) -> CollectionResult:
        started = time.monotonic()
        cfg = self.platform_config
        page_size = max(1, int(cfg.get("page_size", 40)))
        manifest = CollectionManifest(
            platform=self.platform,
            name=str(cfg.get("name", "猎聘")),
        )
        jobs_by_id: dict[str, RawJobPosting] = {}
        list_complete = False
        list_error = ""
        detail_errors: list[str] = []
        detail_circuit_open = False

        try:
            list_complete = self._collect_list(
                jobs_by_id,
                manifest,
                page_size,
            )
        except Exception as exc:
            # 后续页失败时保留已经映射的岗位；首屏失败则返回 error manifest。
            list_error = f"list: {exc}"
            logger.warning("[liepin] %s", list_error)

        if bool(cfg.get("fetch_details", True)) and jobs_by_id:
            detail_errors, detail_circuit_open = self._collect_details(
                list(jobs_by_id.values()),
                manifest,
            )

        manifest.jobs_in_scope = len(jobs_by_id)
        manifest.complete = list_complete and manifest.detail_failed == 0
        if list_error and manifest.pages_fetched == 0:
            manifest.status = "error"
            manifest.stopped_by = "list_error"
        elif list_error:
            manifest.status = "partial"
            manifest.stopped_by = "list_error"
        elif detail_circuit_open:
            manifest.status = "partial"
            manifest.stopped_by = "detail_circuit_open"
        elif manifest.detail_failed:
            manifest.status = "partial"
            manifest.stopped_by = "detail_errors"
        else:
            manifest.status = "success" if manifest.complete else "partial"
            if not manifest.stopped_by:
                manifest.stopped_by = (
                    "source_total_reached"
                    if manifest.complete
                    else "incomplete_list"
                )
        manifest.error = "; ".join(
            error for error in [list_error, *detail_errors] if error
        )
        self.finish_manifest(manifest, started)
        return CollectionResult(list(jobs_by_id.values()), manifest)

    def _collect_list(
        self,
        jobs_by_id: dict[str, RawJobPosting],
        manifest: CollectionManifest,
        page_size: int,
    ) -> bool:
        """逐页采集列表；异常向上抛出，由 collect 保留已完成页面。"""

        seen_job_ids: set[str] = set()
        seen_pages: set[tuple[str, ...]] = set()
        max_pages = max(0, int(self.platform_config.get("max_pages", 0)))
        current_page = 0
        total_known = False

        with self._browser_page() as page:
            while True:
                payload = self._fetch_list_page_with_retry(
                    page,
                    current_page,
                    page_size,
                )
                (
                    records,
                    source_total,
                    source_pages,
                    has_next,
                ) = self._parse_list_payload(payload)

                if source_total is not None:
                    total_known = True
                    manifest.source_total = max(
                        manifest.source_total,
                        source_total,
                    )
                    manifest.expected_pages = math.ceil(
                        manifest.source_total / page_size
                    )
                if source_pages is not None:
                    manifest.expected_pages = max(
                        manifest.expected_pages,
                        source_pages,
                    )

                if not records:
                    pagination_complete = (
                        source_pages == 0
                        or (
                            source_pages is not None
                            and current_page >= source_pages
                        )
                        or (source_pages is None and has_next is False)
                    )
                    if (
                        not pagination_complete
                        and total_known
                        and manifest.records_fetched < manifest.source_total
                    ):
                        raise RuntimeError(
                            "empty list page after "
                            f"{manifest.records_fetched}/{manifest.source_total} records"
                        )
                    if not total_known:
                        manifest.source_total = manifest.records_fetched
                        manifest.expected_pages = manifest.pages_fetched
                    manifest.stopped_by = "empty_page"
                    return True

                page_ids = tuple(self._source_job_id(item) for item in records)
                if page_ids in seen_pages:
                    raise RuntimeError(
                        f"repeated list page at currentPage={current_page}"
                    )
                seen_pages.add(page_ids)

                manifest.pages_fetched += 1
                manifest.records_fetched += len(records)
                for item in records:
                    job = self._map_list_job(item)
                    if not job.job_id:
                        manifest.missing_job_id += 1
                        continue
                    if job.job_id in seen_job_ids:
                        manifest.duplicate_records += 1
                        continue
                    seen_job_ids.add(job.job_id)

                    if self._is_hunter_job(item, job):
                        logger.info(
                            "[liepin] excluded hunter job %s (%s)",
                            job.job_id,
                            job.title,
                        )
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

                if source_pages is not None and current_page + 1 >= source_pages:
                    manifest.stopped_by = "pagination_end"
                    return True
                if source_pages is None and has_next is False:
                    manifest.stopped_by = "pagination_end"
                    return True
                if (
                    source_pages is None
                    and total_known
                    and manifest.records_fetched >= manifest.source_total
                ):
                    manifest.stopped_by = "source_total_reached"
                    return True

                if (
                    source_pages is None
                    and has_next is None
                    and len(records) < page_size
                ):
                    if total_known:
                        raise RuntimeError(
                            "short list page after "
                            f"{manifest.records_fetched}/{manifest.source_total} records"
                        )
                    manifest.source_total = manifest.records_fetched
                    manifest.expected_pages = manifest.pages_fetched
                    manifest.stopped_by = "short_page"
                    return True

                current_page += 1
                if max_pages and current_page >= max_pages:
                    manifest.stopped_by = "max_pages"
                    return not total_known or (
                        manifest.records_fetched >= manifest.source_total
                    )

    def _fetch_list_page_with_retry(
        self,
        page: Any,
        current_page: int,
        page_size: int,
    ) -> dict[str, Any]:
        retries = max(
            1,
            int(self.platform_config.get("list_max_retries", 3)),
        )
        configured = self.platform_config.get(
            "list_retry_backoff_seconds",
            [2, 5, 10],
        )
        delays = configured if isinstance(configured, list) else [2, 5, 10]
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                return self._fetch_list_page(page, current_page, page_size)
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
                    delay = float(2 ** attempt)
                logger.warning(
                    "[liepin] list page %d failed (%d/%d): %s; retrying in %.1fs",
                    current_page,
                    attempt + 1,
                    retries,
                    exc,
                    delay,
                )
                if delay:
                    time.sleep(delay)
        assert last_error is not None
        raise last_error

    @contextmanager
    def _browser_page(self) -> Iterator[Any]:
        """创建仅供猎聘列表使用的浏览器页面，并保证资源始终释放。"""

        # 延迟导入可避免猎聘未运行时影响其他 raw adapter 的加载。
        from playwright.sync_api import sync_playwright

        cfg = self.platform_config
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=bool(cfg.get("browser_headless", True))
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
        current_page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """让真实搜索页请求指定页，并捕获其私有列表 API 响应。"""

        marker = str(
            self.platform_config.get(
                "list_api_marker",
                "/api/com.liepin.searchfront4c.pc-search-job",
            )
        )
        timeout_ms = max(
            1,
            int(float(self.platform_config.get("list_timeout_seconds", 30)) * 1000),
        )
        list_url = self._build_list_url(current_page, page_size)

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

    def _build_list_url(self, current_page: int, page_size: int) -> str:
        cfg = self.platform_config
        params = {
            "city": str(cfg.get("city", "")),
            "dq": str(cfg.get("dq", cfg.get("city", ""))),
            "pubTime": str(cfg.get("pub_time", "")),
            "currentPage": str(current_page),
            "pageSize": str(page_size),
            "key": str(cfg.get("keyword", "")),
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
        # 猎聘前端会把 URL 中的 '+' 当作关键词字符，空格必须编码成 %20。
        return f"{base_url}{separator}{urlencode(params, quote_via=quote)}"

    @staticmethod
    def _parse_list_payload(
        payload: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], int | None, int | None, bool | None]:
        """校验猎聘嵌套响应，格式变化时明确失败而不是静默返回空列表。"""

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

        total: int | None = None
        pagination = outer.get("pagination")
        if pagination is not None and not isinstance(pagination, dict):
            raise LiepinSchemaError("list API data.pagination is not an object")
        containers = (
            data,
            pagination if isinstance(pagination, dict) else {},
            outer,
        )
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

        records = data.get("jobCardList")
        if records is None and total == 0:
            records = []
        if not isinstance(records, list):
            raise LiepinSchemaError("list API missing array data.data.jobCardList")
        if any(not isinstance(item, dict) for item in records):
            raise LiepinSchemaError("list API jobCardList contains non-object record")

        total_pages: int | None = None
        has_next: bool | None = None
        if isinstance(pagination, dict):
            raw_pages = pagination.get("totalPage")
            if raw_pages not in (None, ""):
                try:
                    total_pages = max(0, int(raw_pages))
                except (TypeError, ValueError) as exc:
                    raise LiepinSchemaError(
                        f"list API totalPage is not an integer: {raw_pages!r}"
                    ) from exc
            raw_has_next = pagination.get("hasNext")
            if isinstance(raw_has_next, bool):
                has_next = raw_has_next
        return records, total, total_pages, has_next

    def _map_list_job(self, item: dict[str, Any]) -> RawJobPosting:
        job_info = item.get("job")
        comp_info = item.get("comp")
        if not isinstance(job_info, dict):
            job_info = {}
        if not isinstance(comp_info, dict):
            comp_info = {}

        job_id = self._source_job_id(item)
        title = self._first_text(job_info, "title", "jobTitle", "positionName")
        company = self._first_text(comp_info, "compName", "companyName", "name")
        location = self._first_text(job_info, "dq", "location", "city")
        labels = self._text(job_info.get("labels"))
        detail_url = self._detail_url(item, job_info, job_id)

        return RawJobPosting(
            job_id=job_id,
            platform=self.platform,
            title=title or (f"猎聘职位-{job_id}" if job_id else "猎聘职位"),
            company=company or "公司未披露",
            department=self._first_text(
                job_info,
                "department",
                "departmentName",
                "deptName",
            ),
            location=location,
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
            description=labels or "岗位描述待详情补全",
            requirements="任职要求待详情补全",
            url=detail_url,
        )

    def _detail_url(
        self,
        item: dict[str, Any],
        job_info: dict[str, Any],
        job_id: str,
    ) -> str:
        source_url = self._first_text(
            job_info,
            "link",
            "url",
            "jobUrl",
        ) or self._first_text(item, "link", "url")
        if source_url:
            return urljoin("https://www.liepin.com", source_url)
        template = str(self.platform_config.get("detail_url") or "")
        return template.format(job_id=job_id) if template and job_id else ""

    def _collect_details(
        self,
        jobs: list[RawJobPosting],
        manifest: CollectionManifest,
    ) -> tuple[list[str], bool]:
        """串行补全详情；连续被拦截时熔断并保留全部列表岗位。"""

        block_threshold = max(
            1,
            int(self.platform_config.get("detail_block_threshold", 3)),
        )
        consecutive_blocks = 0
        circuit_open = False
        failure_counts: dict[str, int] = {}
        self._last_detail_request_at = 0.0

        for index, job in enumerate(jobs):
            try:
                detail = self._fetch_detail(job)
                self._apply_detail(job, detail)
                manifest.details_fetched += 1
                consecutive_blocks = 0
            except Exception as exc:
                manifest.detail_failed += 1
                kind = self._detail_failure_kind(exc)
                failure_counts[kind] = failure_counts.get(kind, 0) + 1
                logger.warning(
                    "[liepin] detail failed job_id=%s reason=%s",
                    job.job_id,
                    exc,
                )
                if isinstance(exc, LiepinBlockedError):
                    consecutive_blocks += 1
                else:
                    consecutive_blocks = 0

                if consecutive_blocks >= block_threshold:
                    remaining = len(jobs) - index - 1
                    if remaining:
                        manifest.detail_failed += remaining
                        failure_counts["circuit_skipped"] = remaining
                    circuit_open = True
                    logger.warning(
                        "[liepin] detail circuit opened after %d consecutive blocks; "
                        "skipped %d jobs",
                        consecutive_blocks,
                        remaining,
                    )
                    break

        errors = []
        if failure_counts:
            summary = ", ".join(
                f"{key}={value}" for key, value in sorted(failure_counts.items())
            )
            errors.append(f"detail failures: {summary}")
        return errors, circuit_open

    def _fetch_detail(self, job: RawJobPosting) -> dict[str, Any]:
        if not job.url:
            raise LiepinDetailError("detail URL is missing")

        retries = max(
            1,
            int(self.platform_config.get("detail_max_retries", 3)),
        )
        last_error: Exception | None = None
        for attempt in range(retries):
            self._wait_for_detail_slot()
            response: httpx.Response | None = None
            try:
                response = self.client.request(
                    "GET",
                    job.url,
                    headers={
                        "Accept": (
                            "text/html,application/xhtml+xml,application/xml;"
                            "q=0.9,image/avif,image/webp,*/*;q=0.8"
                        ),
                        "Referer": str(self.platform_config.get("list_url") or ""),
                    },
                )
                self._last_detail_request_at = time.monotonic()

                if response.status_code in (403, 429):
                    raise LiepinBlockedError(
                        f"detail returned HTTP {response.status_code}"
                    )
                if response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code >= 400:
                    raise LiepinDetailError(
                        f"detail returned HTTP {response.status_code}"
                    )
                if self._is_blocked_detail_response(response):
                    raise LiepinBlockedError(
                        "detail redirected to or rendered a security challenge"
                    )
                return self._parse_detail_html(response.text)
            except LiepinDetailError as exc:
                last_error = exc
                # 404、页面结构变化等确定性错误不通过重复请求解决。
                if not isinstance(exc, LiepinBlockedError):
                    raise
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = exc

            if attempt + 1 < retries:
                self._sleep_detail_backoff(
                    attempt,
                    blocked=isinstance(last_error, LiepinBlockedError),
                    response=response,
                )

        assert last_error is not None
        raise last_error

    def _wait_for_detail_slot(self) -> None:
        minimum = max(
            0.0,
            float(self.platform_config.get("detail_delay_min_seconds", 1.5)),
        )
        maximum = max(
            minimum,
            float(self.platform_config.get("detail_delay_max_seconds", 3.0)),
        )
        target_delay = random.uniform(minimum, maximum)
        elapsed = time.monotonic() - getattr(
            self,
            "_last_detail_request_at",
            0.0,
        )
        wait = max(0.0, target_delay - elapsed)
        if wait:
            time.sleep(wait)

    def _sleep_detail_backoff(
        self,
        attempt: int,
        *,
        blocked: bool,
        response: httpx.Response | None,
    ) -> None:
        retry_after = ""
        if response is not None:
            retry_after = response.headers.get("Retry-After", "")
        try:
            delay = max(0.0, float(retry_after))
        except ValueError:
            delay = 0.0

        if not delay:
            key = (
                "detail_block_backoff_seconds"
                if blocked
                else "detail_retry_backoff_seconds"
            )
            defaults = [30, 60, 120] if blocked else [5, 10, 20]
            configured = self.platform_config.get(key, defaults)
            values = configured if isinstance(configured, list) else defaults
            try:
                delay = max(0.0, float(values[min(attempt, len(values) - 1)]))
            except (IndexError, TypeError, ValueError):
                delay = float(defaults[min(attempt, len(defaults) - 1)])
        if delay:
            time.sleep(delay)

    @staticmethod
    def _is_blocked_detail_response(response: httpx.Response) -> bool:
        host = (urlparse(str(response.url)).hostname or "").casefold()
        if (
            host in {"safe.liepin.com", "wow.liepin.com"}
            or host.endswith(".safe.liepin.com")
            or host.endswith(".wow.liepin.com")
        ):
            return True
        sample = response.text[:30000].casefold()
        markers = (
            "<title>安全验证",
            "<title>访问验证",
            "请完成安全验证",
            "请先完成验证",
            "访问过于频繁",
        )
        return any(marker.casefold() in sample for marker in markers)

    @classmethod
    def _parse_detail_html(cls, html: str) -> dict[str, Any]:
        parser = _JsonLdScriptParser()
        parser.feed(html)
        for script in parser.scripts:
            try:
                value = json.loads(script)
            except json.JSONDecodeError:
                # 猎聘部分 JD 会在 JSON 字符串中直接放换行符；strict=False
                # 仅放宽控制字符校验，仍要求整体是合法 JSON 结构。
                try:
                    value = json.loads(script, strict=False)
                except json.JSONDecodeError:
                    continue
            posting = cls._find_job_posting(value)
            if posting is not None:
                return posting
        raise LiepinDetailError("detail JobPosting JSON-LD is missing")

    @classmethod
    def _find_job_posting(cls, value: Any) -> dict[str, Any] | None:
        if isinstance(value, list):
            for item in value:
                posting = cls._find_job_posting(item)
                if posting is not None:
                    return posting
            return None
        if not isinstance(value, dict):
            return None

        schema_type = value.get("@type")
        types = schema_type if isinstance(schema_type, list) else [schema_type]
        if any(str(item).casefold() == "jobposting" for item in types):
            return value
        for key in ("@graph", "mainEntity", "itemListElement"):
            posting = cls._find_job_posting(value.get(key))
            if posting is not None:
                return posting
        return None

    def _apply_detail(
        self,
        job: RawJobPosting,
        detail: dict[str, Any],
    ) -> None:
        title = self._schema_text(detail.get("title"))
        company = self._schema_text(detail.get("hiringOrganization"))
        location = self._detail_location(detail.get("jobLocation"))
        description = self._plain_text(
            self._schema_text(detail.get("description"))
        )
        description, requirements = self._split_jd(description)
        qualifications = self._plain_text(
            self._schema_text(detail.get("qualifications"))
        )

        job.title = title or job.title
        job.company = company or job.company
        job.location = location or job.location
        job.experience = (
            self._schema_text(detail.get("experienceRequirements"))
            or job.experience
        )
        job.education = (
            self._schema_text(detail.get("educationRequirements"))
            or job.education
        )
        job.salary = self._salary_text(detail.get("baseSalary")) or job.salary
        job.description = description or job.description
        job.requirements = (
            requirements
            or qualifications
            or "任职要求未单独披露"
        )

    @classmethod
    def _schema_text(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            return ", ".join(
                part for part in (cls._schema_text(item) for item in value) if part
            )
        if isinstance(value, dict):
            for key in ("name", "value", "text", "label"):
                text = cls._schema_text(value.get(key))
                if text:
                    return text
        return ""

    @classmethod
    def _detail_location(cls, value: Any) -> str:
        locations = value if isinstance(value, list) else [value]
        names: list[str] = []
        for location in locations:
            if not isinstance(location, dict):
                continue
            address = location.get("address")
            if not isinstance(address, dict):
                continue
            parts = [
                cls._schema_text(address.get("addressRegion")),
                cls._schema_text(address.get("addressLocality")),
                cls._schema_text(address.get("streetAddress")),
            ]
            name = "".join(part for part in parts if part)
            if name and name not in names:
                names.append(name)
        return ", ".join(names)

    @classmethod
    def _salary_text(cls, value: Any) -> str:
        if not isinstance(value, dict):
            return cls._schema_text(value)
        currency = cls._schema_text(value.get("currency"))
        amount = value.get("value")
        if not isinstance(amount, dict):
            text = cls._schema_text(amount)
            return " ".join(part for part in (text, currency) if part)
        minimum = cls._schema_text(amount.get("minValue"))
        maximum = cls._schema_text(amount.get("maxValue"))
        unit = cls._schema_text(amount.get("unitText"))
        if minimum and maximum:
            number = f"{minimum}-{maximum}"
        else:
            number = minimum or maximum or cls._schema_text(amount.get("value"))
        return " ".join(part for part in (number, currency, unit) if part)

    @staticmethod
    def _plain_text(value: str) -> str:
        if not value:
            return ""
        parser = _HtmlTextParser()
        parser.feed(value)
        text = "".join(parser.parts)
        lines = [
            re.sub(r"[ \t\u00a0]+", " ", line).strip()
            for line in text.splitlines()
        ]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _split_jd(text: str) -> tuple[str, str]:
        if not text:
            return "", ""
        requirement_heading = re.compile(
            r"(?:^|\n)\s*(?:任职要求|岗位要求|职位要求|任职资格|"
            r"能力要求|岗位资格)\s*[:：]?\s*",
            re.IGNORECASE,
        )
        match = requirement_heading.search(text)
        if not match:
            return text, ""
        description = text[: match.start()].strip()
        requirements = text[match.end() :].strip()
        return description or text, requirements

    @staticmethod
    def _detail_failure_kind(exc: Exception) -> str:
        if isinstance(exc, LiepinBlockedError):
            return "blocked"
        if isinstance(exc, httpx.RequestError):
            return "network"
        if isinstance(exc, httpx.HTTPStatusError):
            return "http"
        if isinstance(exc, LiepinDetailError):
            return "parse_or_status"
        return "unexpected"

    def _is_hunter_job(
        self,
        item: dict[str, Any],
        job: RawJobPosting,
    ) -> bool:
        """排除猎头发布来源和“从事猎头工作”的职位，不修改岗位池规则。"""

        source_values = [
            item.get("jobKind"),
            item.get("sourceType"),
            item.get("recruiterType"),
        ]
        source_text = " ".join(self._text(value) for value in source_values)
        if "猎头" in source_text or "headhunter" in source_text.casefold():
            return True

        excluded_titles = self.platform_config.get("exclude_hunter_titles") or []
        title = job.title.casefold()
        return any(
            str(keyword).strip().casefold() in title
            for keyword in excluded_titles
            if str(keyword).strip()
        )

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
                part for part in (LiepinRawCollector._text(item) for item in value) if part
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
