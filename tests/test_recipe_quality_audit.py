from __future__ import annotations

from urllib.parse import unquote

from cookdex.recipe_quality_audit import LINKED_INGREDIENTS_FILTER, RecipeQualityAuditor


class Client:
    """The recipe list has no ingredients, like Mealie's."""

    def __init__(self) -> None:
        self.recipes = [{"id": f"r{i}", "slug": f"recipe-{i}", "name": f"Recipe {i}"} for i in range(10)]

    def get_recipes(self, per_page: int = 1000):
        return [dict(r) for r in self.recipes]

    def get_paginated(self, path, per_page=1000, timeout=None):
        assert unquote(path) == f"/recipes?queryFilter={LINKED_INGREDIENTS_FILTER}"
        return [{"id": f"r{i}"} for i in range(7)]  # 7 of 10 have a linked ingredient

    def get_recipe(self, slug):
        return {"nutrition": {}}


def test_api_mode_counts_linked_ingredients_from_mealies_filter(tmp_path):
    auditor = RecipeQualityAuditor(Client(), report_file=tmp_path / "quality.json", nutrition_sample_size=2)
    recipes, _hits, _sample, total = auditor._run_api()
    assert total == 10
    assert sum(1 for r in recipes if r["hasParsedIngredients"]) == 7


def test_api_mode_leaves_ingredients_alone_when_the_filter_fails(tmp_path):
    client = Client()
    client.get_paginated = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("filter not supported"))
    auditor = RecipeQualityAuditor(client, report_file=tmp_path / "quality.json", nutrition_sample_size=2)
    recipes, *_ = auditor._run_api()
    assert all("hasParsedIngredients" not in r for r in recipes)
