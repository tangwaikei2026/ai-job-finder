"""Daily Operations V1 over canonical Runner and Daily Health artifacts.

This module never crawls.  Its only executable recovery paths delegate to the
existing Runner ``resume_from`` contract after reusing that Runner's validators.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from tools.run_daily import (
    _load_config,
    _validate_clean_artifact,
    _validate_existing_observation,
)


SCHEMA_VERSION = 1
OPS_STATUSES = frozenset({
    'HEALTHY',
    'DEGRADED_KNOWN',
    'ACTION_REQUIRED',
    'TECHNICAL_FAILURE',
})
MAX_ERROR_SUMMARY = 1_000
MAX_LOG_EXCERPT = 4_000
Runner = Callable[..., tuple[int, Path, dict[str, Any]]]


class DailyOperationsError(RuntimeError):
    """Daily Operations could not safely interpret or persist its inputs."""


@dataclass
class RecoveryOutcome:
    attempted: bool = False
    type: str | None = None
    result: str = 'NOT_APPLICABLE'
    attempt_count: int = 0
    validator_results: dict[str, str] | None = None
    runner_result: tuple[int, Path, dict[str, Any]] | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'attempted': self.attempted,
            'type': self.type,
            'result': self.result,
            'attempt_count': self.attempt_count,
        }


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _compact(value: Any, limit: int = MAX_ERROR_SUMMARY) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[: limit - 1] + '…'


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def _stage_status(run: Mapping[str, Any], name: str) -> str:
    value = run.get(name)
    return str(value.get('status', 'UNKNOWN')) if isinstance(value, Mapping) else 'UNKNOWN'


def _failed_phase(run: Mapping[str, Any]) -> str | None:
    for name in ('crawl', 'clean', 'analysis'):
        if _stage_status(run, name) == 'FAILED':
            return name
    return None


def _stage_error(run: Mapping[str, Any], phase: str | None) -> str:
    if phase is None:
        return ''
    value = run.get(phase)
    return _compact(value.get('error', '')) if isinstance(value, Mapping) else ''


class DailyOperations:
    """Persist one rebuildable operational view per production date."""

    def __init__(
        self,
        *,
        data_dir: Path,
        root: Path,
        config_path: Path,
        trigger: str = 'daily_wrapper',
        generated_at: Callable[[], str] = _now,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.root = Path(root).resolve()
        self.config_path = Path(config_path).resolve()
        self.trigger = trigger
        self.generated_at = generated_at
        self.ops_dir = self.data_dir / 'ops'
        self.db_path = self.ops_dir / 'ops.sqlite3'

    def _connect(self) -> sqlite3.Connection:
        self.ops_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                run_date TEXT NOT NULL UNIQUE,
                generated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                git_head TEXT,
                trigger TEXT NOT NULL,
                ops_status TEXT NOT NULL,
                runner_status TEXT NOT NULL,
                crawl_status TEXT NOT NULL,
                clean_status TEXT NOT NULL,
                analysis_status TEXT NOT NULL,
                technical_run_health TEXT NOT NULL,
                overall_action TEXT NOT NULL,
                human_action_required INTEGER NOT NULL,
                gpt_review_required INTEGER NOT NULL,
                incident_id TEXT,
                error_type TEXT,
                error_summary TEXT
            );
            CREATE TABLE IF NOT EXISTS sources (
                run_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                source_completeness TEXT NOT NULL,
                limitation_state TEXT NOT NULL,
                matched_limitation_id TEXT,
                PRIMARY KEY (run_id, platform),
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                attempt_count INTEGER NOT NULL CHECK (attempt_count <= 1),
                result TEXT NOT NULL,
                validator_results TEXT NOT NULL,
                error_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (run_id, action_type)
            );
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                failed_phase TEXT,
                platform TEXT,
                error_type TEXT NOT NULL,
                error_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        connection.commit()
        return connection

    @staticmethod
    def _recovery_type(run: Mapping[str, Any]) -> str | None:
        if run.get('status') != 'FAILED':
            return None
        if _stage_status(run, 'clean') == 'FAILED':
            return 'clean'
        if (
            _stage_status(run, 'clean') == 'SUCCESS'
            and _stage_status(run, 'analysis') == 'FAILED'
        ):
            return 'analysis'
        return None

    def _validate_recovery_inputs(
        self, run_date: str, recovery_type: str
    ) -> tuple[bool, dict[str, str]]:
        results: dict[str, str] = {}
        try:
            raw_dir, data_dir = _load_config(self.config_path)
            if data_dir.resolve() != self.data_dir:
                raise ValueError('configured data root does not match run artifact root')
            raw_rows, manifest = _validate_existing_observation(
                raw_dir / f'{run_date}.json',
                raw_dir / f'{run_date}_manifest.json',
                self.config_path,
            )
            results['raw_manifest'] = 'PASS'
        except Exception as exc:
            results['raw_manifest'] = f'FAIL: {_compact(exc)}'
            return False, results
        if recovery_type == 'analysis':
            try:
                _validate_clean_artifact(
                    self.data_dir / 'clean' / f'{run_date}.json',
                    manifest,
                    raw_rows,
                )
                results['clean'] = 'PASS'
            except Exception as exc:
                results['clean'] = f'FAIL: {_compact(exc)}'
                return False, results
        return True, results

    def attempt_recovery(
        self,
        run_date: str,
        run: Mapping[str, Any],
        *,
        runner: Runner,
    ) -> RecoveryOutcome:
        """Attempt at most one deterministic downstream recovery for a date."""
        recovery_type = self._recovery_type(run)
        if recovery_type is None:
            return RecoveryOutcome()
        if run.get('resume_from') == recovery_type:
            validators = {'canonical_resume_marker': 'PASS'}
            timestamp = self.generated_at()
            error = _stage_error(run, _failed_phase(run)) or 'resume runner failed'
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO actions(
                        run_id, action_type, attempt_count, result,
                        validator_results, error_summary, created_at, updated_at
                    ) VALUES (?, ?, 1, 'FAILED', ?, ?, ?, ?)
                    """,
                    (
                        run_date,
                        recovery_type,
                        json.dumps(validators, sort_keys=True),
                        _compact(error),
                        timestamp,
                        timestamp,
                    ),
                )
            return RecoveryOutcome(
                attempted=True,
                type=recovery_type,
                result='FAILED',
                attempt_count=1,
                validator_results=validators,
                error=error,
            )
        valid, validator_results = self._validate_recovery_inputs(run_date, recovery_type)
        if not valid:
            invalid = 'RAW' if validator_results.get('raw_manifest') != 'PASS' else 'CLEAN'
            return RecoveryOutcome(
                type=recovery_type,
                result=f'SKIPPED_INVALID_{invalid}',
                validator_results=validator_results,
            )

        timestamp = self.generated_at()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO actions(
                    run_id, action_type, attempt_count, result, validator_results,
                    created_at, updated_at
                ) VALUES (?, ?, 1, 'IN_PROGRESS', ?, ?, ?)
                """,
                (
                    run_date,
                    recovery_type,
                    json.dumps(validator_results, ensure_ascii=False, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
            if cursor.rowcount == 0:
                existing = connection.execute(
                    'SELECT * FROM actions WHERE run_id=? AND action_type=?',
                    (run_date, recovery_type),
                ).fetchone()
                return RecoveryOutcome(
                    attempted=True,
                    type=recovery_type,
                    result=str(existing['result']),
                    attempt_count=int(existing['attempt_count']),
                    validator_results=json.loads(existing['validator_results']),
                    error=existing['error_summary'],
                )

        outcome = RecoveryOutcome(
            attempted=True,
            type=recovery_type,
            result='IN_PROGRESS',
            attempt_count=1,
            validator_results=validator_results,
        )
        try:
            result = runner(
                run_date,
                config_path=self.config_path,
                root=self.root,
                resume_from=recovery_type,
            )
            outcome.runner_result = result
            code, status_path, recovered = result
            persisted = json.loads(Path(status_path).read_text(encoding='utf-8'))
            success = (
                code == 0
                and isinstance(recovered, Mapping)
                and recovered.get('date') == run_date
                and recovered.get('status') in {'SUCCESS', 'DEGRADED'}
                and persisted.get('date') == run_date
                and persisted.get('status') == recovered.get('status')
            )
            if success:
                outcome.result = 'SUCCESS'
            else:
                outcome.result = 'FAILED'
                phase = _failed_phase(recovered) if isinstance(recovered, Mapping) else None
                outcome.error = _stage_error(recovered, phase) or 'resume runner failed validation'
        except Exception as exc:
            outcome.result = 'FAILED'
            outcome.error = _compact(exc)

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE actions SET result=?, error_summary=?, updated_at=?
                WHERE run_id=? AND action_type=?
                """,
                (
                    outcome.result,
                    _compact(outcome.error) if outcome.error else None,
                    self.generated_at(),
                    run_date,
                    recovery_type,
                ),
            )
        return outcome

    def _git_head(self) -> str:
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return 'UNKNOWN'

    def _ref(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root))
        except ValueError:
            return str(path.resolve())

    def _evidence_refs(self, run_date: str) -> dict[str, str]:
        return {
            'run': self._ref(self.data_dir / 'analysis' / 'runs' / f'{run_date}.json'),
            'health': self._ref(self.data_dir / 'analysis' / 'health' / f'{run_date}.json'),
            'manifest': self._ref(self.data_dir / 'raw' / f'{run_date}_manifest.json'),
            'raw': self._ref(self.data_dir / 'raw' / f'{run_date}.json'),
            'clean': self._ref(self.data_dir / 'clean' / f'{run_date}.json'),
            'stdout': self._ref(self.data_dir / 'logs' / 'launchd-daily.stdout.log'),
            'stderr': self._ref(self.data_dir / 'logs' / 'launchd-daily.stderr.log'),
        }

    def _log_excerpt(self) -> str:
        path = self.data_dir / 'logs' / 'launchd-daily.stderr.log'
        try:
            with path.open('rb') as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - 16_384))
                text = handle.read().decode('utf-8', errors='replace')
        except OSError:
            return ''
        lines = text.splitlines()
        markers = ('error', 'exception', 'traceback', 'failed', 'failure')
        selected = [line for line in lines if any(word in line.lower() for word in markers)]
        excerpt = '\n'.join((selected or lines[-20:])[-40:])
        return excerpt[-MAX_LOG_EXCERPT:]

    @staticmethod
    def _source_summary(sources: Mapping[str, Any]) -> dict[str, Any]:
        healthy: list[str] = []
        known: list[str] = []
        action: list[str] = []
        for platform, value in sorted(sources.items()):
            if not isinstance(value, Mapping):
                raise DailyOperationsError(f'invalid Daily Health source: {platform}')
            state = value.get('limitation_state')
            if state == 'NORMAL':
                healthy.append(platform)
            elif state == 'KNOWN_LIMITATION':
                known.append(platform)
            elif state == 'NEW_REGRESSION':
                action.append(platform)
            else:
                raise DailyOperationsError(f'invalid limitation_state for {platform}')
        return {
            'healthy_count': len(healthy),
            'healthy': healthy,
            'known_limitation_count': len(known),
            'known_limitations': known,
            'action_required_count': len(action),
            'action_required': action,
        }

    @staticmethod
    def _ops_status(
        technical: str, overall_action: str, source_summary: Mapping[str, Any]
    ) -> str:
        if technical != 'SUCCESS':
            return 'TECHNICAL_FAILURE'
        if overall_action == 'ACTION_REQUIRED' or source_summary['action_required_count']:
            return 'ACTION_REQUIRED'
        if source_summary['known_limitation_count']:
            return 'DEGRADED_KNOWN'
        return 'HEALTHY'

    def publish(
        self,
        run_date: str,
        *,
        run: Mapping[str, Any],
        health: Mapping[str, Any] | None,
        recovery: RecoveryOutcome | None = None,
        orchestration_error: str | None = None,
    ) -> dict[str, Any]:
        """Write the current machine/human view and idempotently upsert SQLite."""
        recovery = recovery or RecoveryOutcome()
        if run.get('date') != run_date:
            raise DailyOperationsError('run date does not match Operations date')
        runner_status = str(run.get('status', 'FAILED'))
        resume_marker = run.get('resume_from')
        if (
            not recovery.attempted
            and resume_marker in {'clean', 'analysis'}
        ):
            recovery = RecoveryOutcome(
                attempted=True,
                type=str(resume_marker),
                result='SUCCESS' if runner_status in {'SUCCESS', 'DEGRADED'} else 'FAILED',
                attempt_count=1,
                validator_results={'canonical_resume_marker': 'PASS'},
            )
        crawl_status = _stage_status(run, 'crawl')
        clean_status = _stage_status(run, 'clean')
        analysis_status = _stage_status(run, 'analysis')
        sources: Mapping[str, Any] = {}
        if health is not None:
            if health.get('date') != run_date:
                raise DailyOperationsError('Daily Health date does not match Operations date')
            technical = str(health.get('technical_run_health'))
            overall_action = str(health.get('overall_action'))
            source_value = health.get('sources')
            if technical not in {'SUCCESS', 'FAILED'}:
                raise DailyOperationsError('invalid technical_run_health')
            if overall_action not in {'NO_NEW_ACTION', 'ACTION_REQUIRED'}:
                raise DailyOperationsError('invalid overall_action')
            if not isinstance(source_value, Mapping):
                raise DailyOperationsError('invalid Daily Health sources')
            sources = source_value
        else:
            technical = 'FAILED'
            overall_action = 'ACTION_REQUIRED'
        source_summary = self._source_summary(sources)
        ops_status = self._ops_status(technical, overall_action, source_summary)
        if orchestration_error:
            ops_status = 'TECHNICAL_FAILURE'
            technical = 'FAILED'
            overall_action = 'ACTION_REQUIRED'
        human_required = ops_status in {'ACTION_REQUIRED', 'TECHNICAL_FAILURE'}
        gpt_required = human_required
        failed_phase = _failed_phase(run)
        error_summary = _compact(
            orchestration_error or recovery.error or _stage_error(run, failed_phase)
        )
        error_type = (
            'OPS_ORCHESTRATION_ERROR' if orchestration_error
            else 'RECOVERY_FAILED' if recovery.result == 'FAILED'
            else f'{failed_phase.upper()}_FAILURE' if failed_phase
            else 'SOURCE_REGRESSION' if source_summary['action_required_count']
            else None
        )
        incident_id = f'INC-{run_date}' if human_required else None
        generated_at = self.generated_at()
        evidence = self._evidence_refs(run_date)
        artifact: dict[str, Any] = {
            'schema_version': SCHEMA_VERSION,
            'date': run_date,
            'generated_at': generated_at,
            'ops_status': ops_status,
            'runner_status': runner_status,
            'crawl_status': crawl_status,
            'clean_status': clean_status,
            'analysis_status': analysis_status,
            'technical_run_health': technical,
            'overall_action': overall_action,
            'source_summary': source_summary,
            'automatic_recovery': recovery.as_dict(),
            'human_action_required': human_required,
            'gpt_review_required': gpt_required,
            'incident_id': incident_id,
            'canonical_evidence_refs': evidence,
        }
        git_head = self._git_head()
        with self._connect() as connection:
            if recovery.attempted and recovery.type in {'clean', 'analysis'}:
                connection.execute(
                    """
                    INSERT INTO actions(
                        run_id, action_type, attempt_count, result,
                        validator_results, error_summary, created_at, updated_at
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, action_type) DO UPDATE SET
                        result=excluded.result,
                        validator_results=excluded.validator_results,
                        error_summary=excluded.error_summary,
                        updated_at=excluded.updated_at
                    """,
                    (
                        run_date,
                        recovery.type,
                        recovery.result,
                        json.dumps(recovery.validator_results or {}, sort_keys=True),
                        _compact(recovery.error) if recovery.error else None,
                        generated_at,
                        generated_at,
                    ),
                )
            connection.execute(
                """
                INSERT INTO runs(
                    run_id, run_date, generated_at, updated_at, git_head, trigger,
                    ops_status, runner_status, crawl_status, clean_status,
                    analysis_status, technical_run_health, overall_action,
                    human_action_required, gpt_review_required, incident_id,
                    error_type, error_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    git_head=excluded.git_head,
                    trigger=excluded.trigger,
                    ops_status=excluded.ops_status,
                    runner_status=excluded.runner_status,
                    crawl_status=excluded.crawl_status,
                    clean_status=excluded.clean_status,
                    analysis_status=excluded.analysis_status,
                    technical_run_health=excluded.technical_run_health,
                    overall_action=excluded.overall_action,
                    human_action_required=excluded.human_action_required,
                    gpt_review_required=excluded.gpt_review_required,
                    incident_id=excluded.incident_id,
                    error_type=excluded.error_type,
                    error_summary=excluded.error_summary
                """,
                (
                    run_date, run_date, generated_at, generated_at, git_head,
                    self.trigger, ops_status, runner_status, crawl_status,
                    clean_status, analysis_status, technical, overall_action,
                    int(human_required), int(gpt_required), incident_id,
                    error_type, error_summary or None,
                ),
            )
            connection.execute('DELETE FROM sources WHERE run_id=?', (run_date,))
            for platform, value in sources.items():
                connection.execute(
                    """
                    INSERT INTO sources(
                        run_id, platform, source_completeness, limitation_state,
                        matched_limitation_id
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        run_date,
                        platform,
                        str(value.get('source_completeness', 'UNKNOWN')),
                        str(value.get('limitation_state')),
                        value.get('matched_limitation_id'),
                    ),
                )
            if incident_id:
                platforms = ', '.join(source_summary['action_required']) or None
                connection.execute(
                    """
                    INSERT INTO incidents(
                        incident_id, run_id, status, failed_phase, platform,
                        error_type, error_summary, created_at, updated_at
                    ) VALUES (?, ?, 'OPEN', ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        status='OPEN', failed_phase=excluded.failed_phase,
                        platform=excluded.platform, error_type=excluded.error_type,
                        error_summary=excluded.error_summary,
                        updated_at=excluded.updated_at
                    """,
                    (
                        incident_id, run_date, failed_phase, platforms,
                        error_type or 'UNKNOWN', error_summary or None,
                        generated_at, generated_at,
                    ),
                )
            else:
                connection.execute(
                    "UPDATE incidents SET status='RESOLVED', updated_at=? WHERE run_id=?",
                    (generated_at, run_date),
                )

        _write_json_atomic(self.ops_dir / 'latest.json', artifact)
        _write_text_atomic(self.ops_dir / 'latest.md', self._render_summary(artifact))
        incident_path = self.ops_dir / 'latest_incident.md'
        if incident_id:
            _write_text_atomic(
                incident_path,
                self._render_incident(
                    artifact,
                    run=run,
                    git_head=git_head,
                    failed_phase=failed_phase,
                    error_type=error_type or 'UNKNOWN',
                    error_summary=error_summary,
                    recovery=recovery,
                ),
            )
        else:
            incident_path.unlink(missing_ok=True)
        return artifact

    @staticmethod
    def _render_summary(artifact: Mapping[str, Any]) -> str:
        sources = artifact['source_summary']
        recovery = artifact['automatic_recovery']
        overall = 'NORMAL' if artifact['ops_status'] in {'HEALTHY', 'DEGRADED_KNOWN'} else artifact['ops_status'].replace('_', ' ')
        healthy = ', '.join(sources['healthy']) or 'None'
        known = ', '.join(sources['known_limitations']) or 'None'
        attention = ', '.join(sources['action_required']) or 'None'
        action = 'None.' if not artifact['human_action_required'] else 'Review the current incident handoff.'
        recovery_text = 'Not needed.'
        if recovery['attempted']:
            recovery_text = f"{recovery['type']} resume: {recovery['result']} (attempt {recovery['attempt_count']}/1)."
        elif recovery['result'] != 'NOT_APPLICABLE':
            recovery_text = f"Not attempted: {recovery['result']}."
        incident_section = ''
        if artifact['human_action_required']:
            if sources['action_required']:
                problem = ', '.join(
                    f'{platform} — NEW_REGRESSION'
                    for platform in sources['action_required']
                )
            else:
                failed = [
                    name
                    for name, status in (
                        ('Crawl', artifact['crawl_status']),
                        ('Clean', artifact['clean_status']),
                        ('Analysis', artifact['analysis_status']),
                    )
                    if status == 'FAILED'
                ]
                problem = f"{' / '.join(failed) or 'Operations'} technical failure"
            incident_section = (
                'Problem:\n'
                f'{problem}\n\n'
                'System response:\n'
                '- No automatic full Crawl was started.\n'
                f'- Downstream recovery: {recovery_text}\n\n'
            )
        return (
            '# AI Job Finder Daily Status\n\n'
            f"Date: {artifact['date']}\n\n"
            'Overall:\n'
            f'{overall}\n\n'
            'Execution:\n'
            f"Scheduled run {'completed' if artifact['technical_run_health'] == 'SUCCESS' else 'needs attention'}.\n\n"
            'Pipeline:\n'
            f"Crawl: {artifact['crawl_status']}\n"
            f"Clean: {artifact['clean_status']}\n"
            f"Analysis: {artifact['analysis_status']}\n"
            f"Technical Health: {artifact['technical_run_health']}\n\n"
            'Sources:\n'
            f'Healthy: {healthy}\n'
            f'Known limitations: {known}\n'
            f'Needs review: {attention}\n\n'
            f'{incident_section}'
            'Automatic recovery:\n'
            f'{recovery_text}\n\n'
            'Action:\n'
            f'{action}\n\n'
            'GPT review:\n'
            f"{'REQUIRED' if artifact['gpt_review_required'] else 'NOT REQUIRED'}\n\n"
            'Next scheduled run:\n'
            'Managed by the unchanged launchd schedule.\n'
        )

    def _render_incident(
        self,
        artifact: Mapping[str, Any],
        *,
        run: Mapping[str, Any],
        git_head: str,
        failed_phase: str | None,
        error_type: str,
        error_summary: str,
        recovery: RecoveryOutcome,
    ) -> str:
        crawl = run.get('crawl') if isinstance(run.get('crawl'), Mapping) else {}
        retry_attempts = crawl.get('retried_platforms', [])
        validators = recovery.validator_results or {}
        raw_preserved = (
            (self.data_dir / 'raw' / f"{artifact['date']}.json").is_file()
            and (self.data_dir / 'raw' / f"{artifact['date']}_manifest.json").is_file()
        )
        evidence_lines = '\n'.join(
            f'- {name}: `{path}`' for name, path in artifact['canonical_evidence_refs'].items()
        )
        excerpt = self._log_excerpt()
        excerpt_block = f'\n## Compact error log excerpt\n\n```text\n{excerpt}\n```\n' if excerpt else ''
        platform = ', '.join(artifact['source_summary']['action_required']) or 'N/A'
        return (
            '# AI Job Finder Incident Handoff\n\n'
            f"Incident: {artifact['incident_id']}\n"
            f"Run date: {artifact['date']}\n"
            f'Git HEAD: {git_head}\n'
            f'Trigger: {self.trigger}\n'
            f"Failed phase: {failed_phase or 'N/A'}\n"
            f'Platform: {platform}\n'
            f"Runner status: {artifact['runner_status']}\n"
            f'Error type: {error_type}\n'
            f"Error message: {error_summary or 'See canonical artifacts.'}\n"
            f'Retry attempts: {json.dumps(retry_attempts, ensure_ascii=False)}\n'
            f'Validator results: {json.dumps(validators, ensure_ascii=False, sort_keys=True)}\n'
            f"Technical health: {artifact['technical_run_health']}\n"
            f"Overall action: {artifact['overall_action']}\n"
            f"Data preserved: {'YES' if raw_preserved else 'UNKNOWN'}\n"
            f"Automatic recovery: {recovery.result} ({recovery.attempt_count}/1)\n\n"
            '## Relevant artifact paths\n\n'
            f'{evidence_lines}\n'
            f'{excerpt_block}\n'
            '## Question for ChatGPT\n\n'
            '请判断该 incident 的根因、是否需要修复、是否改变业务 contract，'
            '并给出 Codex 下一步指令。\n'
        )


def write_ops_failure_evidence(
    *,
    data_dir: Path,
    run_date: str,
    error: str,
    run: Mapping[str, Any] | None = None,
) -> None:
    """Best-effort evidence when normal Ops publication itself fails."""
    ops_dir = Path(data_dir) / 'ops'
    run = run or {}
    incident_id = f'INC-{run_date}'
    artifact = {
        'schema_version': SCHEMA_VERSION,
        'date': run_date,
        'generated_at': _now(),
        'ops_status': 'TECHNICAL_FAILURE',
        'runner_status': str(run.get('status', 'UNKNOWN')),
        'crawl_status': _stage_status(run, 'crawl'),
        'clean_status': _stage_status(run, 'clean'),
        'analysis_status': _stage_status(run, 'analysis'),
        'technical_run_health': 'FAILED',
        'overall_action': 'ACTION_REQUIRED',
        'source_summary': {
            'healthy_count': 0, 'healthy': [],
            'known_limitation_count': 0, 'known_limitations': [],
            'action_required_count': 0, 'action_required': [],
        },
        'automatic_recovery': RecoveryOutcome().as_dict(),
        'human_action_required': True,
        'gpt_review_required': True,
        'incident_id': incident_id,
        'canonical_evidence_refs': {},
        'ops_error': _compact(error),
    }
    _write_json_atomic(ops_dir / 'latest.json', artifact)
    _write_text_atomic(
        ops_dir / 'latest.md',
        '# AI Job Finder Daily Status\n\n'
        f'Date: {run_date}\n\nOverall:\nTECHNICAL FAILURE\n\n'
        'Action:\nDaily Operations summary generation needs review.\n',
    )
    _write_text_atomic(
        ops_dir / 'latest_incident.md',
        '# AI Job Finder Incident Handoff\n\n'
        f'Incident: {incident_id}\nRun date: {run_date}\n'
        'Error type: OPS_SUMMARY_FAILURE\n'
        f'Error message: {_compact(error)}\n\n'
        '请判断该 incident 的根因、是否需要修复、是否改变业务 contract，'
        '并给出 Codex 下一步指令。\n',
    )


def _read_mapping(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise DailyOperationsError(f'{label} is unavailable: {exc}') from exc
    if not isinstance(value, Mapping):
        raise DailyOperationsError(f'{label} must contain an object')
    return value


def rebuild_daily_operations(
    run_date: str,
    *,
    data_dir: Path,
    root: Path,
    config_path: Path,
    trigger: str = 'offline_rebuild',
) -> dict[str, Any]:
    """Rebuild Ops only from canonical artifacts; never invoke the Runner."""
    data_dir = Path(data_dir)
    run = _read_mapping(
        data_dir / 'analysis' / 'runs' / f'{run_date}.json',
        'canonical run artifact',
    )
    health_path = data_dir / 'analysis' / 'health' / f'{run_date}.json'
    try:
        health = _read_mapping(health_path, 'canonical Daily Health artifact')
    except DailyOperationsError:
        health = None
    operations = DailyOperations(
        data_dir=data_dir,
        root=root,
        config_path=config_path,
        trigger=trigger,
    )
    return operations.publish(run_date, run=run, health=health)


def _date_arg(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError('date must use YYYY-MM-DD') from exc


def main(argv: Sequence[str] | None = None) -> int:
    root_default = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Rebuild Daily Operations from canonical artifacts.')
    parser.add_argument('--date', required=True, type=_date_arg)
    parser.add_argument('--root', type=Path, default=root_default)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args(argv)
    data_dir = args.data_dir or args.root / 'data'
    config_path = args.config or args.root / 'config.yaml'
    try:
        artifact = rebuild_daily_operations(
            args.date,
            data_dir=data_dir,
            root=args.root,
            config_path=config_path,
        )
    except DailyOperationsError as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps({
        'ops_status': artifact['ops_status'],
        'latest_json': str(Path(data_dir) / 'ops' / 'latest.json'),
        'latest_markdown': str(Path(data_dir) / 'ops' / 'latest.md'),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
