from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx

from src.raw.collectors.baidu import BaiduRawCollector
from src.raw.collectors.bytedance import ByteDanceRawCollector
from src.raw.collectors.didi import DidiRawCollector
from src.raw.collectors.feishu import FeishuRawCollector
from src.raw.collectors.kuaishou import KuaishouRawCollector
from src.raw.collectors.meituan import MeituanRawCollector
from src.raw.collectors.netease import NeteaseRawCollector
from src.raw.collectors.quark import QuarkRawCollector
from src.raw.collectors.tencent import TencentRawCollector
from src.raw.collectors.xiaohongshu import XiaohongshuRawCollector


COLLECTION_CONFIG = {
    "cities": ["北京", "上海"],
    "include_unknown_location": False,
    "max_retries": 1,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_tencent_collects_all_pages_then_applies_city_scope():
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pageIndex"])
        assert request.url.params["keyword"] == ""
        assert request.url.params["area"] == ""
        posts = {
            1: [
                {
                    "PostId": "t1",
                    "RecruitPostName": "岗位一",
                    "ComName": "腾讯",
                    "BGName": "CSIG",
                    "LocationName": "北京",
                    "RequireWorkYearsName": "三年以上",
                    "Responsibility": "完整职责一",
                    "PostURL": "https://example.test/t1",
                },
                {
                    "PostId": "t2",
                    "RecruitPostName": "岗位二",
                    "LocationName": "成都",
                },
            ],
            2: [
                {
                    "PostId": "t3",
                    "RecruitPostName": "岗位三",
                    "LocationName": "上海",
                }
            ],
        }[page]
        return httpx.Response(
            200,
            json={"Code": 200, "Data": {"Count": 3, "Posts": posts}},
        )

    collector = TencentRawCollector(
        {
            "name": "腾讯",
            "list_api": "https://example.test/tencent",
            "detail_url": "https://example.test/{job_id}",
            "page_size": 2,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )
    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["t1", "t3"]
    assert result.jobs[0].description == "完整职责一"
    assert result.manifest.complete is True
    assert result.manifest.pages_fetched == 2
    assert result.manifest.records_fetched == 3
    assert result.manifest.jobs_mapped == 3
    assert result.manifest.jobs_in_scope == 2
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.stopped_by == "source_total_reached"


def test_netease_maps_source_fields_without_relevance_filtering():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["keyword"] == ""
        assert "workPlaceName" not in body
        return httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "total": 2,
                    "list": [
                        {
                            "id": 76008,
                            "name": "AI应用工程师（评测方向）",
                            "firstDepName": "技术中心",
                            "workPlaceNameList": ["广州市"],
                            "reqWorkYearsName": "3-5年",
                            "reqEducationName": "本科",
                            "description": "职责原文",
                            "requirement": "要求原文",
                            "beeUrl": "https://example.test/76008",
                        },
                        {
                            "id": 76009,
                            "name": "非AI岗位也应采集",
                            "firstDepName": "市场部",
                            "workPlaceNameList": ["北京市", "杭州市"],
                            "description": "没有AI关键词",
                        },
                    ],
                },
            },
        )

    collector = NeteaseRawCollector(
        {
            "name": "网易",
            "list_api": "https://example.test/netease",
            "detail_url": "https://example.test/{job_id}",
            "page_size": 50,
        },
        {**COLLECTION_CONFIG, "cities": ["北京", "杭州", "广州"]},
        _client(handler),
    )
    result = collector.collect()

    assert len(result.jobs) == 2
    assert result.jobs[0].location == "广州市"
    assert result.jobs[0].experience == "3-5年"
    assert result.jobs[0].education == "本科"
    assert result.jobs[0].description == "职责原文"
    assert result.jobs[0].requirements == "要求原文"
    assert result.jobs[1].title == "非AI岗位也应采集"
    assert result.manifest.complete is True
    assert result.manifest.source_total == 2


def test_unknown_location_policy_is_explicit():
    collector = TencentRawCollector(
        {
            "name": "腾讯",
            "list_api": "https://example.test/tencent",
            "page_size": 1,
        },
        COLLECTION_CONFIG,
        _client(lambda _: httpx.Response(500)),
    )
    assert collector.location_in_scope("") is False

    collector_with_unknown = TencentRawCollector(
        {
            "name": "腾讯",
            "list_api": "https://example.test/tencent",
            "page_size": 1,
        },
        {**COLLECTION_CONFIG, "include_unknown_location": True},
        _client(lambda _: httpx.Response(500)),
    )
    assert collector_with_unknown.location_in_scope("") is True


def test_quark_bootstraps_csrf_and_uses_shared_city_scope():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                text="<html></html>",
                headers={"Set-Cookie": "XSRF-TOKEN=test-token; Path=/"},
            )

        body = json.loads(request.content)
        assert request.headers["x-xsrf-token"] == "test-token"
        assert body["key"] == ""
        assert body["regions"] == ""
        assert body["categories"] == ""
        return httpx.Response(
            200,
            json={
                "success": True,
                "content": {
                    "totalCount": 2,
                    "datas": [
                        {
                            "id": 1001,
                            "name": "岗位一",
                            "workLocations": ["杭州", "上海"],
                            "experience": {"from": 3, "to": None},
                            "degree": "bachelor",
                            "description": "职责原文",
                            "requirement": "要求原文",
                        },
                        {
                            "id": 1002,
                            "name": "岗位二",
                            "workLocations": ["成都"],
                        },
                    ],
                },
            },
        )

    collector = QuarkRawCollector(
        {
            "name": "阿里巴巴",
            "list_url": "https://example.test/jobs",
            "list_api": "https://example.test/position/search",
            "detail_url": "https://example.test/detail?id={job_id}",
            "page_size": 50,
        },
        {**COLLECTION_CONFIG, "cities": ["上海", "杭州"]},
        _client(handler),
    )
    result = collector.collect()

    assert [job.job_id for job in result.jobs] == ["1001"]
    assert result.jobs[0].location == "杭州, 上海"
    assert result.jobs[0].experience == "3年以上"
    assert result.jobs[0].education == "本科"
    assert result.jobs[0].description == "职责原文"
    assert result.jobs[0].requirements == "要求原文"
    assert result.manifest.source_total == 2
    assert result.manifest.jobs_in_scope == 1
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.complete is True


def test_feishu_maps_company_specific_detail_url():
    collector = FeishuRawCollector(
        {"name": "飞书招聘"},
        COLLECTION_CONFIG,
        _client(lambda _: httpx.Response(500)),
    )
    job = collector._map_job(
        {
            "id": "7651",
            "title": "Agent测试开发工程师",
            "city_list": [{"name": "北京"}, {"name": "上海"}],
            "description": "职责原文",
            "requirement": "要求原文",
        },
        {
            "name": "百川智能",
            "detail_url": (
                "https://cq6qe6bvfr6.jobs.feishu.cn/baichuanzhaopin/"
                "position/{job_id}/detail"
            ),
        },
    )

    assert job.company == "百川智能"
    assert job.location == "北京, 上海"
    assert job.requirements == "要求原文"
    assert job.url.endswith("/position/7651/detail")


def test_didi_collects_list_then_enriches_target_city_details():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/social/list/1":
            return httpx.Response(200, text="<html></html>")
        if request.url.path.endswith("/front/list"):
            return httpx.Response(
                200,
                json={
                    "meta": {"code": 0},
                    "data": {
                        "total": 2,
                        "items": [
                            {
                                "jdId": 61202,
                                "jdNo": "JR2026011900S",
                                "jobName": "资深测试开发工程师",
                                "deptName": "ABC平台",
                                "workArea": "北京市",
                            },
                            {
                                "jdId": 61203,
                                "jdNo": "JR2026011900T",
                                "jobName": "其他岗位",
                                "deptName": "其他部门",
                                "workArea": "成都市",
                            },
                        ],
                    },
                },
            )
        if request.url.path.endswith("/front/view/61202"):
            return httpx.Response(
                200,
                json={
                    "meta": {"code": 0},
                    "data": {
                        "jobName": "资深测试开发工程师",
                        "deptName": "ABC平台",
                        "workArea": "北京市",
                        "jobDesc": "职位描述",
                        "qualification": "任职要求",
                    },
                },
            )
        return httpx.Response(404)

    collector = DidiRawCollector(
        {
            "name": "滴滴",
            "list_url": "https://example.test/social/list/1",
            "list_api": "https://example.test/front/list",
            "detail_api": "https://example.test/front/view/{job_id}",
            "detail_url": "https://example.test/social/p/{job_id}",
            "page_size": 16,
            "detail_workers": 1,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )
    result = collector.collect()

    assert len(result.jobs) == 1
    assert result.jobs[0].job_id == "JR2026011900S"
    assert result.jobs[0].url.endswith("/61202")
    assert result.jobs[0].description == "职位描述"
    assert result.jobs[0].requirements == "任职要求"
    assert result.manifest.details_fetched == 1
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.complete is True


def test_bytedance_maps_portal_fields_and_city_codes():
    collector = ByteDanceRawCollector(
        {
            "name": "字节跳动",
            "detail_url": (
                "https://jobs.bytedance.com/experienced/position/{job_id}/detail"
            ),
        },
        COLLECTION_CONFIG,
        _client(lambda _: httpx.Response(500)),
    )
    job = collector._map_job(
        {
            "id": "7537622862884210951",
            "title": "大模型测试开发工程师-抖音",
            "city_info": {"name": "北京"},
            "job_category": {
                "name": "测试",
                "parent": {"name": "研发"},
            },
            "description": "职责原文",
            "requirement": "要求原文",
        }
    )
    codes = collector._city_codes(
        {"city_list": [{"name": "北京市", "code": "CT_11"}]}
    )

    assert job.department == "研发 - 测试"
    assert job.location == "北京"
    assert job.url.endswith("/7537622862884210951/detail")
    assert codes == {"北京": "CT_11"}


def test_baidu_maps_post_id_and_preserves_records_with_same_job_number():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "recruitType=SOCIAL" in body
        assert "pageSize=20" in body
        assert "keyWord=" in body
        assert "postType=" in body
        assert request.headers["referer"] == "https://example.test/social-list"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "total": "3",
                    "pages": 1,
                    "list": [
                        {
                            "name": "大模型推理工程师（J101025）",
                            "postId": "336e82e0-307f-49f1-ae1f-4831fb9d570e",
                            "jobId": "b54865d6-424d-4068-b22a-5f04c25504c1",
                            "postType": "技术",
                            "workPlace": "北京市",
                            "workYears": "1-3年",
                            "education": "本科",
                            "workContent": "完整职责",
                            "serviceCondition": "完整要求",
                            "bgShortName": "ACG",
                        },
                        {
                            "name": "大模型推理工程师（J101025）",
                            "postId": "duplicate-post-id",
                            "workPlace": "北京市",
                        },
                        {
                            "name": "成都岗位（J101026）",
                            "postId": "post-2",
                            "workPlace": "成都市",
                        },
                    ],
                },
            },
        )

    collector = BaiduRawCollector(
        {
            "name": "百度",
            "list_url": "https://example.test/social-list",
            "list_api": "https://example.test/getPostListNew",
            "detail_url": "https://example.test/detail/SOCIAL/{job_id}",
            "page_size": 50,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )
    result = collector.collect()

    assert len(result.jobs) == 2
    assert [job.job_id for job in result.jobs] == [
        "336e82e0-307f-49f1-ae1f-4831fb9d570e",
        "duplicate-post-id",
    ]
    assert result.jobs[0].title == "大模型推理工程师（J101025）"
    assert result.jobs[0].department == "ACG"
    assert result.jobs[0].location == "北京市"
    assert result.jobs[0].experience == "1-3年"
    assert result.jobs[0].education == "本科"
    assert result.jobs[0].description == "完整职责"
    assert result.jobs[0].requirements == "完整要求"
    assert result.jobs[0].url.endswith(
        "/detail/SOCIAL/336e82e0-307f-49f1-ae1f-4831fb9d570e"
    )
    assert result.manifest.source_total == 3
    assert result.manifest.records_fetched == 3
    assert result.manifest.jobs_in_scope == 2
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.duplicate_records == 0
    assert result.manifest.complete is True


def test_baidu_keeps_same_content_for_different_post_ids():
    records = [
        {
            "name": "测试开发工程师（J84347）",
            "postId": "post-first",
            "workPlace": "北京市",
            "bgShortName": "IDG",
            "workContent": "职责一\n职责二",
            "serviceCondition": "本科及以上学历",
        },
        {
            "name": "测试开发工程师（J84347）",
            "postId": "post-exact-duplicate",
            "workPlace": "北京市",
            "bgShortName": "IDG",
            "workContent": "职责一\n职责二",
            "serviceCondition": "本科及以上学历",
        },
        {
            "name": "测试开发工程师（J84347）",
            "postId": "post-different-requirement",
            "workPlace": "北京市",
            "bgShortName": "IDG",
            "workContent": "职责一\n职责二",
            "serviceCondition": "硕士及以上学历",
        },
        {
            "name": "同一postId的重复记录（J999999）",
            "postId": "post-first",
            "workPlace": "上海市",
            "bgShortName": "其他部门",
            "workContent": "不应覆盖第一条",
            "serviceCondition": "不应输出",
        },
    ]

    collector = BaiduRawCollector(
        {
            "name": "百度",
            "list_url": "https://example.test/social-list",
            "list_api": "https://example.test/getPostListNew",
            "detail_url": "https://example.test/detail/SOCIAL/{job_id}",
            "page_size": 20,
        },
        COLLECTION_CONFIG,
        _client(
            lambda _: httpx.Response(
                200,
                json={
                    "status": "ok",
                    "data": {"total": "4", "pages": 1, "list": records},
                },
            )
        ),
    )
    result = collector.collect()

    assert [job.job_id for job in result.jobs] == [
        "post-first",
        "post-exact-duplicate",
        "post-different-requirement",
    ]
    assert result.jobs[0].title == "测试开发工程师（J84347）"
    assert result.jobs[1].title == "测试开发工程师（J84347）"
    assert result.jobs[1].description == "职责一\n职责二"
    assert result.jobs[2].requirements == "硕士及以上学历"
    assert result.manifest.jobs_mapped == 3
    assert result.manifest.duplicate_records == 1
    assert result.manifest.complete is True


def test_baidu_collects_every_page_before_finishing():
    requested_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(parse_qs(request.content.decode())["curPage"][0])
        requested_pages.append(page)
        records = {
            1: [
                {
                    "name": "北京岗位一（J100001）",
                    "postId": "post-1",
                    "workPlace": "北京市",
                    "workContent": "职责一",
                    "serviceCondition": "要求一",
                },
                {
                    "name": "北京岗位二（J100002）",
                    "postId": "post-2",
                    "workPlace": "北京市",
                    "workContent": "职责二",
                    "serviceCondition": "要求二",
                },
            ],
            2: [
                {
                    "name": "上海岗位（J100003）",
                    "postId": "post-3",
                    "workPlace": "上海市",
                    "workContent": "职责三",
                    "serviceCondition": "要求三",
                }
            ],
        }[page]
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "total": "3",
                    "pages": 2,
                    "list": records,
                },
            },
        )

    collector = BaiduRawCollector(
        {
            "name": "百度",
            "list_url": "https://example.test/social-list",
            "list_api": "https://example.test/getPostListNew",
            "detail_url": "https://example.test/detail/SOCIAL/{job_id}",
            "page_size": 2,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )
    result = collector.collect()

    assert requested_pages == [1, 2]
    assert [job.job_id for job in result.jobs] == [
        "post-1",
        "post-2",
        "post-3",
    ]
    assert result.manifest.pages_fetched == 2
    assert result.manifest.expected_pages == 2
    assert result.manifest.records_fetched == 3
    assert result.manifest.stopped_by == "source_total_reached"
    assert result.manifest.complete is True
    assert result.manifest.status == "success"


def test_baidu_records_api_failure_in_manifest():
    collector = BaiduRawCollector(
        {
            "name": "百度",
            "list_url": "https://example.test/social-list",
            "list_api": "https://example.test/getPostListNew",
            "detail_url": "https://example.test/detail/SOCIAL/{job_id}",
            "page_size": 20,
        },
        COLLECTION_CONFIG,
        _client(
            lambda _: httpx.Response(
                200,
                json={"status": "fail", "message": "Illegal argument"},
            )
        ),
    )
    result = collector.collect()

    assert result.jobs == []
    assert result.manifest.status == "error"
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == "error"
    assert "status=fail" in result.manifest.error
    assert "Illegal argument" in result.manifest.error


def test_baidu_stops_when_api_repeats_a_page():
    requested_pages: list[int] = []
    repeated_records = [
        {
            "name": "岗位一（J100001）",
            "postId": "post-1",
            "workPlace": "北京市",
        },
        {
            "name": "岗位二（J100002）",
            "postId": "post-2",
            "workPlace": "上海市",
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(parse_qs(request.content.decode())["curPage"][0])
        requested_pages.append(page)
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "total": "4",
                    "pages": 2,
                    "list": repeated_records,
                },
            },
        )

    collector = BaiduRawCollector(
        {
            "name": "百度",
            "list_url": "https://example.test/social-list",
            "list_api": "https://example.test/getPostListNew",
            "detail_url": "https://example.test/detail/SOCIAL/{job_id}",
            "page_size": 2,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )
    result = collector.collect()

    assert requested_pages == [1, 2]
    assert [job.job_id for job in result.jobs] == ["post-1", "post-2"]
    assert result.manifest.pages_fetched == 1
    assert result.manifest.records_fetched == 2
    assert result.manifest.stopped_by == "repeated_page"
    assert result.manifest.complete is False
    assert result.manifest.status == "partial"


def test_meituan_collects_all_pages_and_deduplicates_only_job_id():
    requested_pages: list[int] = []
    detailed_job_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path.endswith("/getJobList"):
            assert body["keywords"] == ""
            assert body["cityList"] == []
            assert body["department"] == []
            assert body["jfJgList"] == []
            assert body["jobType"] == [{"code": "3", "subCode": []}]
            page = int(body["page"]["pageNo"])
            requested_pages.append(page)
            records = {
                1: [
                    {
                        "jobUnionId": "m1",
                        "name": "LongCat大模型工程师",
                        "cityList": [{"name": "北京市"}],
                        "department": [{"name": "基础研发平台"}],
                        "jobDuty": "列表职责一",
                    },
                    {
                        "jobUnionId": "m2",
                        "name": "成都岗位",
                        "cityList": [{"name": "成都市"}],
                        "department": [{"name": "其他部门"}],
                        "jobDuty": "成都职责",
                    },
                ],
                2: [
                    {
                        "jobUnionId": "m1",
                        "name": "重复ID不应再次输出",
                        "cityList": [{"name": "北京市"}],
                    },
                    {
                        "jobUnionId": "m3",
                        "name": "产品经理",
                        "cityList": [{"name": "上海市"}],
                        "department": [{"name": "美团平台"}],
                        "jobDuty": "列表职责三",
                    },
                ],
            }[page]
            return httpx.Response(
                200,
                json={
                    "status": 1,
                    "message": "成功",
                    "data": {
                        "list": records,
                        "page": {
                            "pageNo": page,
                            "pageSize": 2,
                            "totalPage": 2,
                            "totalCount": 4,
                        },
                    },
                },
            )

        if request.url.path.endswith("/getJobDetail"):
            job_id = str(body["jobUnionId"])
            detailed_job_ids.append(job_id)
            details = {
                "m1": {
                    "jobUnionId": "m1",
                    "name": "LongCat大模型工程师",
                    "cityList": [{"name": "北京市"}, {"name": "上海市"}],
                    "department": [{"name": "核心本地商业-基础研发平台"}],
                    "workYear": "3年以上",
                    "jobDuty": "完整职责一",
                    "jobRequirement": "完整要求一",
                    "highLight": "岗位亮点一",
                },
                "m3": {
                    "jobUnionId": "m3",
                    "name": "产品经理",
                    "cityList": [{"name": "上海市"}],
                    "department": [{"name": "核心本地商业-美团平台"}],
                    "workYear": "5年以上",
                    "jobDuty": "完整职责三",
                    "jobRequirement": "完整要求三",
                },
            }
            return httpx.Response(
                200,
                json={"status": 1, "message": "成功", "data": details[job_id]},
            )
        return httpx.Response(404)

    collector = MeituanRawCollector(
        {
            "name": "美团",
            "list_url": "https://example.test/web/social",
            "list_api": "https://example.test/api/official/job/getJobList",
            "detail_api": "https://example.test/api/official/job/getJobDetail",
            "detail_url": (
                "https://example.test/web/position/detail?"
                "jobUnionId={job_id}&highlightType=social"
            ),
            "page_size": 2,
            "detail_workers": 2,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )
    result = collector.collect()

    assert requested_pages == [1, 2]
    assert sorted(detailed_job_ids) == ["m1", "m3"]
    assert [job.job_id for job in result.jobs] == ["m1", "m3"]
    assert result.jobs[0].department == "核心本地商业-基础研发平台"
    assert result.jobs[0].location == "北京市,上海市"
    assert result.jobs[0].experience == "3年以上"
    assert result.jobs[0].description == "完整职责一\n岗位亮点\n岗位亮点一"
    assert result.jobs[0].requirements == "完整要求一"
    assert result.jobs[0].url.endswith(
        "jobUnionId=m1&highlightType=social"
    )
    assert result.manifest.source_total == 4
    assert result.manifest.records_fetched == 4
    assert result.manifest.jobs_mapped == 3
    assert result.manifest.jobs_in_scope == 2
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.duplicate_records == 1
    assert result.manifest.details_fetched == 2
    assert result.manifest.detail_failed == 0
    assert result.manifest.complete is True


def test_xiaohongshu_collects_every_social_position_before_city_scope():
    requested_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requested_pages.append(body["pageNum"])
        assert body["recruitType"] == "social"
        assert body["positionName"] == ""
        assert body["jobTypes"] == []
        assert body["workplaces"] == []
        records = {
            1: [
                {
                    "positionId": 20686,
                    "positionName": "AI测试开发工程师",
                    "workplace": "北京市",
                    "jobType": "测试开发",
                    "duty": "完整职责",
                    "qualification": "完整要求",
                },
                {
                    "positionId": 21000,
                    "positionName": "成都运营岗位",
                    "workplace": "成都市",
                    "jobType": "运营",
                    "duty": "非关键词岗位也应采集",
                },
            ],
            2: [
                {
                    "positionId": 20941,
                    "positionName": "产品经理",
                    "workplace": "上海市，杭州市",
                    "jobType": "产品经理",
                    "duty": "完整职责二",
                    "qualification": "完整要求二",
                }
            ],
        }[body["pageNum"]]
        return httpx.Response(
            200,
            json={
                "statusCode": 200,
                "alertMsg": "成功",
                "data": {
                    "pageNum": body["pageNum"],
                    "pageSize": 2,
                    "total": 3,
                    "totalPage": 2,
                    "list": records,
                },
            },
        )

    collector = XiaohongshuRawCollector(
        {
            "name": "小红书",
            "list_url": "https://example.test/social/position",
            "list_api": "https://example.test/pageQueryPosition",
            "detail_url": "https://example.test/social/position/{job_id}",
            "page_size": 2,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )
    result = collector.collect()

    assert requested_pages == [1, 2]
    assert [job.job_id for job in result.jobs] == ["20686", "20941"]
    assert result.jobs[0].department == "测试开发"
    assert result.jobs[0].description == "完整职责"
    assert result.jobs[0].requirements == "完整要求"
    assert result.jobs[0].url.endswith("/social/position/20686")
    assert result.manifest.source_total == 3
    assert result.manifest.records_fetched == 3
    assert result.manifest.jobs_mapped == 3
    assert result.manifest.jobs_in_scope == 2
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.complete is True


def test_kuaishou_signs_all_pages_and_maps_dictionary_values():
    requested_pages: list[int] = []
    signing_key = "test-signing-key"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/list":
            return httpx.Response(200, text="<html></html>")
        if request.url.path == "/dictionary":
            assert request.url.params["types"] == (
                "workLocation,positionCategory,positionExperience"
            )
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "message": "ok",
                    "result": {
                        "workLocation": [
                            {"code": "Beijing", "name": "北京"},
                            {"code": "Shanghai", "name": "上海"},
                            {"code": "Chengdu", "name": "成都"},
                        ],
                        "positionCategory": [
                            {"code": "J0001", "name": "研发"},
                        ],
                        "positionExperience": [
                            {"code": "3", "name": "3年以上"},
                        ],
                    },
                },
            )

        params = dict(request.url.params)
        page = int(params["pageNum"])
        requested_pages.append(page)
        assert params["positionNatureCode"] == "C001"
        assert params["recruitProject"] == "socialr"
        timestamp = int(request.headers["signtimestamp"])
        assert request.headers["sign"] == KuaishouRawCollector._generate_signature(
            params,
            timestamp,
            signing_key,
        )
        records = {
            1: [
                {
                    "id": 31396,
                    "name": "AI策略运营",
                    "positionCategoryCode": "J0001",
                    "workLocationsCode": ["Beijing", "Shanghai"],
                    "workExperienceCode": "3",
                    "description": "完整职责",
                    "positionDemand": "完整要求",
                },
                {
                    "id": 31397,
                    "name": "成都岗位",
                    "workLocationsCode": ["Chengdu"],
                },
            ],
            2: [
                {
                    "id": 31398,
                    "name": "非AI岗位也应采集",
                    "departmentName": "商业化",
                    "workLocationsCode": ["Shanghai"],
                    "description": "没有关键词",
                }
            ],
        }[page]
        return httpx.Response(
            200,
            json={
                "code": 0,
                "message": "ok",
                "result": {
                    "total": 3,
                    "pageNum": page,
                    "pageSize": 2,
                    "list": records,
                },
            },
        )

    collector = KuaishouRawCollector(
        {
            "name": "快手",
            "list_url": "https://example.test/list",
            "list_api": "https://example.test/positions",
            "dictionary_api": "https://example.test/dictionary",
            "detail_url": "https://example.test/job-info/{job_id}",
            "signing_key": signing_key,
            "page_size": 2,
        },
        COLLECTION_CONFIG,
        _client(handler),
    )
    result = collector.collect()

    assert requested_pages == [1, 2]
    assert [job.job_id for job in result.jobs] == ["31396", "31398"]
    assert result.jobs[0].department == "研发"
    assert result.jobs[0].location == "北京, 上海"
    assert result.jobs[0].experience == "3年以上"
    assert result.jobs[0].description == "完整职责"
    assert result.jobs[0].requirements == "完整要求"
    assert result.jobs[0].url.endswith("/job-info/31396")
    assert result.manifest.source_total == 3
    assert result.manifest.pages_fetched == 2
    assert result.manifest.records_fetched == 3
    assert result.manifest.jobs_mapped == 3
    assert result.manifest.jobs_in_scope == 2
    assert result.manifest.outside_city_scope == 1
    assert result.manifest.complete is True
