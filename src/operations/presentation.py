"""Single zh-CN interpretation of the Daily Operations machine model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


HUMAN_OUTCOMES = frozenset({
    'NORMAL',
    'KNOWN_LIMITATION',
    'ACTION_REQUIRED',
    'TECHNICAL_FAILURE',
    'AUTO_RECOVERED',
})


def _platform_label(value: str) -> str:
    labels = {
        'bytedance': '字节跳动',
        'didi': '滴滴',
        'feishu': '飞书',
        'jd': '京东',
        'meituan': '美团',
        'netease': '网易',
        'quark': '夸克',
        'tencent': '腾讯',
        'xiaohongshu': '小红书',
    }
    return labels.get(value, value.replace('_', ' '))


def _stage_label(value: str | None) -> str:
    return {
        'crawl': '岗位采集',
        'clean': '数据清洗',
        'analysis': '岗位分析',
    }.get(value or '', '任务执行')


@dataclass(frozen=True)
class HumanPresentation:
    """Complete human copy shared by CLI and email renderers."""

    run_date: str
    outcome: str
    subject: str
    body: str
    action_required: bool


def human_outcome(machine: Mapping[str, Any]) -> str:
    """Map machine state to the only outcome vocabulary used by human interfaces."""
    status = machine.get('ops_status')
    if status == 'TECHNICAL_FAILURE':
        return 'TECHNICAL_FAILURE'
    if status == 'ACTION_REQUIRED':
        return 'ACTION_REQUIRED'
    recovery = machine.get('automatic_recovery')
    if isinstance(recovery, Mapping) and recovery.get('result') == 'SUCCESS':
        return 'AUTO_RECOVERED'
    mapping = {
        'HEALTHY': 'NORMAL',
        'DEGRADED_KNOWN': 'KNOWN_LIMITATION',
        'ACTION_REQUIRED': 'ACTION_REQUIRED',
        'TECHNICAL_FAILURE': 'TECHNICAL_FAILURE',
    }
    return mapping.get(status, 'TECHNICAL_FAILURE')


def _platforms(machine: Mapping[str, Any], key: str) -> tuple[str, ...]:
    source_summary = machine.get('source_summary')
    sources = source_summary if isinstance(source_summary, Mapping) else {}
    values = sources.get(key, [])
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(_platform_label(str(value)) for value in values)


def _failed_stage(machine: Mapping[str, Any]) -> str:
    for stage in ('crawl', 'clean', 'analysis'):
        if machine.get(f'{stage}_status') == 'FAILED':
            return _stage_label(stage)
    return _stage_label(None)


def build_presentation(machine: Mapping[str, Any]) -> HumanPresentation:
    """Translate one machine result into self-contained human-first copy."""
    outcome = str(machine.get('human_outcome') or human_outcome(machine))
    if outcome not in HUMAN_OUTCOMES:
        outcome = 'TECHNICAL_FAILURE'
    run_date = str(machine.get('date') or machine.get('run_date') or '未知日期')
    known = _platforms(machine, 'known_limitations')
    affected = _platforms(machine, 'action_required')
    no_action_subject = 'AI Job Finder｜今日运行完成｜无需处理'
    action_subject = 'AI Job Finder｜发现新问题｜需要查看'

    if outcome == 'NORMAL':
        subject = no_action_subject
        body = (
            '今天的岗位采集和分析已经完成，你不需要处理。\n\n'
            '没有发现新的异常。\n\n'
            '下一次自动运行：明天 10:00。'
        )
    elif outcome == 'KNOWN_LIMITATION':
        names = '、'.join(known) if known else '部分来源'
        subject = no_action_subject
        body = (
            '今天的岗位采集和分析已经完成，你不需要处理。\n\n'
            '需要知道的一点：\n'
            f'{names}仍存在已知的数据抓取限制，因此今天的{names}岗位数据可能不完整。\n'
            '这是已经备案的问题，本次没有发现新的变化。\n\n'
            '其他数据处理、清洗和分析已经完成。\n\n'
            '系统没有发现新的异常，也没有执行额外的全量重跑。\n\n'
            '下一次自动运行：明天 10:00。'
        )
    elif outcome == 'ACTION_REQUIRED':
        names = '、'.join(affected) if affected else '一个岗位来源'
        subject = action_subject
        body = (
            f'今天的自动任务已经完成，但{names}出现新的数据完整性异常。\n\n'
            '发生了什么：\n'
            f'{names}取得的岗位数据可能不完整，这不是已备案的旧问题。\n\n'
            '系统已经自动：\n'
            '- 保留已有数据\n'
            '- 完成仍可安全执行的后续处理\n\n'
            '系统没有：\n'
            '- 自动再次执行完整岗位采集\n\n'
            '你现在需要：\n'
            '让 GPT 分析该异常。\n\n'
            '命令：\n'
            'venv/bin/python tools/opsctl.py incident --latest --format gpt'
        )
    elif outcome == 'AUTO_RECOVERED':
        recovery = machine.get('automatic_recovery')
        recovery_type = (
            str(recovery.get('type')) if isinstance(recovery, Mapping) else ''
        )
        stage = _stage_label(recovery_type)
        subject = no_action_subject
        body = (
            f'{run_date} 的自动任务曾在{stage}步骤失败。\n\n'
            f'系统今天已从{stage}步骤继续执行，并使用保留的数据完成恢复。\n'
            '恢复过程中没有重新采集岗位，也没有执行额外的全量重跑。\n\n'
            '恢复已经成功完成，你不需要处理。\n\n'
            '下一次自动运行：明天 10:00。'
        )
    else:
        stage = _failed_stage(machine)
        subject = action_subject
        body = (
            '今天的自动任务没有完整完成。\n\n'
            '失败在哪一步：\n'
            f'{stage}。\n\n'
            '已有数据是否安全：\n'
            '已有数据仍然保留，系统没有用空结果覆盖旧数据。\n\n'
            '系统是否自动恢复：\n'
            '系统已检查安全恢复条件，但本次没有成功完成恢复，也没有额外执行全量重跑。\n\n'
            '你现在需要：\n'
            '让 GPT 分析该异常。\n\n'
            '命令：\n'
            'venv/bin/python tools/opsctl.py incident --latest --format gpt'
        )

    warning_rows = (machine.get('source_summary') or {}).get('warnings', [])
    if warning_rows:
        lines = []
        for warning in warning_rows:
            name = _platform_label(str(warning['platform']))
            count = warning.get('detail_failed')
            detail = f'{count} 条岗位详情采集失败' if count is not None else '详情缺口数量待核验'
            lines.append(f'- {name}：{detail}。')
        body = body.replace('没有发现新的异常。', '存在少量可容忍的详情缺口。')
        body = body.replace('系统没有发现新的异常，也没有执行额外的全量重跑。',
                            '存在少量可容忍的详情缺口，没有执行额外的全量重跑。')
        body += '\n\nWarning｜可容忍的详情缺口\n' + '\n'.join(lines)
        body += '\n这些详情缺口无需人工处理；相关岗位已保留，详情仍待核验。'
        if outcome in {'ACTION_REQUIRED', 'TECHNICAL_FAILURE'}:
            body += '\n上面的严重告警仍需按原提示处理。'

    return HumanPresentation(
        run_date=run_date,
        outcome=outcome,
        subject=subject,
        body=body,
        action_required=outcome in {'ACTION_REQUIRED', 'TECHNICAL_FAILURE'},
    )


def render_status(presentation: HumanPresentation) -> str:
    return f'AI Job Finder｜{presentation.run_date}\n\n{presentation.body}\n'


def render_email(presentation: HumanPresentation) -> tuple[str, str]:
    return presentation.subject, presentation.body.rstrip() + '\n'
