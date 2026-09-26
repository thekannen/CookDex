"""Focused tests for recipe reimport patch construction."""

from __future__ import annotations

from typing import Any

from cookdex.recipe_reimporter import RecipeReimporter


class _FakeClient:
    def __init__(self) -> None:
        self.patch: dict[str, Any] | None = None
        self.patch_slug: str | None = None

    def get_recipe(self, _slug: str) -> dict[str, Any]:
        return {
            "tags": [{"name": "Dinner"}],
            "recipeCategory": [{"name": "Main"}],
            "orgURL": "https://old.example/recipe",
        }

    def patch_recipe(self, slug: str, patch: dict[str, Any]) -> None:
        self.patch_slug = slug
        self.patch = patch


def test_reimporter_builds_mealie_patch_from_recipe_scrapers_output(tmp_path):
    client = _FakeClient()
    reimporter = RecipeReimporter(client, dry_run=False, report_file=tmp_path / "report.json")

    def _scrape_with_retry(_slug: str, _url: str) -> dict[str, Any]:
        return {
            "description": " Freshly scraped ",
            "ingredients": ["1 cup flour", "2 eggs"],
            "instructions": "Mix the batter.\nBake until set.",
            "nutrients": {"@type": "NutritionInformation", "calories": "200 kcal"},
            "total_time": "45",
            "prep_time": 15,
            "cook_time": 30,
            "yields": "8 servings",
        }

    reimporter._scrape_with_retry = _scrape_with_retry  # type: ignore[method-assign]

    result = reimporter._process_one(1, 1, "cake", "Cake", "https://source.example/cake")

    assert result["status"] == "reimported"
    assert client.patch_slug == "cake"
    assert client.patch is not None
    assert [item["display"] for item in client.patch["recipeIngredient"]] == ["1 cup flour", "2 eggs"]
    assert [step["text"] for step in client.patch["recipeInstructions"]] == [
        "Mix the batter.",
        "Bake until set.",
    ]
    assert client.patch["nutrition"] == {"calories": "200 kcal"}
    assert client.patch["totalTime"] == "PT45M"
    assert client.patch["prepTime"] == "PT15M"
    assert client.patch["cookTime"] == "PT30M"
    assert client.patch["recipeYield"] == "8 servings"
    assert client.patch["orgURL"] == "https://source.example/cake"
    assert client.patch["tags"] == [{"name": "Dinner"}]
    assert client.patch["recipeCategory"] == [{"name": "Main"}]


# The CLI must require explicit apply even when runtime DRY_RUN is false.
def test_reimport_cli_write_gate(monkeypatch, tmp_path):
    import sys

    from cookdex import recipe_reimporter as module
    from cookdex.webui_server.tasks import TaskRegistry

    class Client(_FakeClient):
        def get_recipes(self):
            return [{"slug": "cake", "name": "Cake", "orgURL": "https://example.com/cake"}]

        def request_json(self, *args, **kwargs):
            return {"ingredients": ["1 cup flour"]}

    client = Client()
    monkeypatch.setattr(module, 'MealieApiClient', lambda **kwargs: client)
    monkeypatch.setattr(module, 'resolve_mealie_url', lambda: 'http://127.0.0.1:1/api')
    monkeypatch.setattr(module, 'resolve_mealie_api_key', lambda **kwargs: 'test-token')
    monkeypatch.setattr(module, 'resolve_repo_path', lambda path: tmp_path / 'report.json')
    for runtime_dry_run in (False, True):
        for apply in (False, True):
            client.patch = None
            monkeypatch.setattr(module, 'env_or_config', lambda *args: runtime_dry_run)
            monkeypatch.setattr(sys, 'argv', ['reimport', '--delay', '0', *(['--apply'] if apply else [])])
            assert module.main() == 0
            assert (client.patch is not None) == (apply and not runtime_dry_run)

    registry = TaskRegistry()
    for dry_run in (False, True):
        execution = registry.build_execution('reimport-recipes', {'dry_run': dry_run})
        assert ('--apply' in execution.command) == (not dry_run)
        assert execution.env['DRY_RUN'] == str(dry_run).lower()
