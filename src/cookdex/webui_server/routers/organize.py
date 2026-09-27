"""Organize: live tags, categories and tools from the recipe manager.

Reads go through the configured provider (see cookdex.providers) with recipe
counts and suggested merges. Writes go through the ``organize-apply`` task
(see cookdex.organize_apply), so they get run history, a backup first and
the usual safety checks.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...providers import Capability, ProviderError, RecipeProvider, get_provider
from ...taxonomy_duplicates import build_duplicate_groups, choose_canonical
from ..deps import Services, build_runtime_env, require_editor_session, require_services

router = APIRouter(tags=["organize"])


def _provider(services: Services) -> RecipeProvider:
    try:
        return get_provider(build_runtime_env(services.state, services.cipher))
    except ProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _require_collections(provider: RecipeProvider) -> None:
    if Capability.RULE_COLLECTIONS not in provider.capabilities():
        raise HTTPException(status_code=404, detail=f"{provider.display_name} doesn't have rule-based collections.")


# Registered before /organize/{kind} so "cookbooks" isn't read as a term kind.
@router.get("/organize/cookbooks")
def list_cookbooks(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    provider = _provider(services)
    _require_collections(provider)
    try:
        collections = provider.list_collections()
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    def matches(rule: str) -> dict[str, Any]:
        if not rule.strip():
            return {"matches": 0, "error": ""}
        try:
            return {"matches": provider.count_rule_matches(rule)[0], "error": ""}
        except ProviderError as exc:
            return {"matches": None, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        counts = list(pool.map(matches, (c.rule for c in collections)))
    return {
        "items": [
            {"id": c.id, "name": c.name, "description": c.description, "rule": c.rule,
             "public": c.public, "position": c.position, **count}
            for c, count in zip(collections, counts)
        ],
        "total": len(collections),
    }


class RulePreviewRequest(BaseModel):
    rule: str = Field(default="", max_length=20_000)


@router.post("/organize/cookbooks/preview")
def preview_cookbook_rule(
    payload: RulePreviewRequest,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    """Count the recipes an unsaved filter would match, with a few examples."""
    provider = _provider(services)
    _require_collections(provider)
    if not payload.rule.strip():
        return {"matches": 0, "sample": [], "error": ""}
    try:
        count, sample = provider.count_rule_matches(payload.rule, sample=5)
    except ProviderError as exc:
        return {"matches": None, "sample": [], "error": str(exc)}
    return {"matches": count, "sample": sample, "error": ""}


@router.get("/organize/{kind}")
def list_organizers(
    kind: str,
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    provider = _provider(services)
    if kind not in provider.term_kinds():
        raise HTTPException(status_code=404, detail=f"Unknown kind '{kind}'.")
    try:
        terms = provider.list_terms(kind)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Suggested merges: near-duplicate spellings go to the most-used one.
    raw = [{"id": t.id, "name": t.name, "groupId": t.extra.get("groupId") or ""} for t in terms]
    usage = {t.id: t.count for t in terms}
    suggestions: dict[str, dict[str, Any]] = {}
    for candidates in build_duplicate_groups(raw).values():
        canonical = choose_canonical(candidates, usage)
        for item in candidates:
            if item["id"] != canonical["id"]:
                suggestions[item["id"]] = {"id": canonical["id"], "name": canonical["name"]}

    items = sorted(
        (
            {"id": t.id, "name": t.name, "count": t.count, "parent_id": t.parent_id, "merge_into": suggestions.get(t.id)}
            for t in terms
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
