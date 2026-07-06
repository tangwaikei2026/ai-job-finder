from __future__ import annotations

from urllib.parse import parse_qs

import httpx

from src.collectors.baidu import BaiduRawCollector
from src.collectors.tencent import TencentRawCollector


COLLECTION_CONFIG = {
    "cities": ["北京", "上海"],
    "include_unknown_location": False,
    "max_retries": 1,
}


def test_tencent_schema_change_is_reported_in_manifest() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "Code": 200,
                "Data": {
                    "Count": 1,
                    "Posts": {"unexpected": "object-not-list"},
                },
            },
            request=request,
        )
    )

    with httpx.Client(transport=transport) as client:
        collector = TencentRawCollector(
            {
                "name": "腾讯",
                "list_api": "https://example.test/tencent",
                "page_size": 20,
            },
            COLLECTION_CONFIG,
            client,
        )
        result = collector.collect()

    assert result.jobs == []
    assert result.manifest.complete is False
    assert result.manifest.status in {"error", "partial"}
    assert result.manifest.stopped_by == "error"
    assert result.manifest.error


def test_baidu_later_page_failure_is_partial() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(parse_qs(request.content.decode())["curPage"][0])
        if page == 2:
            return httpx.Response(
                500,
                json={"message": "temporary failure"},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "total": "2",
                    "pages": 2,
                    "list": [
                        {
                            "name": "AI测试工程师",
                            "postId": "post-1",
                            "workPlace": "北京市",
                        }
                    ],
                },
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collector = BaiduRawCollector(
            {
                "name": "百度",
                "list_url": "https://example.test/social-list",
                "list_api": "https://example.test/getPostListNew",
                "detail_url": "https://example.test/detail/{job_id}",
                "page_size": 1,
            },
            COLLECTION_CONFIG,
            client,
        )
        result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["post-1"]
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert result.manifest.pages_fetched == 1
    assert result.manifest.records_fetched == 1
    assert result.manifest.jobs_in_scope == 1
    assert result.manifest.stopped_by == "error"
    assert "500" in result.manifest.error
