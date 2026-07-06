from __future__ import annotations

import httpx

from src.collectors.tencent import TencentRawCollector


COLLECTION_CONFIG = {
    "cities": ["北京", "上海"],
    "include_unknown_location": False,
    "max_retries": 1,
}

PLATFORM_CONFIG = {
    "name": "腾讯",
    "list_api": "https://example.test/tencent/list",
    "detail_api": "https://example.test/tencent/detail",
    "detail_url": "https://example.test/jobs/{job_id}",
    "page_size": 100,
    "detail_workers": 2,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _list_response(posts: list[dict[str, object]]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"Code": 200, "Data": {"Count": len(posts), "Posts": posts}},
    )


def test_maps_list_fields() -> None:
    with _client(lambda _: httpx.Response(500)) as client:
        collector = TencentRawCollector(
            PLATFORM_CONFIG,
            COLLECTION_CONFIG,
            client,
        )
        job = collector._map_list_job(
            {
                "PostId": "t1",
                "RecruitPostName": "后台开发工程师",
                "ComName": "腾讯科技",
                "BGName": "CSIG",
                "LocationName": "北京市",
                "RequireWorkYearsName": "三年以上",
                "Responsibility": "列表职责",
                "PostURL": "https://example.test/source/t1",
            }
        )

    assert job.job_id == "t1"
    assert job.title == "后台开发工程师"
    assert job.company == "腾讯科技"
    assert job.department == "CSIG"
    assert job.location == "北京市"
    assert job.experience == "三年以上"
    assert job.description == "列表职责"
    assert job.requirements == ""
    assert job.url == "https://example.test/source/t1"


def test_enriches_requirements_and_description_from_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/list"):
            return _list_response(
                [
                    {
                        "PostId": "t1",
                        "RecruitPostName": "后台开发工程师",
                        "ComName": "腾讯科技",
                        "BGName": "CSIG",
                        "LocationName": "北京市",
                        "RequireWorkYearsName": "三年以上",
                        "Responsibility": "列表职责",
                        "PostURL": "https://example.test/source/t1",
                    }
                ]
            )

        assert dict(request.url.params) == {
            "timestamp": "careers",
            "postId": "t1",
            "language": "zh-cn",
        }
        return httpx.Response(
            200,
            json={
                "Code": 200,
                "Data": {
                    "Responsibility": "详情职责",
                    "Requirement": "详情任职要求",
                },
            },
        )

    with _client(handler) as client:
        result = TencentRawCollector(
            PLATFORM_CONFIG,
            COLLECTION_CONFIG,
            client,
        ).collect()

    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.job_id == "t1"
    assert job.description == "详情职责"
    assert job.requirements == "详情任职要求"
    assert result.manifest.details_fetched == 1
    assert result.manifest.detail_failed == 0
    assert result.manifest.status == "success"


def test_detail_failure_is_partial_and_keeps_list_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/list"):
            return _list_response(
                [
                    {
                        "PostId": "t1",
                        "RecruitPostName": "岗位一",
                        "LocationName": "北京",
                        "Responsibility": "列表职责",
                    }
                ]
            )
        return httpx.Response(503, json={"message": "unavailable"})

    with _client(handler) as client:
        result = TencentRawCollector(
            PLATFORM_CONFIG,
            COLLECTION_CONFIG,
            client,
        ).collect()

    assert [job.job_id for job in result.jobs] == ["t1"]
    assert result.jobs[0].description == "列表职责"
    assert result.manifest.status == "partial"
    assert result.manifest.complete is False
    assert result.manifest.details_fetched == 0
    assert result.manifest.detail_failed == 1
    assert result.manifest.stopped_by == "detail_errors"


def test_fetches_details_only_for_jobs_in_city_scope() -> None:
    detail_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/list"):
            return _list_response(
                [
                    {
                        "PostId": "in-scope",
                        "RecruitPostName": "北京岗位",
                        "LocationName": "北京",
                    },
                    {
                        "PostId": "out-of-scope",
                        "RecruitPostName": "成都岗位",
                        "LocationName": "成都",
                    },
                ]
            )
        detail_ids.append(request.url.params["postId"])
        return httpx.Response(
            200,
            json={"Code": 200, "Data": {"Requirement": "要求"}},
        )

    with _client(handler) as client:
        result = TencentRawCollector(
            PLATFORM_CONFIG,
            COLLECTION_CONFIG,
            client,
        ).collect()

    assert [job.job_id for job in result.jobs] == ["in-scope"]
    assert detail_ids == ["in-scope"]
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.details_fetched == 1


def test_empty_detail_fields_do_not_overwrite_non_empty_list_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/list"):
            return _list_response(
                [
                    {
                        "PostId": "t1",
                        "RecruitPostName": "岗位一",
                        "LocationName": "上海",
                        "Responsibility": "列表职责",
                    }
                ]
            )
        return httpx.Response(
            200,
            json={
                "Code": 200,
                "Data": {"Responsibility": "", "Requirement": ""},
            },
        )

    with _client(handler) as client:
        result = TencentRawCollector(
            PLATFORM_CONFIG,
            COLLECTION_CONFIG,
            client,
        ).collect()

    assert result.jobs[0].description == "列表职责"
    assert result.jobs[0].requirements == ""
    assert result.manifest.details_fetched == 1
    assert result.manifest.status == "success"


def test_fetch_details_false_does_not_request_detail() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return _list_response(
            [
                {
                    "PostId": "t1",
                    "RecruitPostName": "岗位一",
                    "LocationName": "北京",
                    "Responsibility": "列表职责",
                }
            ]
        )

    with _client(handler) as client:
        result = TencentRawCollector(
            {**PLATFORM_CONFIG, "fetch_details": False},
            COLLECTION_CONFIG,
            client,
        ).collect()

    assert requests == ["/tencent/list"]
    assert result.jobs[0].requirements == ""
    assert result.manifest.details_fetched == 0
    assert result.manifest.detail_failed == 0
    assert result.manifest.status == "success"


def test_missing_detail_data_is_counted_as_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/list"):
            return _list_response(
                [
                    {
                        "PostId": "t1",
                        "RecruitPostName": "岗位一",
                        "LocationName": "北京",
                    }
                ]
            )
        return httpx.Response(200, json={"Code": 200})

    with _client(handler) as client:
        result = TencentRawCollector(
            PLATFORM_CONFIG,
            COLLECTION_CONFIG,
            client,
        ).collect()

    assert [job.job_id for job in result.jobs] == ["t1"]
    assert result.manifest.status == "partial"
    assert result.manifest.details_fetched == 0
    assert result.manifest.detail_failed == 1
