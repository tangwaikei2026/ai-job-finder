from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import plistlib
import re

from ops.launchd.run_daily_launchd import build_command


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOT = Path('/Users/waikei/Developer/ai-job-finder')
OLD_ROOT = Path('/Users/waikei/Documents/Codex/ai-job-finder')
PLIST_PATH = ROOT / 'ops' / 'launchd' / 'com.waikei.ai-job-finder.daily.plist'


def test_command_supplies_runtime_local_date_to_official_wrapper():
    runtime_now = datetime(2026, 9, 16, 9, 30, tzinfo=timezone(timedelta(hours=8)))

    command = build_command(runtime_now)

    assert command == [
        str(PRODUCTION_ROOT / 'venv' / 'bin' / 'python'),
        str(PRODUCTION_ROOT / 'tools' / 'run_daily_with_health.py'),
        '--date',
        '2026-09-16',
    ]
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', command[-1])
    assert date.fromisoformat(command[-1]).isoformat() == command[-1]
    assert '--resume-from' not in command
    assert str(OLD_ROOT) not in '\n'.join(command)


def test_plist_keeps_the_single_approved_schedule_and_launchd_contract():
    with PLIST_PATH.open('rb') as handle:
        plist = plistlib.load(handle)

    assert plist['ProgramArguments'] == [
        str(PRODUCTION_ROOT / 'venv' / 'bin' / 'python'),
        str(PRODUCTION_ROOT / 'ops' / 'launchd' / 'run_daily_launchd.py'),
    ]
    assert plist['StartCalendarInterval'] == {'Hour': 9, 'Minute': 30}
    assert plist['WorkingDirectory'] == str(PRODUCTION_ROOT)
    assert plist['StandardOutPath'] == str(
        PRODUCTION_ROOT / 'data' / 'logs' / 'launchd-daily.stdout.log'
    )
    assert plist['StandardErrorPath'] == str(
        PRODUCTION_ROOT / 'data' / 'logs' / 'launchd-daily.stderr.log'
    )
    assert 'RunAtLoad' not in plist
    assert 'KeepAlive' not in plist
    assert 'StartInterval' not in plist
    serialized = PLIST_PATH.read_text(encoding='utf-8')
    assert '--resume-from' not in serialized
    assert str(OLD_ROOT) not in serialized
