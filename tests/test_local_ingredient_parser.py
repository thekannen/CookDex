from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import MagicMock

import requests

from cookdex import ingredient_parser
from cookdex.local_ingredient_parser import (
    FoodUnitMatcher,
    LocalIngredientParser,
    extract_quantity_from_string,
    normalize,
)
from cookdex.webui_server.tasks import TaskRegistry

FOODS = [
    {"id": "f-flour", "name": "flour", "pluralName": None, "aliases": [{"name": "all-purpose flour"}]},
    {"id": "f-stock", "name": "chicken stock", "aliases": []},
    {"id": "f-broth", "name": "vegetable broth"},
    {"id": "f-tomato", "name": "diced tomatoes"},
    {"id": "f-milk", "name": "milk"},
    {"id": "f-egg", "name": "egg", "pluralName": "eggs"},
    {"id": "f-soda", "name": "baking soda"},
]
UNITS = [
    {"id": "u-cup", "name": "cup", "pluralName": "cups", "abbreviation": "c", "aliases": []},
    {"id": "u-can", "name": "can", "pluralName": "cans"},
    {"id": "u-tbsp", "name": "tablespoon", "pluralName": "tablespoons", "abbreviation": "tbsp", "aliases": [{"name": "T"}]},
]


def _parser(foods=FOODS, units=UNITS):
    return LocalIngredientParser(FoodUnitMatcher(foods, units))


# -- matching -----------------------------------------------------------------


def test_normalize_matches_mealie():
    assert normalize("  Crème Fraîche ") == "creme fraiche"
    assert normalize("all-purpose flour") == "all purpose flour"
    # Mealie keeps quotes, which are reserved for quoted searches.
    assert normalize("Jack's \"Best\"") == "jack's \"best\""


def test_matcher_finds_names_plurals_aliases_and_close_spellings():
    matcher = FoodUnitMatcher(FOODS, UNITS)
    assert matcher.find_food("Eggs")["id"] == "f-egg"
    assert matcher.find_food("All-Purpose Flour")["id"] == "f-flour"
    assert matcher.find_food("chiken stock")["id"] == "f-stock"  # fuzzy, above 85
    assert matcher.find_food("chicken") is None  # too far from anything
    assert matcher.find_unit("Tbsp")["id"] == "u-tbsp"
    assert matcher.find_unit("t")["id"] == "u-tbsp"  # alias


def test_matcher_hands_the_library_mealie_custom_units():
    assert FoodUnitMatcher([], UNITS).custom_units() == {
        "cups": "cup",
        "c": "c",
        "cans": "can",
        "tablespoons": "tablespoon",
        "tbsp": "tbsp",
    }


def test_matcher_learns_foods_created_during_the_run():
    matcher = FoodUnitMatcher([], [])
    assert matcher.find_food("saffron") is None
    matcher.add_food({"id": "new-1", "name": "saffron"})
    assert matcher.find_food("saffron")["id"] == "new-1"


def test_quantity_from_string_handles_fractions():
    assert extract_quantity_from_string("1 1/2") == 1.5
    assert extract_quantity_from_string("½") == 0.5
    assert extract_quantity_from_string("1½") == 1.5
    assert extract_quantity_from_string("2.25") == 2.25
    assert extract_quantity_from_string("a few") == 0


# -- parsing ------------------------------------------------------------------


def test_parse_returns_mealie_shape_with_matched_food_and_unit():
    result = _parser().parse_one("2 cups flour")
    ingredient = result["ingredient"]
    assert ingredient["quantity"] == 2.0
    assert ingredient["unit"]["id"] == "u-cup"
    assert ingredient["food"]["id"] == "f-flour"
    assert ingredient["originalText"] == "2 cups flour"
    assert ingredient["referenceId"]
    assert result["input"] == "2 cups flour"
    assert result["confidence"]["average"] > 0.9


def test_parse_handles_fractions_ranges_and_cans():
    parser = _parser()
    assert parser.parse_one("1 1/2 cups milk")["ingredient"]["quantity"] == 1.5
    ranged = parser.parse_one("2-3 cups all-purpose flour")["ingredient"]
    assert (ranged["quantity"], ranged["food"]["id"]) == (2.0, "f-flour")
    can = parser.parse_one("1 (14 oz) can diced tomatoes, drained")["ingredient"]
    assert (can["quantity"], can["unit"]["id"], can["food"]["id"]) == (1.0, "u-can", "f-tomato")
    assert can["note"] == "drained"


def test_parse_leaves_unknown_foods_as_new_names():
    ingredient = _parser().parse_one("200 g Mehl")["ingredient"]
    assert ingredient["quantity"] == 200.0
    assert ingredient["food"] == {"name": "Mehl"}  # created later, only on a real run
    assert "id" not in ingredient["unit"]  # unmatched unit; CookDex drops it before patching


def test_parse_turns_alternatives_into_substitutions_like_mealie():
    ingredient = _parser().parse_one("1 cup chicken stock or vegetable broth")["ingredient"]
    assert ingredient["food"]["id"] == "f-stock"
    assert ingredient["substitutions"] == [{"substituteFoodId": "f-broth", "note": None}]


def test_unit_and_food_split_from_one_food_are_joined_back():
    ingredient = {"food": {"name": "soda"}, "unit": {"name": "baking"}}
    _parser()._match(ingredient)
    assert ingredient["food"]["id"] == "f-soda"
    assert ingredient["unit"] is None


def test_parse_never_drops_a_line():
    lines = ["2 cups flour", "???", "Salt", "1 Prise Salz", "-"]
    results = _parser().parse(lines)
    assert [r["input"] for r in results] == lines
    assert results[1]["confidence"]["average"] == 0  # nothing found: falls through to the next strategy


# -- the run ------------------------------------------------------------------


def _config(tmp_path, strategies=("local", "nlp", "brute")):
    return ingredient_parser.ParserRunConfig(
        confidence_threshold=0.7,
        parser_strategies=strategies,
        force_parser=None,
        page_size=50,
        delay_seconds=0,
        timeout_seconds=5,
        request_retries=0,
        request_backoff_seconds=0,
        max_recipes=None,
        after_slug=None,
        dry_run=False,
        output_dir=tmp_path,
        low_confidence_filename="review.json",
        success_log_filename="success.log",
        scan_cache_filename="cache.json",
        recheck_review=False,
        no_cache=True,
        review_tag_name="Parser: Needs Review",
    )


def _recipe(slug, *lines):
    return {
        "slug": slug,
        "name": slug,
        "hasParsedIngredients": False,
        "tags": [],
        "recipeIngredient": [{"note": line, "originalText": line, "food": None, "referenceId": f"{slug}-{i}"} for i, line in enumerate(lines)],
    }


def _client(*recipes):
    client = MagicMock()
    client.get_organizer_items.return_value = [{"id": "review-id", "name": "Parser: Needs Review"}]
    client.get_recipes.return_value = list(recipes)
    client.list_foods.return_value = list(FOODS)
    client.list_units.return_value = list(UNITS)
    return client


def _mealie_result(food="flour", conf=0.95):
    return {"confidence": {"average": conf}, "ingredient": {"quantity": 1, "food": {"id": "f-flour", "name": food}, "note": ""}}


def test_run_parses_locally_without_asking_mealie(tmp_path):
    client = _client(_recipe("r1", "2 cups flour", "3 eggs", "1 cup milk"))
    summary = ingredient_parser.run_parser(client, _config(tmp_path))

    assert summary.parsed_successfully == 1
    client.parse_ingredients.assert_not_called()
    slug, patched = client.patch_recipe_ingredients.call_args.args
    assert slug == "r1"
    assert [i["food"]["id"] for i in patched] == ["f-flour", "f-egg", "f-milk"]
    assert [i["referenceId"] for i in patched] == ["r1-0", "r1-1", "r1-2"]  # original ids kept
    assert client.list_foods.call_count == 1  # loaded once per run, not per recipe


def test_run_falls_back_to_mealie_when_local_confidence_is_low(tmp_path):
    client = _client(_recipe("r1", "???"))
    client.parse_ingredients.return_value = [_mealie_result()]
    summary = ingredient_parser.run_parser(client, _config(tmp_path))

    assert summary.parsed_successfully == 1
    # Mealie's nlp parser would repeat the local answer, so the next one is brute.
    client.parse_ingredients.assert_called_once_with(["???"], strategy="brute")


def test_low_local_confidence_while_mealie_is_down_is_retried_not_reviewed(tmp_path):
    client = _client(_recipe("r1", "???"))
    client.parse_ingredients.side_effect = requests.exceptions.ReadTimeout("slow")
    summary = ingredient_parser.run_parser(client, _config(tmp_path))

    review = json.loads((tmp_path / "review.json").read_text())[0]
    assert review["reason"] == "mealie_unreachable"
    assert summary.tagged_for_review == 0
    client.patch_recipe.assert_not_called()


def test_local_only_low_confidence_goes_to_review(tmp_path):
    client = _client(_recipe("r1", "???"))
    summary = ingredient_parser.run_parser(client, _config(tmp_path, strategies=("local",)))

    review = json.loads((tmp_path / "review.json").read_text())[0]
    assert review["reason"] == "parser_failed_threshold"
    assert summary.tagged_for_review == 1


def test_run_uses_mealie_when_foods_cannot_be_loaded(tmp_path, capsys):
    client = _client(_recipe("r1", "2 cups flour"))
    client.list_foods.side_effect = requests.exceptions.ConnectionError("refused")
    client.parse_ingredients.return_value = [_mealie_result()]
    summary = ingredient_parser.run_parser(client, _config(tmp_path))

    assert summary.parsed_successfully == 1
    assert "Parsing in CookDex is off for this run" in capsys.readouterr().out
    client.parse_ingredients.assert_called_once_with(["2 cups flour"], strategy="nlp")


def test_a_local_parser_error_falls_back_to_mealie(tmp_path, monkeypatch):
    broken = MagicMock()
    broken.parse.side_effect = ValueError("boom")
    monkeypatch.setattr(ingredient_parser, "_load_local_parser", lambda client: broken)
    client = _client(_recipe("r1", "2 cups flour"))
    client.parse_ingredients.return_value = [_mealie_result()]
    summary = ingredient_parser.run_parser(client, _config(tmp_path))

    assert summary.parsed_successfully == 1
    client.parse_ingredients.assert_called_once_with(["2 cups flour"], strategy="brute")


def test_food_created_for_one_recipe_is_matched_in_the_next(tmp_path):
    client = _client(_recipe("r1", "1 cup quinoa"), _recipe("r2", "2 cups quinoa"))
    client.create_food.return_value = {"id": "f-quinoa", "name": "quinoa"}
    ingredient_parser.run_parser(client, _config(tmp_path))

    assert client.create_food.call_count == 1
    second = client.patch_recipe_ingredients.call_args_list[1].args[1]
    assert second[0]["food"] == {"id": "f-quinoa", "name": "quinoa"}


def test_dry_run_with_local_parser_creates_and_patches_nothing(tmp_path):
    client = _client(_recipe("r1", "1 cup quinoa", "2 cups flour"))
    summary = ingredient_parser.run_parser(client, replace(_config(tmp_path), dry_run=True))

    assert summary.parsed_successfully == 1
    assert summary.foods_planned == 1
    client.create_food.assert_not_called()
    client.patch_recipe_ingredients.assert_not_called()


# -- the job option -------------------------------------------------------------


def _parse_cmd(options):
    return TaskRegistry().build_execution("ingredient-parse", options).command


def test_job_option_puts_the_local_strategy_first_by_default():
    assert "--parsers" not in _parse_cmd({"parse_locally": False})
    cmd = _parse_cmd({})
    assert cmd[cmd.index("--parsers") + 1] == "local"
    cmd = _parse_cmd({"parse_locally": True, "parsers": "nlp,openai"})
    assert cmd[cmd.index("--parsers") + 1] == "local,nlp,openai"


def test_local_strategy_keeps_mealie_fallbacks_behind_it():
    assert ingredient_parser._parse_parser_strategies("local", None) == ("local", "nlp", "brute", "openai")
