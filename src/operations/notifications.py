"""Bounded, idempotent notification delivery for Daily Operations."""
from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from src.operations.daily_ops import DailyOperations, _compact
from src.operations.presentation import build_presentation, render_email


MAX_DELIVERY_ATTEMPTS = 3
MAX_PENDING_PER_RUN = 3
NOTIFICATION_TYPES = frozenset({'DAILY_STATUS', 'RECOVERY'})


class NotificationAdapter(Protocol):
    configured: bool

    def send(self, subject: str, body: str) -> None: ...


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    sender: str
    recipient: str
    username: str | None = None
    password: str | None = None
    security: str = 'starttls'

    @classmethod
    def from_environment(cls) -> EmailConfig | None:
        config, _ = cls.from_environment_with_error()
        return config

    @classmethod
    def from_environment_with_error(
        cls,
    ) -> tuple[EmailConfig | None, str | None]:
        """Return config plus a non-secret validation error for operators."""
        host = os.environ.get('AI_JOB_FINDER_EMAIL_HOST', '').strip()
        sender = os.environ.get('AI_JOB_FINDER_EMAIL_FROM', '').strip()
        recipient = os.environ.get('AI_JOB_FINDER_EMAIL_TO', '').strip()
        username = os.environ.get('AI_JOB_FINDER_EMAIL_USERNAME', '').strip() or None
        password = os.environ.get('AI_JOB_FINDER_EMAIL_PASSWORD') or None
        required = {
            'AI_JOB_FINDER_EMAIL_HOST': host,
            'AI_JOB_FINDER_EMAIL_FROM': sender,
            'AI_JOB_FINDER_EMAIL_TO': recipient,
        }
        missing = sorted(key for key, value in required.items() if not value)
        if missing:
            return None, f"missing required field(s): {', '.join(missing)}"
        if username and not password:
            return None, (
                'AI_JOB_FINDER_EMAIL_PASSWORD is required when '
                'AI_JOB_FINDER_EMAIL_USERNAME is configured'
            )
        try:
            port = int(os.environ.get('AI_JOB_FINDER_EMAIL_PORT', '587'))
        except ValueError:
            return None, 'AI_JOB_FINDER_EMAIL_PORT must be an integer'
        security = os.environ.get(
            'AI_JOB_FINDER_EMAIL_SECURITY', 'starttls'
        ).strip().lower()
        if port < 1 or port > 65535:
            return None, 'AI_JOB_FINDER_EMAIL_PORT must be between 1 and 65535'
        if security not in {'starttls', 'ssl', 'none'}:
            return None, (
                'AI_JOB_FINDER_EMAIL_SECURITY must be starttls, ssl, or none'
            )
        return cls(
            host=host,
            port=port,
            sender=sender,
            recipient=recipient,
            username=username,
            password=password,
            security=security,
        ), None


class EmailAdapter:
    def __init__(self, config: EmailConfig | None = None) -> None:
        self.config = config or EmailConfig.from_environment()
        self.configured = self.config is not None

    def send(self, subject: str, body: str) -> None:
        if self.config is None:
            raise RuntimeError('email adapter is not configured')
        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = self.config.sender
        message['To'] = self.config.recipient
        message.set_content(body)
        if self.config.security == 'ssl':
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                self.config.host,
                self.config.port,
                timeout=15,
                context=ssl.create_default_context(),
            )
        else:
            client = smtplib.SMTP(self.config.host, self.config.port, timeout=15)
        with client:
            if self.config.security == 'starttls':
                client.starttls(context=ssl.create_default_context())
            if self.config.username:
                client.login(self.config.username, self.config.password or '')
            client.send_message(message)


class NotificationService:
    def __init__(
        self,
        operations: DailyOperations,
        *,
        adapter: NotificationAdapter | None = None,
    ) -> None:
        self.operations = operations
        self.adapter = adapter or EmailAdapter()

    def render(self, run_date: str) -> tuple[str, str]:
        machine = self.operations.machine_status(run_date)
        if machine is None:
            raise ValueError(f'no Ops status for {run_date}')
        return render_email(build_presentation(machine))

    def queue(self, run_date: str, notification_type: str = 'DAILY_STATUS') -> bool:
        if notification_type not in NOTIFICATION_TYPES:
            raise ValueError(f'unsupported notification type: {notification_type}')
        if self.operations.machine_status(run_date) is None:
            raise ValueError(f'no Ops status for {run_date}')
        timestamp = self.operations.generated_at()
        with self.operations._connect() as connection:
            if notification_type == 'RECOVERY':
                connection.execute(
                    """
                    UPDATE notifications
                    SET delivery_status='SUPERSEDED', updated_at=?
                    WHERE run_date=? AND notification_type='DAILY_STATUS'
                      AND delivery_status IN ('PENDING', 'FAILED')
                    """,
                    (timestamp, run_date),
                )
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO notifications(
                    run_date, notification_type, delivery_status, attempt_count,
                    last_attempt_at, last_error, created_at, updated_at
                ) VALUES (?, ?, 'PENDING', 0, NULL, NULL, ?, ?)
                """,
                (run_date, notification_type, timestamp, timestamp),
            )
        return cursor.rowcount == 1

    def send_pending(
        self,
        *,
        run_date: str | None = None,
        limit: int = MAX_PENDING_PER_RUN,
    ) -> list[dict[str, object]]:
        if limit < 0 or limit > MAX_PENDING_PER_RUN:
            raise ValueError(f'limit must be between 0 and {MAX_PENDING_PER_RUN}')
        if not self.adapter.configured or limit == 0:
            return []
        where = "delivery_status IN ('PENDING', 'FAILED') AND attempt_count < ?"
        parameters: list[object] = [MAX_DELIVERY_ATTEMPTS]
        if run_date is not None:
            where += ' AND run_date=?'
            parameters.append(run_date)
        parameters.append(limit)
        with self.operations._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM notifications WHERE {where}
                ORDER BY created_at, run_date, notification_type LIMIT ?
                """,
                parameters,
            ).fetchall()
        results: list[dict[str, object]] = []
        for row in rows:
            timestamp = self.operations.generated_at()
            status = 'DELIVERED'
            error: str | None = None
            try:
                subject, body = self.render(row['run_date'])
                self.adapter.send(subject, body)
            except Exception as exc:
                status = 'FAILED'
                error = _compact(exc)
            with self.operations._connect() as connection:
                connection.execute(
                    """
                    UPDATE notifications
                    SET delivery_status=?, attempt_count=attempt_count + 1,
                        last_attempt_at=?, last_error=?, updated_at=?
                    WHERE run_date=? AND notification_type=?
                      AND delivery_status != 'DELIVERED'
                      AND attempt_count < ?
                    """,
                    (
                        status, timestamp, error, timestamp,
                        row['run_date'], row['notification_type'],
                        MAX_DELIVERY_ATTEMPTS,
                    ),
                )
            results.append({
                'date': row['run_date'],
                'notification_type': row['notification_type'],
                'delivery_status': status,
                'error': error,
            })
        return results

    def state(self, run_date: str, notification_type: str) -> dict[str, object] | None:
        with self.operations._connect() as connection:
            row = connection.execute(
                """
                SELECT run_date, notification_type, delivery_status, attempt_count,
                       last_attempt_at, last_error
                FROM notifications WHERE run_date=? AND notification_type=?
                """,
                (run_date, notification_type),
            ).fetchone()
        return dict(row) if row is not None else None
