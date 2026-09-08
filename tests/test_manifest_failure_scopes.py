"""Manifest enrichment uses existing failure boundaries, with all IO mocked."""
from unittest.mock import MagicMock

import httpx
import pytest

from src.collectors.didi import DidiRawCollector
from src.collectors.feishu import FeishuRawCollector
from src.collectors.meituan import MeituanRawCollector
from src.models import RawJobPosting


@pytest.mark.parametrize('collector_type', [DidiRawCollector, MeituanRawCollector])
def test_detail_failure_id_is_preserved(collector_type, monkeypatch):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        collector = collector_type({'list_url': 'https://example.test', 'list_api': 'https://example.test',
                                    'detail_workers': 1}, {'cities': ['北京'], 'max_retries': 1}, client)
        monkeypatch.setattr(collector, 'request', lambda *args, **kwargs: None)
        row = RawJobPosting(job_id='known-id', platform=collector.platform, company='Company', title='Title', location='北京')
        if collector_type is DidiRawCollector:
            payload = {'meta': {'code': 0}, 'data': {'total': 1, 'items': [{'jdId': 'known-id'}]}}
            monkeypatch.setattr(collector, '_map_list_job', lambda item: row)
        else:
            payload = {'status': 1, 'data': {'page': {'totalCount': 1, 'totalPage': 1}, 'list': [{'jobUnionId': 'known-id'}]}}
            monkeypatch.setattr(collector, '_map_job', lambda item: row)
        monkeypatch.setattr(collector, 'request_json', lambda *args, **kwargs: payload)
        def fail(item):
            raise RuntimeError('mock detail unavailable')
        monkeypatch.setattr(collector, '_fetch_detail', fail)
        result = collector.collect()
    assert result.manifest.detail_failed == 1
    assert result.manifest.detail_failed_job_ids == ['known-id']
    assert result.jobs == [row]


def test_feishu_records_attempted_failed_companies_and_releases_context(monkeypatch):
    import playwright.sync_api
    browser = MagicMock()
    context = browser.new_context.return_value
    playwright_manager = MagicMock()
    playwright_manager.__enter__.return_value.chromium.launch.return_value = browser
    monkeypatch.setattr(playwright.sync_api, 'sync_playwright', lambda: playwright_manager)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        collector = FeishuRawCollector({'companies': [{'name': 'Healthy'}, {'name': 'Failed'}]}, {}, client)
        def collect_company(page, company, size, jobs, manifest):
            if company['name'] == 'Failed':
                raise RuntimeError('mock failure')
        monkeypatch.setattr(collector, '_collect_company', collect_company)
        result = collector.collect()
    assert result.manifest.attempted_companies == ['Healthy', 'Failed']
    assert result.manifest.failed_companies == ['Failed']
    assert result.manifest.stopped_by == 'company_error'
    assert result.manifest.error == 'Failed: mock failure'
    assert context.close.call_count == 2
    browser.close.assert_called_once()
