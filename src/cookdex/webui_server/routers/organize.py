"""Organize: live tags, categories and tools from Mealie.

Reads come straight from Mealie with recipe counts and suggested merges.
Writes go through the ``organize-apply`` task (see cookdex.organize_apply),
so they get run history, a backup first and the usual safety checks.
"""
from __future__ import annotations

from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException

from ...api_client import MealieApiClient
from ...taxonomy_duplicates import build_duplicate_groups, choose_canonical
from ..deps import Services, build_runtime_env, require_editor_session, require_services

router = APIRouter(tags=["organize"])

KINDS = ("tags", "categories", "tools")


def _client(services: Services) -> MealieApiClient:
    env = build_runtime_env(services.state, services.cipher)
    url, key = env.get("MEALIE_URL", "").strip(), env.get("MEALIE_API_KEY", "").strip()
    if not url or not key:
        raise HTTPException(status_code=409, detail="Connect Mealie in Settings first.")
    return MealieApiClient(base_url=url, api_key=key)


def _usage(client: MealieApiClient, kind: str, items: list[dict[str, Any]]) -> dict[str, int]:
    if items and all(isinstance(item.get("recipeCount"), int) for item in items):
        return {str(item["id"]): int(item["recipeCount"]) for item in items}
    # Older Mealie servers: count links from recipe summaries.
    field = {"tags": "tags", "categories": "recipeCategory", "tools": "tools"}[kind]
    usage: dict[str, int] = {}
    for recipe in client.get_recipes(per_page=1000):
        for entry in recipe.get(field) or []:
            if isinstance(entry, dict) and entry.get("id"):
                usage[str(entry["id"])] = usage.get(str(entry["id"]), 0) + 1
    return usage


@router.get("/organize/{kind}")
def list_organizers(
    kind: str,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown kind '{kind}'.")
    client = _client(services)
    try:
        raw = client.list_tools() if kind == "tools" else client.get_organizer_items(kind)
        usage = _usage(client, kind, raw)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Couldn't read {kind} from Mealie: {type(exc).__name__}.") from exc

    # Suggested merges: near-duplicate spellings go to the most-used one.
    suggestions: dict[str, dict[str, Any]] = {}
    for candidates in build_duplicate_groups(raw).values():
        canonical = choose_canonical(candidates, usage)
        for item in candidates:
            if item.get("id") != canonical.get("id"):
                suggestions[str(item["id"])] = {"id": str(canonical["id"]), "name": str(canonical.get("name") or "")}

    items = sorted(
        (
            {
                "id": str(item["id"]),
                "name": str(item.get("name") or ""),
                "slug": str(item.get("slug") or ""),
                "count": usage.get(str(item["id"]), 0),
                "merge_into": suggestions.get(str(item["id"])),
            }
            for item in raw
            if item.get("id")
        ),
        key=lambda item: item["name"].lower(),
    )
    return {
        "kind": kind,
        "items": items,
        "total": len(items),
        "unused": sum(1 for item in items if item["count"] == 0),
        "suggested_merges": sum(1 for item in items if item["merge_into"]),
    }
