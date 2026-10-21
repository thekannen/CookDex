from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

from cookdex import mealie_slots, organize_apply
from cookdex.webui_server import lanes
from cookdex.webui_server.runner import RunQueueManager, _blocker, _Slot
from cookdex.webui_server.state import StateStore
from cookdex.webui_server.tasks import TaskExecution, TaskRegistry

PARSER = lanes.scope("recipes", "foods", "units", "tags:parser: needs review")


def _organize(changes, **options):
    return {"dry_run": False, "plan": {"organize": {"changes": changes}}, **options}


def _delete_unused(name, kind="tags", item_id="t1"):
    return {"op": "delete", "kind": kind, "id": item_id, "name": name, "unused": True}


# ── Lane choice ──────────────────────────────────────────────────────────


def test_unused_deletes_go_in_the_light_lane():
    plan = TaskRegistry().lane_for("organize-apply", _organize([_delete_unused("Dinner")], backup_first=False))
    assert plan.lane == lanes.LIGHT
    assert plan.writes == {"tags:dinner"}


def test_organize_plan_with_a_backup_goes_in_the_heavy_lane():
    change = {"op": "rename", "kind": "tags", "id": "t1", "name": "dinner", "to": "Dinner"}
    plan = TaskRegistry().lane_for("organize-apply", _organize([change], backup_first=True))
    assert plan.lane == lanes.HEAVY
    assert "recipes" in plan.writes


def test_long_jobs_go_in_the_heavy_lane():
    registry = TaskRegistry()
    for task_id in ("ingredient-parse", "tag-categorize", "clean-recipes", "cleanup-duplicates", "health-check",
                    "reimport-recipes", "recipe-dredger", "yield-normalize", "slug-repair", "mealie-backup",
                    "data-maintenance"):
        assert registry.get(task_id).lane == lanes.HEAVY, task_id
    assert registry.get("workflow").lane == lanes.HEAVY


def test_parser_writes_recipes_foods_units_and_its_review_tag():
    plan = TaskRegistry().lane_for("ingredient-parse", {"dry_run": False, "backup_first": False})
    assert plan.writes == PARSER


def test_parser_review_tag_follows_the_setting():
    plan = TaskRegistry().lane_for("ingredient-parse", {"dry_run": False, "backup_first": False}, {"PARSER_REVIEW_TAG": "Check Me"})
    assert "tags:check me" in plan.writes


def test_previews_write_nothing():
    registry = TaskRegistry()
    assert registry.lane_for("ingredient-parse", {"dry_run": True}).writes == frozenset()
    assert registry.lane_for("organize-apply", {**_organize([_delete_unused("x")]), "dry_run": True}).writes == frozenset()


def test_a_run_that_cant_be_built_is_heavy_and_writes_everything():
    plan = TaskRegistry().lane_for("organize-apply", {"plan": "not json"})
    assert plan == lanes.RunLane(lanes.HEAVY, frozenset({lanes.EVERYTHING}))
    assert TaskRegistry().lane_for("no-such-task").lane == lanes.HEAVY


# ── Write scopes ─────────────────────────────────────────────────────────


def test_deleting_other_unused_tags_doesnt_meet_the_parser():
    assert not lanes.overlaps(PARSER, lanes.organize_writes([_delete_unused("Dinner"), _delete_unused("Old")]))


def test_touching_the_review_tag_meets_the_parser():
    assert lanes.overlaps(PARSER, lanes.organize_writes([_delete_unused("Parser: Needs Review")]))
    create = {"op": "create", "kind": "tags", "id": "new-1", "name": "parser: needs review", "to": {"name": "Parser: Needs Review"}}
    assert lanes.overlaps(PARSER, lanes.organize_writes([create]))


def test_changes_that_move_recipes_meet_jobs_that_write_recipes():
    merge = {"op": "merge", "kind": "tags", "id": "t2", "name": "salads", "target_id": "t1", "target_name": "Salad"}
    used_delete = {"op": "delete", "kind": "tags", "id": "t3", "name": "Old"}
    assert lanes.overlaps(PARSER, lanes.organize_writes([merge]))
    assert lanes.overlaps(PARSER, lanes.organize_writes([used_delete]))
    assert "cookbooks" in lanes.organize_writes([merge])


def test_food_and_unit_changes_meet_the_parser():
    assert lanes.overlaps(PARSER, lanes.organize_writes([_delete_unused("pinch", kind="units")]))
    update = {"op": "update", "kind": "foods", "id": "f1", "name": "tomato", "to": {"name": "Tomato"}}
    assert lanes.overlaps(PARSER, lanes.organize_writes([update]))


def test_scope_overlap_rules():
    assert lanes.overlaps(frozenset({"tags"}), frozenset({"tags:dinner"}))
    assert not lanes.overlaps(frozenset({"tags:lunch"}), frozenset({"tags:dinner"}))
    assert lanes.overlaps(frozenset({"*"}), frozenset({"cookbooks:x"}))
    assert not lanes.overlaps(frozenset({"*"}), frozenset())
    assert not lanes.overlaps(frozenset({"tags"}), frozenset({"categories"}))


# ── Who waits for whom ───────────────────────────────────────────────────


def _slot(run_id, lane=lanes.HEAVY, writes=("*",), title=None, task_id="ingredient-parse"):
    return _Slot(run_id, task_id, lane, frozenset(writes), title or run_id)


def test_light_run_goes_alongside_a_heavy_one_it_doesnt_meet():
    parse = _slot("parse", writes=PARSER)
    delete = _slot("delete", lanes.LIGHT, ["tags:dinner"])
    assert _blocker(delete, [], [parse]) is None


def test_light_run_waits_for_a_heavy_one_it_meets():
    parse = _slot("parse", writes=PARSER)
    delete = _slot("delete", lanes.LIGHT, ["tags:parser: needs review"])
    assert _blocker(delete, [], [parse]) is parse


def test_heavy_runs_go_one_at_a_time_in_order():
    first, second = _slot("first", writes=()), _slot("second", writes=())
    assert _blocker(second, [], [first]) is first
    assert _blocker(second, [first], []) is first


def test_light_runs_go_one_at_a_time():
    one, two = _slot("one", lanes.LIGHT, ["tags:a"]), _slot("two", lanes.LIGHT, ["tags:b"])
    assert _blocker(two, [], [one]) is one


def test_runs_that_meet_keep_the_order_they_were_started_in():
    parse = _slot("parse", writes=PARSER)
    delete = _slot("delete", lanes.LIGHT, ["tags:parser: needs review"])
    assert _blocker(delete, [parse], []) is parse


# ── Running both lanes ───────────────────────────────────────────────────


class _FakeRegistry:
    """Runs each task as a tiny Python script and puts it in the lane given."""

    def __init__(self, plans):
        self.plans = plans

    def lane_for(self, task_id, options=None, env=None):
        return self.plans[task_id]

    def get(self, task_id):
        return None

    def build_execution(self, task_id, options=None):
        seconds = float((options or {}).get("seconds", 0))
        script = f"import time; time.sleep({seconds}); print('done')"
        return TaskExecution([sys.executable, "-c", script], {}, dangerous_requested=True)


def _manager(tmp_path, plans):
    state = StateStore(tmp_path / "state.db")
    state.initialize([])
    manager = RunQueueManager(state, _FakeRegistry(plans), lambda: {}, tmp_path / "logs")
    manager.start()
    return manager, state


def _wait_for(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_light_change_finishes_while_a_long_job_runs(tmp_path):
    manager, state = _manager(tmp_path, {
        "long": lanes.RunLane(lanes.HEAVY, PARSER),
        "quick": lanes.RunLane(lanes.LIGHT, frozenset({"tags:dinner"})),
    })
    try:
        long_run = manager.enqueue("long", {"seconds": 5}, "tester")
        assert _wait_for(lambda: state.get_run(long_run["run_id"])["status"] == "running")
        quick = manager.enqueue("quick", {}, "tester")
        assert _wait_for(lambda: state.get_run(quick["run_id"])["status"] == "succeeded")
        assert state.get_run(long_run["run_id"])["status"] == "running"
    finally:
        manager.stop()


def test_queued_change_says_what_it_waits_for_and_can_be_canceled(tmp_path):
    manager, state = _manager(tmp_path, {
        "long": lanes.RunLane(lanes.HEAVY, PARSER),
        "quick": lanes.RunLane(lanes.LIGHT, frozenset({"tags:parser: needs review"})),
    })
    try:
        long_run = manager.enqueue("long", {"seconds": 5}, "tester")
        assert _wait_for(lambda: state.get_run(long_run["run_id"])["status"] == "running")
        manager._progress[long_run["run_id"]] = {"label": "Parsing", "done": 142, "total": 4397}
        quick = manager.enqueue("quick", {}, "tester")
        time.sleep(0.3)
        described = manager.describe(state.get_run(quick["run_id"]))
        assert described["status"] == "queued"
        assert described["waiting"]["message"] == "Waiting for long (142 of 4,397) to finish"
        assert described["waiting"]["run_id"] == long_run["run_id"]

        assert manager.cancel(quick["run_id"])
        assert state.get_run(quick["run_id"])["error"] == "Stopped before it started."
        assert manager.waiting(quick["run_id"]) is None
        assert manager.cancel(long_run["run_id"])
        assert _wait_for(lambda: not manager._running)
        assert state.get_run(long_run["run_id"])["status"] == "canceled"
    finally:
        manager.stop()


def test_waiting_messages(tmp_path):
    manager = RunQueueManager(None, _FakeRegistry({}), lambda: {}, tmp_path)  # type: ignore[arg-type]
    parse = _slot("parse", writes=PARSER, title="Ingredient Parser")
    first = _slot("first", lanes.LIGHT, ["tags:parser: needs review"], title="Apply Organize Changes")
    second = _slot("second", lanes.LIGHT, ["tags:parser: needs review"])
    manager._running = {"parse": parse}
    manager._pending = [first, second]
    assert manager.waiting("first")["message"] == "Waiting for Ingredient Parser to finish"
    manager._progress["parse"] = {"label": "", "done": 142, "total": 4397}
    assert manager.waiting("first")["message"] == "Waiting for Ingredient Parser (142 of 4,397) to finish"
    manager._running = {}
    assert manager.waiting("first")["message"] == "Starting…"
    assert manager.waiting("second")["message"] == "Waiting for Apply Organize Changes to go first"
    assert manager.waiting("nope") is None


def test_log_rotation_keeps_logs_of_runs_in_use(tmp_path):
    manager = RunQueueManager(None, _FakeRegistry({}), lambda: {}, tmp_path, max_log_files=1)  # type: ignore[arg-type]
    old = tmp_path / "busy.log"
    old.write_text("x")
    time.sleep(0.01)
    (tmp_path / "new.log").write_text("y")
    manager._running = {"busy": _slot("busy")}
    manager._rotate_logs()
    assert old.exists()


# ── Shared cap on Mealie requests ────────────────────────────────────────


def _count_concurrency(slot_sets, threads_each=6, hold_seconds=0.05):
    lock = threading.Lock()
    now = {"in": 0, "max": 0}

    def worker(slots):
        with slots.hold():
            with lock:
                now["in"] += 1
                now["max"] = max(now["max"], now["in"])
            time.sleep(hold_seconds)
            with lock:
                now["in"] -= 1

    workers = [threading.Thread(target=worker, args=(s,)) for s in slot_sets for _ in range(threads_each)]
    for t in workers:
        t.start()
    for t in workers:
        t.join(10)
    return now["max"]


@pytest.mark.skipif(mealie_slots.fcntl is None, reason="needs POSIX file locks")
def test_jobs_share_one_cap(tmp_path):
    # Two "jobs" with their own slot objects, like two processes would have.
    jobs = [mealie_slots.RequestSlots(tmp_path, 4, lanes.HEAVY) for _ in range(2)]
    assert _count_concurrency(jobs) <= 2  # 4 slots, 2 kept for light jobs


@pytest.mark.skipif(mealie_slots.fcntl is None, reason="needs POSIX file locks")
def test_light_job_gets_a_slot_while_a_long_job_uses_its_share(tmp_path):
    heavy = mealie_slots.RequestSlots(tmp_path, 4, lanes.HEAVY)
    held = [heavy._try(i) for i in heavy.candidates]
    assert all(fd is not None for fd in held)
    light = mealie_slots.RequestSlots(tmp_path, 4, lanes.LIGHT)
    started = time.monotonic()
    with light.hold():
        pass
    assert time.monotonic() - started < 0.5
    # And a light job alone never sends more than two requests at once.
    assert _count_concurrency([light]) <= 2


@pytest.mark.skipif(mealie_slots.fcntl is None, reason="needs POSIX file locks")
def test_cap_holds_across_processes(tmp_path):
    ready = tmp_path / "ready"
    child = subprocess.Popen([
        sys.executable, "-c",
        "import sys, time; from pathlib import Path; from cookdex.mealie_slots import RequestSlots\n"
        f"s = RequestSlots(Path({str(tmp_path)!r}), 3, 'heavy')\n"
        "fds = [s._try(i) for i in s.candidates]\n"
        f"Path({str(ready)!r}).write_text(str(sum(fd is not None for fd in fds)))\n"
        "time.sleep(30)\n",
    ], env={**__import__("os").environ, "PYTHONPATH": str(Path(organize_apply.__file__).parents[1])})
    try:
        assert _wait_for(ready.exists)
        assert ready.read_text() == "1"
        mine = mealie_slots.RequestSlots(tmp_path, 3, lanes.HEAVY)
        assert [mine._try(i) for i in mine.candidates] == [None]
    finally:
        child.kill()
        child.wait()
    # The lock goes with the process, so nothing stays stuck.
    assert mine._try(0) is not None


def test_no_shared_cap_outside_the_runner(monkeypatch):
    monkeypatch.delenv(mealie_slots.SLOTS_DIR_ENV, raising=False)
    assert mealie_slots.shared() is None
    with mealie_slots.request_slot():
        pass


def test_light_lane_client_retries_less(monkeypatch):
    from cookdex.api_client import MealieApiClient

    monkeypatch.setenv(mealie_slots.LANE_ENV, "light")
    assert MealieApiClient("http://mealie.test/api", "token").retries == 1
    monkeypatch.setenv(mealie_slots.LANE_ENV, "heavy")
    assert MealieApiClient("http://mealie.test/api", "token").retries == 3


# ── Organize stops when Mealie doesn't answer ────────────────────────────


class _DownMealie:
    def __init__(self):
        self.deletes = 0

    def get_organizer_items(self, kind):
        return [{"id": f"t{i}", "name": f"Old {i}", "recipeCount": 0} for i in range(3)]

    def list_cookbooks(self):
        return []

    def delete_organizer_item(self, kind, item_id):
        self.deletes += 1
        raise requests.HTTPError("DELETE failed") from requests.exceptions.ReadTimeout("read timed out")


def test_organize_stops_when_mealie_doesnt_answer(monkeypatch, tmp_path, capsys):
    changes = [_delete_unused(f"Old {i}", item_id=f"t{i}") for i in range(3)]
    monkeypatch.setenv("COOKDEX_APPLY_PLAN", json.dumps({"organize": {"changes": changes}}))
    monkeypatch.setenv("COOKDEX_RESULT_PATH", str(tmp_path / "results.jsonl"))
    client = _DownMealie()

    result = organize_apply.run(client, dry_run=False)  # type: ignore[arg-type]

    assert client.deletes == 1
    assert result["failed"] == 3
    statuses = [item["status"] for item in result["items"]]
    assert statuses == ["error", "skipped", "skipped"]
    assert "Mealie isn't answering" in capsys.readouterr().out
