"""Recipes someone chose to leave as they are.

The Library's "Leave as is" remembers a recipe that a cleanup flagged but that
should stay: a page Mealie won't delete, or a name that can't be cleaned up
without clashing with another recipe. The web UI passes the list to jobs in
``COOKDEX_KEPT_RECIPES`` as ``{slug: updatedAt}``. A job leaves those recipes
alone until they change in Mealie: an edit may have fixed the problem, or made
a new one, so a changed recipe is checked again.
"""
from __future__ import annotations

import json
import os
from typing import Any, Mapping

ENV_KEY = "COOKDEX_KEPT_RECIPES"


def stamp(recipe: Mapping[str, Any]) -> str:
    """When Mealie last changed a recipe, as it reports it."""
    return str(recipe.get("updatedAt") or recipe.get("dateUpdated") or "")


def load(env: Mapping[str, str] | None = None) -> dict[str, str]:
    raw = (env if env is not None else os.environ).get(ENV_KEY, "")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return {str(slug): str(value or "") for slug, value in data.items()} if isinstance(data, dict) else {}


def is_kept(recipe: Mapping[str, Any], kept: Mapping[str, str]) -> bool:
    """Whether a recipe was left as is and hasn't changed since."""
    slug = str(recipe.get("slug") or "")
    if slug not in kept:
        return False
    marked = kept[slug]
    return not marked or not stamp(recipe) or marked == stamp(recipe)
