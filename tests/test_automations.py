from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cookdex import workflow_runner
from cookdex.webui_server import automations as store
from cookdex.webui_server.tasks import TaskRegistry
from tests.test_webui_app import _CSRF, _login
from tests.test_webui_library import _make_app

API = "/cookdex/api/v1"
START = "2030-01-06T08:00:00Z"


def _by_name(listing, name):
    return next(item for item in listing["items"] if item["name"] == name)


def test_standard_automations_ship_switched_off(tmp_path: Path, monkeypatch):
    app, _ = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        items = client.get(f"{API}/automations").json()["items"]
        assert {item["builtin"] for item in items} == {"nightly-backup", "weekly-check", "weekly-organize", "weekly-discover"}
        assert not any(item["enabled"] for item in items)
        assert client.get(f"{API}/schedules").json()["items"] == []
        check = next(item for item in items if item["builtin"] == "weekly-check")
        assert [step["task_id"] for step in check["steps"]] == ["health-check", "clean-recipes", "cleanup-duplicates"]
        assert check["writes"] is False


def test_a_workflow_owns_one_schedule_and_changes_need_approval(tmp_path: Path, monkeypatch):
    app, _ = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        items = client.get(f"{API}/automations").json()["items"]
        check = next(item for item in items if item["builtin"] == "weekly-check")
        on = client.post(f"{API}/automations/{check['id']}/enabled", json={"enabled": True, "start_at": START}, headers=_CSRF)
        assert on.status_code == 200, on.text
        assert _by_name(on.json(), check["name"])["next_run_at"]
        schedules = client.get(f"{API}/schedules").json()["items"]
        assert [s["task_id"] for s in schedules] == ["workflow"]

        # Something that changes Mealie asks the owner first, then remembers.
        backup = next(item for item in items if item["builtin"] == "nightly-backup")
        asked = client.post(f"{API}/automations/{backup['id']}/enabled", json={"enabled": True, "start_at": START}, headers=_CSRF)
        assert asked.status_code == 409 and asked.json()["detail"] == "approval_required"
        allowed = client.post(
            f"{API}/automations/{backup['id']}/enabled", json={"enabled": True, "start_at": START, "allow_changes": True}, headers=_CSRF
        )
        assert allowed.status_code == 200
        assert _by_name(allowed.json(), backup["name"])["approved"] is True
        assert len(client.get(f"{API}/schedules").json()["items"]) == 2

        # Off removes the schedule; deleting removes the automation.
        client.post(f"{API}/automations/{check['id']}/enabled", json={"enabled": False}, headers=_CSRF)
        assert len(client.get(f"{API}/schedules").json()["items"]) == 1
        left = client.delete(f"{API}/automations/{backup['id']}", headers=_CSRF).json()["items"]
        assert backup["id"] not in {item["id"] for item in left}
        assert client.get(f"{API}/schedules").json()["items"] == []


def test_build_a_custom_workflow_and_run_it(tmp_path: Path, monkeypatch):
    app, _ = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        body = {
            "name": "Sunday tidy-up",
            "trigger": {"type": "manual"},
            "mode": "preview",
            "steps": [{"task_id": "slug-repair", "options": {}}, {"task_id": "yield-normalize", "options": {}}],
        }
        created = client.post(f"{API}/automations", json=body, headers=_CSRF)
        assert created.status_code == 201, created.text
        mine = _by_name(created.json(), "Sunday tidy-up")
        assert mine["writes"] is False and mine["schedule_id"] is None

        bad = client.post(f"{API}/automations", json={**body, "steps": [{"task_id": "nope", "options": {}}]}, headers=_CSRF)
        assert bad.status_code == 422

        started = client.post(f"{API}/automations/{mine['id']}/run", json={"preview": True}, headers=_CSRF)
        assert started.status_code == 202, started.text
        run = started.json()
        assert run["task_id"] == "workflow"
        assert run["options"]["workflow"]["steps"][0]["task_id"] == "slug-repair"


def test_older_schedules_become_automations(tmp_path: Path):
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    registry = TaskRegistry()
    state.initialize(registry.task_ids)
    state.set_task_policy("yield-normalize", True)

    class FakeScheduler:
        def __init__(self):
            self.deleted, self.created = [], []

        def delete_schedule(self, schedule_id):
            self.deleted.append(schedule_id)
            return True

        def create_schedule(self, payload):
            self.created.append(payload)
            return {"schedule_id": f"new-{len(self.created)}"}

    state.create_schedule(
        schedule_id="old-1", name="Nightly yields", task_id="yield-normalize", schedule_kind="interval",
        schedule_data={"seconds": 86400, "start_at": START}, options={"dry_run": False}, enabled=True, validation_error=None,
    )
    scheduler = FakeScheduler()
    result = store.migrate(state, scheduler, registry)
    assert result == {"converted": 1}
    doc = store.load(state)
    converted = next(r for r in doc["items"].values() if r["name"] == "Nightly yields")
    assert converted["mode"] == "apply" and converted["enabled"] is True
    assert converted["steps"] == [{"task_id": "yield-normalize", "options": {}}]
    assert store.is_approved(state, converted)  # the job was approved, so the automation is
    assert "old-1" in scheduler.deleted
    assert scheduler.created[0].task_id == "workflow"
    # Standard automations are there too, off.
    assert sum(1 for r in doc["items"].values() if r["builtin"]) == 4
    assert store.migrate(state, scheduler, registry) is None


def test_steps_follow_the_automation_mode():
    registry = TaskRegistry()
    spec = {
        "mode": "apply",
        "steps": [{"task_id": "clean-recipes", "options": {"dry_run": True, "backup_first": True}}, {"task_id": "health-check", "options": {}}],
    }
    steps = workflow_runner.plan(spec, registry)
    assert steps[0]["options"]["dry_run"] is False
    assert steps[0]["options"]["backup_first"] is False  # one backup up front instead
    assert steps[0]["execution"].dangerous_requested is True
    assert steps[1]["execution"].dangerous_requested is False
    preview = workflow_runner.plan({**spec, "mode": "preview"}, registry)
    assert preview[0]["options"]["dry_run"] is True

    with pytest.raises(ValueError):
        workflow_runner.plan({"steps": [{"task_id": "workflow"}]}, registry)
    with pytest.raises(ValueError):
        workflow_runner.plan({"steps": []}, registry)


def test_daily_and_weekly_intervals_become_calendar_triggers(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    trigger = store.to_calendar(
        {"type": "interval", "seconds": store.WEEK, "start_at": "2030-01-06T13:00:00Z"}, "America/New_York"
    )
    # 13:00 UTC on a Sunday in January is 8:00 AM in New York.
    assert trigger == {"type": "calendar", "every": "week", "time": "08:00", "weekday": 0, "timezone": "America/New_York"}
    assert store.to_calendar({"type": "interval", "seconds": 6 * 3600, "start_at": "2030-01-06T13:00:00Z"}, "UTC") is None
    kind, data = store.schedule_definition(trigger)
    assert kind == "calendar" and data["run_if_missed"] is True
