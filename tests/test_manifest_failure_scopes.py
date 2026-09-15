"""Manifest enrichment uses existing failure boundaries, with all IO mocked."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from src.collectors.didi import DidiRawCollector
from src.collectors.bytedance import ByteDanceRawCollector
from src.collectors.feishu import FeishuRawCollector
from src.collectors.meituan import MeituanRawCollector
from src.models import RawJobPosting


def _mock_bytedance_browser(monkeypatch):
    import playwright.sync_api

    browser = MagicMock()
    context = browser.new_context.return_value
    playwright_manager = MagicMock()
    playwright_manager.__enter__.return_value.chromium.launch.return_value = browser
    monkeypatch.setattr(playwright.sync_api, 'sync_playwright', lambda: playwright_manager)
    return browser, context


def test_bytedance_late_page_failure_finalizes_retained_job_count(monkeypatch):
    import src.collectors.bytedance as bytedance_module

    browser, context = _mock_bytedance_browser(monkeypatch)
    monkeypatch.setattr(
        bytedance_module,
        'bootstrap_portal',
        lambda *args, **kwargs: SimpleNamespace(
            filter_data={'city_list': [{'name': '北京市', 'code': 'CT_11'}]},
        ),
    )
    calls = 0

    def fetch_page(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('mock late page failure')
        return {
            'data': {
                'count': 2,
                'job_post_list': [{
                    'id': 'known-id',
                    'title': 'AI 测试工程师',
                    'city_info': {'name': '北京'},
                }],
            },
        }

    monkeypatch.setattr(bytedance_module, 'fetch_portal_page', fetch_page)
    with httpx.Client() as client:
        collector = ByteDanceRawCollector(
            {'name': '字节跳动', 'list_url': 'https://example.test', 'page_size': 1},
            {'cities': ['北京'], 'include_unknown_location': False},
            client,
        )
        result = collector.collect()

    assert [job.job_id for job in result.jobs] == ['known-id']
    assert result.manifest.status == 'error'
    assert result.manifest.complete is False
    assert result.manifest.stopped_by == 'error'
    assert result.manifest.error == 'mock late page failure'
    assert result.manifest.jobs_in_scope == len(result.jobs) == 1
    assert result.manifest.records_fetched == (
        result.manifest.jobs_mapped
        + result.manifest.duplicate_records
        + result.manifest.missing_job_id
    )
    assert result.manifest.jobs_mapped == (
        result.manifest.jobs_in_scope + result.manifest.outside_city_scope
    )
    context.close.assert_called_once()
    browser.close.assert_called_once()


def test_bytedance_early_failure_keeps_empty_scope_counters(monkeypatch):
    import src.collectors.bytedance as bytedance_module

    _mock_bytedance_browser(monkeypatch)

    def fail_bootstrap(*args, **kwargs):
        raise RuntimeError('mock early failure')

    monkeypatch.setattr(bytedance_module, 'bootstrap_portal', fail_bootstrap)
    with httpx.Client() as client:
        collector = ByteDanceRawCollector(
            {'name': '字节跳动', 'list_url': 'https://example.test'},
            {'cities': ['北京']},
            client,
        )
        result = collector.collect()

    assert result.jobs == []
    assert result.manifest.jobs_in_scope == 0
    assert result.manifest.status == 'error'
    assert result.manifest.complete is False


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
        if collector_type is DidiRawCollector:
            monkeypatch.setattr(
                collector,
                'request_json',
                lambda *args, **kwargs: (
                    {'meta': {'code': 0}, 'data': {'total': 1, 'items': []}}
                    if kwargs.get('params', {}).get('page') == 2
                    else payload
                ),
            )
        else:
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
