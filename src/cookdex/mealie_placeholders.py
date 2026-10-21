"""Mealie's placeholders for a recipe made without ingredients or steps.

Mealie 3.21 through 3.29 give such a recipe (made in Mealie, imported from a
page without a recipe, or created through the API) one ingredient, "1 Cup
Flour", and one step that explains markdown. They aren't part of the recipe,
so CookDex treats them as nothing there.

The match is strict, so a real "1 cup flour" in a real recipe counts: only the
exact placeholder, with no amount, unit, food or original text, and only as
the recipe's single ingredient or step.
"""
from __future__ import annotations

from typing import Any

PLACEHOLDER_INGREDIENT = "1 Cup Flour"
PLACEHOLDER_STEP_START = "Recipe steps as well as other fields in the recipe page support markdown syntax."


def is_placeholder_ingredients(items: Any) -> bool:
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return False
    item = items[0]
    if item.get("quantity") not in (None, 0, 0.0):
        return False
    if any(item.get(key) for key in ("unit", "food", "originalText", "referencedRecipe", "title")):
        return False
    return str(item.get("note") or "") == PLACEHOLDER_INGREDIENT and str(item.get("display") or PLACEHOLDER_INGREDIENT) == PLACEHOLDER_INGREDIENT


def is_placeholder_steps(items: Any) -> bool:
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return False
    step = items[0]
    return str(step.get("text") or "").strip().startswith(PLACEHOLDER_STEP_START) and not str(step.get("title") or "").strip()


def without_placeholders(recipe: dict[str, Any]) -> dict[str, Any]:
    """The recipe with Mealie's placeholder ingredient and step taken out."""
    out = recipe
    if is_placeholder_ingredients(recipe.get("recipeIngredient")):
        out = {**out, "recipeIngredient": []}
    if is_placeholder_steps(recipe.get("recipeInstructions")):
        out = {**out, "recipeInstructions": []}
    return out
