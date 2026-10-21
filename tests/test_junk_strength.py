"""Junk filter: about, contact, policy, trip and story pages, and strength levels."""
from __future__ import annotations

import pytest

from cookdex.recipe_junk_filter import (
    STRENGTHS,
    RecipeJunkFilter,
    _auto_delete,
    _classify_content,
    _classify_name,
    _content_facts,
    _inspect,
    _measured,
    _protected,
)
from tests.fixtures.junk_corpus import ABOUT_PAGES, CORPUS, STORY_POSTS, TRICKY_RECIPES, TRIP_POSTS, page

from tests.fixtures.junk_corpus_holdout import CORPUS as HOLDOUT
from tests.fixtures.junk_corpus_holdout2 import CORPUS as HOLDOUT2

# Pages that aren't recipes, by any of the content rules.
PAGE_CODES = {"about_page", "travel_post", "story_post", "no_recipe"}


def verdict(recipe: dict, strength: str) -> str:
    """What the junk filter does with one page: delete, review or keep."""
    fact = _inspect({**recipe, "id": "x"})
    content = fact["content"]
    name_code, _ = _classify_name(fact["name"], recipe["slug"])
    content_code, _ = _classify_content(content, fact["name"], recipe["slug"])
    instruction_code = fact["instruction_code"] or None
    if not fact["has_ingredients"] and not (fact["has_instructions"] and not instruction_code):
        return "delete"
    if _auto_delete(strength, content_code=content_code, name_code=name_code,
                    instruction_code=instruction_code, facts=content):
        return "delete"
    if name_code or content_code or instruction_code or fact["scrape_code"]:
        return "review"
    return "keep"


def tally(corpus, strength):
    out = {"junk": {"delete": 0, "review": 0, "keep": 0}, "recipe": {"delete": 0, "review": 0, "keep": 0}}
    for recipe, label in corpus:
        out[label][verdict(recipe, strength)] += 1
    return out


# ── Single rules ──────────────────────────────────────────────────────


@pytest.mark.parametrize("line", ["2 cups flour", "1/2 tsp salt", "½ cup sugar", "a pinch of salt", "Salt, 1 tsp",
                                  "3 cloves garlic", "one large onion", "8 oz cream cheese"])
def test_measured_ingredient_lines(line):
    assert _measured({"note": line})


@pytest.mark.parametrize("line", ["salt", "olive oil", "Day 1: Florence", "Follow me on Instagram", "Ramen at Ichiran"])
def test_unmeasured_lines(line):
    assert not _measured({"note": line})


def test_parsed_quantity_or_unit_counts_as_measured():
    assert _measured({"quantity": 2, "food": {"name": "flour"}, "note": ""})
    assert _measured({"quantity": 0, "unit": {"name": "cup"}, "note": ""})


@pytest.mark.parametrize("recipe", ABOUT_PAGES, ids=lambda r: r["slug"])
def test_about_contact_and_policy_pages_are_detected(recipe):
    code, reason = _classify_content(_content_facts(recipe), recipe["name"], recipe["slug"])
    assert code == "about_page", reason


@pytest.mark.parametrize("recipe", TRIP_POSTS, ids=lambda r: r["slug"])
def test_trip_posts_are_detected(recipe):
    code, reason = _classify_content(_content_facts(recipe), recipe["name"], recipe["slug"])
    assert code in PAGE_CODES, reason


@pytest.mark.parametrize("recipe", STORY_POSTS, ids=lambda r: r["slug"])
def test_story_posts_are_detected(recipe):
    code, reason = _classify_content(_content_facts(recipe), recipe["name"], recipe["slug"])
    assert code in PAGE_CODES, reason


@pytest.mark.parametrize("recipe", TRICKY_RECIPES, ids=lambda r: r["slug"])
def test_real_recipes_never_look_like_pages(recipe):
    code, reason = _classify_content(_content_facts(recipe), recipe["name"], recipe["slug"])
    assert code is None, reason


def test_travel_words_in_a_title_mean_nothing_alone():
    recipe = page("Tuscan Chicken", "tuscan-chicken", ingredients=["chicken", "spinach", "cream"],
                  steps=["Sear the chicken in a skillet, add the cream and spinach and simmer."])
    assert _protected(_content_facts(recipe))


def test_prose_instructions_with_an_ingredient_list_are_a_recipe():
    recipe = page("Grandpa's Stew", "grandpas-stew", ingredients=["beef", "carrots", "potatoes", "onion"], steps=[
        "Grandpa always told us to brown the beef first, then we would add the vegetables and let the pot simmer "
        "for hours while we played cards in the kitchen. I still make it his way every winter for my own family.",
    ])
    facts = _content_facts(recipe)
    assert _protected(facts)
    assert _classify_content(facts, recipe["name"], recipe["slug"]) == (None, "")


def test_short_recipes_are_kept():
    recipe = page("Lemon Water", "lemon-water", ingredients=["1 lemon", "2 cups water"], steps=["Squeeze the lemon into the water."])
    assert all(verdict(recipe, strength) == "keep" for strength in STRENGTHS)


def test_existing_rules_still_apply():
    assert _classify_name("Privacy", "privacy-policy")[0] == "utility"
    assert _classify_name("Top 10 Desserts", "top-10-desserts")[0] == "listicle"
    empty = page("About Us", "about-us", steps=[])
    assert all(verdict(empty, strength) == "delete" for strength in STRENGTHS)


# ── Strength levels ───────────────────────────────────────────────────


def test_cautious_deletes_only_empty_pages():
    content_page = ABOUT_PAGES[0]
    assert verdict(content_page, "cautious") == "review"
    assert verdict(content_page, "balanced") == "delete"


def test_strong_deletes_name_matches_with_almost_no_recipe():
    roundup = page("Top 10 Summer Desserts", "top-10-summer-desserts", steps=[
        "Summer is here and these are the desserts everyone in my family asks for. Click through for each one.",
    ])
    assert verdict(roundup, "cautious") == "review"
    assert verdict(roundup, "balanced") == "review"
    assert verdict(roundup, "strong") == "delete"


def test_strong_keeps_name_matches_that_are_real_recipes():
    recipe = page("How to Make Rice", "how-to-make-rice", ingredients=["1 cup rice", "2 cups water"],
                  steps=["Rinse the rice.", "Simmer covered for 18 minutes."])
    assert verdict(recipe, "strong") == "review"


@pytest.mark.parametrize("strength", STRENGTHS)
def test_no_real_recipe_is_deleted_at_any_level(strength):
    counts = tally(CORPUS, strength)
    assert counts["recipe"]["delete"] == 0


# Two sets written by someone who hadn't seen the rules.
@pytest.mark.parametrize("strength", STRENGTHS)
@pytest.mark.parametrize("corpus", [HOLDOUT, HOLDOUT2], ids=["holdout", "holdout2"])
def test_no_held_out_recipe_is_deleted_at_any_level(corpus, strength):
    assert tally(corpus, strength)["recipe"]["delete"] == 0


def test_held_out_pages_are_mostly_caught():
    for corpus in (HOLDOUT, HOLDOUT2):
        junk = sum(1 for _, label in corpus if label == "junk")
        strong = tally(corpus, "strong")["junk"]
        assert strong["delete"] >= 0.9 * junk
        assert strong["keep"] <= 2  # missed entirely: neither deleted nor reviewed


def test_amounts_written_into_the_steps_make_it_a_recipe():
    recipe = page("Cold Brew", "cold-brew", ingredients=["coarse ground coffee", "cold water"],
                  steps=["Steep 1 cup grounds in 4 cups water in the fridge for 12 hours, then strain over ice."])
    assert all(verdict(recipe, strength) == "keep" for strength in STRENGTHS)


def test_levels_catch_more_as_they_get_stronger():
    deleted = {strength: tally(CORPUS, strength)["junk"]["delete"] for strength in STRENGTHS}
    assert deleted["cautious"] == 0
    assert deleted["cautious"] < deleted["balanced"] <= deleted["strong"]
    junk = len([1 for _, label in CORPUS if label == "junk"])
    assert deleted["strong"] == junk
    # Whatever isn't deleted is still shown for review: nothing is missed.
    for strength in STRENGTHS:
        assert tally(CORPUS, strength)["junk"]["keep"] == 0


# ── Through the job ───────────────────────────────────────────────────


class FakeMealie:
    def __init__(self, recipes):
        self.recipes = {r["slug"]: {**r, "id": f"id-{r['slug']}"} for r in recipes}
        self.deleted = []

    def get_recipes(self):
        return [{"slug": slug, "name": r["name"]} for slug, r in self.recipes.items()]

    def get_recipe(self, slug):
        return self.recipes[slug]

    def delete_recipe(self, slug):
        self.deleted.append(slug)

    def recipe_export_formats(self):
        return {}

    def get_recipe_image(self, recipe_id):
        return None


@pytest.mark.parametrize("strength,expected", [
    ("cautious", set()),
    ("balanced", {"our-week-in-tuscany", "about"}),
    ("strong", {"our-week-in-tuscany", "about"}),
])
def test_job_deletes_by_strength_and_keeps_copies(tmp_path, strength, expected):
    from cookdex.deleted_recipes import RecipeArchive

    pages = [TRIP_POSTS[0], ABOUT_PAGES[0], TRICKY_RECIPES[0], TRICKY_RECIPES[2]]
    mealie = FakeMealie(pages)
    archive = RecipeArchive(tmp_path / "copies", mealie)
    report = RecipeJunkFilter(mealie, apply=True, dry_run=False, report_file=tmp_path / "r.json",
                              archive=archive, strength=strength).run()
    assert set(mealie.deleted) == expected
    assert {copy["slug"] for copy in archive.list()} == expected
    assert report["summary"]["strength"] == strength
    review = {item["slug"] for item in report["review_candidates"]}
    assert review == {"our-week-in-tuscany", "about"} - expected
    assert "tuscan-chicken" not in mealie.deleted and "road-trip-trail-mix" not in mealie.deleted


def test_unknown_strength_is_refused():
    with pytest.raises(ValueError):
        RecipeJunkFilter(FakeMealie([]), strength="nuclear")


def test_strength_reaches_the_job():
    from cookdex.data_maintenance import StageRuntimeOptions, stage_command
    from cookdex.webui_server.tasks import TaskRegistry

    registry = TaskRegistry()
    alone = registry.build_execution("clean-recipes", {"run_dedup": False, "run_names": False, "strength": "strong"})
    assert alone.command[-2:] == ["--strength", "strong"]
    together = registry.build_execution("clean-recipes", {"strength": "balanced"})
    assert together.command[-2:] == ["--junk-strength", "balanced"]
    with pytest.raises(ValueError):
        registry.build_execution("clean-recipes", {"strength": "nuclear"})
    cmd = stage_command("junk", apply_cleanups=True, stage_options=StageRuntimeOptions(junk_strength="strong"))
    assert cmd[-2:] == ["--strength", "strong"]
