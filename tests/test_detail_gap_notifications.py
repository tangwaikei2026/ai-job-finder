"""Offline notification rendering through persisted Ops; no sends or production writes."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.operations.daily_ops import DailyOperations
from src.operations.notifications import NotificationService
from src.operations.presentation import build_presentation, render_status
from tools import opsctl

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/detail_gap_notifications.json').read_text())


def prepare(root, case):
    config = root / 'config.yaml'
    config.write_text('output_dir: data/raw\n')
    operations = DailyOperations(root=root, data_dir=root / 'data', config_path=config)
    health_path = root / 'data/analysis/health' / f"{case['run']['date']}.json"
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text(json.dumps(case['health']))
    artifact = operations.publish(case['run']['date'], run=case['run'], health=case['health'])
    return operations, health_path, artifact


@pytest.mark.parametrize('case', FIXTURE['cases'], ids=lambda c: c['name'])
def test_frozen_notification_bodies_and_cli_agree(tmp_path, capsys, case):
    operations, _, artifact = prepare(tmp_path, case)
    day = case['run']['date']
    # Reload from SQLite and canonical Health, as actual delayed email delivery does.
    machine = operations.machine_status(day)
    assert machine['ops_status'] == artifact['ops_status'] == case['ops_status']
    assert machine['source_summary'] == artifact['source_summary']
    subject, body = NotificationService(operations).render(day)
    presentation = build_presentation(artifact)
    assert body == presentation.body.rstrip() + '\n'
    assert opsctl.main(['--root',str(tmp_path),'status','--date',day]) == 0
    assert capsys.readouterr().out == render_status(presentation)
    assert machine['human_action_required'] is (case['ops_status']=='ACTION_REQUIRED')
    if case['name'] in ('detail_warning','mixed'):
        assert 'Warning｜可容忍的详情缺口' in body
        assert '腾讯：3 条岗位详情采集失败' in body
        assert '美团：1 条岗位详情采集失败' in body
        assert '这些详情缺口无需人工处理' in body
        assert '没有发现新的异常' not in body
        assert '完全成功' not in body
        assert '详情仍待核验' in body
    else:
        assert 'Warning' not in body
        assert '可容忍的详情缺口' not in body
    if case['name']=='complete':
        assert body == ('今天的岗位采集和分析已经完成，你不需要处理。\n\n'
                        '没有发现新的异常。\n\n下一次自动运行：明天 10:00。\n')
    elif case['name']=='detail_warning':
        assert subject.endswith('无需处理')
        assert machine['incident_id'] is None
    else:
        assert subject.endswith('需要查看')
        assert machine['incident_id'] is not None
        affected = '飞书' if case['name']=='mixed' else '腾讯'
        assert f'{affected}出现新的数据完整性异常' in body
        assert '让 GPT 分析该异常' in body
        if case['name']=='mixed':
            assert '上面的严重告警仍需按原提示处理' in body
        else:
            # No-warning severe notification must retain the existing template exactly.
            old_machine=deepcopy(machine)
            old_machine['source_summary'].pop('warnings')
            assert build_presentation(old_machine).body == presentation.body


@pytest.mark.parametrize('damage', ['missing','invalid_json','wrong_date','wrong_state',
                                    'wrong_action','wrong_count','invalid_warnings'])
def test_unavailable_or_mismatched_evidence_never_looks_gap_free(tmp_path, damage):
    case=deepcopy(next(c for c in FIXTURE['cases'] if c['name']=='detail_warning'))
    operations, path, artifact=prepare(tmp_path,case)
    if damage=='missing':
        path.unlink()
    elif damage=='invalid_json':
        path.write_text('{')
    else:
        health=case['health']
        if damage=='wrong_date':
            health['date']='2026-10-07'
        elif damage=='wrong_action':
            health['overall_action']='ACTION_REQUIRED'
        elif damage=='wrong_state':
            for source in health['sources'].values():
                source['source_completeness']='COMPLETE'
        elif damage=='invalid_warnings':
            for source in health['sources'].values():
                source['warnings']=123
        else:
            for source in health['sources'].values():
                source['detail_failed']=True
        path.write_text(json.dumps(health))
    machine=operations.machine_status(case['run']['date'])
    assert machine['ops_status']==artifact['ops_status']=='HEALTHY'
    assert machine['human_action_required'] is False
    _,body=NotificationService(operations).render(case['run']['date'])
    assert 'Warning' in body and '数量待核验' in body
    assert '没有发现新的异常' not in body
    assert '3 条' not in body and '1 条' not in body


def test_warning_cannot_override_technical_failure(tmp_path):
    case=deepcopy(next(c for c in FIXTURE['cases'] if c['name']=='detail_warning'))
    case['run']['analysis']['status']='FAILED'
    case['health'].update(technical_run_health='FAILED',overall_action='ACTION_REQUIRED')
    operations,_,_=prepare(tmp_path,case)
    machine=operations.machine_status(case['run']['date'])
    assert machine['ops_status']=='TECHNICAL_FAILURE'
    subject,body=NotificationService(operations).render(case['run']['date'])
    assert subject.endswith('需要查看')
    assert '今天的自动任务没有完整完成' in body
    assert 'Warning' in body
    assert '上面的严重告警仍需按原提示处理' in body
