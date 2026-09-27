"""Automations API: list, build, switch on and off, and run workflows.

See ``webui_server.automations`` for what an automation is. Automations that
apply changes need an owner's approval before they run on their own; an
editor who changes such an automation's steps or settings withdraws it.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import automations as store
from ..deps import ROLE_OWNER, Services, enforce_safety, require_editor_session, require_services
from ..state import utc_now_iso
from ..tasks import WORKFLOW_TASK

router = APIRouter(tags=["automations"])

MAX_STEPS = 12


class Step(BaseModel):
    task_id: str = Field(min_length=1)
    options: dict[str, Any] = Field(default_factory=dict)


class Trigger(BaseModel):
    type: Literal["manual", "interval", "once"] = "manual"
    seconds: int | None = None
    start_at: str | None = None
    run_at: str | None = None
    # How the person picked it, so the builder can show it the same way.
    time: str | None = Field(default=None, max_length=5)
    weekday: int | None = Field(default=None, ge=0, le=6)


class AutomationIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=400)
    enabled: bool = False
    trigger: Trigger = Field(default_factory=Trigger)
    mode: Literal["preview", "apply"] = "preview"
    backup_first: bool = True
    stop_on_error: bool = True
    steps: list[Step] = Field(min_length=1, max_length=MAX_STEPS)
    # Set by an owner who agreed to let this automation change Mealie on its own.
    allow_changes: bool = False


class EnableIn(BaseModel):
    enabled: bool
    start_at: str | None = None
    allow_changes: bool = False


class RunIn(BaseModel):
    preview: bool = False
    confirmed: bool = False


def _is_owner(session: dict[str, Any]) -> bool:
    return str(session.get("role") or "").lower() == ROLE_OWNER


def _last_run(services: Services, record: dict[str, Any]) -> dict[str, Any] | None:
    for run in services.state.list_runs(limit=300):
        if run.get("task_id") != WORKFLOW_TASK or run.get("status") in {"queued", "running"}:
            continue
        spec = (run.get("options") or {}).get("workflow") or {}
        if spec.get("id") == record["id"]:
            return {"run_id": run.get("run_id"), "status": run.get("status"), "finished_at": run.get("finished_at"), "error": run.get("error")}
    return None


def _describe(services: Services, record: dict[str, Any], schedules: dict[str, dict[str, Any]]) -> dict[str, Any]:
    problem = ""
    try:
        changes = store.writes(services.registry, record)
    except (ValueError, KeyError) as exc:
        changes = record.get("mode") == "apply"
        problem = str(exc.args[0] if exc.args else exc)
    schedule = schedules.get(record.get("schedule_id") or "")
    approved = store.is_approved(services.state, record)
    return {
        **record,
        "writes": changes,
        "approved": approved,
        "needs_approval": changes and not approved,
        "problem": problem or (schedule or {}).get("validation_error") or "",
        "next_run_at": (schedule or {}).get("next_run_at"),
        "last_run": _last_run(services, record),
    }


def _listing(services: Services) -> dict[str, Any]:
    doc = store.load(services.state)
    if store.adopt_schedules(services.state, services.scheduler, services.registry, doc):
        store.save(services.state, doc)
    schedules = {s["schedule_id"]: s for s in services.scheduler.list_schedules()}
    items = [doc["items"][rid] for rid in doc["order"] if rid in doc["items"]]
    return {"items": [_describe(services, record, schedules) for record in items]}


def _get(doc: dict[str, Any], automation_id: str) -> dict[str, Any]:
    record = doc["items"].get(automation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    return record


def _check_steps(services: Services, record: dict[str, Any]) -> bool:
    """Validate the steps; return whether the automation changes Mealie."""
    for step in record["steps"]:
        if step["task_id"] not in services.registry.task_ids or step["task_id"] == WORKFLOW_TASK:
            raise HTTPException(status_code=422, detail=f"Unknown job '{step['task_id']}'.")
    try:
        return store.writes(services.registry, record)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc.args[0] if exc.args else exc)) from exc


def _approve_or_refuse(services: Services, session: dict[str, Any], record: dict[str, Any], allow_changes: bool) -> None:
    """An automation that changes Mealie on its own needs an owner's say-so."""
    if store.is_approved(services.state, record):
        return
    if not _is_owner(session):
        raise HTTPException(status_code=403, detail="This automation changes Mealie on its own, so an owner has to approve it.")
    if not allow_changes:
        raise HTTPException(status_code=409, detail="approval_required")
    store.set_approved(services.state, record, True)


def _save(services: Services, doc: dict[str, Any], record: dict[str, Any]) -> None:
    try:
        store.sync_schedule(services.scheduler, record)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record["updated_at"] = utc_now_iso()
    doc["items"][record["id"]] = record
    if record["id"] not in doc["order"]:
        doc["order"].append(record["id"])
    store.save(services.state, doc)


@router.get("/automations")
def list_automations(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    return _listing(services)


@router.post("/automations", status_code=201)
def create_automation(
    payload: AutomationIn,
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    doc = store.load(services.state)
    body = payload.model_dump(exclude={"allow_changes"})
    record = store.new_record(body, enabled=payload.enabled, trigger=body["trigger"])
    changes = _check_steps(services, record)
    if record["enabled"] and changes:
        _approve_or_refuse(services, session, record, payload.allow_changes)
    _save(services, doc, record)
    return _listing(services)


@router.put("/automations/{automation_id}")
def update_automation(
    automation_id: str,
    payload: AutomationIn,
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    doc = store.load(services.state)
    current = _get(doc, automation_id)
    body = payload.model_dump(exclude={"allow_changes"})
    record = {**current, **body}
    changes = _check_steps(services, record)
    what_it_does = ("steps", "mode", "backup_first", "stop_on_error")
    if not _is_owner(session) and any(current.get(key) != record.get(key) for key in what_it_does):
        # What was approved isn't what will run any more.
        store.set_approved(services.state, record, False)
    if record["enabled"] and changes:
        _approve_or_refuse(services, session, record, payload.allow_changes)
    _save(services, doc, record)
    return _listing(services)


@router.post("/automations/{automation_id}/enabled")
def set_enabled(
    automation_id: str,
    payload: EnableIn,
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    doc = store.load(services.state)
    record = dict(_get(doc, automation_id))
    record["enabled"] = payload.enabled
    trigger = dict(record.get("trigger") or {})
    if payload.enabled and payload.start_at and trigger.get("type") == "interval":
        trigger["start_at"] = payload.start_at
    record["trigger"] = trigger
    if payload.enabled and _check_steps(services, record):
        _approve_or_refuse(services, session, record, payload.allow_changes)
    _save(services, doc, record)
    return _listing(services)


@router.delete("/automations/{automation_id}")
def delete_automation(
    automation_id: str,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    doc = store.load(services.state)
    record = _get(doc, automation_id)
    if record.get("schedule_id"):
        services.scheduler.delete_schedule(record["schedule_id"])
    store.set_approved(services.state, record, False)
    doc["items"].pop(automation_id, None)
    doc["order"] = [rid for rid in doc["order"] if rid != automation_id]
    store.save(services.state, doc)
    return _listing(services)


@router.post("/automations/{automation_id}/run", status_code=202)
def run_automation(
    automation_id: str,
    payload: RunIn,
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    doc = store.load(services.state)
    record = _get(doc, automation_id)
    options = store.workflow_options(record, mode="preview" if payload.preview else None)
    enforce_safety(services, WORKFLOW_TASK, options, confirmed_by_owner=bool(payload.confirmed and _is_owner(session)))
    return services.runner.enqueue(task_id=WORKFLOW_TASK, options=options, triggered_by=str(session["username"]))
