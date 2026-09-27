from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..deps import (
    ROLE_OWNER,
    Services,
    build_runtime_env,
    enforce_safety,
    require_editor_session,
    require_owner_session,
    require_services,
)
from ...config import configured_ai_providers
from ..rate_limit import ActionRateLimiter
from ..schemas import PoliciesUpdateRequest, RunCreateRequest

router = APIRouter(tags=["runs"])
_action_limiter = ActionRateLimiter(max_per_minute=30)


@router.get("/tasks")
def list_tasks(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    tasks = services.registry.describe_tasks()
    policies = services.state.list_task_policies()
    runtime_env = build_runtime_env(services.state, services.cipher)
    db_configured = bool(runtime_env.get("MEALIE_DB_TYPE", "").strip())
    ready_providers = configured_ai_providers(runtime_env)
    provider_labels = {"chatgpt": "ChatGPT (OpenAI)", "anthropic": "Anthropic", "ollama": "Ollama (Local)"}
    for task in tasks:
        task["policy"] = policies.get(task["task_id"], {"allow_dangerous": False})
        for option in task.get("options", []):
            if db_configured and option["key"] == "use_db":
                option["default"] = True
            if task["task_id"] == "tag-categorize" and option["key"] == "method" and not ready_providers:
                # Without an AI provider, "Both" would only run rules and then report
                # a skipped step. Start from what will actually run.
                option["default"] = "rules"
                option["help_text"] = "Rules Only works without AI. Set up an AI provider in Settings → AI to use the other methods."
            if task["task_id"] in {"tag-categorize", "data-maintenance"} and option["key"] == "provider":
                if not ready_providers:
                    option["hidden"] = True
                else:
                    option["choices"] = [
                        {"value": "", "label": "Default"},
                        *({"value": name, "label": provider_labels[name]} for name in ready_providers),
                    ]
    return {"items": tasks}


@router.get("/policies")
def get_policies(
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    return {"policies": services.state.list_task_policies()}


@router.put("/policies")
def put_policies(
    payload: PoliciesUpdateRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    for task_id, item in payload.policies.items():
        services.state.set_task_policy(task_id.strip(), item.allow_dangerous)
    return {"policies": services.state.list_task_policies()}


@router.post("/runs", status_code=202)
def create_run(
    payload: RunCreateRequest,
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    _action_limiter.check(session["username"])
    task_id = payload.task_id.strip()
    if task_id not in services.registry.task_ids:
        raise HTTPException(status_code=404, detail=f"Unknown task '{task_id}'.")
    options = dict(payload.options)
    is_owner = str(session.get("role") or "").strip().lower() == ROLE_OWNER
    enforce_safety(services, task_id, options, confirmed_by_owner=bool(payload.confirmed and is_owner))
    return services.runner.enqueue(task_id=task_id, options=options, triggered_by=str(session["username"]))


@router.get("/runs")
def list_runs(
    limit: int = 100,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    value = min(max(limit, 1), 500)
    return {"items": services.state.list_runs(limit=value)}


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    run = services.state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@router.get("/runs/{run_id}/result")
def get_run_result(
    run_id: str,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    """Structured results a run reported, one entry per summary it emitted."""
    run = services.state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    status = str(run.get("status") or "")
    if status in {"queued", "running"}:
        results = services.state.get_run_results(run_id)
    else:
        # The worker stores results right after the run ends; ingest here too
        # so a client that asks in that moment still gets them.
        results = services.runner.ingest_results(run_id)
    return {
        "run_id": run_id,
        "task_id": run.get("task_id"),
        "status": status,
        "results": results or [],
    }


@router.get("/runs/{run_id}/log")
def get_run_log(
    run_id: str,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> PlainTextResponse:
    try:
        text = services.runner.read_log(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.")
    return PlainTextResponse(text)


@router.get("/runs/{run_id}/log/tail")
def get_run_log_tail(
    run_id: str,
    offset: int = Query(default=0, ge=0),
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    """Return log bytes from `offset` onwards, plus the current total file size."""
    record = services.state.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    log_path = record.get("log_path")
    if not log_path:
        return {"content": "", "size": 0}
    path = Path(str(log_path))
    if not path.exists():
        return {"content": "", "size": 0}
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            total = fh.tell()
            fh.seek(min(offset, total))
            chunk = fh.read(200_000)
        return {"content": chunk.decode("utf-8", errors="replace"), "size": total}
    except OSError:
        return {"content": "", "size": 0}


@router.post("/runs/{run_id}/cancel")
def cancel_run(
    run_id: str,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    if not services.runner.cancel(run_id):
        raise HTTPException(status_code=409, detail="Run cannot be canceled.")
    run = services.state.get_run(run_id)
    return {"ok": True, "run": run}
