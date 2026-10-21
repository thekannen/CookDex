"""What Mealie 3.21-3.29 puts on a recipe made without ingredients or steps (seen live)."""
from __future__ import annotations

from typing import Any

PLACEHOLDER_INGREDIENT = {
    "quantity": 0.0, "unit": None, "food": None, "referencedRecipe": None, "note": "1 Cup Flour",
    "display": "1 Cup Flour", "title": None, "originalText": None, "substitutions": [],
    "referenceId": "e3d08d03-9f1f-4cef-a86a-358246fbfe56",
}
PLACEHOLDER_STEP = {
    "id": "58924359-cd07-4048-bdcf-4356a564326e", "title": "", "summary": "",
    "text": "Recipe steps as well as other fields in the recipe page support markdown syntax.\n\n"
            "**Add a link**\n\n[My Link](https://demo.mealie.io)\n",
    "ingredientReferences": [], "noteReferences": [],
}


def as_mealie_made(recipe: dict[str, Any]) -> dict[str, Any]:
    """The recipe as Mealie stores it: placeholders where it has no ingredients or steps."""
    out = dict(recipe)
    if not out.get("recipeIngredient"):
        out["recipeIngredient"] = [dict(PLACEHOLDER_INGREDIENT)]
    if not out.get("recipeInstructions"):
        out["recipeInstructions"] = [dict(PLACEHOLDER_STEP)]
    return out
