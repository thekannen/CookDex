from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import logging
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import uuid4

logger = logging.getLogger(__name__)

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .runner import RunQueueManager
from .state import StateStore
from .tasks import RETIRED_TASKS, TaskRegistry

_DISPATCHERS: dict[str, Callable[[str], None]] = {}
_HOUSEKEEPERS: dict[str, Callable[[], None]] = {}
_HOUSEKEEPING_INTERVAL_SECONDS = 15 * 60
_DEFAULT_MISFIRE_GRACE_SECONDS = 60
_MISSED_INTERVAL_GRACE_SECONDS = 7 * 24 * 60 * 60
_MISSED_ONCE_GRACE_SECONDS = 30 * 24 * 60 * 60


def _dispatcher_id_for_path(sqlite_path: str) -> str:
    digest = hashlib.sha256(sqlite_path.encode("utf-8")).hexdigest()
    return f"scheduler:{digest}"


def _run_registered_dispatcher(dispatcher_id: str, schedule_id: str) -> None:
    dispatcher = _DISPATCHERS.get(dispatcher_id)
    if dispatcher is None:
        return
    dispatcher(schedule_id)


def _run_registered_housekeeping(dispatcher_id: str) -> None:
    housekeeper = _HOUSEKEEPERS.get(dispatcher_id)
    if housekeeper is None:
        return
    housekeeper()

# APScheduler numbers days from Monday; CookDex (like JavaScript) from Sunday.
_CRON_DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]


def server_timezone() -> str:
    """The container's time zone (TZ), for schedules saved without one."""
    import os

    name = os.environ.get("TZ", "").strip()
    if name:
        try:
            ZoneInfo(name)
            return name
        except (ZoneInfoNotFoundError, ValueError):
            pass
    try:
        from tzlocal import get_localzone_name

        return get_localzone_name() or "UTC"
    except Exception:
        return "UTC"


def parse_calendar(data: dict[str, Any]) -> tuple[str, int, int, int, ZoneInfo]:
    """(every, hour, minute, weekday, zone) of a calendar schedule, or ValueError.

    Calendar schedules run at a wall-clock time in a time zone ("every Sunday
    at 8:00 AM"), so they follow daylight saving, unlike a fixed interval.
    """
    every = str(data.get("every") or "")
    if every not in {"day", "week"}:
        raise ValueError("Calendar schedules run every 'day' or every 'week'.")
    try:
        hour, minute = (int(part) for part in str(data.get("time") or "").split(":"))
    except ValueError as exc:
        raise ValueError("Calendar schedules need a time like '08:00'.") from exc
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError("Calendar schedules need a time like '08:00'.")
    weekday = int(data.get("weekday") or 0)
    if not 0 <= weekday <= 6:
        raise ValueError("Weekday must be 0 (Sunday) to 6 (Saturday).")
    try:
        zone = ZoneInfo(str(data.get("timezone") or "UTC"))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown time zone '{data.get('timezone')}'.") from exc
    return every, hour, minute, weekday, zone


def last_calendar_time(data: dict[str, Any], now: datetime) -> datetime | None:
    """The latest time at or before *now* that a calendar schedule was due."""
    every, hour, minute, weekday, zone = parse_calendar(data)
    local = now.astimezone(zone)
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if every == "week":
        # Python's weekday() is Monday=0; CookDex's is Sunday=0.
        days_back = (local.weekday() + 1 - weekday) % 7
        candidate = candidate - timedelta(days=days_back)
    if candidate > local:
        candidate -= timedelta(days=7 if every == "week" else 1)
    # Rebuild in the zone so a daylight-saving change in between is respected.
    candidate = datetime(candidate.year, candidate.month, candidate.day, hour, minute, tzinfo=zone)
    return candidate.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SchedulePayload:
    name: str
    task_id: str
    schedule_kind: str
    schedule_data: dict[str, Any]
    options: dict[str, Any]
    enabled: bool = True


class SchedulerService:
    def __init__(
        self,
        state: StateStore,
        runner: RunQueueManager,
        registry: TaskRegistry,
        sqlite_path: str,
    ) -> None:
        self.state = state
        self.runner = runner
        self.registry = registry
        self.dispatcher_id = _dispatcher_id_for_path(sqlite_path)
        _DISPATCHERS[self.dispatcher_id] = self._fire_schedule
        _HOUSEKEEPERS[self.dispatcher_id] = self._run_housekeeping
        self.scheduler = BackgroundScheduler(
            timezone="UTC",
            # The schedules table is the only record of schedules; jobs are
            # rebuilt from it at every start, so they're kept in memory.
            jobstores={
                "default": MemoryJobStore(),
                "housekeeping": MemoryJobStore(),
            },
        )

    def start(self) -> None:
        self._restore_from_db()
        self._schedule_housekeeping()
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        _DISPATCHERS.pop(self.dispatcher_id, None)
        _HOUSEKEEPERS.pop(self.dispatcher_id, None)
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def _schedule_housekeeping(self) -> None:
        self.scheduler.add_job(
            func=_run_registered_housekeeping,
            trigger=IntervalTrigger(
                seconds=_HOUSEKEEPING_INTERVAL_SECONDS,
                timezone="UTC",
            ),
            id=f"housekeeping:{self.dispatcher_id}",
            replace_existing=True,
            kwargs={"dispatcher_id": self.dispatcher_id},
            misfire_grace_time=_DEFAULT_MISFIRE_GRACE_SECONDS,
            coalesce=True,
            max_instances=1,
            jobstore="housekeeping",
        )

    def _run_housekeeping(self) -> None:
        """Periodic state trimming that used to run on the request path."""
        from .state import utc_now_iso

        try:
            self.state.purge_expired_sessions(utc_now_iso())
        except Exception:
            logger.exception("housekeeping: purging expired sessions failed")
        try:
            self.state.prune_runs()
        except Exception:
            logger.exception("housekeeping: pruning run history failed")

    def list_schedules(self) -> list[dict[str, Any]]:
        schedules = self.state.list_schedules()
        for item in schedules:
            job = self.scheduler.get_job(item["schedule_id"])
            item["next_run_at"] = _iso(job.next_run_time) if job else None
        return schedules

    def create_schedule(self, payload: SchedulePayload) -> dict[str, Any]:
        self._validate_schedule_definition(payload.schedule_kind, payload.schedule_data)
        schedule_id = str(uuid4())
        record = self.state.create_schedule(
            schedule_id=schedule_id,
            name=payload.name,
            task_id=payload.task_id,
            schedule_kind=payload.schedule_kind,
            schedule_data=payload.schedule_data,
            options=payload.options,
            enabled=payload.enabled,
            validation_error=None,
        )
        self._sync_schedule_job(record)
        return self._with_next_run(record)

    def update_schedule(self, schedule_id: str, payload: SchedulePayload) -> dict[str, Any] | None:
        if self.state.get_schedule(schedule_id) is None:
            return None
        self._validate_schedule_definition(payload.schedule_kind, payload.schedule_data)
        record = self.state.update_schedule(
            schedule_id=schedule_id,
            name=payload.name,
            task_id=payload.task_id,
            schedule_kind=payload.schedule_kind,
            schedule_data=payload.schedule_data,
            options=payload.options,
            enabled=payload.enabled,
            validation_error=None,
        )
        self._sync_schedule_job(record)
        return self._with_next_run(record)

    def delete_schedule(self, schedule_id: str) -> bool:
        existing = self.state.get_schedule(schedule_id)
        if existing is None:
            return False
        try:
            self.scheduler.remove_job(schedule_id, jobstore="default")
        except Exception:
            pass
        self.state.delete_schedule(schedule_id)
        return True

    def _retire_unknown_task(self, schedule_id: str, task_id: str) -> None:
        """Turn off a schedule whose task no longer exists, and say why."""
        reason = RETIRED_TASKS.get(task_id, f"The task '{task_id}' no longer exists. Pick another task for this schedule.")
        changed = self.state.retire_schedules({task_id: reason})
        try:
            self.scheduler.remove_job(schedule_id, jobstore="default")
        except Exception:
            pass
        if changed:
            logger.warning("schedule %s uses unknown task %s; turned it off", schedule_id, task_id)

    def _restore_from_db(self) -> None:
        for item in self.state.list_schedules():
            if str(item["task_id"]) not in self.registry.task_ids:
                self._retire_unknown_task(str(item["schedule_id"]), str(item["task_id"]))
                continue
            try:
                kind = str(item["schedule_kind"])
                schedule_data = dict(item["schedule_data"])
                if self._should_skip_restored_once_schedule(item, schedule_data):
                    if item.get("validation_error"):
                        self.state.set_schedule_validation_error(str(item["schedule_id"]), None)
                    continue
                self._validate_schedule_definition(kind, schedule_data, enforce_future_once=False)
                if item.get("validation_error"):
                    self.state.set_schedule_validation_error(str(item["schedule_id"]), None)
                    item["validation_error"] = None
                self._sync_schedule_job(item)
                self._catch_up_if_missed(item, schedule_data)
            except Exception as exc:
                detail = str(exc)
                self.state.set_schedule_validation_error(str(item["schedule_id"]), detail)
                logger.warning(
                    "Skipping schedule %s (%s) on restore: %s",
                    item.get("schedule_id"), item.get("name"), detail,
                )

    def _catch_up_if_missed(self, record: dict[str, Any], schedule_data: dict[str, Any]) -> None:
        """Run a repeating schedule once now if it came due while CookDex was down.

        Jobs are rebuilt in memory at start, and a rebuilt interval trigger
        only looks forward, so a schedule marked "run if missed" gets one
        catch-up run for its most recent missed time (within a week).
        """
        kind = str(record.get("schedule_kind"))
        if not bool(record.get("enabled")) or kind not in {"interval", "calendar"}:
            return
        if not bool(schedule_data.get("run_if_missed")):
            return
        now = datetime.now(timezone.utc)
        due = last_calendar_time(schedule_data, now) if kind == "calendar" else self.last_due_time(schedule_data, now)
        if due is None:
            return
        since = self._parse_dt(record.get("last_enqueued_at")) or self._parse_dt(record.get("created_at"))
        if since is not None and due <= since:
            return
        if (datetime.now(timezone.utc) - due).total_seconds() > _MISSED_INTERVAL_GRACE_SECONDS:
            return
        logger.info("schedule %s came due at %s while CookDex was down; running it now", record.get("schedule_id"), _iso(due))
        self._fire_schedule(str(record["schedule_id"]))

    @classmethod
    def last_due_time(cls, schedule_data: dict[str, Any], now: datetime) -> datetime | None:
        """The latest time at or before *now* that an interval schedule was due."""
        seconds = int(schedule_data.get("seconds") or 0)
        start = cls._parse_dt(schedule_data.get("start_at"))
        if seconds <= 0 or start is None or start > now:
            return None
        end = cls._parse_dt(schedule_data.get("end_at"))
        last = start + timedelta(seconds=seconds * int((now - start).total_seconds() // seconds))
        if end is not None and last > end:
            return None
        return last

    def _with_next_run(self, record: dict[str, Any]) -> dict[str, Any]:
        job = self.scheduler.get_job(str(record["schedule_id"]))
        payload = dict(record)
        payload["next_run_at"] = _iso(job.next_run_time) if job else None
        return payload

    def _sync_schedule_job(self, record: dict[str, Any]) -> None:
        schedule_id = str(record["schedule_id"])
        if not bool(record["enabled"]):
            try:
                self.scheduler.remove_job(schedule_id, jobstore="default")
            except Exception:
                pass
            return
        schedule_data = dict(record["schedule_data"])
        trigger = self._build_trigger(record["schedule_kind"], schedule_data)
        misfire_grace_time = self._resolve_misfire_grace_time(str(record["schedule_kind"]), schedule_data)
        self.scheduler.add_job(
            func=_run_registered_dispatcher,
            trigger=trigger,
            id=schedule_id,
            replace_existing=True,
            kwargs={"dispatcher_id": self.dispatcher_id, "schedule_id": schedule_id},
            misfire_grace_time=misfire_grace_time,
            coalesce=True,
            max_instances=1,
            jobstore="default",
        )

    def _resolve_misfire_grace_time(self, kind: str, schedule_data: dict[str, Any]) -> int:
        run_if_missed = bool(schedule_data.get("run_if_missed", False))
        if not run_if_missed:
            return _DEFAULT_MISFIRE_GRACE_SECONDS
        if kind == "once":
            return _MISSED_ONCE_GRACE_SECONDS
        return _MISSED_INTERVAL_GRACE_SECONDS  # interval and calendar

    @staticmethod
    def _parse_dt(val: str | None) -> datetime | None:
        """Parse a datetime string to a timezone-aware UTC datetime.

        Accepts ISO 8601 with Z suffix (from frontend), naive datetime-local
        strings (legacy), and full ISO 8601 with offset.
        """
        if not val:
            return None
        s = str(val).strip()
        if not s:
            return None
        # Pad "YYYY-MM-DDTHH:MM" → "YYYY-MM-DDTHH:MM:00" for fromisoformat
        if len(s) == 16 and "T" in s:
            s = s + ":00"
        # Replace trailing Z with +00:00 for fromisoformat (Python 3.9 compat)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _should_skip_restored_once_schedule(
        self,
        record: dict[str, Any],
        schedule_data: dict[str, Any],
    ) -> bool:
        if str(record.get("schedule_kind") or "") != "once":
            return False
        if record.get("last_enqueued_at") is None:
            return False
        run_at = self._parse_dt(schedule_data.get("run_at"))
        return run_at is not None and run_at <= datetime.now(timezone.utc)

    def _validate_schedule_definition(
        self,
        kind: str,
        schedule_data: dict[str, Any],
        *,
        enforce_future_once: bool = True,
    ) -> None:
        if kind == "interval":
            start_date = self._parse_dt(schedule_data.get("start_at"))
            end_date = self._parse_dt(schedule_data.get("end_at"))
            if start_date is not None and end_date is not None and start_date >= end_date:
                raise ValueError("Interval schedules require 'start_at' before 'end_at'.")
            self._build_trigger(kind, schedule_data)
            return

        if kind == "once":
            run_at_raw = str(schedule_data.get("run_at", "")).strip()
            if not run_at_raw:
                raise ValueError("Once schedules require non-empty 'run_at'.")
            run_at = self._parse_dt(run_at_raw)
            if run_at is None:
                raise ValueError("Once schedules require non-empty 'run_at'.")
            if enforce_future_once and run_at <= datetime.now(timezone.utc):
                raise ValueError("Once schedules require 'run_at' in the future.")
            self._build_trigger(kind, schedule_data)
            return

        if kind == "calendar":
            parse_calendar(schedule_data)
            return

        raise ValueError(f"Unsupported schedule kind: {kind}")

    def _build_trigger(self, kind: str, schedule_data: dict[str, Any]) -> IntervalTrigger | DateTrigger:
        if kind == "interval":
            seconds = int(schedule_data.get("seconds", 0))
            if seconds <= 0:
                raise ValueError("Interval schedules require positive 'seconds'.")
            start_date = self._parse_dt(schedule_data.get("start_at"))
            end_date = self._parse_dt(schedule_data.get("end_at"))
            return IntervalTrigger(seconds=seconds, timezone="UTC", start_date=start_date, end_date=end_date)
        if kind == "once":
            run_at_raw = str(schedule_data.get("run_at", "")).strip()
            if not run_at_raw:
                raise ValueError("Once schedules require non-empty 'run_at'.")
            run_at = self._parse_dt(run_at_raw)
            return DateTrigger(run_date=run_at)
        if kind == "calendar":
            every, hour, minute, weekday, zone = parse_calendar(schedule_data)
            return CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=_CRON_DAYS[weekday] if every == "week" else "*",
                timezone=zone,
            )
        raise ValueError(f"Unsupported schedule kind: {kind}")

    def _fire_schedule(self, schedule_id: str) -> None:
        record = self.state.get_schedule(schedule_id)
        if record is None or not bool(record["enabled"]):
            return
        task_id = str(record["task_id"])
        if task_id not in self.registry.task_ids:
            self._retire_unknown_task(schedule_id, task_id)
            return
        options = dict(record["options"])
        # Re-check approval when the schedule fires, not only when it was
        # saved: revoking a task's unattended-run policy must stop live runs.
        try:
            writes = self.registry.build_execution(task_id, options).dangerous_requested
        except (ValueError, KeyError):
            writes = False
        from .tasks import policy_key

        policy = self.state.list_task_policies().get(policy_key(task_id, options), {})
        if writes and not policy.get("allow_dangerous"):
            self.runner.record_skipped(
                task_id,
                options,
                "scheduler",
                "Not run: this schedule applies changes, and unattended changes for this task aren't approved. "
                "An owner can approve them on the Automations page.",
                schedule_id=schedule_id,
            )
            self.state.touch_schedule_enqueue(schedule_id)
            return
        self.runner.enqueue(
            task_id=task_id,
            options=options,
            triggered_by="scheduler",
            schedule_id=schedule_id,
        )
        self.state.touch_schedule_enqueue(schedule_id)
