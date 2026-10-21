from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import Condition, Event, Lock, Thread
from typing import Any, Callable
from uuid import uuid4

from ..config import REPO_ROOT
from ..mealie_backup import backup_timeout_seconds
from ..mealie_slots import LANE_ENV, SLOTS_DIR_ENV
from ..reporting import PROGRESS_PREFIX, RESULT_PATH_ENV, read_results
from .env_catalog import DEFAULT_MAX_RUN_DURATION_SECONDS, MAX_RUN_DURATION_SECONDS_CAP
from . import lanes
from .state import StateStore, utc_now_iso
from .tasks import WORKFLOW_TASK, TaskRegistry

logger = logging.getLogger(__name__)

ENVProvider = Callable[[], dict[str, str]]


def _coerce_max_duration_seconds(value: object, default: int = DEFAULT_MAX_RUN_DURATION_SECONDS) -> int:
    try:
        seconds = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if seconds <= 0:
        return default
    return min(seconds, MAX_RUN_DURATION_SECONDS_CAP)


def _resolve_max_duration_seconds(runtime_env: dict[str, str], execution_max_duration: int | None) -> int:
    configured = _coerce_max_duration_seconds(runtime_env.get("MAX_RUN_DURATION_SECONDS"))
    if execution_max_duration is None:
        return configured
    return _coerce_max_duration_seconds(execution_max_duration, default=configured)


@dataclass(frozen=True)
class _Slot:
    run_id: str
    task_id: str
    lane: str
    writes: frozenset[str]
    title: str


def _blocker(slot: _Slot, earlier: list[_Slot], running: list[_Slot]) -> _Slot | None:
    """The run that has to finish (or start) before *slot* can start, if any.

    Each lane runs one run at a time. Runs whose writes overlap go in the order
    they were started, whatever their lane; heavy runs keep their order too.
    """
    for other in running:
        if other.lane == slot.lane or lanes.overlaps(other.writes, slot.writes):
            return other
    for other in earlier:
        if (other.lane == lanes.HEAVY and slot.lane == lanes.HEAVY) or lanes.overlaps(other.writes, slot.writes):
            return other
    return None


def _slots_dir(logs_dir: Path) -> Path:
    # On the container's own disk, not the data volume: file locks can be
    # unreliable on network shares and some bind mounts (see #102).
    key = sha256(str(logs_dir.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"cookdex-mealie-slots-{key}"


class RunQueueManager:
    def __init__(
        self,
        state: StateStore,
        registry: TaskRegistry,
        environment_provider: ENVProvider,
        logs_dir: Path,
        max_log_files: int = 200,
    ) -> None:
        self.state = state
        self.registry = registry
        self.environment_provider = environment_provider
        self.logs_dir = logs_dir
        self.max_log_files = max_log_files
        self._stop = Event()
        self._thread: Thread | None = None
        self._active: dict[str, subprocess.Popen[str]] = {}
        self._active_lock = Lock()
        # Runs waiting to start, oldest first, and runs started. Guarded by _cond.
        self._cond = Condition()
        self._pending: list[_Slot] = []
        self._running: dict[str, _Slot] = {}
        self._run_threads: dict[str, Thread] = {}
        self.slots_dir = _slots_dir(logs_dir)
        # Latest "[progress] {json}" line per running run; see reporting.Progress.
        self._progress: dict[str, dict[str, Any]] = {}

    def _record_progress(self, run_id: str, line: str) -> None:
        try:
            data = json.loads(line[len(PROGRESS_PREFIX):])
        except ValueError:
            return
        if isinstance(data, dict):
            self._progress[run_id] = {
                "label": str(data.get("label") or ""),
                "done": int(data.get("done") or 0),
                "total": int(data.get("total") or 0),
            }

    def progress(self, run_id: str) -> dict[str, Any] | None:
        """How far along a running run is, from its latest [progress] line."""
        return self._progress.get(run_id)

    def start(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._dispatch_loop, daemon=True, name="webui-runner")
        self._thread.start()

    def stop(self, timeout_seconds: float = 5.0) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout_seconds)
            self._thread = None
        with self._active_lock:
            for proc in list(self._active.values()):
                self._terminate_process_tree(proc, wait_for_exit=True)
            self._active.clear()
        for thread in list(self._run_threads.values()):
            thread.join(timeout_seconds)

    def _title(self, task_id: str, options: dict[str, Any]) -> str:
        workflow = options.get("workflow")
        if task_id == WORKFLOW_TASK and isinstance(workflow, dict) and workflow.get("name"):
            return str(workflow["name"])
        definition = self.registry.get(task_id)
        return definition.title if definition else task_id

    def _make_slot(self, run_id: str, task_id: str, options: dict[str, Any]) -> _Slot:
        try:
            env = self.environment_provider()
        except Exception:
            env = {}
        plan = self.registry.lane_for(task_id, options, env)
        return _Slot(run_id, task_id, plan.lane, plan.writes, self._title(task_id, options))

    def enqueue(
        self,
        task_id: str,
        options: dict[str, Any],
        triggered_by: str,
        schedule_id: str | None = None,
    ) -> dict[str, Any]:
        run_id = str(uuid4())
        log_path = (self.logs_dir / f"{run_id}.log").resolve()
        record = self.state.create_run(
            run_id=run_id,
            task_id=task_id,
            options=options,
            triggered_by=triggered_by,
            schedule_id=schedule_id,
            log_path=str(log_path),
        )
        slot = self._make_slot(run_id, task_id, options)
        with self._cond:
            self._pending.append(slot)
            self._cond.notify_all()
        logger.info("run %s queued: task=%s lane=%s triggered_by=%s", run_id, task_id, slot.lane, triggered_by)
        return self._with_waiting(record)

    def waiting(self, run_id: str) -> dict[str, Any] | None:
        """What a queued run is waiting for, in words, or None if it isn't queued here."""
        with self._cond:
            index = next((i for i, slot in enumerate(self._pending) if slot.run_id == run_id), None)
            if index is None:
                return None
            blocker = _blocker(self._pending[index], self._pending[:index], list(self._running.values()))
            running = blocker is not None and blocker.run_id in self._running
        if blocker is None:
            return {"message": "Starting…", "run_id": None, "task_id": None}
        if running:
            progress = self.progress(blocker.run_id) or {}
            done, total = int(progress.get("done") or 0), int(progress.get("total") or 0)
            count = f" ({done:,} of {total:,})" if total > 0 else ""
            message = f"Waiting for {blocker.title}{count} to finish"
        else:
            message = f"Waiting for {blocker.title} to go first"
        return {"message": message, "run_id": blocker.run_id, "task_id": blocker.task_id}

    def _with_waiting(self, run: dict[str, Any]) -> dict[str, Any]:
        if run.get("status") == "queued":
            run["waiting"] = self.waiting(str(run.get("run_id")))
        return run

    def describe(self, run: dict[str, Any]) -> dict[str, Any]:
        """Add what the run is waiting for (queued) or how far along it is (running)."""
        if run.get("status") == "running":
            run["progress"] = self.progress(str(run.get("run_id")))
        return self._with_waiting(run)

    def record_skipped(
        self,
        task_id: str,
        options: dict[str, Any],
        triggered_by: str,
        reason: str,
        schedule_id: str | None = None,
    ) -> dict[str, Any]:
        """Record a run that was not started, so it shows in history with why."""
        run_id = str(uuid4())
        log_path = (self.logs_dir / f"{run_id}.log").resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(f"[skip] {reason}\n", encoding="utf-8")
        self.state.create_run(
            run_id=run_id,
            task_id=task_id,
            options=options,
            triggered_by=triggered_by,
            schedule_id=schedule_id,
            log_path=str(log_path),
        )
        self.state.update_run_status(run_id, status="canceled", finished_at=utc_now_iso(), error_text=reason)
        return self.state.get_run(run_id) or {"run_id": run_id}

    def cancel(self, run_id: str) -> bool:
        record = self.state.get_run(run_id)
        if record is None:
            return False
        status = str(record.get("status"))
        if status in {"succeeded", "failed", "canceled"}:
            return False

        # Hold the locks across both the status check and the termination to
        # avoid a race with the run starting or _execute_run finishing.
        with self._cond, self._active_lock:
            pending = next((slot for slot in self._pending if slot.run_id == run_id), None)
            if pending is not None:
                self._pending.remove(pending)
                self._cond.notify_all()
            # _execute_run moves a run to running under this lock, so this is current.
            status = str((self.state.get_run(run_id) or {}).get("status"))
            if status in {"succeeded", "failed", "canceled"}:
                return False
            if status == "queued":
                self.state.update_run_status(
                    run_id,
                    status="canceled",
                    finished_at=utc_now_iso(),
                    exit_code=None,
                    error_text="Stopped before it started.",
                )
                logger.info("run %s canceled before execution", run_id)
                return True

            proc = self._active.get(run_id)
            if proc is not None:
                self._terminate_process_tree(proc, wait_for_exit=False)
            self.state.update_run_status(
                run_id,
                status="canceled",
                finished_at=utc_now_iso(),
                exit_code=None,
                error_text="Stopped while running. Changes it made before then stay.",
            )
            logger.info("run %s canceled while running", run_id)
            return True

    def _was_canceled(self, run_id: str) -> bool:
        current = self.state.get_run(run_id)
        return bool(current) and str(current.get("status")) == "canceled"

    def _result_path(self, run_id: str) -> Path:
        return (self.logs_dir / f"{run_id}.result.jsonl").resolve()

    def ingest_results(self, run_id: str) -> list[dict[str, Any]] | None:
        """Move a finished run's result file into state.db and return the results.

        Safe to call more than once: once the file is gone, stored results are
        returned unchanged.
        """
        path = self._result_path(run_id)
        if not path.exists():
            return self.state.get_run_results(run_id)
        results = read_results(path)
        self.state.set_run_results(run_id, results)
        try:
            path.unlink()
        except OSError:
            pass
        return results

    def read_log(self, run_id: str, max_bytes: int = 200_000) -> str:
        record = self.state.get_run(run_id)
        if record is None:
            raise KeyError(run_id)
        path = Path(str(record["log_path"]))
        if not path.exists():
            return ""
        data = path.read_text(encoding="utf-8", errors="replace")
        if len(data.encode("utf-8")) <= max_bytes:
            return data
        trimmed = data.encode("utf-8")[-max_bytes:].decode("utf-8", errors="replace")
        return trimmed

    def _next_startable(self) -> _Slot | None:
        running = list(self._running.values())
        for index, slot in enumerate(self._pending):
            if _blocker(slot, self._pending[:index], running) is None:
                return slot
        return None

    def _dispatch_loop(self) -> None:
        while not self._stop.is_set():
            with self._cond:
                slot = self._next_startable()
                if slot is None:
                    self._cond.wait(timeout=0.5)
                    continue
                self._pending.remove(slot)
                self._running[slot.run_id] = slot
                thread = Thread(target=self._run_one, args=(slot,), daemon=True, name=f"run-{slot.run_id[:8]}")
                self._run_threads[slot.run_id] = thread
            logger.info("run %s dispatched: lane=%s writes=%s", slot.run_id, slot.lane, ",".join(sorted(slot.writes)) or "nothing")
            thread.start()

    def _run_one(self, slot: _Slot) -> None:
        run_id = slot.run_id
        try:
            run = self.state.get_run(run_id)
            if run is None or str(run.get("status")) != "queued":
                return
            self._execute_run(run_id, run, lane=slot.lane)
        except Exception as exc:
            logger.exception("run %s crashed in the runner", run_id)
            current_run = self.state.get_run(run_id)
            if current_run and str(current_run.get("status")) in {"queued", "running"}:
                self.state.update_run_status(
                    run_id,
                    status="failed",
                    finished_at=utc_now_iso(),
                    exit_code=1,
                    error_text=f"Runner internal error: {exc}",
                )
            log_path_raw = str((current_run or {}).get("log_path") or "").strip()
            if log_path_raw:
                log_path = Path(log_path_raw)
                try:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    with log_path.open("a", encoding="utf-8") as log_file:
                        log_file.write(f"[runner-error] {type(exc).__name__}: {exc}\n")
                    self.state.update_run_log_size(run_id, log_path.stat().st_size)
                except OSError:
                    pass
        finally:
            try:
                self.ingest_results(run_id)
            except Exception:
                logger.exception("run %s failed while storing its results", run_id)
            with self._cond:
                self._running.pop(run_id, None)
                self._run_threads.pop(run_id, None)
                self._cond.notify_all()
            try:
                self._rotate_logs()
            except Exception:
                logger.exception("run %s failed during log rotation", run_id)

    def _execute_run(self, run_id: str, run: dict[str, Any], lane: str = lanes.HEAVY) -> None:
        task_id = str(run["task_id"])
        started_at = utc_now_iso()
        # Under the lock cancel() holds, so a Stop pressed just now isn't overwritten.
        with self._active_lock:
            if self._was_canceled(run_id):
                return
            self.state.update_run_status(run_id, status="running", started_at=started_at)
        logger.info("run %s starting: task=%s lane=%s", run_id, task_id, lane)
        log_path = Path(str(run["log_path"]))
        log_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            execution = self.registry.build_execution(task_id, dict(run.get("options") or {}))
        except (KeyError, ValueError, TypeError) as exc:
            message = f"Task build failed: {exc}"
            log_path.write_text(message + "\n", encoding="utf-8")
            self.state.update_run_status(
                run_id,
                status="failed",
                finished_at=utc_now_iso(),
                exit_code=1,
                error_text=message,
            )
            self.state.update_run_log_size(run_id, log_path.stat().st_size)
            logger.error("run %s failed to build task=%s: %s", run_id, task_id, exc)
            return

        # Build a minimal environment for the subprocess — avoid leaking the
        # full parent process env (which may contain unrelated secrets).
        env: dict[str, str] = {}
        # Inherit only essential system vars needed for Python/subprocesses.
        for key in ("PATH", "HOME", "USER", "LANG", "LC_ALL", "SYSTEMROOT",
                     "TEMP", "TMP", "COMSPEC", "VIRTUAL_ENV", "PYTHONPATH",
                     # Where the web UI keeps its data, so jobs find dredger.db next to it.
                     "WEB_STATE_DB_PATH"):
            if key in os.environ:
                env[key] = os.environ[key]
        env.update(self.environment_provider())
        env.update(execution.env)
        # Suppress urllib3's LibreSSL warning — macOS ships LibreSSL which triggers
        # a noisy NotOpenSSLWarning on every import; it's harmless and clutters logs.
        # Filter format: action:message:category:module:lineno
        # Modules append structured results here (see cookdex.reporting).
        result_path = self._result_path(run_id)
        try:
            result_path.unlink()
        except FileNotFoundError:
            pass
        env[RESULT_PATH_ENV] = str(result_path)
        _suppress = "ignore:::urllib3"
        _existing = env.get("PYTHONWARNINGS", "")
        env["PYTHONWARNINGS"] = f"{_existing},{_suppress}" if _existing else _suppress
        # Jobs print recipe names and arrows; make them write UTF-8 to the pipe
        # (and to any stages they start) whatever the host's locale, as a
        # Windows console encoding can't represent them and the job would crash.
        env["PYTHONIOENCODING"] = "utf-8"
        # Every job's Mealie requests share one cap (see cookdex.mealie_slots).
        env[SLOTS_DIR_ENV] = str(self.slots_dir)
        env[LANE_ENV] = lane
        command = execution.command

        with log_path.open("w", encoding="utf-8") as log_file:
            # Run pre-commands (e.g. Mealie backup) before the main task.
            for pre_cmd in execution.pre_commands:
                log_file.write(f"$ {' '.join(pre_cmd)}\n")
                log_file.flush()
                try:
                    # Popen rather than run, so Stop can end a backup too.
                    pre_proc = subprocess.Popen(
                        pre_cmd,
                        cwd=str(REPO_ROOT),
                        env=env,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        text=True,
                        start_new_session=True,
                    )
                    with self._active_lock:
                        self._active[run_id] = pre_proc
                    try:
                        # Pre-commands are backups: give them the backup wait plus a margin.
                        pre_proc.wait(timeout=backup_timeout_seconds(env) + 300)
                    except subprocess.TimeoutExpired:
                        self._terminate_process_tree(pre_proc, wait_for_exit=True)
                        raise
                    finally:
                        with self._active_lock:
                            self._active.pop(run_id, None)
                    pre_result = pre_proc
                    if self._was_canceled(run_id):
                        self.state.update_run_log_size(run_id, log_path.stat().st_size)
                        return
                    if pre_result.returncode != 0:
                        message = f"Pre-command failed (exit {pre_result.returncode}): {' '.join(pre_cmd)}"
                        log_file.write(f"\n{message}\n")
                        self.state.update_run_status(
                            run_id,
                            status="failed",
                            finished_at=utc_now_iso(),
                            exit_code=pre_result.returncode,
                            error_text=message,
                        )
                        self.state.update_run_log_size(run_id, log_path.stat().st_size)
                        logger.error("run %s pre-command failed: %s", run_id, message)
                        return
                except Exception as exc:
                    message = f"Pre-command error: {exc}"
                    log_file.write(f"\n{message}\n")
                    self.state.update_run_status(
                        run_id,
                        status="failed",
                        finished_at=utc_now_iso(),
                        exit_code=1,
                        error_text=message,
                    )
                    self.state.update_run_log_size(run_id, log_path.stat().st_size)
                    return

            log_file.write(f"$ {' '.join(command)}\n")
            log_file.flush()
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(REPO_ROOT),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    start_new_session=True,
                )
            except FileNotFoundError as exc:
                message = f"Failed to start process: {exc}"
                log_file.write(message + "\n")
                self.state.update_run_status(
                    run_id,
                    status="failed",
                    finished_at=utc_now_iso(),
                    exit_code=1,
                    error_text=message,
                )
                self.state.update_run_log_size(run_id, log_path.stat().st_size)
                logger.error("run %s failed to start process: %s", run_id, exc)
                return

            with self._active_lock:
                self._active[run_id] = process
                stopped_first = self._was_canceled(run_id)
            if stopped_first:
                # Stopped between the backup and the job: don't start it.
                self._terminate_process_tree(process, wait_for_exit=True)

            max_duration = _resolve_max_duration_seconds(env, execution.max_duration)
            timed_out = False
            try:
                # Stream stdout in a background thread so the main thread can
                # enforce a max-duration deadline without blocking on I/O.
                done_event = Event()

                def _stream_stdout() -> None:
                    try:
                        if process.stdout is not None:
                            for line in process.stdout:
                                if line.startswith(PROGRESS_PREFIX):
                                    self._record_progress(run_id, line)
                                    continue
                                log_file.write(line)
                                log_file.flush()
                    finally:
                        done_event.set()

                streamer = Thread(target=_stream_stdout, daemon=True, name=f"log-{run_id[:8]}")
                streamer.start()

                deadline = time.monotonic() + max_duration
                while not done_event.is_set():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        hrs = max_duration / 3600
                        timeout_msg = (
                            f"\n[error] Run exceeded maximum duration "
                            f"({hrs:.1f}h) — terminating.\n"
                        )
                        log_file.write(timeout_msg)
                        log_file.flush()
                        self._terminate_process_tree(process, wait_for_exit=True)
                        break
                    done_event.wait(timeout=min(remaining, 5.0))

                streamer.join(timeout=5)
                exit_code = process.wait(timeout=5) if not timed_out else process.poll()
            finally:
                with self._active_lock:
                    self._active.pop(run_id, None)
                self._progress.pop(run_id, None)

            current_run = self.state.get_run(run_id)
            if current_run and str(current_run.get("status")) == "canceled":
                self.state.update_run_log_size(run_id, log_path.stat().st_size)
                return

            if timed_out:
                hrs = max_duration / 3600
                self.state.update_run_status(
                    run_id,
                    status="failed",
                    finished_at=utc_now_iso(),
                    exit_code=exit_code,
                    error_text=f"Timed out after {hrs:.1f}h (max {max_duration}s).",
                )
                logger.error("run %s timed out: task=%s max_duration=%ss", run_id, task_id, max_duration)
            elif exit_code == 0:
                self.state.update_run_status(
                    run_id,
                    status="succeeded",
                    finished_at=utc_now_iso(),
                    exit_code=0,
                    error_text=None,
                )
                # Invalidate cached metrics so the next dashboard load is fresh.
                try:
                    self.state.cache_invalidate_all()
                except Exception:
                    pass
                logger.info("run %s succeeded: task=%s", run_id, task_id)
            else:
                self.state.update_run_status(
                    run_id,
                    status="failed",
                    finished_at=utc_now_iso(),
                    exit_code=exit_code,
                    error_text=f"Process exited with code {exit_code}.",
                )
                logger.error("run %s failed: task=%s exit_code=%s", run_id, task_id, exit_code)
            self.state.update_run_log_size(run_id, log_path.stat().st_size)

    def _terminate_process_tree(self, process: subprocess.Popen[str], *, wait_for_exit: bool) -> None:
        try:
            if process.poll() is not None:
                return
        except OSError:
            return

        can_kill_process_group = hasattr(os, "killpg") and hasattr(os, "getpgid")
        sent = False
        if can_kill_process_group:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                sent = True
            except OSError:
                pass

        if not sent:
            try:
                process.terminate()
                sent = True
            except OSError:
                pass

        if not wait_for_exit:
            return

        try:
            process.wait(timeout=3)
            return
        except (subprocess.TimeoutExpired, OSError):
            pass

        if can_kill_process_group:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except OSError:
                try:
                    process.kill()
                except OSError:
                    return
        else:
            try:
                process.kill()
            except OSError:
                return

        try:
            process.wait(timeout=1)
        except (subprocess.TimeoutExpired, OSError):
            pass

    def _rotate_logs(self) -> None:
        if self.max_log_files <= 0:
            return
        try:
            log_files = sorted(self.logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
        except OSError:
            return
        excess = len(log_files) - self.max_log_files
        with self._cond:
            # Two runs can finish together now; never remove a log still in use.
            in_use = {f"{run_id}.log" for run_id in self._running} | {f"{slot.run_id}.log" for slot in self._pending}
        for path in log_files[:excess]:
            if path.name in in_use:
                continue
            try:
                path.unlink()
            except OSError:
                continue
