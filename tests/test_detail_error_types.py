"""Collectors retain bounded type counters without serializing exception text."""
import json

import httpx
import pytest

from src.collectors.tencent import TencentRawCollector
from src.collectors.meituan import MeituanRawCollector


@pytest.mark.parametrize('collector_type', [TencentRawCollector, MeituanRawCollector])
def test_detail_error_types_are_bounded_sanitized_and_keep_jobs(collector_type, monkeypatch):
    secret = 'Cookie=session-secret Token=token-secret person@example.test'
    # Even a custom class name must not introduce an unbounded or sensitive key.
    private_exception = type('Private' + secret, (Exception,), {})
    errors = [httpx.ReadTimeout(secret), TimeoutError(secret),
              httpx.HTTPStatusError(secret, request=httpx.Request('GET', 'https://example.test'),
                                    response=httpx.Response(500)),
              httpx.ConnectError(secret), ValueError(secret), TypeError(secret),
              KeyError(secret), RuntimeError(secret), private_exception(secret)] * 3
    total = len(errors) + 1
    config = dict(list_api='https://example.test/list', detail_api='https://example.test/detail',
                  list_url='https://example.test', page_size=100, detail_workers=1,
                  detail_delay_seconds=0, detail_strategy='all')
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail('Unexpected HTTP'))) as client:
        collector = collector_type(config, {'cities': ['北京'], 'max_retries': 1}, client)
        if collector_type is TencentRawCollector:
            records = [dict(PostId=str(i), RecruitPostName='AI岗位', LocationName='北京',
                            Responsibility='列表职责') for i in range(total)]
            payload = {'Code': 200, 'Data': {'Count': total, 'Posts': records}}
        else:
            records = [dict(jobUnionId=str(i), name='AI岗位', cityList=[{'name':'北京'}],
                            jobDescription='列表职责') for i in range(total)]
            payload = {'status':1, 'data':{'list':records,'page':{'totalCount':total,'totalPage':1}}}
        monkeypatch.setattr(collector, 'request_json', lambda *a, **kw: payload)

        def detail(target):
            index = int(target.job_id if collector_type is TencentRawCollector else target['jobUnionId'])
            if index < len(errors):
                raise errors[index]
            return {'Requirement':'可靠详情', 'jobRequirement':'可靠详情'}

        monkeypatch.setattr(collector, '_fetch_detail', detail)
        result = collector.collect()
    manifest = result.manifest
    counts = manifest.metadata['detail_error_types']
    assert len(counts) == 9
    assert set(counts.values()) == {3}
    assert sum(counts.values()) == manifest.detail_failed == len(errors)
    assert manifest.details_fetched == 1
    assert len(result.jobs) == total
    assert manifest.status == 'partial' and not manifest.complete
    assert manifest.stopped_by == 'detail_errors'
    assert secret not in json.dumps(manifest.metadata)
    assert set(counts) == {'TimeoutException', 'TimeoutError', 'HTTPStatusError', 'RequestError',
                           'ValueError', 'TypeError', 'KeyError', 'RuntimeError', 'Exception'}
