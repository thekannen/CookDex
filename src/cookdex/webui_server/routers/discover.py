"""Discover: recipe sources, what each has contributed, and the latest run.

Source add/update/delete stay on the existing /settings/dredger-sites routes.
Runs go through the recipe-dredger task.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import Services, require_editor_session, require_services
from .settings_api import _get_dredger_store

router = APIRouter(tags=["discover"])


def _host(url: str) -> str:
    return (urlsplit(url if "://" in url else f"https://{url}").hostname or "").lower().removeprefix("www.")


@router.get("/discover")
def get_discover(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    store = _get_dredger_store()
    sites = store.get_all_sites()
    if not sites:
        from cookdex.recipe_dredger.sites import DEFAULT_SITES

        # Suggested sources start switched off; people choose what to crawl.
        store.seed_defaults(DEFAULT_SITES, enabled=False)
        sites = store.get_all_sites()
    stats = store.site_stats()

    sources = []
    for site in sites:
        entry = stats.get(_host(str(site.get("url") or "")), {})
        sources.append({
            "id": site.get("id"),
            "url": site.get("url"),
            "label": site.get("label") or _host(str(site.get("url") or "")),
            "group": site.get("site_group") or site.get("group") or "Other",
            "enabled": bool(site.get("enabled")),
            "imported": int(entry.get("imported") or 0),
            "rejected": int(entry.get("rejected") or 0),
            "last_imported_at": entry.get("last_imported_at"),
        })

    last_run = None
    running = False
    for run in services.state.list_runs(limit=200):
        if run.get("task_id") != "recipe-dredger":
            continue
        if run.get("status") in {"queued", "running"}:
            running = True
            continue
        results = services.state.get_run_results(run["run_id"]) or []
        items = [item for entry in results if entry.get("kind") == "recipe_import" for item in entry.get("items") or []]
        options = run.get("options") or {}
        last_run = {
            "run_id": run["run_id"],
            "status": run.get("status"),
            "finished_at": run.get("finished_at"),
            "preview": options.get("dry_run", True) is not False,
            "count": len(items),
            "items": items[:50],
        }
        break

    return {
        "sources": sources,
        "enabled_count": sum(1 for s in sources if s["enabled"]),
        "total": len(sources),
        "imported_total": sum(s["imported"] for s in sources),
        "running": running,
        "last_run": last_run,
    }


class SourcesEnabledRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=1000)
    enabled: bool


@router.post("/discover/sources/enabled")
def set_sources_enabled(
    payload: SourcesEnabledRequest,
    _session: dict[str, Any] = Depends(require_editor_session),
    _services: Services = Depends(require_services),
) -> dict[str, Any]:
    """Switch several sources on or off at once, e.g. a whole cuisine group."""
    store = _get_dredger_store()
    changed = sum(1 for site_id in payload.ids if store.update_site(site_id, enabled=payload.enabled))
    return {"changed": changed}
