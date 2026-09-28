from __future__ import annotations

import json
from unittest.mock import MagicMock

import requests

from cookdex import ingredient_parser
from cookdex.ingredient_parser import ReviewTagManager


def test_build_candidate_slugs_prefers_has_parsed_flag_when_present():
    recipes = [
        {"slug": "already", "hasParsedIngredients": True, "updatedAt": "2026-01-01T00:00:00Z"},
        {"slug": "todo", "hasParsedIngredients": False, "updatedAt": "2026-01-02T00:00:00Z"},
    ]

    slugs, skipped_cached, missing_flag, updated = ingredient_parser._build_candidate_slugs(
        recipes,
        cache={},
        recheck_review=False,
    )

    assert slugs == ["todo"]
    assert skipped_cached == 0
    assert missing_flag == 0
    assert updated["already"] == "2026-01-01T00:00:00Z"
    assert updated["todo"] == "2026-01-02T00:00:00Z"


def test_build_candidate_slugs_skips_unchanged_cached_recipe_when_flag_missing():
    recipes = [{"slug": "cached", "updatedAt": "2026-01-03T00:00:00Z"}]
    cache = {"cached": {"updated_at": "2026-01-03T00:00:00Z", "status": "already_parsed", "checked_at": "x"}}

    slugs, skipped_cached, missing_flag, _ = ingredient_parser._build_candidate_slugs(
        recipes,
        cache=cache,
        recheck_review=False,
    )

    assert slugs == []
    assert skipped_cached == 1
    assert missing_flag == 1


def test_build_candidate_slugs_recheck_review_overrides_cache_skip():
    recipes = [{"slug": "reviewed", "updatedAt": "2026-01-04T00:00:00Z"}]
    cache = {"reviewed": {"updated_at": "2026-01-04T00:00:00Z", "status": "needs_review", "checked_at": "x"}}

    slugs_default, skipped_default, _, _ = ingredient_parser._build_candidate_slugs(
        recipes,
        cache=cache,
        recheck_review=False,
    )
    slugs_recheck, skipped_recheck, _, _ = ingredient_parser._build_candidate_slugs(
        recipes,
        cache=cache,
        recheck_review=True,
    )

    assert slugs_default == []
    assert skipped_default == 1
    assert slugs_recheck == ["reviewed"]
    assert skipped_recheck == 0


def test_build_candidate_slugs_skips_planned_parse_from_dry_run():
    recipes = [{"slug": "dry-ran", "updatedAt": "2026-01-06T00:00:00Z"}]
    cache = {"dry-ran": {"updated_at": "2026-01-06T00:00:00Z", "status": "planned_parse", "checked_at": "x"}}

    slugs, skipped_cached, missing_flag, _ = ingredient_parser._build_candidate_slugs(
        recipes,
        cache=cache,
        recheck_review=False,
    )

    assert slugs == []
    assert skipped_cached == 1
    assert missing_flag == 1

    # Applying for real parses what the preview planned.
    slugs, skipped_cached, _, _ = ingredient_parser._build_candidate_slugs(
        recipes, cache=cache, recheck_review=False, skip_planned=False
    )
    assert slugs == ["dry-ran"]
    assert skipped_cached == 0


def test_build_candidate_slugs_requeues_when_recipe_was_updated():
    recipes = [{"slug": "changed", "updatedAt": "2026-01-05T00:00:00Z"}]
    cache = {"changed": {"updated_at": "2026-01-01T00:00:00Z", "status": "already_parsed", "checked_at": "x"}}

    slugs, skipped_cached, missing_flag, _ = ingredient_parser._build_candidate_slugs(
        recipes,
        cache=cache,
        recheck_review=False,
    )

    assert slugs == ["changed"]
    assert skipped_cached == 0
    assert missing_flag == 1


# ── ReviewTagManager tests ───────────────────────────────────────────


def _mock_client(existing_tags=None, patch_side_effect=None):
    client = MagicMock()
    client.get_organizer_items.return_value = existing_tags or []
    client.create_organizer_item.return_value = {"id": "new-tag-id", "name": "Parser: Needs Review"}
    if patch_side_effect:
        client.patch_recipe.side_effect = patch_side_effect
    else:
        client.patch_recipe.return_value = {}
    return client


def test_review_tag_manager_creates_tag_when_not_found():
    client = _mock_client(existing_tags=[])
    mgr = ReviewTagManager(client, "Parser: Needs Review", dry_run=False)
    result = mgr.ensure_tagged("my-recipe", [])
    assert result is True
    client.create_organizer_item.assert_called_once_with("tags", {"name": "Parser: Needs Review"})
    client.patch_recipe.assert_called_once()
    call_args = client.patch_recipe.call_args
    assert call_args[0][0] == "my-recipe"
    tags_payload = call_args[0][1]["tags"]
    assert any(t["id"] == "new-tag-id" for t in tags_payload)


def test_review_tag_manager_reuses_existing_tag():
    client = _mock_client(existing_tags=[{"id": "existing-id", "name": "Parser: Needs Review"}])
    mgr = ReviewTagManager(client, "Parser: Needs Review", dry_run=False)
    result = mgr.ensure_tagged("my-recipe", [])
    assert result is True
    client.create_organizer_item.assert_not_called()
    call_args = client.patch_recipe.call_args
    tags_payload = call_args[0][1]["tags"]
    assert any(t["id"] == "existing-id" for t in tags_payload)


def test_ensure_tagged_preserves_existing_tags():
    client = _mock_client(existing_tags=[{"id": "review-id", "name": "Parser: Needs Review"}])
    mgr = ReviewTagManager(client, "Parser: Needs Review", dry_run=False)
    existing_recipe_tags = [{"id": "aaa", "name": "Dinner"}, {"id": "bbb", "name": "Quick"}]
    mgr.ensure_tagged("my-recipe", existing_recipe_tags)
    call_args = client.patch_recipe.call_args
    tags_payload = call_args[0][1]["tags"]
    tag_ids = {t["id"] for t in tags_payload}
    assert tag_ids == {"aaa", "bbb", "review-id"}


def test_ensure_tagged_noop_when_already_present():
    client = _mock_client(existing_tags=[{"id": "review-id", "name": "Parser: Needs Review"}])
    mgr = ReviewTagManager(client, "Parser: Needs Review", dry_run=False)
    existing_recipe_tags = [{"id": "review-id", "name": "Parser: Needs Review"}, {"id": "aaa", "name": "Dinner"}]
    result = mgr.ensure_tagged("my-recipe", existing_recipe_tags)
    assert result is False
    client.patch_recipe.assert_not_called()


def test_ensure_untagged_removes_review_tag():
    client = _mock_client(existing_tags=[{"id": "review-id", "name": "Parser: Needs Review"}])
    mgr = ReviewTagManager(client, "Parser: Needs Review", dry_run=False)
    existing_recipe_tags = [{"id": "review-id", "name": "Parser: Needs Review"}, {"id": "aaa", "name": "Dinner"}]
    result = mgr.ensure_untagged("my-recipe", existing_recipe_tags)
    assert result is True
    call_args = client.patch_recipe.call_args
    tags_payload = call_args[0][1]["tags"]
    tag_ids = {t["id"] for t in tags_payload}
    assert tag_ids == {"aaa"}


def test_ensure_untagged_noop_when_not_present():
    client = _mock_client(existing_tags=[{"id": "review-id", "name": "Parser: Needs Review"}])
    mgr = ReviewTagManager(client, "Parser: Needs Review", dry_run=False)
    existing_recipe_tags = [{"id": "aaa", "name": "Dinner"}]
    result = mgr.ensure_untagged("my-recipe", existing_recipe_tags)
    assert result is False
    client.patch_recipe.assert_not_called()


def test_dry_run_skips_patch():
    client = _mock_client(existing_tags=[{"id": "review-id", "name": "Parser: Needs Review"}])
    mgr = ReviewTagManager(client, "Parser: Needs Review", dry_run=True)
    result = mgr.ensure_tagged("my-recipe", [])
    assert result is True
    client.patch_recipe.assert_not_called()


def test_review_tag_name_case_insensitive_match():
    client = _mock_client(existing_tags=[{"id": "review-id", "name": "parser: needs review"}])
    mgr = ReviewTagManager(client, "Parser: Needs Review", dry_run=False)
    mgr.ensure_tagged("my-recipe", [])
    client.create_organizer_item.assert_not_called()
    call_args = client.patch_recipe.call_args
    tags_payload = call_args[0][1]["tags"]
    assert any(t["id"] == "review-id" for t in tags_payload)


# ── Ingredient metadata carry-over (issue #47) ──────────────────────


def _raw_ing(text, ref=None, title=None, substitutions=None):
    return {
        "referenceId": ref,
        "title": title,
        "note": text,
        "originalText": text,
        "food": None,
        "unit": None,
        "quantity": 0,
        "substitutions": substitutions or [],
    }


def _parsed(food_name, qty=1.0):
    return {
        "input": food_name,
        "confidence": {"average": 0.95},
        "ingredient": {
            "quantity": qty,
            "unit": None,
            "food": {"id": f"food-{food_name}", "name": food_name},
            "note": "",
            "referenceId": f"parser-ref-{food_name}",
            "title": None,
            "display": food_name,
        },
    }


_SUB = {
    "substituteFoodId": "sub-food-id",
    "note": "or oat milk",
    "substituteFood": {"id": "sub-food-id", "name": "oat milk", "pluralName": None},
}


def _carry(recipe, parsed_block):
    entries = ingredient_parser.extract_raw_entries(recipe)
    lines, line_idx, _ = ingredient_parser.sanitize_raw_entries(entries)
    normalized, _, _, positions = ingredient_parser.normalize_parsed_block_indexed(MagicMock(), parsed_block)
    return lines, ingredient_parser.carry_ingredient_metadata(
        entries, line_idx, len(parsed_block), positions, normalized, recipe
    )


def test_extract_raw_lines_unchanged_by_entry_tracking():
    recipe = {"recipeIngredient": [_raw_ing("1 cup milk"), _raw_ing("", title="Topping"), _raw_ing("2 eggs")]}
    assert ingredient_parser.extract_raw_lines(recipe) == ["1 cup milk", "2 eggs"]
    entries = ingredient_parser.extract_raw_entries(recipe)
    assert [text for text, _ in entries] == ["1 cup milk", "", "2 eggs"]
    assert entries[1][1]["title"] == "Topping"


def test_sanitize_raw_entries_matches_sanitize_raw_lines():
    entries = [("For the dough:", {}), ("", {}), ("2 cups flour", {}), ("1  cup milk", {})]
    lines, indices, dropped = ingredient_parser.sanitize_raw_entries(entries)
    assert (lines, dropped) == ingredient_parser.sanitize_raw_lines(["For the dough:", "2 cups flour", "1  cup milk"])
    assert indices == [2, 3]


def test_carry_metadata_aligned_one_to_one():
    recipe = {
        "recipeIngredient": [
            _raw_ing("2 cups flour", ref="r1", title="Dough"),
            _raw_ing("1 cup milk", ref="r2", substitutions=[_SUB]),
        ],
        "recipeInstructions": [{"text": "Mix", "ingredientReferences": [{"referenceId": "r2"}]}],
    }
    _, (merged, problems) = _carry(recipe, [_parsed("flour"), _parsed("milk")])
    assert problems == []
    assert [i["referenceId"] for i in merged] == ["r1", "r2"]
    assert merged[0]["title"] == "Dough"
    assert merged[1]["title"] is None
    assert merged[1]["substitutions"] == [{"substituteFoodId": "sub-food-id", "note": "or oat milk"}]
    assert "substitutions" not in merged[0]


def test_carry_metadata_moves_title_from_dropped_header_line():
    recipe = {
        "recipeIngredient": [
            _raw_ing("For the dough:", ref="h1", title="Dough"),
            _raw_ing("2 cups flour", ref="r1"),
            _raw_ing("", ref="h2", title="Topping"),
            _raw_ing("1 tsp salt", ref="r2"),
        ],
    }
    lines, (merged, problems) = _carry(recipe, [_parsed("flour"), _parsed("salt")])
    assert lines == ["2 cups flour", "1 tsp salt"]
    assert problems == []
    assert [(i["referenceId"], i["title"]) for i in merged] == [("r1", "Dough"), ("r2", "Topping")]


def test_carry_metadata_survivor_title_wins_over_dropped_title():
    recipe = {
        "recipeIngredient": [
            _raw_ing("For the dough:", ref="h1", title="Dough"),
            _raw_ing("2 cups flour", ref="r1", title="Filling"),
        ],
    }
    _, (merged, problems) = _carry(recipe, [_parsed("flour")])
    assert problems == []
    assert merged[0]["title"] == "Filling"


def test_carry_metadata_moves_title_past_blank_parse_result():
    recipe = {"recipeIngredient": [_raw_ing("some garnish", ref="r1", title="Garnish"), _raw_ing("1 lemon", ref="r2")]}
    blank = {"confidence": {"average": 1.0}, "ingredient": {"quantity": 0, "note": "", "food": None, "unit": None}}
    _, (merged, problems) = _carry(recipe, [blank, _parsed("lemon")])
    assert problems == []
    assert len(merged) == 1
    assert (merged[0]["referenceId"], merged[0]["title"]) == ("r2", "Garnish")


def test_carry_metadata_flags_dropped_step_reference_and_substitution():
    recipe = {
        "recipeIngredient": [
            _raw_ing("For serving:", ref="h1", substitutions=[_SUB]),
            _raw_ing("2 cups flour", ref="r1"),
        ],
        "recipeInstructions": [{"text": "Serve", "ingredientReferences": [{"referenceId": "h1"}]}],
    }
    _, (_, problems) = _carry(recipe, [_parsed("flour")])
    assert len(problems) == 2
    assert "linked from a step" in problems[0]
    assert "substitutions" in problems[1]


def test_carry_metadata_ignores_dropped_unreferenced_reference_id():
    recipe = {
        "recipeIngredient": [_raw_ing("For the dough:", ref="h1"), _raw_ing("2 cups flour", ref="r1")],
        "recipeInstructions": [{"text": "Mix", "ingredientReferences": [{"referenceId": "r1"}]}],
    }
    _, (merged, problems) = _carry(recipe, [_parsed("flour")])
    assert problems == []
    assert merged[0]["referenceId"] == "r1"


def test_carry_metadata_flags_misaligned_parser_output_only_when_metadata_present():
    plain = {"recipeIngredient": [_raw_ing("2 cups flour", ref="r1"), _raw_ing("1 cup milk", ref="r2")]}
    _, (merged, problems) = _carry(plain, [_parsed("flour")])
    assert problems == []
    assert merged[0]["referenceId"] == "parser-ref-flour"

    titled = {"recipeIngredient": [_raw_ing("2 cups flour", ref="r1", title="Dough"), _raw_ing("1 cup milk", ref="r2")]}
    _, (_, problems) = _carry(titled, [_parsed("flour")])
    assert problems and "cannot align" in problems[0]
    assert "section title" in problems[1]


def test_carry_metadata_noop_for_string_ingredients():
    recipe = {"recipeIngredient": ["2 cups flour", "1 cup milk"]}
    _, (merged, problems) = _carry(recipe, [_parsed("flour"), _parsed("milk")])
    assert problems == []
    assert [i["referenceId"] for i in merged] == ["parser-ref-flour", "parser-ref-milk"]


def test_substitutions_payload_falls_back_to_substitute_food_id():
    source = {"substitutions": [{"note": "n", "substituteFood": {"id": "fid"}}, {"note": None}, "junk"]}
    assert ingredient_parser._substitutions_payload(source) == [{"substituteFoodId": "fid", "note": "n"}]


def _run_config(tmp_path, dry_run=False):
    return ingredient_parser.ParserRunConfig(
        confidence_threshold=0.7,
        parser_strategies=("nlp",),
        force_parser=None,
        page_size=50,
        delay_seconds=0,
        timeout_seconds=5,
        request_retries=0,
        request_backoff_seconds=0,
        max_recipes=None,
        after_slug=None,
        dry_run=dry_run,
        output_dir=tmp_path,
        low_confidence_filename="review.json",
        success_log_filename="success.log",
        scan_cache_filename="cache.json",
        recheck_review=False,
        no_cache=True,
        review_tag_name="Parser: Needs Review",
    )


def _run_client(recipe, parsed_block):
    client = _mock_client(existing_tags=[{"id": "review-id", "name": "Parser: Needs Review"}])
    client.get_recipes.return_value = [recipe]
    client.parse_ingredients.return_value = parsed_block
    return client


def test_run_parser_patches_with_carried_metadata(tmp_path):
    recipe = {
        "slug": "m47",
        "name": "M47",
        "hasParsedIngredients": False,
        "recipeIngredient": [
            _raw_ing("For the dough:", ref="h1", title="Dough"),
            _raw_ing("2 cups flour", ref="r1"),
            _raw_ing("1 cup milk", ref="r2", substitutions=[_SUB]),
        ],
        "recipeInstructions": [{"text": "Mix", "ingredientReferences": [{"referenceId": "r2"}]}],
    }
    client = _run_client(recipe, [_parsed("flour"), _parsed("milk")])
    summary = ingredient_parser.run_parser(client, _run_config(tmp_path))
    assert summary.parsed_successfully == 1
    client.parse_ingredients.assert_called_once_with(["2 cups flour", "1 cup milk"], strategy="nlp")
    slug, patched = client.patch_recipe_ingredients.call_args[0]
    assert slug == "m47"
    assert [(i["referenceId"], i["title"]) for i in patched] == [("r1", "Dough"), ("r2", None)]
    assert patched[1]["substitutions"] == [{"substituteFoodId": "sub-food-id", "note": "or oat milk"}]


def test_run_parser_sends_recipe_to_review_when_linked_line_dropped(tmp_path):
    recipe = {
        "slug": "m47-drop",
        "name": "M47 drop",
        "hasParsedIngredients": False,
        "tags": [],
        "recipeIngredient": [_raw_ing("For serving:", ref="h1"), _raw_ing("2 cups flour", ref="r1")],
        "recipeInstructions": [{"text": "Serve", "ingredientReferences": [{"referenceId": "h1"}]}],
    }
    for dry_run in (False, True):
        client = _run_client(recipe, [_parsed("flour")])
        summary = ingredient_parser.run_parser(client, _run_config(tmp_path, dry_run=dry_run))
        assert summary.parsed_successfully == 0
        assert summary.requires_review == 1
        assert summary.tagged_for_review == 1
        client.patch_recipe_ingredients.assert_not_called()
        review = json.loads((tmp_path / "review.json").read_text())[0]
        assert review["reason"] == "ingredient_metadata_would_be_lost"
        assert "linked from a step" in review["details"][0]


def _new_food_parsed(food_name):
    parsed = _parsed(food_name)
    parsed["ingredient"]["food"] = {"id": None, "name": food_name}
    return parsed


def _new_food_recipe(slug):
    return {
        "slug": slug,
        "name": slug,
        "hasParsedIngredients": False,
        "tags": [],
        "recipeIngredient": [_raw_ing("1 cup oat milk"), _raw_ing("2 cups flour")],
    }


def test_run_parser_dry_run_plans_new_foods_without_creating_them(tmp_path, capsys):
    client = _run_client(_new_food_recipe("r1"), [_new_food_parsed("oat milk"), _parsed("flour")])
    summary = ingredient_parser.run_parser(client, _run_config(tmp_path, dry_run=True))
    client.create_food.assert_not_called()
    client.patch_recipe_ingredients.assert_not_called()
    assert summary.parsed_successfully == 1
    assert summary.foods_planned == 1
    assert "would create food 'oat milk'" in capsys.readouterr().out


def test_run_parser_creates_each_new_food_once_right_before_patching(tmp_path):
    client = _run_client(_new_food_recipe("r1"), [_new_food_parsed("oat milk"), _parsed("flour")])
    client.get_recipes.return_value = [_new_food_recipe("r1"), _new_food_recipe("r2")]
    client.create_food.return_value = {"id": "oat-id", "name": "oat milk", "groupId": "g"}
    summary = ingredient_parser.run_parser(client, _run_config(tmp_path))
    client.create_food.assert_called_once_with("oat milk", group_id=None)
    assert summary.foods_created == 1
    assert summary.parsed_successfully == 2
    for call in client.patch_recipe_ingredients.call_args_list:
        assert call[0][1][0]["food"] == {"id": "oat-id", "name": "oat milk"}


def test_run_parser_reviews_recipe_when_food_cannot_be_created(tmp_path):
    client = _run_client(_new_food_recipe("r1"), [_new_food_parsed("oat milk"), _parsed("flour")])
    client.create_food.side_effect = requests.HTTPError("500 boom")
    summary = ingredient_parser.run_parser(client, _run_config(tmp_path))
    client.patch_recipe_ingredients.assert_not_called()
    assert summary.requires_review == 1
    review = json.loads((tmp_path / "review.json").read_text())[0]
    assert review["reason"] == "food_create_failed"
    assert review["foods"] == ["oat milk"]


def test_run_parser_does_not_create_foods_for_recipes_sent_to_review(tmp_path):
    recipe = _new_food_recipe("r1")
    recipe["recipeIngredient"] = [_raw_ing("For serving:", ref="h1"), _raw_ing("1 cup oat milk", ref="r1")]
    recipe["recipeInstructions"] = [{"text": "Serve", "ingredientReferences": [{"referenceId": "h1"}]}]
    client = _run_client(recipe, [_new_food_parsed("oat milk")])
    ingredient_parser.run_parser(client, _run_config(tmp_path))
    client.create_food.assert_not_called()
