"""Recipes the Library was told to leave as they are.

Stored in state.db as one document, ``{slug: {...}}``. Jobs get the list as
``COOKDEX_KEPT_RECIPES`` (see cookdex.kept_recipes) and leave those recipes
alone until they change in Mealie.
"""
from __future__ import annotations

from typing import Any, Iterable

from .state import StateStore, utc_now_iso

_DOC_KEY = "library_kept"
KINDS = {"junk", "review", "rename", "name_clash"}


def all_kept(state: StateStore) -> dict[str, dict[str, Any]]:
    data = state.get_document(_DOC_KEY)
    return {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def keep(state: StateStore, items: Iterable[dict[str, Any]], username: str) -> int:
    kept = all_kept(state)
    added = 0
    for item in items:
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        kept[slug] = {
            "name": str(item.get("name") or slug),
            "kind": str(item.get("kind") or "") if item.get("kind") in KINDS else "",
            "updated_at": str(item.get("updated_at") or ""),
            "at": utc_now_iso(),
            "by": username,
        }
        added += 1
    state.set_document(_DOC_KEY, kept)
    return added


def forget(state: StateStore, slugs: Iterable[str]) -> int:
    kept = all_kept(state)
    removed = sum(1 for slug in set(slugs) if kept.pop(str(slug), None) is not None)
    state.set_document(_DOC_KEY, kept)
    return removed


def job_env(state: StateStore) -> dict[str, str]:
    """What a job needs: each kept slug and when the recipe last changed."""
    return {slug: str(entry.get("updated_at") or "") for slug, entry in all_kept(state).items()}


def covers(item: dict[str, Any], kept: dict[str, dict[str, Any]]) -> bool:
    """Whether a flagged item is one that was left as is and hasn't changed since."""
    entry = kept.get(str(item.get("slug") or ""))
    if entry is None:
        return False
    marked, seen = str(entry.get("updated_at") or ""), str(item.get("updated_at") or "")
    return not marked or not seen or marked == seen
