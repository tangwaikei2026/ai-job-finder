"""Single human-facing interpretation of the Daily Operations machine model."""
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
        'bytedance': 'ByteDance',
        'didi': 'Didi',
        'feishu': 'Feishu',
        'jd': 'JD',
        'netease': 'NetEase',
        'quark': 'Quark',
        'tencent': 'Tencent',
        'xiaohongshu': 'Xiaohongshu',
    }
    return labels.get(value, value.replace('_', ' ').title())


@dataclass(frozen=True)
class HumanPresentation:
    run_date: str
    outcome: str
    summary: str
    action: str
    known_limitations: tuple[str, ...] = ()
    affected_platforms: tuple[str, ...] = ()
    incident_id: str | None = None

    @property
    def result_label(self) -> str:
        return self.outcome.replace('_', ' ')

    @property
    def email_label(self) -> str:
        labels = {
            'NORMAL': 'Normal',
            'KNOWN_LIMITATION': 'Known Limitation',
            'ACTION_REQUIRED': 'Action Required',
            'TECHNICAL_FAILURE': 'Technical Failure',
            'AUTO_RECOVERED': 'Auto-Recovered',
        }
        return labels[self.outcome]


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


def build_presentation(machine: Mapping[str, Any]) -> HumanPresentation:
    outcome = str(machine.get('human_outcome') or human_outcome(machine))
    if outcome not in HUMAN_OUTCOMES:
        outcome = 'TECHNICAL_FAILURE'
    source_summary = machine.get('source_summary')
    sources = source_summary if isinstance(source_summary, Mapping) else {}
    known = tuple(
        _platform_label(str(value))
        for value in sources.get('known_limitations', [])
    )
    affected = tuple(
        _platform_label(str(value))
        for value in sources.get('action_required', [])
    )
    copy = {
        'NORMAL': (
            'Daily Runner completed successfully.',
            'No action required.',
        ),
        'KNOWN_LIMITATION': (
            'Daily Runner completed with a known, accepted limitation.',
            'No action required.',
        ),
        'ACTION_REQUIRED': (
            (
                f"{', '.join(affected)} has a new completeness regression."
                if affected else 'A new source regression requires review.'
            ),
            'GPT review required.',
        ),
        'TECHNICAL_FAILURE': (
            'The daily pipeline did not complete successfully.',
            'GPT review required.',
        ),
        'AUTO_RECOVERED': (
            'A technical failure was automatically recovered from preserved data.',
            'No action required.',
        ),
    }
    summary, action = copy[outcome]
    return HumanPresentation(
        run_date=str(machine.get('date') or machine.get('run_date') or 'UNKNOWN'),
        outcome=outcome,
        summary=summary,
        action=action,
        known_limitations=known,
        affected_platforms=affected,
        incident_id=machine.get('incident_id'),
    )


def render_status(presentation: HumanPresentation) -> str:
    lines = [
        f'AI Job Finder — {presentation.run_date}',
        '',
        'Result:',
        presentation.result_label,
        '',
        presentation.summary,
        presentation.action,
    ]
    if presentation.known_limitations:
        lines.extend([
            '',
            'Known limitation:',
            ', '.join(presentation.known_limitations),
        ])
    if presentation.affected_platforms:
        lines.extend([
            '',
            'Affected source:',
            ', '.join(presentation.affected_platforms),
        ])
    if presentation.incident_id and presentation.outcome in {
        'ACTION_REQUIRED', 'TECHNICAL_FAILURE'
    }:
        lines.extend(['', 'Incident ID:', presentation.incident_id])
    lines.extend([
        '',
        'Next scheduled run:',
        'Managed by the existing 10:00 local schedule.',
    ])
    return '\n'.join(lines) + '\n'


def render_email(presentation: HumanPresentation) -> tuple[str, str]:
    short_date = presentation.run_date[5:] if len(presentation.run_date) >= 10 else presentation.run_date
    subject = f'AI Job Finder · {short_date} · {presentation.email_label}'
    if presentation.outcome in {'ACTION_REQUIRED', 'TECHNICAL_FAILURE'}:
        lines = ['Problem:', presentation.summary, '']
    else:
        lines = [presentation.summary, '']
    if presentation.outcome in {'NORMAL', 'KNOWN_LIMITATION'}:
        lines.extend(['Data collection:', 'Completed', ''])
    if presentation.known_limitations:
        lines.extend([
            'Known limitation:',
            ', '.join(presentation.known_limitations),
            '',
        ])
    if presentation.outcome in {'ACTION_REQUIRED', 'TECHNICAL_FAILURE'}:
        lines.extend([
            'System response:',
            '- bounded safe recovery evaluated',
            '- existing data preserved when available',
            '',
            'Manual full crawl:',
            'Not performed',
            '',
        ])
    if presentation.outcome == 'AUTO_RECOVERED':
        lines.extend([
            'System response:',
            '- recovery used preserved canonical artifacts',
            '- no historical crawl performed',
            '',
        ])
    lines.extend(['Action required:', presentation.action.replace('.', ''), ''])
    if presentation.incident_id:
        lines.extend(['Incident ID:', presentation.incident_id, ''])
    lines.extend(['Next run:', 'Managed by the existing 10:00 local schedule.'])
    return subject, '\n'.join(lines).rstrip() + '\n'
