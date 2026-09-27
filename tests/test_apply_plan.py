"""Reviewed plans: modules apply exactly what the user approved."""
from __future__ import annotations

import json
from pathlib import Path

from cookdex.recipe_deduplicator import RecipeDeduplicator
from cookdex.recipe_junk_filter import RecipeJunkFilter
from cookdex.recipe_name_normalizer import RecipeNameNormalizer
from cookdex.reporting import read_results


class FakeClient:
    def __init__(self, recipes: list[dict]) -> None:
        self.recipes = {r["slug"]: r for r in recipes}
        self.deleted: list[str] = []
        self.patched: dict[str, dict] = {}

    def get_recipes(self):
        return list(self.recipes.values())

    def get_recipe(self, slug):
        return self.recipes[slug]

    def delete_recipe(self, slug):
        self.deleted.append(slug)

    def patch_recipe(self, slug, payload):
        self.patched[slug] = payload


def _full(slug, name, *, ingredients=True, steps=True, url=None):
    return {
        "slug": slug,
        "name": name,
        "orgURL": url,
        "recipeIngredient": [{"note": "1 cup rice"}] if ingredients else [],
        "recipeInstructions": [{"text": "Cook the rice until tender."}] if steps else [],
    }


def _plan(monkeypatch, tmp_path: Path, plan: dict) -> Path:
    results = tmp_path / "results.jsonl"
    monkeypatch.setenv("COOKDEX_APPLY_PLAN", json.dumps(plan))
    monkeypatch.setenv("COOKDEX_RESULT_PATH", str(results))
    return results


def test_junk_filter_deletes_only_approved_items_including_review_candidates(monkeypatch, tmp_path):
    client = FakeClient([
        _full("privacy-policy", "Privacy Policy", ingredients=False, steps=False),
        _full("untitled-recipe", "Untitled Recipe", ingredients=False, steps=False),
        _full("gift-guide", "Kitchen Gadget Gift Guide 2026"),
        _full("pad-thai", "Pad Thai"),
    ])
    results = _plan(monkeypatch, tmp_path, {"junk": {"delete": ["privacy-policy", "gift-guide", "pad-thai"]}})

    RecipeJunkFilter(client, dry_run=False, apply=True, report_file=tmp_path / "r.json").run()

    # pad-thai was approved but isn't junk or a review candidate, so it stays.
    assert sorted(client.deleted) == ["gift-guide", "privacy-policy"]
    items = next(e["items"] for e in read_results(results) if e.get("kind") == "recipe_delete")
    status = {item["slug"]: (item["group"], item["status"]) for item in items}
    assert status["untitled-recipe"] == ("junk", "skipped")
    assert status["gift-guide"] == ("review", "applied")


def test_junk_filter_preview_lists_review_candidates(monkeypatch, tmp_path):
    client = FakeClient([_full("gift-guide", "Kitchen Gadget Gift Guide 2026")])
    results = tmp_path / "results.jsonl"
    monkeypatch.delenv("COOKDEX_APPLY_PLAN", raising=False)
    monkeypatch.setenv("COOKDEX_RESULT_PATH", str(results))

    RecipeJunkFilter(client, dry_run=True, report_file=tmp_path / "r.json").run()

    items = next(e["items"] for e in read_results(results) if e.get("kind") == "recipe_delete")
    assert items == [{
        "slug": "gift-guide", "name": "Kitchen Gadget Gift Guide 2026", "group": "review",
        "reason_code": "review", "reason": items[0]["reason"], "status": "planned",
    }]
    assert client.deleted == []


def test_deduplicator_skips_unapproved_duplicates(monkeypatch, tmp_path):
    url = "https://example.com/chili"
    client = FakeClient([
        _full("weeknight-chili-better", "Weeknight Chili (Better)", url=url),
        _full("weeknight-chili", "weeknight-chili", url=url),
        _full("weeknight-chili-copy", "Weeknight Chili (Copy)", url=url),
    ])
    _plan(monkeypatch, tmp_path, {"dedup": {"delete": ["weeknight-chili-copy"]}})

    RecipeDeduplicator(client, dry_run=False, apply=True, report_file=tmp_path / "r.json").run()

    assert client.deleted == ["weeknight-chili-copy"]


def test_name_normalizer_applies_edited_names_and_skips_changed_recipes(monkeypatch, tmp_path):
    client = FakeClient([
        {"slug": "banana-bread-2", "name": "banana-bread-2"},
        {"slug": "pad-thai", "name": "Pad Thai (renamed since preview)"},
    ])
    results = _plan(monkeypatch, tmp_path, {"names": {"rename": {
        "banana-bread-2": {"from": "banana-bread-2", "to": "Grandma's Banana Bread"},
        "pad-thai": {"from": "pad-thai", "to": "Pad Thai"},
    }}})

    RecipeNameNormalizer(client, dry_run=False, apply=True, report_file=tmp_path / "r.json").run()

    assert list(client.patched) == ["banana-bread-2"]
    assert client.patched["banana-bread-2"]["name"] == "Grandma's Banana Bread"
    items = next(e["items"] for e in read_results(results) if e.get("kind") == "recipe_rename")
    assert {i["slug"]: i["status"] for i in items} == {"banana-bread-2": "applied", "pad-thai": "skipped"}


def test_name_normalizer_reports_renames_for_removed_recipes(monkeypatch, tmp_path):
    client = FakeClient([{"slug": "pad-thai", "name": "pad-thai"}])
    results = _plan(monkeypatch, tmp_path, {"names": {"rename": {"gone-1": {"from": "gone-1", "to": "Gone"}}}})

    RecipeNameNormalizer(client, dry_run=False, apply=True, report_file=tmp_path / "r.json").run()

    items = next(e["items"] for e in read_results(results) if e.get("kind") == "recipe_rename")
    gone = next(i for i in items if i["slug"] == "gone-1")
    assert gone["status"] == "skipped"
    assert "removed earlier" in gone["error"]
