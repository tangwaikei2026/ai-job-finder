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
from src.operations.presentation import human_outcome


SCHEMA_VERSION = 2
OPS_STATUSES = frozenset({
    'HEALTHY',
    'DEGRADED_KNOWN',
    'ACTION_REQUIRED',
    'TECHNICAL_FAILURE',
})
MAX_ERROR_SUMMARY = 1_000
MAX_HISTORICAL_RECOVERY_DATES = 2
MAX_RECOVERY_ATTEMPTS = 1
Runner = Callable[..., tuple[int, Path, dict[str, Any]]]
HealthGenerator = Callable[..., tuple[Path, dict[str, Any]]]


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


@dataclass(frozen=True)
class RecoveryCandidate:
    run_date: str
    recovery_type: str | None
    eligible: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            'date': self.run_date,
            'recovery_type': self.recovery_type,
            'eligible': self.eligible,
            'reason': self.reason,
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
                error_summary TEXT,
                human_outcome TEXT
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
            CREATE TABLE IF NOT EXISTS notifications (
                run_date TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                delivery_status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count <= 3),
                last_attempt_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (run_date, notification_type)
            );
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        run_columns = {
            str(row['name'])
            for row in connection.execute('PRAGMA table_info(runs)').fetchall()
        }
        if 'human_outcome' not in run_columns:
            connection.execute('ALTER TABLE runs ADD COLUMN human_outcome TEXT')
        connection.execute(
            """
            UPDATE runs SET human_outcome = CASE ops_status
                WHEN 'HEALTHY' THEN 'NORMAL'
                WHEN 'DEGRADED_KNOWN' THEN 'KNOWN_LIMITATION'
                WHEN 'ACTION_REQUIRED' THEN 'ACTION_REQUIRED'
                ELSE 'TECHNICAL_FAILURE'
            END
            WHERE human_outcome IS NULL
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
            'analysis_events': self._ref(self.data_dir / 'analysis' / 'events' / f'{run_date}.jsonl'),
            'analysis_audit': self._ref(self.data_dir / 'analysis' / 'audit' / f'{run_date}_bundle.json'),
            'manifest': self._ref(self.data_dir / 'raw' / f'{run_date}_manifest.json'),
            'raw': self._ref(self.data_dir / 'raw' / f'{run_date}.json'),
            'clean': self._ref(self.data_dir / 'clean' / f'{run_date}.json'),
        }

    @staticmethod
    def _source_summary(sources: Mapping[str, Any]) -> dict[str, Any]:
        healthy: list[str] = []
        known: list[str] = []
        action: list[str] = []
        warnings: list[dict[str, Any]] = []
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
            warning_codes = value.get('warnings')
            if ((isinstance(warning_codes, list) and 'TOLERATED_DETAIL_GAP' in warning_codes)
                    or (state == 'NORMAL' and value.get('source_completeness') == 'PARTIAL')):
                # A historical SQLite view retains PARTIAL even if its optional
                # health evidence is unavailable. Never describe it as gap-free.
                count = value.get('detail_failed')
                warnings.append({
                    'platform': platform,
                    'detail_failed': count if type(count) is int and count > 0 else None,
                })
        return {
            'healthy_count': len(healthy),
            'healthy': healthy,
            'known_limitation_count': len(known),
            'known_limitations': known,
            'action_required_count': len(action),
            'action_required': action,
            'warnings': warnings,
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
        write_latest: bool = True,
    ) -> dict[str, Any]:
        """Write the machine view and idempotently upsert the rebuildable index."""
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
        artifact['human_outcome'] = human_outcome(artifact)
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
                    error_type, error_summary, human_outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    error_summary=excluded.error_summary,
                    human_outcome=excluded.human_outcome
                """,
                (
                    run_date, run_date, generated_at, generated_at, git_head,
                    self.trigger, ops_status, runner_status, crawl_status,
                    clean_status, analysis_status, technical, overall_action,
                    int(human_required), int(gpt_required), incident_id,
                    error_type, error_summary or None, artifact['human_outcome'],
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
            recovered_incident = (
                artifact['human_outcome'] == 'AUTO_RECOVERED'
                and connection.execute(
                    'SELECT 1 FROM incidents WHERE run_id=?', (run_date,)
                ).fetchone()
            )
            if recovered_incident:
                incident_id = f'INC-{run_date}'
                artifact['incident_id'] = incident_id
                connection.execute(
                    """
                    UPDATE incidents
                    SET status='AUTO_RECOVERED', updated_at=?
                    WHERE run_id=?
                    """,
                    (generated_at, run_date),
                )
                connection.execute(
                    'UPDATE runs SET incident_id=? WHERE run_id=?',
                    (incident_id, run_date),
                )
            elif incident_id:
                platforms = ', '.join(source_summary['action_required']) or None
                incident_status = (
                    'NEEDS_HUMAN'
                    if ops_status == 'ACTION_REQUIRED' or failed_phase == 'crawl'
                    else 'OPEN'
                )
                connection.execute(
                    """
                    INSERT INTO incidents(
                        incident_id, run_id, status, failed_phase, platform,
                        error_type, error_summary, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        status=excluded.status, failed_phase=excluded.failed_phase,
                        platform=excluded.platform, error_type=excluded.error_type,
                        error_summary=excluded.error_summary,
                        updated_at=excluded.updated_at
                    """,
                    (
                        incident_id, run_date, incident_status, failed_phase, platforms,
                        error_type or 'UNKNOWN', error_summary or None,
                        generated_at, generated_at,
                    ),
                )
            else:
                connection.execute(
                    "UPDATE incidents SET status='RESOLVED', updated_at=? WHERE run_id=?",
                    (generated_at, run_date),
                )

        if write_latest:
            _write_json_atomic(self.ops_dir / 'latest.json', artifact)
        (self.ops_dir / 'latest.md').unlink(missing_ok=True)
        (self.ops_dir / 'latest_incident.md').unlink(missing_ok=True)
        return artifact

    def machine_status(self, run_date: str | None = None) -> dict[str, Any] | None:
        """Return one historical machine view from SQLite without reading Markdown."""
        with self._connect() as connection:
            if run_date is None:
                row = connection.execute(
                    'SELECT * FROM runs ORDER BY run_date DESC LIMIT 1'
                ).fetchone()
            else:
                row = connection.execute(
                    'SELECT * FROM runs WHERE run_date=?', (run_date,)
                ).fetchone()
            if row is None:
                return None
            sources = connection.execute(
                'SELECT * FROM sources WHERE run_id=? ORDER BY platform',
                (row['run_id'],),
            ).fetchall()
            action = connection.execute(
                'SELECT * FROM actions WHERE run_id=? ORDER BY action_id DESC LIMIT 1',
                (row['run_id'],),
            ).fetchone()
        presentation_sources = {
            source['platform']: {
                'source_completeness': source['source_completeness'],
                'limitation_state': source['limitation_state'],
                'matched_limitation_id': source['matched_limitation_id'],
            }
            for source in sources
        }
        # SQLite remains the owner of operational state. Read only the matching
        # canonical Health artifact for presentation details that it does not store.
        try:
            health = _read_mapping(
                self.data_dir / 'analysis' / 'health' / f'{row["run_date"]}.json',
                'canonical Daily Health artifact',
            )
        except DailyOperationsError:
            health = {}
        if (health.get('date') == row['run_date']
                and health.get('technical_run_health') == row['technical_run_health']
                and health.get('overall_action') == row['overall_action']
                and isinstance(health.get('sources'), Mapping)):
            for platform, value in presentation_sources.items():
                evidence = health['sources'].get(platform, {})
                if (isinstance(evidence, Mapping)
                        and evidence.get('limitation_state') == value['limitation_state']
                        and evidence.get('source_completeness') == value['source_completeness']
                        and isinstance(evidence.get('warnings'), list)
                        and 'TOLERATED_DETAIL_GAP' in evidence['warnings']):
                    value.update(warnings=['TOLERATED_DETAIL_GAP'],
                                 detail_failed=evidence.get('detail_failed'))
        source_summary = self._source_summary(presentation_sources)
        recovery = RecoveryOutcome().as_dict()
        if action is not None:
            recovery = {
                'attempted': True,
                'type': action['action_type'],
                'result': action['result'],
                'attempt_count': action['attempt_count'],
            }
        return {
            'schema_version': SCHEMA_VERSION,
            'date': row['run_date'],
            'generated_at': row['updated_at'],
            'ops_status': row['ops_status'],
            'runner_status': row['runner_status'],
            'crawl_status': row['crawl_status'],
            'clean_status': row['clean_status'],
            'analysis_status': row['analysis_status'],
            'technical_run_health': row['technical_run_health'],
            'overall_action': row['overall_action'],
            'source_summary': source_summary,
            'automatic_recovery': recovery,
            'human_action_required': bool(row['human_action_required']),
            'gpt_review_required': bool(row['gpt_review_required']),
            'incident_id': row['incident_id'],
            'canonical_evidence_refs': self._evidence_refs(row['run_date']),
            'human_outcome': row['human_outcome'] or 'TECHNICAL_FAILURE',
        }

    def history(self, days: int) -> list[dict[str, Any]]:
        if days < 1:
            raise ValueError('days must be positive')
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_date, human_outcome, human_action_required
                FROM runs ORDER BY run_date DESC LIMIT ?
                """,
                (days,),
            ).fetchall()
        return [dict(row) for row in rows]

    def incidents(self, *, open_only: bool = False) -> list[dict[str, Any]]:
        query = 'SELECT * FROM incidents'
        parameters: tuple[Any, ...] = ()
        if open_only:
            query += " WHERE status IN ('OPEN', 'NEEDS_HUMAN')"
        query += ' ORDER BY run_id DESC'
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, parameters)]

    def _canonical_run(self, run_date: str) -> Mapping[str, Any]:
        return _read_mapping(
            self.data_dir / 'analysis' / 'runs' / f'{run_date}.json',
            'canonical run artifact',
        )

    def _inspect_recovery_candidate(
        self,
        run_date: str,
        *,
        ops_status: str,
    ) -> RecoveryCandidate:
        if ops_status == 'ACTION_REQUIRED':
            return RecoveryCandidate(run_date, None, False, 'SOURCE_REGRESSION')
        try:
            run = self._canonical_run(run_date)
        except DailyOperationsError:
            return RecoveryCandidate(run_date, None, False, 'CANONICAL_RUN_UNAVAILABLE')
        recovery_type = self._recovery_type(run)
        if recovery_type is None:
            reason = (
                'HISTORICAL_CRAWL_FORBIDDEN'
                if _stage_status(run, 'crawl') == 'FAILED'
                else 'NO_SAFE_DOWNSTREAM_RECOVERY'
            )
            return RecoveryCandidate(run_date, None, False, reason)
        if run.get('resume_from') == recovery_type:
            return RecoveryCandidate(run_date, recovery_type, False, 'ATTEMPT_LIMIT_REACHED')
        with self._connect() as connection:
            action = connection.execute(
                'SELECT attempt_count FROM actions WHERE run_id=? AND action_type=?',
                (run_date, recovery_type),
            ).fetchone()
        if action is not None and int(action['attempt_count']) >= MAX_RECOVERY_ATTEMPTS:
            return RecoveryCandidate(run_date, recovery_type, False, 'ATTEMPT_LIMIT_REACHED')
        valid, validators = self._validate_recovery_inputs(run_date, recovery_type)
        if not valid:
            reason = (
                'CANONICAL_RAW_INVALID'
                if validators.get('raw_manifest') != 'PASS'
                else 'CANONICAL_CLEAN_INVALID'
            )
            return RecoveryCandidate(run_date, recovery_type, False, reason)
        return RecoveryCandidate(run_date, recovery_type, True, 'ELIGIBLE')

    def deferred_recovery_candidates(
        self,
        current_date: str,
        *,
        include_ineligible: bool = False,
    ) -> list[RecoveryCandidate]:
        """Use SQLite to find historical incidents, then re-check canonical evidence."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT r.run_date, r.ops_status
                FROM runs r JOIN incidents i ON i.run_id=r.run_id
                WHERE r.run_date < ? AND i.status IN ('OPEN', 'NEEDS_HUMAN')
                ORDER BY r.run_date
                """,
                (current_date,),
            ).fetchall()
        candidates = [
            self._inspect_recovery_candidate(row['run_date'], ops_status=row['ops_status'])
            for row in rows
        ]
        if include_ineligible:
            return candidates
        return [candidate for candidate in candidates if candidate.eligible]

    def process_deferred_recovery(
        self,
        current_date: str,
        *,
        runner: Runner,
        health_generator: HealthGenerator,
        limit: int = MAX_HISTORICAL_RECOVERY_DATES,
    ) -> list[dict[str, Any]]:
        """Bounded historical clean/analysis recovery; never executes Crawl."""
        if limit < 0 or limit > MAX_HISTORICAL_RECOVERY_DATES:
            raise ValueError(
                f'limit must be between 0 and {MAX_HISTORICAL_RECOVERY_DATES}'
            )
        inspected = self.deferred_recovery_candidates(
            current_date, include_ineligible=True
        )
        for candidate in inspected:
            if candidate.eligible:
                continue
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE incidents SET status='NEEDS_HUMAN', updated_at=?
                    WHERE run_id=? AND status IN ('OPEN', 'NEEDS_HUMAN')
                    """,
                    (self.generated_at(), candidate.run_date),
                )
        results: list[dict[str, Any]] = []
        for candidate in [value for value in inspected if value.eligible][:limit]:
            run = self._canonical_run(candidate.run_date)
            outcome = self.attempt_recovery(candidate.run_date, run, runner=runner)
            result: dict[str, Any] = candidate.as_dict()
            result['result'] = outcome.result
            if outcome.result == 'SUCCESS' and outcome.runner_result is not None:
                recovered = outcome.runner_result[2]
                health_path = (
                    self.data_dir / 'analysis' / 'health' / f'{candidate.run_date}.json'
                )
                health_path.unlink(missing_ok=True)
                try:
                    generated_path, health = health_generator(
                        candidate.run_date, data_dir=self.data_dir
                    )
                    if (
                        Path(generated_path).resolve() != health_path.resolve()
                        or not health_path.is_file()
                        or not isinstance(health, Mapping)
                    ):
                        raise ValueError('Daily Health wrote an unexpected artifact')
                    artifact = self.publish(
                        candidate.run_date,
                        run=recovered,
                        health=health,
                        recovery=outcome,
                        write_latest=False,
                    )
                    result['human_outcome'] = artifact['human_outcome']
                except Exception as exc:
                    self.publish(
                        candidate.run_date,
                        run=recovered,
                        health=None,
                        recovery=outcome,
                        orchestration_error=f'Deferred Daily Health failed: {exc}',
                        write_latest=False,
                    )
                    result['result'] = 'HEALTH_FAILED'
            else:
                effective = (
                    outcome.runner_result[2]
                    if outcome.runner_result is not None
                    else run
                )
                self.publish(
                    candidate.run_date,
                    run=effective,
                    health=None,
                    recovery=outcome,
                    write_latest=False,
                )
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE incidents SET status='NEEDS_HUMAN', updated_at=? WHERE run_id=?",
                        (self.generated_at(), candidate.run_date),
                    )
            results.append(result)
        return results

    def render_incident_gpt(self, run_date: str | None = None) -> str:
        """Generate a compact incident handoff on demand; never persist a copy."""
        with self._connect() as connection:
            if run_date is None:
                incident = connection.execute(
                    'SELECT * FROM incidents ORDER BY run_id DESC LIMIT 1'
                ).fetchone()
            else:
                incident = connection.execute(
                    'SELECT * FROM incidents WHERE run_id=?', (run_date,)
                ).fetchone()
            if incident is None:
                raise DailyOperationsError('no incident is available')
            run_row = connection.execute(
                'SELECT * FROM runs WHERE run_id=?', (incident['run_id'],)
            ).fetchone()
            action = connection.execute(
                'SELECT * FROM actions WHERE run_id=? ORDER BY action_id DESC LIMIT 1',
                (incident['run_id'],),
            ).fetchone()
        try:
            run = self._canonical_run(incident['run_id'])
        except DailyOperationsError:
            run = {}
        crawl = run.get('crawl') if isinstance(run.get('crawl'), Mapping) else {}
        validators = json.loads(action['validator_results']) if action else {}
        retry = crawl.get('retried_platforms', [])
        preserved = (
            (self.data_dir / 'raw' / f"{incident['run_id']}.json").is_file()
            and (self.data_dir / 'raw' / f"{incident['run_id']}_manifest.json").is_file()
        )
        evidence = self._evidence_refs(incident['run_id'])
        evidence_lines = '\n'.join(f'- {name}: {path}' for name, path in evidence.items())
        return (
            'AI Job Finder incident handoff\n\n'
            f"Date: {incident['run_id']}\n"
            f"Git HEAD: {run_row['git_head'] or 'UNKNOWN'}\n"
            f"Failed stage: {incident['failed_phase'] or 'N/A'}\n"
            f"Platform: {incident['platform'] or 'N/A'}\n"
            f"Error type: {incident['error_type']}\n"
            f"Error message: {incident['error_summary'] or 'See canonical evidence.'}\n"
            f"Retry: {json.dumps(retry, ensure_ascii=False)}\n"
            f"Validators: {json.dumps(validators, ensure_ascii=False, sort_keys=True)}\n"
            f"Data preservation: {'YES' if preserved else 'NO'}\n"
            f"Technical health: {run_row['technical_run_health']}\n"
            f"Overall action: {run_row['overall_action']}\n"
            f"Incident status: {incident['status']}\n\n"
            'Canonical evidence refs:\n'
            f'{evidence_lines}\n\n'
            '请判断根因、是否需要修复、是否会改变受保护的业务 contract，并给出下一步。\n'
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
        'human_outcome': 'TECHNICAL_FAILURE',
    }
    _write_json_atomic(ops_dir / 'latest.json', artifact)
    (ops_dir / 'latest.md').unlink(missing_ok=True)
    (ops_dir / 'latest_incident.md').unlink(missing_ok=True)


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
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
