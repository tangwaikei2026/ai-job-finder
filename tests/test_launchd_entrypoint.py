from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import plistlib
import re
import subprocess
import sys

import pytest

from ops.launchd.run_daily_launchd import (
    CAFFEINATE,
    EMAIL_ENVIRONMENT_KEYS,
    EmailEnvironmentError,
    build_command,
    build_caffeinated_command,
    load_email_environment,
    rotate_log,
)
from ops.launchd.run_wake_guard import (
    WAKE_GUARD_SECONDS,
    build_command as build_wake_guard_command,
)


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOT = Path('/Users/waikei/Developer/ai-job-finder')
OLD_ROOT = Path('/Users/waikei/Documents/Codex/ai-job-finder')
PLIST_PATH = ROOT / 'ops' / 'launchd' / 'com.waikei.ai-job-finder.daily.plist'
WAKE_GUARD_PLIST_PATH = (
    ROOT / 'ops' / 'launchd' / 'com.waikei.ai-job-finder.wake-guard.plist'
)


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


def test_runner_is_wrapped_by_idle_sleep_assertion_without_changing_arguments():
    runner_command = build_command(
        datetime(2026, 9, 16, 9, 30, tzinfo=timezone(timedelta(hours=8)))
    )

    protected_command = build_caffeinated_command(runner_command)

    assert protected_command[:2] == [str(CAFFEINATE), '-i']
    assert protected_command[2:] == runner_command
    assert '-d' not in protected_command
    assert '-s' not in protected_command


@pytest.mark.skipif(not CAFFEINATE.exists(), reason='macOS caffeinate is unavailable')
def test_caffeinate_propagates_runner_exit_code():
    completed = subprocess.run(
        [
            str(CAFFEINATE),
            '-i',
            sys.executable,
            '-c',
            'raise SystemExit(23)',
        ],
        check=False,
    )

    assert completed.returncode == 23


def test_plist_keeps_the_single_approved_schedule_and_launchd_contract():
    with PLIST_PATH.open('rb') as handle:
        plist = plistlib.load(handle)

    assert plist['ProgramArguments'] == [
        str(PRODUCTION_ROOT / 'venv' / 'bin' / 'python'),
        str(PRODUCTION_ROOT / 'ops' / 'launchd' / 'run_daily_launchd.py'),
    ]
    assert plist['StartCalendarInterval'] == {'Hour': 10, 'Minute': 0}
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


def test_wake_guard_is_single_purpose_and_bounded_across_daily_launch():
    with WAKE_GUARD_PLIST_PATH.open('rb') as handle:
        plist = plistlib.load(handle)

    assert plist['ProgramArguments'] == [
        str(PRODUCTION_ROOT / 'venv' / 'bin' / 'python'),
        str(PRODUCTION_ROOT / 'ops' / 'launchd' / 'run_wake_guard.py'),
    ]
    assert plist['StartCalendarInterval'] == {'Hour': 9, 'Minute': 55}
    assert plist['WorkingDirectory'] == str(PRODUCTION_ROOT)
    assert 'RunAtLoad' not in plist
    assert 'KeepAlive' not in plist
    assert 'StartInterval' not in plist

    command = build_wake_guard_command()
    assert command == [str(CAFFEINATE), '-i', '-t', '600']
    assert WAKE_GUARD_SECONDS == 600
    assert '-d' not in command
    assert '-s' not in command


def test_launchd_log_rotation_is_size_bounded_with_fixed_backups(tmp_path):
    log = tmp_path / 'daily.log'
    log.write_text('current')
    for index in range(1, 5):
        log.with_name(f'daily.log.{index}').write_text(f'backup-{index}')

    assert rotate_log(log, max_bytes=1, backups=3) is True
    assert not log.exists()
    assert log.with_name('daily.log.1').read_text() == 'current'
    assert log.with_name('daily.log.2').read_text() == 'backup-1'
    assert log.with_name('daily.log.3').read_text() == 'backup-2'
    assert not log.with_name('daily.log.4').exists()


def test_missing_email_config_keeps_email_environment_unconfigured(tmp_path):
    environment: dict[str, str] = {}

    assert load_email_environment(tmp_path / 'missing.json', environment=environment) is False
    assert environment == {}


def test_private_email_config_loads_only_supported_keys_without_overrides(tmp_path):
    config = tmp_path / 'email.json'
    config.write_text(
        '{"AI_JOB_FINDER_EMAIL_HOST": "smtp.example.com", '
        '"AI_JOB_FINDER_EMAIL_PASSWORD": "private-value"}',
        encoding='utf-8',
    )
    config.chmod(0o600)
    environment = {'AI_JOB_FINDER_EMAIL_HOST': 'explicit.example.com'}

    assert load_email_environment(config, environment=environment) is True
    assert environment == {
        'AI_JOB_FINDER_EMAIL_HOST': 'explicit.example.com',
        'AI_JOB_FINDER_EMAIL_PASSWORD': 'private-value',
    }


def test_email_config_rejects_permissions_available_to_other_users(tmp_path):
    config = tmp_path / 'email.json'
    config.write_text('{}', encoding='utf-8')
    config.chmod(0o644)

    with pytest.raises(EmailEnvironmentError, match='permissions'):
        load_email_environment(config, environment={})


def test_email_config_rejects_unknown_keys_without_disclosing_values(tmp_path):
    config = tmp_path / 'email.json'
    config.write_text('{"TYPO_EMAIL_PASSWORD": "must-not-appear"}', encoding='utf-8')
    config.chmod(0o600)

    with pytest.raises(EmailEnvironmentError) as raised:
        load_email_environment(config, environment={})

    assert 'must-not-appear' not in str(raised.value)
    assert EMAIL_ENVIRONMENT_KEYS == {
        'AI_JOB_FINDER_EMAIL_HOST',
        'AI_JOB_FINDER_EMAIL_PORT',
        'AI_JOB_FINDER_EMAIL_FROM',
        'AI_JOB_FINDER_EMAIL_TO',
        'AI_JOB_FINDER_EMAIL_USERNAME',
        'AI_JOB_FINDER_EMAIL_PASSWORD',
        'AI_JOB_FINDER_EMAIL_SECURITY',
    }
