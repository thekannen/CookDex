from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from cookdex.webui_server.scheduler import SchedulerService


def _make_service(tmp_path):
    """Create a minimal SchedulerService without starting it."""
    from unittest.mock import MagicMock
    from cookdex.webui_server.scheduler import SchedulerService
    from cookdex.webui_server.tasks import TaskRegistry

    svc = SchedulerService.__new__(SchedulerService)
    svc.state = MagicMock()
    svc.runner = MagicMock()
    svc.registry = MagicMock()
    svc.registry.task_ids = set(TaskRegistry().task_ids)  # restore skips unknown tasks
    svc.dispatcher_id = "test-dispatcher"

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.memory import MemoryJobStore
    svc.scheduler = BackgroundScheduler(timezone="UTC", jobstores={"default": MemoryJobStore()})
    return svc


class TestBuildTrigger:
    def test_interval_returns_interval_trigger(self, tmp_path):
        svc = _make_service(tmp_path)
        trigger = svc._build_trigger("interval", {"seconds": 3600})
        assert isinstance(trigger, IntervalTrigger)

    def test_interval_zero_seconds_raises(self, tmp_path):
        svc = _make_service(tmp_path)
        with pytest.raises(ValueError, match="positive"):
            svc._build_trigger("interval", {"seconds": 0})

    def test_interval_negative_seconds_raises(self, tmp_path):
        svc = _make_service(tmp_path)
        with pytest.raises(ValueError, match="positive"):
            svc._build_trigger("interval", {"seconds": -60})

    def test_once_full_iso_returns_date_trigger(self, tmp_path):
        svc = _make_service(tmp_path)
        run_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        trigger = svc._build_trigger("once", {"run_at": run_at})
        assert isinstance(trigger, DateTrigger)

    def test_once_short_format_normalized(self, tmp_path):
        """datetime-local inputs produce "YYYY-MM-DDTHH:MM" without seconds."""
        svc = _make_service(tmp_path)
        run_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        assert len(run_at) == 16  # confirm short format
        trigger = svc._build_trigger("once", {"run_at": run_at})
        assert isinstance(trigger, DateTrigger)

    def test_once_missing_run_at_raises(self, tmp_path):
        svc = _make_service(tmp_path)
        with pytest.raises(ValueError, match="run_at"):
            svc._build_trigger("once", {})

    def test_once_empty_run_at_raises(self, tmp_path):
        svc = _make_service(tmp_path)
        with pytest.raises(ValueError, match="run_at"):
            svc._build_trigger("once", {"run_at": ""})

    def test_unsupported_kind_raises(self, tmp_path):
        svc = _make_service(tmp_path)
        with pytest.raises(ValueError, match="Unsupported"):
            svc._build_trigger("cron", {"expression": "* * * * *"})


class TestMisfirePolicy:
    def test_default_grace_short(self, tmp_path):
        svc = _make_service(tmp_path)
        assert svc._resolve_misfire_grace_time("interval", {}) == 60

    def test_interval_run_if_missed_extends_grace(self, tmp_path):
        svc = _make_service(tmp_path)
        assert svc._resolve_misfire_grace_time("interval", {"run_if_missed": True}) == 7 * 24 * 60 * 60

    def test_once_run_if_missed_extends_grace(self, tmp_path):
        svc = _make_service(tmp_path)
        assert svc._resolve_misfire_grace_time("once", {"run_if_missed": True}) == 30 * 24 * 60 * 60


class TestRestoreFromDb:
    def test_bad_schedule_does_not_crash_restore(self, tmp_path):
        """A schedule with invalid data should be skipped, not crash the server."""
        svc = _make_service(tmp_path)
        svc.state.list_schedules.return_value = [
            {
                "schedule_id": "bad-id",
                "name": "Broken",
                "task_id": "tag-categorize",
                "schedule_kind": "once",
                "schedule_data": {"run_at": ""},  # invalid — empty run_at
                "options": {},
                "enabled": True,
            }
        ]
        svc.scheduler.start()
        try:
            # Should complete without raising
            svc._restore_from_db()
        finally:
            svc.scheduler.shutdown(wait=False)
        svc.state.set_schedule_validation_error.assert_called_with(
            "bad-id",
            "Once schedules require non-empty 'run_at'.",
        )

    def test_restore_clears_legacy_validation_error_for_valid_schedule(self, tmp_path):
        svc = _make_service(tmp_path)
        future_run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        svc.state.list_schedules.return_value = [
            {
                "schedule_id": "good-id",
                "name": "Recovered",
                "task_id": "tag-categorize",
                "schedule_kind": "once",
                "schedule_data": {"run_at": future_run_at},
                "options": {},
                "enabled": False,
                "validation_error": "Old error",
            }
        ]
        svc.scheduler.start()
        try:
            svc._restore_from_db()
        finally:
            svc.scheduler.shutdown(wait=False)
        svc.state.set_schedule_validation_error.assert_called_with("good-id", None)

    def test_restore_skips_already_fired_once_schedule_without_marking_it_invalid(self, tmp_path):
        svc = _make_service(tmp_path)
        past_run_at = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        svc.state.list_schedules.return_value = [
            {
                "schedule_id": "done-id",
                "name": "Already fired",
                "task_id": "tag-categorize",
                "schedule_kind": "once",
                "schedule_data": {"run_at": past_run_at},
                "options": {},
                "enabled": True,
                "last_enqueued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "validation_error": "Old error",
            }
        ]
        svc.scheduler.start()
        try:
            svc._restore_from_db()
            assert svc.scheduler.get_job("done-id") is None
        finally:
            svc.scheduler.shutdown(wait=False)
        svc.state.set_schedule_validation_error.assert_called_with("done-id", None)


class TestStartOrder:
    def test_start_restores_before_starting_scheduler(self, tmp_path):
        """Verify _restore_from_db runs before scheduler.start()."""
        from unittest.mock import MagicMock

        svc = SchedulerService.__new__(SchedulerService)
        svc.state = MagicMock()
        svc.runner = MagicMock()
        svc.registry = MagicMock()
        svc.dispatcher_id = "test-dispatcher"
        svc.state.list_schedules.return_value = []

        # Use a mock scheduler to track call order
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        svc.scheduler = mock_scheduler

        call_order = []
        svc.state.list_schedules.side_effect = lambda: (call_order.append("restore"), [])[-1]
        mock_scheduler.start.side_effect = lambda: call_order.append("start")

        svc.start()

        assert call_order == ["restore", "start"], f"Expected restore before start, got {call_order}"


def test_housekeeping_purges_sessions_and_prunes_runs(tmp_path):
    """Session purge moved off the request path into the scheduler."""
    from cookdex.webui_server.scheduler import SchedulerService
    from cookdex.webui_server.state import StateStore
    from cookdex.webui_server.tasks import TaskRegistry

    db_path = tmp_path / "state.db"
    state = StateStore(db_path)
    registry = TaskRegistry()
    state.initialize(registry.task_ids)
    state.create_user("someone", "pbkdf2_sha256$1$AAAA$AAAA", role="owner")

    state.create_session(token="stale", username="someone", expires_at="2000-01-01T00:00:00Z")
    state.create_session(token="fresh", username="someone", expires_at="2999-01-01T00:00:00Z")

    service = SchedulerService(
        state=state,
        runner=None,
        registry=registry,
        sqlite_path=str(db_path),
    )
    service._run_housekeeping()

    assert state.get_session("stale") is None
    assert state.get_session("fresh") is not None


def test_housekeeping_job_is_not_persisted(tmp_path):
    """The housekeeping job stays out of the store that holds user schedules."""
    from cookdex.webui_server.scheduler import SchedulerService
    from cookdex.webui_server.state import StateStore
    from cookdex.webui_server.tasks import TaskRegistry

    db_path = tmp_path / "state.db"
    state = StateStore(db_path)
    registry = TaskRegistry()
    state.initialize(registry.task_ids)

    service = SchedulerService(state=state, runner=None, registry=registry, sqlite_path=str(db_path))
    service._schedule_housekeeping()
    # Jobs stay pending until the scheduler starts, so start it (paused, so
    # nothing actually fires) to flush them into their jobstores.
    service.scheduler.start(paused=True)
    try:
        job_id = f"housekeeping:{service.dispatcher_id}"
        assert [job.id for job in service.scheduler.get_jobs(jobstore="housekeeping")] == [job_id]
        assert service.scheduler.get_jobs(jobstore="default") == []
    finally:
        service.shutdown()


class TestFireRechecksPolicy:
    def _svc(self, tmp_path, *, writes: bool, allowed: bool):
        from unittest.mock import MagicMock

        svc = _make_service(tmp_path)
        svc.state.get_schedule.return_value = {"enabled": True, "task_id": "clean-recipes", "options": {"dry_run": False}}
        svc.registry.task_ids = {"clean-recipes"}
        svc.registry.build_execution.return_value = MagicMock(dangerous_requested=writes)
        svc.state.list_task_policies.return_value = {"clean-recipes": {"allow_dangerous": allowed}}
        return svc

    def test_live_schedule_is_skipped_after_policy_is_revoked(self, tmp_path):
        svc = self._svc(tmp_path, writes=True, allowed=False)
        svc._fire_schedule("s1")
        svc.runner.enqueue.assert_not_called()
        svc.runner.record_skipped.assert_called_once()
        assert "aren't approved" in svc.runner.record_skipped.call_args.args[3]

    def test_live_schedule_runs_when_approved(self, tmp_path):
        svc = self._svc(tmp_path, writes=True, allowed=True)
        svc._fire_schedule("s1")
        svc.runner.enqueue.assert_called_once()

    def test_read_only_schedule_runs_without_approval(self, tmp_path):
        svc = self._svc(tmp_path, writes=False, allowed=False)
        svc._fire_schedule("s1")
        svc.runner.enqueue.assert_called_once()



def test_last_due_time_is_the_latest_occurrence_before_now():
    start = datetime(2030, 1, 6, 8, 0, tzinfo=timezone.utc)
    data = {"seconds": 7 * 86400, "start_at": "2030-01-06T08:00:00Z"}
    now = start + timedelta(days=15, hours=1)
    assert SchedulerService.last_due_time(data, now) == start + timedelta(days=14)
    assert SchedulerService.last_due_time(data, start - timedelta(seconds=1)) is None


def test_a_schedule_missed_while_down_runs_once_at_start(tmp_path):
    """Jobs are rebuilt in memory at start; run-if-missed schedules catch up once."""
    from unittest.mock import MagicMock

    from cookdex.webui_server.state import StateStore
    from cookdex.webui_server.tasks import TaskRegistry

    state = StateStore(tmp_path / "state.db")
    registry = TaskRegistry()
    state.initialize(registry.task_ids)
    three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat().replace("+00:00", "Z")
    for schedule_id, missed in (("missed", True), ("not-asked", False)):
        state.create_schedule(
            schedule_id=schedule_id, name=schedule_id, task_id="health-check", schedule_kind="interval",
            schedule_data={"seconds": 86400, "start_at": three_days_ago, "run_if_missed": missed},
            options={}, enabled=True, validation_error=None,
        )
    runner = MagicMock()
    service = SchedulerService(state=state, runner=runner, registry=registry, sqlite_path=str(tmp_path / "state.db"))
    # created_at is now, after the last due time; pretend it was made before.
    with state._connect() as conn:
        conn.execute("UPDATE schedules SET created_at = ?;", ("2000-01-01T00:00:00Z",))
    service._restore_from_db()
    assert [call.kwargs["schedule_id"] for call in runner.enqueue.call_args_list] == ["missed"]

    # It ran, so starting again doesn't run it a second time.
    runner.reset_mock()
    service._restore_from_db()
    runner.enqueue.assert_not_called()


def test_state_db_migrations_are_numbered_and_run_once(tmp_path):
    import sqlite3

    from cookdex.webui_server import migrations

    db = tmp_path / "state.db"
    # An older database: created before numbering, with a column missing
    # and APScheduler's copy of the schedules.
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);"
        "CREATE TABLE apscheduler_jobs (id TEXT PRIMARY KEY);"
    )
    conn.close()

    applied = migrations.migrate(str(db))
    assert applied == [number for number, _, _ in migrations.MIGRATIONS]
    conn = sqlite3.connect(db)
    assert migrations.current_version(conn) == applied[-1]
    assert {"role", "last_sign_in", "force_password_reset"} <= migrations._columns(conn, "users")
    assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'apscheduler_jobs'").fetchone() is None
    conn.close()
    assert migrations.migrate(str(db)) == []


def test_a_failed_migration_leaves_the_database_at_the_last_good_version(tmp_path):
    import sqlite3

    from cookdex.webui_server import migrations

    db = tmp_path / "state.db"

    def broken(conn):
        conn.execute("CREATE TABLE half_done (x INTEGER);")
        raise RuntimeError("boom")

    steps = [*migrations.MIGRATIONS, (99, "broken", broken)]
    with pytest.raises(RuntimeError):
        migrations.migrate(str(db), steps)
    conn = sqlite3.connect(db)
    assert migrations.current_version(conn) == migrations.MIGRATIONS[-1][0]
    assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'half_done'").fetchone() is None
    conn.close()


def test_calendar_schedules_keep_their_local_time_across_daylight_saving(tmp_path):
    from zoneinfo import ZoneInfo

    svc = _make_service(tmp_path)
    data = {"every": "day", "time": "03:00", "timezone": "America/New_York"}
    trigger = svc._build_trigger("calendar", data)
    zone = ZoneInfo("America/New_York")
    before = trigger.get_next_fire_time(None, datetime(2030, 3, 8, 12, tzinfo=zone))
    after = trigger.get_next_fire_time(None, datetime(2030, 3, 11, 12, tzinfo=zone))
    assert (before.hour, after.hour) == (3, 3)  # 3:00 AM on both sides of the change
    assert before.utcoffset() != after.utcoffset()


def test_calendar_schedules_are_validated(tmp_path):
    svc = _make_service(tmp_path)
    for bad in (
        {"every": "month", "time": "03:00"},
        {"every": "day", "time": "25:00"},
        {"every": "week", "time": "03:00", "weekday": 9},
        {"every": "day", "time": "03:00", "timezone": "Mars/Olympus"},
    ):
        with pytest.raises(ValueError):
            svc._validate_schedule_definition("calendar", bad)


def test_last_calendar_time_for_weekly_and_daily():
    from cookdex.webui_server.scheduler import last_calendar_time

    weekly = {"every": "week", "time": "08:00", "weekday": 0, "timezone": "America/New_York"}
    # Wednesday 9 Jan 2030 -> Sunday 6 Jan 2030, 8:00 AM EST.
    assert last_calendar_time(weekly, datetime(2030, 1, 9, 12, tzinfo=timezone.utc)) == datetime(2030, 1, 6, 13, tzinfo=timezone.utc)
    daily = {"every": "day", "time": "03:00", "timezone": "America/New_York"}
    # The day clocks go forward, 3:00 AM is 07:00 UTC, not 08:00.
    assert last_calendar_time(daily, datetime(2030, 3, 10, 12, tzinfo=timezone.utc)) == datetime(2030, 3, 10, 7, tzinfo=timezone.utc)
