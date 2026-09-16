from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import plistlib
import re

import pytest

from ops.launchd.run_daily_launchd import (
    EMAIL_ENVIRONMENT_KEYS,
    EmailEnvironmentError,
    build_command,
    load_email_environment,
    rotate_log,
)


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
