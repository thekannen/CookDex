"""Automations: named workflows of jobs, run on a trigger.

An automation is an ordered list of steps (a job and its options), settings
that apply to the whole run (preview or apply, back up first, stop when a step
fails) and a trigger (run by hand, every so often, or once). Enabled
automations with a time-based trigger own one schedule, which starts the
hidden ``workflow`` task (see cookdex.workflow_runner).

CookDex ships a few standard automations, switched off. On first start,
schedules made before automations existed are converted into automations,
keeping their timing, options and approval.
"""
from __future__ import annotations

import uuid
from typing import Any

from datetime import datetime
from zoneinfo import ZoneInfo

from .scheduler import SchedulePayload, parse_calendar, server_timezone
from .state import StateStore, utc_now_iso
from .tasks import WORKFLOW_TASK, TaskRegistry, policy_key

DOCUMENT_KEY = "automations_v2"
LEGACY_DOCUMENT_KEY = "automations"
DAY = 86_400
WEEK = 7 * DAY
MODE_KEYS = ("dry_run", "backup_first", "apply_cleanups")

BUILTINS: list[dict[str, Any]] = [
    {
        "builtin": "nightly-backup",
        "name": "Back up Mealie every night",
        "description": "Makes a Mealie backup and keeps the newest 7 that CookDex made, so there's always a recent restore point. Backups you make yourself are never deleted.",
        "trigger": {"type": "calendar", "every": "day", "time": "03:00"},
        "mode": "apply",
        "backup_first": False,
        "steps": [{"task_id": "mealie-backup", "options": {"keep": 7}}],
    },
    {
        "builtin": "weekly-check",
        "name": "Check the library every week",
        "description": "Scores the library and looks for pages that aren't recipes, duplicates, messy names and duplicate tags. It only looks; you review what it finds in the Library.",
        "trigger": {"type": "calendar", "every": "week", "time": "08:00", "weekday": 0},
        "mode": "preview",
        "steps": [
            {"task_id": "health-check", "options": {}},
            {"task_id": "clean-recipes", "options": {}},
            {"task_id": "cleanup-duplicates", "options": {"target": "taxonomy"}},
        ],
    },
    {
        "builtin": "weekly-organize",
        "name": "Organize new recipes every week",
        "description": "Links ingredients, adds tags and categories with your rules, and fills in servings. Starts as a preview, so you can see what it would do before letting it apply.",
        "trigger": {"type": "calendar", "every": "week", "time": "09:00", "weekday": 0},
        "mode": "preview",
        "steps": [
            {"task_id": "ingredient-parse", "options": {}},
            {"task_id": "tag-categorize", "options": {"method": "rules"}},
            {"task_id": "yield-normalize", "options": {}},
        ],
    },
    {
        "builtin": "weekly-discover",
        "name": "Import new recipes every week",
        "description": "Imports new recipes from the sources switched on in Discover, up to the number you choose.",
        "trigger": {"type": "calendar", "every": "week", "time": "08:00", "weekday": 0},
        "mode": "apply",
        "backup_first": False,
        "steps": [{"task_id": "recipe-dredger", "options": {"max_total": 25}}],
    },
]


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def new_record(template: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    now = utc_now_iso()
    record = {
        "id": _new_id(),
        "name": template["name"],
        "description": template.get("description", ""),
        "builtin": template.get("builtin"),
        "enabled": False,
        "trigger": dict(template.get("trigger") or {"type": "manual"}),
        "mode": template.get("mode", "preview"),
        "backup_first": template.get("backup_first", True),
        "stop_on_error": template.get("stop_on_error", True),
        "steps": [dict(step) for step in template.get("steps", [])],
        "schedule_id": None,
        "created_at": now,
        "updated_at": now,
    }
    record.update(overrides)
    return record


def load(state: StateStore) -> dict[str, Any]:
    value = state.get_document(DOCUMENT_KEY)
    if isinstance(value, dict) and isinstance(value.get("items"), dict):
        return value
    return {"items": {}, "order": []}


def save(state: StateStore, doc: dict[str, Any]) -> None:
    state.set_document(DOCUMENT_KEY, doc)


def workflow_options(record: dict[str, Any], *, mode: str | None = None) -> dict[str, Any]:
    """Options for the hidden workflow task that runs *record*."""
    return {
        "workflow": {
            "id": record["id"],
            "name": record["name"],
            "mode": mode or record.get("mode", "preview"),
            "backup_first": bool(record.get("backup_first", True)),
            "stop_on_error": bool(record.get("stop_on_error", True)),
            "steps": record.get("steps") or [],
        }
    }


def writes(registry: TaskRegistry, record: dict[str, Any]) -> bool:
    return registry.build_execution(WORKFLOW_TASK, workflow_options(record)).dangerous_requested


def is_approved(state: StateStore, record: dict[str, Any]) -> bool:
    key = policy_key(WORKFLOW_TASK, workflow_options(record))
    return bool(state.list_task_policies().get(key, {}).get("allow_dangerous"))


def set_approved(state: StateStore, record: dict[str, Any], approved: bool) -> None:
    state.set_task_policy(policy_key(WORKFLOW_TASK, workflow_options(record)), approved)


def schedule_definition(trigger: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """(kind, data) for a time-based trigger, or None for manual ones."""
    kind = str(trigger.get("type") or "manual")
    if kind == "interval":
        seconds = int(trigger.get("seconds") or 0)
        start_at = str(trigger.get("start_at") or "").strip()
        if seconds < 300:
            raise ValueError("Run at most every 5 minutes.")
        if not start_at:
            raise ValueError("Choose when this automation should run.")
        return "interval", {"seconds": seconds, "start_at": start_at, "run_if_missed": True}
    if kind == "once":
        run_at = str(trigger.get("run_at") or "").strip()
        if not run_at:
            raise ValueError("Choose when this automation should run.")
        return "once", {"run_at": run_at, "run_if_missed": True}
    if kind == "calendar":
        data = {
            "every": trigger.get("every"),
            "time": trigger.get("time"),
            "weekday": int(trigger.get("weekday") or 0),
            "timezone": trigger.get("timezone") or server_timezone(),
            "run_if_missed": True,
        }
        parse_calendar(data)
        return "calendar", data
    return None


def to_calendar(trigger: dict[str, Any], zone_name: str) -> dict[str, Any] | None:
    """A daily or weekly interval trigger as a calendar one at the same local time.

    Fixed intervals are anchored in UTC, so they drift by an hour across a
    daylight-saving change; calendar triggers keep the wall-clock time.
    """
    if trigger.get("type") != "interval" or int(trigger.get("seconds") or 0) not in (DAY, WEEK):
        return None
    start = trigger.get("start_at")
    zone = ZoneInfo(zone_name)
    if start:
        local = datetime.fromisoformat(str(start).replace("Z", "+00:00")).astimezone(zone)
        time_text, weekday = f"{local.hour:02d}:{local.minute:02d}", (local.weekday() + 1) % 7
    else:
        time_text, weekday = str(trigger.get("time") or "03:00"), int(trigger.get("weekday") or 0)
    return {
        "type": "calendar",
        "every": "day" if int(trigger["seconds"]) == DAY else "week",
        "time": time_text,
        "weekday": weekday,
        "timezone": zone_name,
    }


def sync_schedule(scheduler, record: dict[str, Any]) -> None:
    """Make the automation's schedule match it: one while on and timed, none otherwise."""
    old = record.get("schedule_id")
    if old:
        scheduler.delete_schedule(old)
    record["schedule_id"] = None
    if not record.get("enabled"):
        return
    definition = schedule_definition(record.get("trigger") or {})
    if definition is None:
        return
    kind, data = definition
    created = scheduler.create_schedule(
        SchedulePayload(
            name=record["name"],
            task_id=WORKFLOW_TASK,
            schedule_kind=kind,
            schedule_data=data,
            options=workflow_options(record),
            enabled=True,
        )
    )
    record["schedule_id"] = created["schedule_id"]


def _steps_from_options(task_id: str, options: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"task_id": task_id, "options": {k: v for k, v in (options or {}).items() if k not in MODE_KEYS}}]


def _trigger_from_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    data = schedule.get("schedule_data") or {}
    if schedule.get("schedule_kind") == "once":
        return {"type": "once", "run_at": data.get("run_at")}
    return {"type": "interval", "seconds": int(data.get("seconds") or DAY), "start_at": data.get("start_at")}


def migrate(state: StateStore, scheduler, registry: TaskRegistry) -> dict[str, int] | None:
    """Create the standard automations and convert older schedules, once.

    Later versions may add standard automations; those are added (switched
    off) on the next start.
    """
    existing = state.get_document(DOCUMENT_KEY)
    if isinstance(existing, dict) and isinstance(existing.get("items"), dict):
        have = {record.get("builtin") for record in existing["items"].values()}
        added = [template for template in BUILTINS if template["builtin"] not in have]
        for template in added:
            record = new_record(template)
            existing["items"][record["id"]] = record
            existing["order"].append(record["id"])
        adopted = adopt_schedules(state, scheduler, registry, existing)
        converted = _calendar_triggers(scheduler, existing)
        if added or adopted or converted:
            save(state, existing)
        return None

    doc: dict[str, Any] = {"items": {}, "order": []}
    legacy = state.get_document(LEGACY_DOCUMENT_KEY)
    legacy = legacy if isinstance(legacy, dict) else {}
    policies = state.list_task_policies()
    schedules = {s["schedule_id"]: s for s in state.list_schedules()}

    for template in BUILTINS:
        old = legacy.get(template["builtin"]) or {}
        record = new_record(template)
        owned = [sid for sid in old.get("schedule_ids") or [] if sid in schedules]
        if old.get("enabled") and owned:
            first = schedules[owned[0]]
            record["enabled"] = True
            record["trigger"] = {
                **_trigger_from_schedule(first),
                "time": old.get("time") or template["trigger"].get("time"),
                "weekday": old.get("weekday", template["trigger"].get("weekday")),
            }
            if template["builtin"] == "weekly-discover" and old.get("max_total"):
                record["steps"] = [{"task_id": "recipe-dredger", "options": {"max_total": int(old["max_total"])}}]
            if all(policies.get(step["task_id"], {}).get("allow_dangerous") for step in record["steps"]):
                set_approved(state, record, True)
        for sid in owned:
            schedules.pop(sid, None)
            scheduler.delete_schedule(sid)
        doc["items"][record["id"]] = record
        doc["order"].append(record["id"])

    converted = adopt_schedules(state, scheduler, registry, doc, schedules=list(schedules.values()), sync=False)

    for record in doc["items"].values():
        try:
            sync_schedule(scheduler, record)
        except ValueError:
            record["enabled"] = False
    save(state, doc)
    return {"converted": converted}


def adopt_schedules(
    state: StateStore,
    scheduler,
    registry: TaskRegistry,
    doc: dict[str, Any],
    *,
    schedules: list[dict[str, Any]] | None = None,
    sync: bool = True,
) -> int:
    """Turn plain job schedules into one-step automations, so there's one list.

    Covers schedules made before automations existed and ones made later in
    the classic tools view. Timing, options and the job's approval carry over.
    """
    policies = state.list_task_policies()
    converted = 0
    for schedule in schedules if schedules is not None else state.list_schedules():
        task_id = str(schedule.get("task_id") or "")
        if task_id == WORKFLOW_TASK or task_id not in registry.task_ids:
            continue
        options = dict(schedule.get("options") or {})
        applies = ("dry_run" in options and options.get("dry_run") is False) or bool(options.get("apply_cleanups"))
        if task_id == "mealie-backup" and options.get("keep"):
            applies = True
        record = new_record(
            {"name": str(schedule.get("name") or registry.get(task_id).title)},
            enabled=bool(schedule.get("enabled")),
            trigger=to_calendar(_trigger_from_schedule(schedule), server_timezone()) or _trigger_from_schedule(schedule),
            mode="apply" if applies else "preview",
            backup_first=bool(options.get("backup_first", True)),
            steps=_steps_from_options(task_id, options),
            description="Made from a schedule.",
        )
        if applies and policies.get(task_id, {}).get("allow_dangerous"):
            set_approved(state, record, True)
        scheduler.delete_schedule(schedule["schedule_id"])
        if sync:
            try:
                sync_schedule(scheduler, record)
            except ValueError:
                record["enabled"] = False
        doc["items"][record["id"]] = record
        doc["order"].append(record["id"])
        converted += 1
    return converted


def _calendar_triggers(scheduler, doc: dict[str, Any]) -> int:
    """Turn daily and weekly interval triggers into calendar ones, in the server's zone."""
    zone_name = server_timezone()
    changed = 0
    for record in doc["items"].values():
        trigger = to_calendar(record.get("trigger") or {}, zone_name)
        if trigger is None:
            continue
        record["trigger"] = trigger
        try:
            sync_schedule(scheduler, record)
        except ValueError:
            record["enabled"] = False
        changed += 1
    return changed
