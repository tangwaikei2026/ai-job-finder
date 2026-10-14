"""Meituan-only process boundary. The parent owns time, IPC receipts and evidence.

No shared process groups are signalled. A direct child remains unreaped until
its identity check/signal finishes, so its PID cannot be recycled in that window.
Worker code is HTTP + threads only; creating descendants is explicitly denied.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from src.invocation import validate_clock
from src.models import CollectionManifest, CollectionResult, RawJobPosting, write_json_atomic

CONTEXT_ENV = 'AI_JOB_FINDER_MEITUAN_WORKER_CONTEXT'
MAX_FRAME = 16 * 1024 * 1024
POLL_SECONDS = 0.05


def command_environment(command):
    """Bind only official crawl subprocesses to their invocation-side evidence."""
    env = dict(os.environ)
    env.pop(CONTEXT_ENV, None)
    if len(command) < 3 or command[1:3] != ['-m', 'src.main']:
        return env
    def arg(flag):
        return command[command.index(flag) + 1]
    if '--invocation-id' in command and '--output-dir' in command:
        context = dict(id=arg('--invocation-id'), run_date=arg('--date'),
                       started_at=arg('--started-at'))
        env[CONTEXT_ENV] = json.dumps(dict(
            invocation=context, retry='--merge-existing' in command,
            config_sha256=hashlib.sha256(Path(arg('--config')).read_bytes()).hexdigest(),
            directory=str(Path(arg('--output-dir')).resolve().parent.parent / 'meituan-worker'),
        ))
    return env


def retry_exhausted(row):
    if row.get('platform') != 'meituan':
        return False
    audit = row.get('metadata', {}).get('worker', {})
    deadline = audit.get('budget_deadline')
    return (audit.get('budget_exhausted') is True
            or (type(deadline) in (int, float) and time.monotonic() >= deadline))


def verify_worker_cleanup(raw_dir):
    """Retry rejection must not hide a worker whose exit was never established."""
    directory = Path(raw_dir).resolve().parent.parent / 'meituan-worker'
    # A handshake/OS identity failure can precede creation of the launch file.
    # Its BLOCKED result must still stop Daily, including a rejected Retry.
    for result in directory.glob('*-result.json'):
        try:
            audit = json.loads(result.read_text())['manifest']['metadata']['worker']
            if (audit['exit_reason'] == 'BLOCKED' or (audit.get('pid') is not None and (
                    not audit['exit_confirmed'] or audit['remaining_descendants'] != []))):
                raise WorkerBlocked('worker result does not prove cleanup')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise WorkerBlocked('worker result evidence invalid') from exc
    for launch in directory.glob('*-launch.json'):
        try:
            started = json.loads(launch.read_text())
            final = json.loads(launch.with_name(
                launch.name.replace('-launch.json', '-result.json')).read_text())
            audit = final['manifest']['metadata']['worker']
            if (audit['launch_token'] != started['launch_token'] or audit['pid'] != started['pid']
                    or not audit['exit_confirmed'] or audit['remaining_descendants'] != []
                    or audit['exit_reason'] == 'BLOCKED'):
                raise WorkerBlocked('worker exit evidence does not prove cleanup')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise WorkerBlocked('worker exit evidence missing or invalid') from exc


def _utc():
    return datetime.now(timezone.utc).isoformat()


class WorkerBlocked(RuntimeError):
    pass


class Budget:
    """A locked, invocation-specific absolute monotonic deadline, never reset by retry."""
    def __init__(self, seconds, context=None):
        self.context = context
        self.directory = Path(context['directory']) if context else Path(
            tempfile.mkdtemp(prefix='meituan-worker-'))
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = (self.directory / 'budget.lock').open('a+')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = self.directory / 'budget.json'
            identity = ({k: context[k] for k in ('invocation', 'config_sha256')}
                        if context else {'standalone_id': str(uuid4())})
            if path.exists():
                self.state = json.loads(path.read_text())
                if self.state['identity'] != identity or time.monotonic() < self.state['start']:
                    raise WorkerBlocked('budget identity/clock mismatch')
                if self.state['seconds'] != seconds:
                    raise WorkerBlocked('budget configuration changed')
            else:
                if context and context['retry']:
                    raise WorkerBlocked('retry budget evidence missing')
                now = time.monotonic()
                self.state = dict(identity=identity, start=now, deadline=now + seconds,
                                  wall_start=time.time(), seconds=seconds)
                write_json_atomic(path, self.state)
        except BaseException:
            self.lock.close()
            raise

    def remaining(self):
        return max(0., self.state['deadline'] - time.monotonic())

    def check_date(self):
        if self.context:
            validate_clock(self.context['invocation'])

    def close(self):
        self.lock.close()  # Worker never inherits this descriptor.


class Receipts:
    """Only fully decoded/validated messages may enter the parent's observation."""
    def __init__(self, name):
        self.manifest = CollectionManifest(platform='meituan', name=name)
        self.jobs = {}
        self.attempted = set()
        self.succeeded = set()
        self.failed = set()
        self.sequence = 0
        self.last_message = None
        self.done = False
        self.list_complete = False

    def accept(self, message):
        sequence = message['seq']
        if sequence == self.sequence:
            if message != self.last_message:
                raise ValueError('conflicting retransmission')
            return
        if sequence != self.sequence + 1 or self.done:
            raise ValueError('out of order IPC')
        event = message['event']
        if event in {'list', 'list_end', 'done'}:
            manifest = CollectionManifest(**message['manifest'])
            if manifest.platform != 'meituan':
                raise ValueError('wrong IPC platform')
            if event == 'list':
                jobs = [RawJobPosting(**j) for j in message['jobs']]
                if any(j.platform != 'meituan' or not j.job_id for j in jobs):
                    raise ValueError('invalid IPC job')
                if self.attempted or len({j.job_id for j in jobs}) != len(jobs):
                    raise ValueError('invalid list snapshot')
                self.jobs = {j.job_id: j for j in jobs}
            if event == 'list_end':
                self.list_complete = manifest.complete
            if event == 'done':
                if (manifest.details_fetched != len(self.succeeded)
                        or set(manifest.detail_failed_job_ids) != self.failed
                        or manifest.detail_failed != len(self.failed)
                        or (manifest.complete and (
                            not self.list_complete or len(self.succeeded) != len(self.jobs)))):
                    raise ValueError('completion does not match receipts')
                self.done = True
            self.manifest = manifest
        elif event in {'attempt', 'failure', 'success'}:
            job = RawJobPosting(**message['job']) if event == 'success' else None
            job_id = job.job_id if job else message['job_id']
            if job_id not in self.jobs or (job and job.platform != 'meituan'):
                raise ValueError('unknown IPC job')
            if event == 'attempt':
                if job_id in self.attempted:
                    raise ValueError('duplicate attempt')
                self.attempted.add(job_id)
            else:
                if job_id not in self.attempted or job_id in self.succeeded | self.failed:
                    raise ValueError('invalid terminal job event')
                if job:
                    self.jobs[job_id] = job
                    self.succeeded.add(job_id)
                else:
                    self.failed.add(job_id)
        else:
            raise ValueError('unknown IPC event')
        self.sequence = sequence
        self.last_message = message

    def result(self, audit, reason):
        manifest = self.manifest
        manifest.jobs_in_scope = len(self.jobs)
        manifest.details_fetched = len(self.succeeded)
        manifest.detail_failed = len(self.failed)
        manifest.detail_failed_job_ids = sorted(self.failed)
        if reason != 'completed':
            # Preserve list-only content verbatim, but never make UNKNOWN content
            # reliable through the existing partial/detail_errors tolerance rule.
            manifest.status = 'error'
            manifest.complete = False
            manifest.stopped_by = 'worker_' + reason
            manifest.error = 'meituan worker: ' + reason
        audit.update(list_discovered=manifest.records_fetched,
                     list_complete=self.list_complete, detail_targets=len(self.jobs),
                     detail_attempted=len(self.attempted), detail_succeeded=len(self.succeeded),
                     detail_failed=len(self.failed), detail_unattempted=len(self.jobs.keys() - self.attempted),
                     detail_unknown=len(self.attempted - self.succeeded - self.failed),
                     unattempted_job_ids=sorted(self.jobs.keys() - self.attempted),
                     unknown_job_ids=sorted(self.attempted - self.succeeded - self.failed),
                     last_confirmed_sequence=self.sequence)
        manifest.metadata['worker'] = audit
        if reason != 'completed':
            manifest.metadata.setdefault('progress', {}).update(
                list_complete=self.list_complete, detail_targets=len(self.jobs),
                detail_started=len(self.attempted), detail_succeeded=len(self.succeeded),
                detail_failed=len(self.failed), detail_not_started=audit['detail_unattempted'],
                detail_in_flight=audit['detail_unknown'],
                detail_unfinished=audit['detail_unattempted'] + audit['detail_unknown'])
        manifest.finished_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        manifest.duration_seconds = audit.get('elapsed_seconds', 0.)
        return CollectionResult(list(self.jobs.values()), manifest)


def _identity(process):
    # poll() first; if live, even an immediate exit remains our unreaped child.
    if process.poll() is not None:
        return False
    if (os.getpgid(process.pid) != process.pid or os.getsid(process.pid) != process.pid
            or process.pid == os.getpgrp() or process.pid == os.getpid()):
        raise WorkerBlocked('independent worker identity cannot be proven')
    return True


def _signal(process, sig, audit):
    if _identity(process):
        os.kill(process.pid, sig)  # Deliberately never killpg().
        audit[signal.Signals(sig).name.lower()] = True


def _descendants(pid):
    """Verify the worker-only no-descendants contract, without signalling strangers."""
    output = subprocess.check_output(
        ['ps', '-axo', 'pid=,ppid=,pgid='], text=True, timeout=2)
    rows = [tuple(map(int, line.split())) for line in output.splitlines()]
    found = {p for p, parent, group in rows if parent == pid or (group == pid and p != pid)}
    changed = True
    while changed:
        children = {p for p, parent, _ in rows if parent in found}
        changed = bool(children - found)
        found |= children
    return sorted(found)


def supervise(platform_config, collection_config, budget, *, command_factory=None):
    """Run one attempt; command_factory is an offline test seam, never a config option."""
    started, wall_started = time.monotonic(), time.time()
    receipts = Receipts(str(platform_config.get('name', '美团')))
    audit = dict(attempt_id=str(uuid4()), started_at=_utc(), pid=None,
                 sigterm=False, sigkill=False, exit_confirmed=False,
                 budget_seconds=budget.state['seconds'], budget_start=budget.state['start'],
                 budget_deadline=budget.state['deadline'], remaining_at_start=budget.remaining(),
                 clock='time.monotonic', evidence_directory=str(budget.directory))
    reason = 'completed'
    process = None
    parent, child = socket.socketpair()
    token = str(uuid4())
    audit['launch_token'] = token
    parent.setblocking(False)
    buffer = b''
    outgoing = (json.dumps(dict(platform=platform_config, collection=collection_config,
                                token=token)) + '\n').encode()
    ready = False
    eof = False
    term_at = term_wall = None
    grace = min(10., max(0., float(platform_config.get('worker_term_grace_seconds', 10))))
    journal = budget.directory / (audit['attempt_id'] + '.jsonl')
    try:
        budget.check_date()
        if budget.remaining() <= 0:
            reason = 'budget_exhausted'
        else:
            command = (command_factory(child.fileno(), token) if command_factory else [
                sys.executable, '-c',
                'from src.collectors.meituan_worker import worker_main; worker_main()',
                str(child.fileno()), token])
            process = subprocess.Popen(command, pass_fds=(child.fileno(),),
                                       start_new_session=True, close_fds=True)
            audit['pid'] = process.pid
            child.close()
            _identity(process)
            audit.update(pgid=process.pid, sid=process.pid, parent_pid=os.getpid(),
                         invocation=budget.context['invocation'] if budget.context else None)
            write_json_atomic(budget.directory / (audit['attempt_id'] + '-launch.json'), audit)
            with journal.open('x', encoding='utf-8') as evidence:
                while True:
                    now = time.monotonic()
                    trigger = None
                    try:
                        budget.check_date()
                    except ValueError:
                        trigger = 'date_window_expired'
                    if budget.remaining() <= 0:
                        trigger = trigger or 'budget_exhausted'
                    if trigger and term_at is None:
                        reason = trigger
                        term_at, term_wall = now, time.time()
                        outgoing = b''  # No additional work/ACK is authorized.
                        _signal(process, signal.SIGTERM, audit)
                    if term_at is not None and process.poll() is None:
                        if now - term_at >= grace or time.time() - term_wall >= 30:
                            audit['grace_exit_reason'] = ('active_grace' if now - term_at >= grace
                                                         else 'wall_safety')
                            _signal(process, signal.SIGKILL, audit)
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired as exc:
                                raise WorkerBlocked('worker not reaped after SIGKILL') from exc
                    if process.poll() is not None and (eof or term_at is not None):
                        break
                    readable, writable, _ = select.select(
                        [] if eof else [parent], [parent] if outgoing else [], [], POLL_SECONDS)
                    if writable:
                        try:
                            outgoing = outgoing[parent.send(outgoing):]
                        except (BrokenPipeError, ConnectionResetError):
                            outgoing = b''
                    if readable:
                        try:
                            chunk = parent.recv(65536)
                        except ConnectionResetError:
                            chunk = b''
                        if not chunk:
                            eof = True
                            if term_at is None and not receipts.done and process.poll() is None:
                                reason = 'ipc_closed'
                                term_at, term_wall = time.monotonic(), time.time()
                                _signal(process, signal.SIGTERM, audit)
                        else:
                            buffer += chunk
                            if len(buffer) > MAX_FRAME:
                                raise ValueError('IPC frame too large')
                            while b'\n' in buffer:
                                line, buffer = buffer.split(b'\n', 1)
                                message = json.loads(line)
                                if not ready:
                                    expected = dict(event='ready', pid=process.pid,
                                                    ppid=os.getpid(), pgid=process.pid,
                                                    sid=process.pid, token=token)
                                    if message != expected:
                                        raise WorkerBlocked('worker handshake identity mismatch')
                                    ready = True
                                    audit['handshake_confirmed'] = True
                                    outgoing += b'{"ack":0}\n'
                                    continue
                                if term_at is not None:
                                    continue  # Unconfirmed buffered results are never successes.
                                receipts.accept(message)
                                evidence.write(json.dumps(message, ensure_ascii=False) + '\n')
                                evidence.flush()
                                outgoing += (json.dumps({'ack': receipts.sequence}) + '\n').encode()
                    if eof and process.poll() is not None:
                        break
                evidence.flush()
                os.fsync(evidence.fileno())
            if reason == 'completed' and (process.returncode != 0 or not receipts.done or buffer):
                reason = 'abnormal_exit'
    except WorkerBlocked as exc:
        # No broad kill fallback: retain identity/IPC evidence for human recovery.
        reason = 'BLOCKED'
        audit['blocked_reason'] = str(exc)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        reason = 'ipc_or_start_failure'
        audit['failure_type'] = type(exc).__name__
    finally:
        if process is not None:
            # Covers parser/journal failures too, without a blocking socket read/join.
            if process.poll() is None and reason != 'BLOCKED':
                try:
                    term_at = term_at or time.monotonic()
                    term_wall = term_wall or time.time()
                    _signal(process, signal.SIGTERM, audit)
                    while (process.poll() is None and time.monotonic() - term_at < grace
                           and time.time() - term_wall < 30):
                        time.sleep(POLL_SECONDS)
                    if process.poll() is None:
                        _signal(process, signal.SIGKILL, audit)
                        process.wait(timeout=2)
                except (WorkerBlocked, OSError, subprocess.TimeoutExpired) as exc:
                    reason = 'BLOCKED'
                    audit['blocked_reason'] = str(exc)
            audit['returncode'] = process.poll()
            audit['exit_confirmed'] = process.returncode is not None
            try:
                descendants = _descendants(process.pid)
                audit['remaining_descendants'] = descendants
                if descendants:
                    reason = 'BLOCKED'
                    audit['blocked_reason'] = 'unexpected descendants; no unproven signals sent'
            except (OSError, subprocess.SubprocessError) as exc:
                reason = 'BLOCKED'
                audit['blocked_reason'] = 'descendant cleanup verification unavailable'
        parent.close()
        child.close()
    elapsed, wall = time.monotonic() - started, time.time() - wall_started
    audit.update(exit_reason=reason, exited_at=_utc(), elapsed_seconds=round(elapsed, 6),
                 wall_seconds=round(wall, 6), sleep_or_wall_adjustment_seconds=round(wall - elapsed, 6),
                 shutdown_seconds=round(time.monotonic() - term_at, 6) if term_at else 0.,
                 budget_exhausted=budget.remaining() <= 0,
                 remaining_seconds=budget.remaining())
    result = receipts.result(audit, reason)
    # Evidence lives alongside staging, and is never published as production Raw.
    try:
        write_json_atomic(budget.directory / (audit['attempt_id'] + '-result.json'),
                          dict(manifest=result.manifest.to_dict(), jobs=[j.to_dict() for j in result.jobs]))
    except OSError as exc:
        audit['evidence_write_error'] = type(exc).__name__
        result.manifest.status = 'error'
        result.manifest.complete = False
        result.manifest.error = 'worker evidence write failed'
        result.manifest.stopped_by = 'worker_evidence_failure'

    return result


class MeituanWorkerCollector:
    platform = 'meituan'

    def __init__(self, platform_config, collection_config):
        self.platform_config = platform_config
        self.collection_config = collection_config

    def collect(self):
        try:
            context = json.loads(os.environ[CONTEXT_ENV]) if CONTEXT_ENV in os.environ else None
            budget = Budget(min(1800., max(0., float(
                self.platform_config.get('worker_budget_seconds', 1800)))), context)
        except (WorkerBlocked, OSError, ValueError, KeyError) as exc:
            manifest = CollectionManifest(
                platform='meituan', name=str(self.platform_config.get('name', '美团')),
                status='error', complete=False, stopped_by='worker_BLOCKED',
                error='Meituan worker budget unavailable: ' + type(exc).__name__,
                finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            manifest.metadata['worker'] = dict(exit_reason='BLOCKED', pid=None,
                                               blocked_reason=str(exc))
            return CollectionResult([], manifest)
        try:
            return supervise(self.platform_config, self.collection_config, budget)
        finally:
            budget.close()

    def close(self):
        pass


def worker_main():
    """An exec'd HTTP-only worker; SIGTERM stops admission even if a request hangs."""
    from src.collectors.meituan import MeituanRawCollector
    channel = socket.socket(fileno=int(sys.argv[1]))
    stream = channel.makefile('rwb', buffering=0)
    config = json.loads(stream.readline(MAX_FRAME))
    token = sys.argv[2]
    if config['token'] != token:
        raise ValueError('worker token mismatch')
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    def no_descendants(event, args):
        if event in {'subprocess.Popen', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.system', 'os.exec'}:
            raise PermissionError('Meituan HTTP worker cannot create/replace processes')
    sys.addaudithook(no_descendants)
    lock = threading.Lock()
    seq = 0
    def send(message, expected):
        payload = (json.dumps(message, ensure_ascii=False) + '\n').encode()
        if len(payload) > MAX_FRAME:
            raise ValueError('worker frame too large')
        channel.sendall(payload)
        reply = json.loads(stream.readline(1024))
        if reply != {'ack': expected}:
            raise ValueError('worker ACK mismatch')
    send(dict(event='ready', pid=os.getpid(), ppid=os.getppid(), pgid=os.getpgrp(),
              sid=os.getsid(0), token=token), 0)
    def emit(event, **payload):
        nonlocal seq
        with lock:
            if stop.is_set():
                raise InterruptedError('worker stopping')
            seq += 1
            send(dict(seq=seq, event=event, **payload), seq)
    collector = MeituanRawCollector(config['platform'], config['collection'])
    collector.worker_emit = emit
    collector.worker_stop = stop
    # Keep the existing HTTP retry contract; gate each new request admission.
    original_request = collector.client.request
    def request(*args, **kwargs):
        if stop.is_set():
            raise InterruptedError('worker stopping')
        return original_request(*args, **kwargs)
    collector.client.request = request
    try:
        result = collector.collect()
        collector.close()
        emit('done', manifest=result.manifest.to_dict())
    finally:
        channel.close()
