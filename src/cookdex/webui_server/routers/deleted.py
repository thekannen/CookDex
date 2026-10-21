"""Recently deleted: copies of recipes the junk filter or the duplicate finder deleted.

Listing and clearing copies happen here. Restoring writes to Mealie, so it's
a run (``recipe-restore``) in the light lane like other quick changes.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...deleted_recipes import DIR_NAME, CopyError, RecipeArchive, keep_days
from ..deps import ROLE_OWNER, Services, build_runtime_env, require_editor_session, require_services, require_task_available
from ..rate_limit import ActionRateLimiter

router = APIRouter(tags=["deleted-recipes"])
_action_limiter = ActionRateLimiter(max_per_minute=30)

RESTORE_TASK = "recipe-restore"
ACTIVE = {"queued", "running"}


class RestoreRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)


def archive_for(services: Services) -> RecipeArchive:
    return RecipeArchive(services.settings.state_db_path.parent / DIR_NAME)


def _require_can_change(services: Services, session: dict[str, Any]) -> None:
    """Owners, and editors when live cleanups are approved for them."""
    if str(session.get("role") or "").strip().lower() == ROLE_OWNER:
        return
    policy = services.state.list_task_policies().get("clean-recipes", {})
    if not policy.get("allow_dangerous"):
        raise HTTPException(status_code=403, detail="An owner has to approve live cleanups before you can restore or clear recipes.")


def _restoring(services: Services) -> dict[str, str]:
    """Saved copies a queued or running restore is working on, with its run."""
    out: dict[str, str] = {}
    for run in services.state.list_runs(limit=200):
        if run.get("task_id") != RESTORE_TASK or run.get("status") not in ACTIVE:
            continue
        for entry_id in (run.get("options") or {}).get("ids") or []:
            out[str(entry_id)] = str(run["run_id"])
    return out


@router.get("/deleted-recipes")
def list_deleted(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    archive = archive_for(services)
    restoring = _restoring(services)
    items = archive.list()
    # Run history is trimmed sooner than copies expire; link only runs still there.
    known = {run_id for run_id in {str(i.get("run_id") or "") for i in items} if run_id and services.state.get_run(run_id)}
    items = [
        {**item, "restoring_run_id": restoring.get(str(item.get("id"))), "run_in_history": str(item.get("run_id") or "") in known}
        for item in items
    ]
    return {
        "items": items,
        "total_bytes": archive.total_size(),
        "keep_days": keep_days(build_runtime_env(services.state, services.cipher)),
    }


@router.post("/deleted-recipes/restore", status_code=202)
def restore_deleted(
    payload: RestoreRequest,
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    _action_limiter.check(session["username"])
    _require_can_change(services, session)
    require_task_available(services, RESTORE_TASK)
    archive = archive_for(services)
    restoring = _restoring(services)
    ids = [entry_id for entry_id in dict.fromkeys(payload.ids) if entry_id not in restoring]
    try:
        missing = [entry_id for entry_id in ids if archive.get(entry_id) is None]
    except CopyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if missing:
        raise HTTPException(status_code=404, detail="Some of these recipes aren't in Recently deleted any more. Refresh the list.")
    if not ids:
        raise HTTPException(status_code=409, detail="These recipes are already being restored.")
    return services.runner.enqueue(task_id=RESTORE_TASK, options={"ids": ids}, triggered_by=str(session["username"]))


@router.delete("/deleted-recipes/{entry_id}")
def clear_deleted(
    entry_id: str,
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    _action_limiter.check(session["username"])
    _require_can_change(services, session)
    if entry_id in _restoring(services):
        raise HTTPException(status_code=409, detail="This recipe is being restored right now.")
    try:
        removed = archive_for(services).forget(entry_id)
    except CopyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="That recipe isn't in Recently deleted.")
    return {"ok": True}
