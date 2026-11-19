"""Reusing AI answers across runs, and applying a reviewed Tag & Categorize preview."""
import json

import pytest

from cookdex.categorize_preview import load_preview
from cookdex.categorizer_core import MealieCategorizer
from cookdex.reporting import read_results
from cookdex.webui_server.tasks import TaskRegistry

RUN_ID = "11111111-2222-3333-4444-555555555555"
CATEGORIES = [{"id": "1", "name": "Dinner", "slug": "dinner"}, {"id": "2", "name": "Lunch", "slug": "lunch"}]
TAGS = [{"id": "t1", "name": "Quick", "slug": "quick"}, {"id": "t2", "name": "Spicy", "slug": "spicy"}]


class _Ok:
    status_code = 200
    text = ""


def _recipe(slug, **overrides):
    recipe = {
        "slug": slug,
        "name": slug.title(),
        "description": f"About {slug}",
        "recipeIngredient": [{"display": "1 onion"}],
        "recipeCategory": [],
        "tags": [],
        "tools": [],
    }
    recipe.update(overrides)
    return recipe


class _Library:
    """A fake Mealie: recipes by slug, the PATCHes sent, and the AI prompts asked."""

    def __init__(self, recipes):
        self.recipes = {r["slug"]: r for r in recipes}
        self.patches = []
        self.prompts = []
        self.categories = list(CATEGORIES)
        self.tags = list(TAGS)

    @property
    def asked(self):
        """Main classifier prompts sent (follow-up tag/tool prompts aren't counted)."""
        return [p for p in self.prompts if p.startswith("You are a food recipe classifier")]

    def answer(self, prompt):
        self.prompts.append(prompt)
        slugs = [slug for slug in self.recipes if f"slug={slug} " in prompt]
        return json.dumps([{"slug": s, "categories": ["Dinner"], "tags": ["Quick"], "tools": []} for s in slugs])

    def categorizer(self, monkeypatch, tmp_path, *, dry_run, replace_existing=False, target_mode="missing-either"):
        cat = MealieCategorizer(
            mealie_url="http://example/api",
            mealie_api_key="token",
            batch_size=10,
            max_workers=1,
            replace_existing=replace_existing,
            cache_file=tmp_path / "cache" / "results_test.json",
            query_text=self.answer,
            provider_name="Test (model-a)",
            target_mode=target_mode,
            dry_run=dry_run,
            provider_heartbeat_seconds=0,
        )
        monkeypatch.setattr(cat, "get_all_recipes", lambda: [dict(r) for r in self.recipes.values()])
        monkeypatch.setattr(cat, "get_all_categories", lambda: self.categories)
        monkeypatch.setattr(cat, "get_all_tags", lambda: self.tags)
        monkeypatch.setattr(cat, "get_all_tools", lambda: [])
        monkeypatch.setattr(cat, "with_details", lambda targets: [dict(self.recipes[r["slug"]]) for r in targets])

        def patch(slug, payload):
            self.patches.append((slug, payload))
            self.recipes[slug].update(payload)
            return _Ok()

        monkeypatch.setattr(cat, "_patch_recipe", patch)
        return cat


@pytest.fixture
def run_env(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKDEX_RUN_ID", RUN_ID)
    monkeypatch.setenv("COOKDEX_RESULT_PATH", str(tmp_path / "result.jsonl"))
    monkeypatch.delenv("COOKDEX_APPLY_PLAN", raising=False)
    return tmp_path / "result.jsonl"


def _items(result_path):
    entries = [e for e in read_results(result_path) if e.get("kind") == "recipe_categorize"]
    return {item["slug"]: item for item in entries[-1]["items"]} if entries else {}


def _apply_plan(monkeypatch, exclude=()):
    monkeypatch.setenv("COOKDEX_APPLY_PLAN", json.dumps({"categorize": {"from_run": RUN_ID, "exclude": list(exclude)}}))


# ── Reusing answers ──────────────────────────────────────────────────


def test_apply_after_preview_reuses_ai_answers(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup"), _recipe("stew")])
    library.categorizer(monkeypatch, tmp_path, dry_run=True).run()
    assert len(library.asked) == 1
    assert library.patches == []
    prompts_after_preview = len(library.prompts)

    live = library.categorizer(monkeypatch, tmp_path, dry_run=False)
    live.run()

    assert len(library.prompts) == prompts_after_preview, "the live run must not ask the AI again"
    assert live.stats_snapshot()["suggestions_reused"] == 2
    assert sorted(slug for slug, _ in library.patches) == ["soup", "stew"]


def test_changed_recipe_text_is_asked_about_again(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup"), _recipe("stew")])
    library.categorizer(monkeypatch, tmp_path, dry_run=True).run()
    library.recipes["stew"]["description"] = "Now with beans"

    library.categorizer(monkeypatch, tmp_path, dry_run=True).run()

    assert len(library.asked) == 2
    assert "slug=stew " in library.asked[1] and "slug=soup " not in library.asked[1]


def test_new_taxonomy_term_invalidates_saved_answers(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup")])
    library.categorizer(monkeypatch, tmp_path, dry_run=True).run()
    library.categories.append({"id": "3", "name": "Brunch", "slug": "brunch"})

    library.categorizer(monkeypatch, tmp_path, dry_run=True).run()

    assert len(library.asked) == 2


def test_empty_answers_are_not_saved(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup")])
    library.answer = lambda prompt: library.prompts.append(prompt) or '[{"slug":"soup","categories":[],"tags":[],"tools":[]}]'
    library.categorizer(monkeypatch, tmp_path, dry_run=True).run()
    first = len(library.asked)
    library.categorizer(monkeypatch, tmp_path, dry_run=True).run()
    assert len(library.asked) > first


# ── Saved previews ───────────────────────────────────────────────────


def test_preview_records_items_and_saves_its_plan(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup"), _recipe("salad", recipeCategory=[CATEGORIES[1]], tags=[TAGS[1]])])
    cat = library.categorizer(monkeypatch, tmp_path, dry_run=True)
    cat.run()

    items = _items(run_env)
    assert items["soup"] == {"status": "planned", "slug": "soup", "name": "Soup", "categories": ["Dinner"], "tags": ["Quick"], "tools": []}
    record = load_preview(cat.cache_file, RUN_ID)
    assert {item["slug"] for item in record["items"]} == {"soup", "salad"}
    salad = next(item for item in record["items"] if item["slug"] == "salad")
    assert salad["before"] == {"categories": ["lunch"], "tags": ["spicy"], "tools": []}
    assert salad["suggested"] == {"categories": ["Dinner"], "tags": ["Quick"], "tools": []}


def test_no_preview_saved_outside_the_web_runner(monkeypatch, tmp_path, run_env):
    monkeypatch.delenv("COOKDEX_RUN_ID")
    library = _Library([_recipe("soup")])
    cat = library.categorizer(monkeypatch, tmp_path, dry_run=True)
    cat.run()
    assert not (cat.cache_file.parent / "categorize_previews").exists()


# ── Applying a reviewed preview ──────────────────────────────────────


def test_reviewed_apply_writes_only_what_was_reviewed_and_still_fits(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup"), _recipe("stew"), _recipe("pie"), _recipe("cake"), _recipe("tart")])
    library.categorizer(monkeypatch, tmp_path, dry_run=True, target_mode="missing-categories").run()
    prompts_after_preview = len(library.prompts)

    del library.recipes["pie"]  # deleted
    library.recipes["cake"]["name"] = "Carrot Cake"  # text changed
    library.recipes["tart"]["recipeCategory"] = [CATEGORIES[1]]  # filled in by someone
    library.recipes["soup"]["tags"] = [TAGS[1]]  # still missing a category: still a candidate
    library.recipes["new"] = _recipe("new")  # never previewed

    _apply_plan(monkeypatch, exclude=["stew"])
    cat = library.categorizer(monkeypatch, tmp_path, dry_run=False)
    cat.run()

    assert len(library.prompts) == prompts_after_preview, "applying a review must not ask the AI"
    assert [slug for slug, _ in library.patches] == ["soup"]
    soup = library.patches[0][1]
    assert [c["slug"] for c in soup["recipeCategory"]] == ["dinner"]
    assert [t["slug"] for t in soup["tags"]] == ["spicy", "quick"], "a tag added since the preview is kept"

    items = _items(run_env)
    assert items["soup"]["status"] == "applied"
    assert items["stew"]["error"] == "Not selected in the review."
    assert "deleted" in items["pie"]["error"]
    assert "changed after the preview" in items["cake"]["error"]
    assert "filled in after the preview" in items["tart"]["error"]
    assert "new" not in items
    assert cat.stats_snapshot()["skipped_since_preview"] == 3


def test_reviewed_recat_skips_recipes_whose_taxonomy_changed(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup", recipeCategory=[CATEGORIES[1]]), _recipe("stew", recipeCategory=[CATEGORIES[1]])])
    library.categorizer(monkeypatch, tmp_path, dry_run=True, replace_existing=True).run()
    library.recipes["stew"]["tags"] = [TAGS[1]]

    _apply_plan(monkeypatch)
    # The apply run's own options don't matter: the preview's mode is used.
    library.categorizer(monkeypatch, tmp_path, dry_run=False, replace_existing=False).run()

    assert [slug for slug, _ in library.patches] == ["soup"]
    assert [c["slug"] for c in library.patches[0][1]["recipeCategory"]] == ["dinner"], "re-categorize replaces"
    assert "changed after the preview" in _items(run_env)["stew"]["error"]


def test_reviewed_apply_drops_terms_deleted_since_the_preview(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup")])
    library.categorizer(monkeypatch, tmp_path, dry_run=True).run()
    library.tags = [TAGS[1]]  # "Quick" was deleted

    _apply_plan(monkeypatch)
    library.categorizer(monkeypatch, tmp_path, dry_run=False).run()

    assert library.patches[0][1].keys() == {"recipeCategory"}


def test_reviewed_apply_fails_clearly_when_the_preview_is_gone(monkeypatch, tmp_path, run_env, capsys):
    library = _Library([_recipe("soup")])
    _apply_plan(monkeypatch)
    with pytest.raises(SystemExit) as exc_info:
        library.categorizer(monkeypatch, tmp_path, dry_run=False).run()
    assert exc_info.value.code == 1
    assert "Run the preview again" in capsys.readouterr().out
    assert library.prompts == [] and library.patches == []


def test_load_preview_rejects_unsafe_run_ids(tmp_path):
    assert load_preview(tmp_path / "results_x.json", "../../etc/passwd") is None


# ── Task builder ─────────────────────────────────────────────────────


def _build(options):
    return TaskRegistry().build_execution("tag-categorize", options)


def test_builder_passes_reviewed_plan_and_skips_rules():
    plan = {"categorize": {"from_run": RUN_ID, "exclude": ["stew"]}}
    execution = _build({"dry_run": False, "method": "both", "plan": plan})
    assert json.loads(execution.env["COOKDEX_APPLY_PLAN"]) == plan
    assert "--skip-rules" in execution.command


def test_builder_without_plan_runs_both_layers():
    execution = _build({"dry_run": False, "method": "both"})
    assert "COOKDEX_APPLY_PLAN" not in execution.env
    assert "--skip-rules" not in execution.command


@pytest.mark.parametrize(
    "plan",
    [
        {"categorize": {"from_run": "../x"}},
        {"categorize": {"from_run": RUN_ID, "exclude": "stew"}},
        {"categorize": {"from_run": RUN_ID}, "names": {}},
        {"categorize": {"from_run": RUN_ID, "extra": 1}},
    ],
)
def test_builder_rejects_bad_plans(plan):
    with pytest.raises(ValueError):
        _build({"dry_run": False, "method": "ai", "plan": plan})


def test_builder_rejects_plan_for_rules_only():
    with pytest.raises(ValueError):
        _build({"dry_run": False, "method": "rules", "plan": {"categorize": {"from_run": RUN_ID}}})


def test_plan_for_other_jobs_changes_nothing(monkeypatch, tmp_path, run_env):
    library = _Library([_recipe("soup")])
    monkeypatch.setenv("COOKDEX_APPLY_PLAN", json.dumps({"names": {"rename": {}}}))
    library.categorizer(monkeypatch, tmp_path, dry_run=False).run()
    assert library.prompts == [] and library.patches == []
