"""Discover: recipe sources, what each has contributed, and the latest run.

Source add/update/delete stay on the existing /settings/dredger-sites routes.
Runs go through the recipe-dredger task.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...recipe_dredger import sites as suggested
from .. import responsible_use
from ..deps import ROLE_OWNER, Services, require_editor_session, require_owner_session, require_services
from .settings_api import _get_dredger_store

router = APIRouter(tags=["discover"])


def _host(url: str) -> str:
    return (urlsplit(url if "://" in url else f"https://{url}").hostname or "").lower().removeprefix("www.")


# The suggestions list version this install last saw. An install from before
# versions were kept has none, so everything added or retired since is news.
_SEEN_KEY = "discover_suggestions_seen"


def _seen_version(services: Services) -> str:
    record = services.state.get_document(_SEEN_KEY)
    return str(record.get("version") or "") if isinstance(record, dict) else ""


def _mark_seen(services: Services) -> None:
    services.state.set_document(_SEEN_KEY, {"version": suggested.list_version()})


def _suggestions_update(services: Services, sites: list[dict[str, Any]]) -> dict[str, Any] | None:
    """New suggestions and retired ones still in this install, since it last looked.

    Nothing here changes the sources: people choose what to add or remove.
    """
    current = suggested.list_version()
    seen = _seen_version(services)
    if not current or seen >= current:
        return None
    have = {suggested.site_key(str(site.get("url") or "")): site for site in sites}
    new = [
        {"url": entry["url"], "label": entry.get("label") or _host(entry["url"]), "group": entry.get("group") or "Other"}
        for entry in suggested.load_default_sites()
        if str(entry.get("added") or "") > seen and suggested.site_key(entry["url"]) not in have
    ]
    retired = []
    for entry in suggested.load_retired_sites():
        site = have.get(suggested.site_key(entry["url"]))
        if site is None or str(entry.get("retired") or "") <= seen:
            continue
        retired.append({
            "id": site.get("id"),
            "url": site.get("url"),
            "label": site.get("label") or _host(str(site.get("url") or "")),
            "reason": entry["reason"],
            "reason_text": suggested.RETIRED_REASONS.get(entry["reason"], ""),
            "moved_to": entry.get("moved_to"),
        })
    if not new and not retired:
        _mark_seen(services)
        return None
    return {"version": current, "new": new, "retired": retired}


@router.get("/discover")
def get_discover(
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    store = _get_dredger_store()
    sites = store.get_all_sites()
    if not sites:
        # Suggested sources start switched off; people choose what to crawl.
        store.seed_defaults(suggested.load_default_sites(), enabled=False)
        _mark_seen(services)
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
    running_run_ids: list[str] = []
    for run in services.state.list_runs(limit=200):
        if run.get("task_id") != "recipe-dredger":
            continue
        if run.get("status") in {"queued", "running"}:
            running = True
            running_run_ids.append(str(run["run_id"]))
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
        # So the page can stop an import it didn't start itself (an automation's).
        "running_run_ids": running_run_ids,
        "last_run": last_run,
        "responsible_use": {
            **(responsible_use.acceptance(services.state) or {}),
            "accepted": responsible_use.is_accepted(services.state),
            "can_accept": str(session.get("role") or "").strip().lower() == ROLE_OWNER,
        },
        "suggestions_update": _suggestions_update(services, sites),
    }


@router.post("/discover/responsible-use")
def accept_responsible_use(
    session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    """An owner accepts that they choose the sites and answer for following their terms."""
    return {**responsible_use.accept(services.state, str(session["username"])), "accepted": True}


class SuggestionsApplyRequest(BaseModel):
    add: list[str] = Field(default_factory=list, max_length=1000)
    remove_ids: list[int] = Field(default_factory=list, max_length=1000)


@router.post("/discover/suggestions")
def apply_suggestions(
    payload: SuggestionsApplyRequest,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    """Add the chosen new suggestions (switched off) and remove the chosen retired ones.

    Called with nothing chosen, it just dismisses the update.
    """
    store = _get_dredger_store()
    wanted = {suggested.site_key(url) for url in payload.add}
    to_add = [entry for entry in suggested.load_default_sites() if suggested.site_key(entry["url"]) in wanted]
    added = store.seed_defaults(to_add, merge=True, enabled=False) if to_add else 0
    retired = {suggested.site_key(entry["url"]) for entry in suggested.load_retired_sites()}
    removed = 0
    for site in store.get_all_sites():
        # Only retired suggestions go this way; other sources are removed one by one.
        if site["id"] in payload.remove_ids and suggested.site_key(site["url"]) in retired:
            removed += int(store.delete_site(site["id"]))
    _mark_seen(services)
    return {"added": added, "removed": removed}


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
