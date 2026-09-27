from __future__ import annotations

from cookdex.categorizer_core import MealieCategorizer


def test_prompt_sends_mealies_ingredients_and_asks_for_a_course():
    recipe = {
        "slug": "instant-pot-chicken-and-rice",
        "name": "Instant Pot Chicken and Rice",
        "description": "Weeknight one-pot dinner.",
        "recipeIngredient": [
            {"display": "2 cups long-grain rice"},
            {"note": "1 lb chicken thighs"},
            {"food": {"name": "onion"}},
        ],
    }
    prompt = MealieCategorizer.make_prompt([recipe], ["Dinner", "Side"], ["Easy"], ["Instant Pot"])
    assert "ingredients: 2 cups long-grain rice, 1 lb chicken thighs, onion" in prompt
    assert "about: Weeknight one-pot dinner." in prompt
    assert "give every recipe the one category that fits best" in prompt
    category_prompt = MealieCategorizer.make_category_prompt([recipe], ["Dinner", "Side"])
    assert "fits best" in category_prompt and "Use empty arrays when nothing fits." not in category_prompt
