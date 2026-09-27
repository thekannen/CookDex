"""Automations: plain-language routines built on schedules.

Each routine owns one or more schedules. Turning a routine on creates them;
changing its time or turning it off replaces or removes them. Routines that
apply changes need the task's unattended-run approval, which only an owner
can give. Which schedules belong to which routine is kept in state.db.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import ROLE_OWNER, Services, require_editor_session, require_services
from ..scheduler import SchedulePayload

router = APIRouter(tags=["automations"])

DOCUMENT_KEY = "automations"
DAY = 86_400
WEEK = 7 * DAY

ROUTINES: dict[str, dict[str, Any]] = {
    "nightly-backup": {
        "title": "Back up Mealie every night",
        "description": "Makes a Mealie backup and keeps the newest 7 nightly backups, so there's always a recent restore point. Backups you make yourself are never deleted.",
        "period": "daily",
        "writes": True,
        "tasks": [("mealie-backup", {"keep": 7})],
    },
    "weekly-check": {
        "title": "Check the library every week",
        "description": "Scans for pages that aren't recipes, duplicates, messy names and missing details. It only looks; you review what it finds in the Library.",
        "period": "weekly",
        "writes": False,
        "tasks": [
            ("health-check", {}),
            ("clean-recipes", {"dry_run": True}),
            ("cleanup-duplicates", {"dry_run": True, "target": "taxonomy"}),
        ],
    },
    "weekly-discover": {
        "title": "Import new recipes every week",
        "description": "Imports new recipes from the sources switched on in Discover, up to the number you choose.",
        "period": "weekly",
        "writes": True,
        "tasks": [("recipe-dredger", {"dry_run": False})],
        "config": {"max_total": {"default": 25, "min": 1, "max": 200}},
    },
}


class RoutineUpdate(BaseModel):
    enabled: bool
    # Next local occurrence of the chosen time, as UTC ISO. The browser
    # computes it so "3:00 AM" means 3:00 AM where the person is.
    start_at: str | None = None
    time: str = Field(default="", max_length=5)  # "HH:MM", for display
    weekday: int | None = Field(default=None, ge=0, le=6)  # 0 = Sunday
    max_total: int | None = None
    allow_unattended: bool = False


def _stored(services: Services) -> dict[str, Any]:
    value = services.state.get_document(DOCUMENT_KEY)
    return value if isinstance(value, dict) else {}


def _task_options(routine_id: str, task_options: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    options = dict(task_options)
    if routine_id == "weekly-discover":
        options["max_total"] = int(state.get("max_total") or ROUTINES[routine_id]["config"]["max_total"]["default"])
    return options


def _describe(services: Services, routine_id: str, state: dict[str, Any], schedules: dict[str, dict[str, Any]], policies: dict[str, Any]) -> dict[str, Any]:
    routine = ROUTINES[routine_id]
    schedule_ids = [sid for sid in state.get("schedule_ids") or [] if sid in schedules]
    next_runs = sorted(str(schedules[sid]["next_run_at"]) for sid in schedule_ids if schedules[sid].get("next_run_at"))
    task_ids = [task_id for task_id, _ in routine["tasks"]]
    last = None
    for run in services.state.list_runs(limit=300):
        if run.get("schedule_id") in schedule_ids and run.get("status") not in {"queued", "running"}:
            last = {"status": run.get("status"), "finished_at": run.get("finished_at"), "error": run.get("error")}
            break
    return {
        "id": routine_id,
        "title": routine["title"],
        "description": routine["description"],
        "period": routine["period"],
        "writes": routine["writes"],
        "enabled": bool(state.get("enabled")) and bool(schedule_ids),
        "time": state.get("time") or ("03:00" if routine["period"] == "daily" else "08:00"),
        "weekday": state.get("weekday", 0),
        "max_total": state.get("max_total") if routine_id == "weekly-discover" else None,
        "approved": all(policies.get(task_id, {}).get("allow_dangerous") for task_id in task_ids) if routine["writes"] else True,
        "next_run_at": next_runs[0] if next_runs else None,
        "last_run": last,
    }


@router.get("/automations")
def list_automations(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    stored = _stored(services)
    schedules = {s["schedule_id"]: s for s in services.scheduler.list_schedules()}
    policies = services.state.list_task_policies()
    owned = {sid for state in stored.values() for sid in state.get("schedule_ids") or []}
    return {
        "routines": [_describe(services, rid, stored.get(rid, {}), schedules, policies) for rid in ROUTINES],
        "other_schedules": [
            {"schedule_id": s["schedule_id"], "name": s["name"], "task_id": s["task_id"],
             "enabled": bool(s["enabled"]), "next_run_at": s.get("next_run_at")}
            for s in schedules.values()
            if s["schedule_id"] not in owned
        ],
    }


@router.put("/automations/{routine_id}")
def update_automation(
    routine_id: str,
    payload: RoutineUpdate,
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    routine = ROUTINES.get(routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail=f"Unknown routine '{routine_id}'.")
    is_owner = str(session.get("role") or "").lower() == ROLE_OWNER
    stored = _stored(services)
    state = dict(stored.get(routine_id) or {})

    if payload.enabled and routine["writes"]:
        policies = services.state.list_task_policies()
        missing = [task_id for task_id, _ in routine["tasks"] if not policies.get(task_id, {}).get("allow_dangerous")]
        if missing:
            if not (is_owner and payload.allow_unattended):
                raise HTTPException(
                    status_code=403,
                    detail="This routine changes Mealie without asking each time. An owner has to approve that first.",
                )
            for task_id in missing:
                services.state.set_task_policy(task_id, True)

    if routine_id == "weekly-discover" and payload.max_total is not None:
        limits = routine["config"]["max_total"]
        state["max_total"] = max(limits["min"], min(limits["max"], int(payload.max_total)))

    # Replace this routine's schedules with ones matching the new settings.
    for schedule_id in state.get("schedule_ids") or []:
        services.scheduler.delete_schedule(schedule_id)
    state["schedule_ids"] = []
    state["enabled"] = payload.enabled
    if payload.time:
        state["time"] = payload.time
    if payload.weekday is not None:
        state["weekday"] = payload.weekday

    if payload.enabled:
        if not payload.start_at:
            raise HTTPException(status_code=422, detail="Choose when this routine should run.")
        seconds = DAY if routine["period"] == "daily" else WEEK
        for index, (task_id, task_options) in enumerate(routine["tasks"]):
            record = services.scheduler.create_schedule(
                SchedulePayload(
                    name=f"{routine['title']}" + (f" ({index + 1})" if len(routine["tasks"]) > 1 else ""),
                    task_id=task_id,
                    schedule_kind="interval",
                    schedule_data={"seconds": seconds, "start_at": payload.start_at, "run_if_missed": True},
                    options=_task_options(routine_id, task_options, state),
                    enabled=True,
                )
            )
            state["schedule_ids"].append(record["schedule_id"])

    stored[routine_id] = state
    services.state.set_document(DOCUMENT_KEY, stored)
    return list_automations(session, services)
