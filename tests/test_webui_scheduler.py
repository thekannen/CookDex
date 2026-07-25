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

    svc = SchedulerService.__new__(SchedulerService)
    svc.state = MagicMock()
    svc.runner = MagicMock()
    svc.registry = MagicMock()
    svc.dispatcher_id = "test-dispatcher"

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    svc.scheduler = BackgroundScheduler(
        timezone="UTC",
        jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{tmp_path}/sched.db")},
    )
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
    """The housekeeping job must not accumulate in the SQLAlchemy jobstore."""
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
