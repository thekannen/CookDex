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

from ...providers import Capability, ProviderError, RecipeProvider, Unit, get_provider
from ...taxonomy_duplicates import build_duplicate_groups, choose_canonical, normalize_name
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


@router.get("/organize/labels")
def list_labels(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    provider = _provider(services)
    if Capability.LABELS not in provider.capabilities():
        raise HTTPException(status_code=404, detail=f"{provider.display_name} doesn't have food labels.")
    try:
        labels = provider.list_labels()
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    # Suggested merges: the same name in different case or spacing.
    raw = [{"id": label.id, "name": label.name, "groupId": ""} for label in labels]
    usage = {label.id: label.count for label in labels}
    suggestions: dict[str, dict[str, Any]] = {}
    for candidates in build_duplicate_groups(raw).values():
        canonical = choose_canonical(candidates, usage)
        for item in candidates:
            if item["id"] != canonical["id"]:
                suggestions[item["id"]] = {"id": canonical["id"], "name": canonical["name"]}
    items = [
        {"id": label.id, "name": label.name, "color": label.color, "count": label.count, "merge_into": suggestions.get(label.id)}
        for label in labels
    ]
    return {"items": items, "total": len(items), "unused": sum(1 for i in items if i["count"] == 0)}


# Counting is one small request per item; past this many we skip it.
MAX_COUNTED = 1500


def _ingredient_counts(provider: RecipeProvider, kind: str, ids: list[str]) -> dict[str, int | None]:
    if len(ids) > MAX_COUNTED:
        return dict.fromkeys(ids)

    def count(item_id: str) -> int | None:
        try:
            return provider.count_ingredient_uses(kind, item_id)
        except ProviderError:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(zip(ids, pool.map(count, ids)))


def _suggest_merges(entries: list[dict[str, Any]], usage: dict[str, int | None]) -> dict[str, dict[str, Any]]:
    """Near-duplicate names go to the most-used spelling."""
    raw = [{"id": e["id"], "name": e["name"], "groupId": ""} for e in entries]
    counts = {key: value or 0 for key, value in usage.items()}
    suggestions: dict[str, dict[str, Any]] = {}
    for candidates in build_duplicate_groups(raw).values():
        canonical = choose_canonical(candidates, counts)
        for item in candidates:
            if item["id"] != canonical["id"]:
                suggestions[item["id"]] = {"id": canonical["id"], "name": canonical["name"]}
    return suggestions


def _ingredient_response(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": items,
        "total": len(items),
        "counted": any(item["count"] is not None for item in items),
        "unused": sum(1 for item in items if item["count"] == 0),
        "suggested_merges": sum(1 for item in items if item["merge_into"]),
    }


@router.get("/organize/foods")
def list_foods(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    provider = _provider(services)
    if Capability.FOODS not in provider.capabilities():
        raise HTTPException(status_code=404, detail=f"{provider.display_name} doesn't have editable foods.")
    try:
        foods = provider.list_foods()
        labels = {label.id: label for label in provider.list_labels()} if Capability.LABELS in provider.capabilities() else {}
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    usage = _ingredient_counts(provider, "foods", [f.id for f in foods])
    suggestions = _suggest_merges([{"id": f.id, "name": f.name} for f in foods], usage)
    items = []
    for food in foods:
        label = labels.get(food.label_id)
        items.append({
            "id": food.id, "name": food.name, "plural_name": food.plural_name, "aliases": food.aliases,
            "label_id": food.label_id, "label": {"name": label.name, "color": label.color} if label else None,
            "count": usage.get(food.id), "merge_into": suggestions.get(food.id),
        })
    response = _ingredient_response(items)
    response["unlabeled"] = sum(1 for item in items if not item["label_id"])
    return response


@router.get("/organize/units")
def list_units(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    provider = _provider(services)
    if Capability.UNITS not in provider.capabilities():
        raise HTTPException(status_code=404, detail=f"{provider.display_name} doesn't have editable units.")
    try:
        units = provider.list_units()
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    usage = _ingredient_counts(provider, "units", [u.id for u in units])
    suggestions = _suggest_merges([{"id": u.id, "name": u.name} for u in units], usage)
    # A unit named like another unit's abbreviation, plural or alias
    # ("tbsp" next to "tablespoon") belongs to that unit.
    owners: dict[str, Unit] = {}
    for unit in units:
        for other in (unit.abbreviation, unit.plural_name, *unit.aliases):
            key = normalize_name(other)
            if key and key != normalize_name(unit.name):
                owners.setdefault(key, unit)
    for unit in units:
        owner = owners.get(normalize_name(unit.name))
        if owner and owner.id != unit.id and unit.id not in suggestions:
            suggestions[unit.id] = {"id": owner.id, "name": owner.name}
    items = [
        {"id": u.id, "name": u.name, "plural_name": u.plural_name, "abbreviation": u.abbreviation,
         "aliases": u.aliases, "count": usage.get(u.id), "merge_into": suggestions.get(u.id)}
        for u in units
    ]
    return _ingredient_response(items)


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
