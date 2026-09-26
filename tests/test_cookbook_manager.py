import pytest

from cookdex.cookbook_manager import MealieCookbookManager, normalize_cookbook_items


def test_normalize_cookbook_items_minimal_defaults():
    items = normalize_cookbook_items([
        {
            "name": "Weeknight Dinners",
            "queryFilterString": "tags.name CONTAINS_ANY [\"Quick\"]",
        }
    ])

    assert items[0]["name"] == "Weeknight Dinners"
    assert items[0]["description"] == ""
    assert items[0]["public"] is False
    assert items[0]["position"] == 1


def test_normalize_cookbook_items_rejects_non_list():
    with pytest.raises(ValueError):
        normalize_cookbook_items({"name": "Invalid"})


def test_sync_cookbooks_dry_run_plans_create_update_delete(monkeypatch, capsys):
    manager = MealieCookbookManager("http://example/api", "token", dry_run=True)

    monkeypatch.setattr(
        manager,
        "build_name_id_maps",
        lambda: ({"meal prep": "tag-id-1", "weeknight": "tag-id-2", "quick": "tag-id-3"}, {"dinner": "cat-id-1"}),
    )

    monkeypatch.setattr(
        manager,
        "get_cookbooks",
        lambda: [
            {
                "id": "1",
                "name": "Weeknight Dinners",
                "description": "Old",
                "queryFilterString": "old",
                "public": False,
                "position": 1,
            },
            {
                "id": "2",
                "name": "To Remove",
                "description": "",
                "queryFilterString": "",
                "public": False,
                "position": 9,
            },
        ],
    )


    desired = [
        {
            "name": "Weeknight Dinners",
            "description": "New",
            "queryFilterString": "new",
            "public": False,
            "position": 1,
        },
        {
            "name": "Meal Prep",
            "description": "",
            "queryFilterString": "tags.name CONTAINS_ANY [\"Meal Prep\"]",
            "public": False,
            "position": 2,
        },
    ]

    created, updated, deleted, skipped, failed = manager.sync_cookbooks(desired, replace=True)
    out = capsys.readouterr().out

    assert "[plan] Update cookbook: Weeknight Dinners" in out
    assert "[plan] Create cookbook: Meal Prep" in out
    assert "[plan] Delete cookbook: To Remove" in out
    assert (created, updated, deleted, skipped, failed) == (1, 1, 1, 0, 0)


def test_normalize_cookbook_items_converts_contains_any_to_in():
    items = normalize_cookbook_items(
        [
            {
                "name": "Quick Meals",
                "queryFilterString": "tags.name CONTAINS_ANY [\"Quick\", \"Weeknight\"]",
            }
        ]
    )

    assert items[0]["queryFilterString"] == 'tags.name IN ["Quick", "Weeknight"]'


def test_compile_query_filter_for_editor_converts_name_filters_to_ids():
    manager = MealieCookbookManager("http://example/api", "token", dry_run=True)
    query_filter = (
        'recipeCategory.name IN ["Dinner"] AND '
        'tags.name IN ["Weeknight", "30-Minute"]'
    )

    compiled = manager.compile_query_filter_for_editor(
        query_filter,
        {"dinner": "cat-1"},
        {"weeknight": "tag-1", "30-minute": "tag-2"},
    )

    assert compiled == 'recipe_category.id IN ["cat-1"] AND tags.id IN ["tag-1","tag-2"]'


def test_compile_query_filter_for_editor_handles_bracket_inside_quoted_value():
    manager = MealieCookbookManager("http://example/api", "token", dry_run=True)
    query_filter = 'tags.name IN ["Tag ] Name"]'

    compiled = manager.compile_query_filter_for_editor(
        query_filter,
        {},
        {"tag ] name": "tag-1"},
    )

    assert compiled == 'tags.id IN ["tag-1"]'


def test_compile_query_filter_for_editor_normalizes_recipe_category_id_field():
    manager = MealieCookbookManager("http://example/api", "token", dry_run=True)
    query_filter = 'recipeCategory.id IN ["cat-1"]'

    compiled = manager.compile_query_filter_for_editor(
        query_filter,
        {},
        {},
    )

    assert compiled == 'recipe_category.id IN ["cat-1"]'


def test_compile_query_filter_for_editor_keeps_unknown_names():
    manager = MealieCookbookManager("http://example/api", "token", dry_run=True)
    query_filter = 'tags.name IN ["Unknown Tag"]'

    compiled = manager.compile_query_filter_for_editor(
        query_filter,
        {},
        {},
    )

    assert compiled == query_filter


def test_compile_query_filter_for_editor_resolves_food_label_names_and_keeps_rating():
    manager = MealieCookbookManager("http://example/api", "token", dry_run=True)
    query_filter = 'rating >= 4 AND recipeIngredient.food.label.name IN ["Seafood"]'

    compiled = manager.compile_query_filter_for_editor(
        query_filter,
        {},
        {},
        {},
        {"seafood": "label-1"},
    )

    assert compiled == 'rating >= 4 AND recipe_ingredient.food.label_id IN ["label-1"]'


def test_compile_query_filter_for_editor_keeps_unresolved_food_label_names():
    manager = MealieCookbookManager("http://example/api", "token", dry_run=True)
    query_filter = 'recipeIngredient.food.label.name IN ["Seafood"]'

    assert manager.compile_query_filter_for_editor(query_filter, {}, {}, {}, {}) == query_filter
    # Without a label map (e.g. lookup failed) the name clause passes through; Mealie accepts it as-is.
    assert manager.compile_query_filter_for_editor(query_filter, {}, {}) == query_filter


def test_sync_cookbooks_builds_label_map_only_when_label_names_are_used(monkeypatch):
    manager = MealieCookbookManager("http://example/api", "token", dry_run=True)
    calls: list[str] = []
    monkeypatch.setattr(manager, "get_cookbooks", lambda: [])
    monkeypatch.setattr(manager, "build_name_id_maps", lambda: calls.append("organizers") or ({}, {}, {}))
    monkeypatch.setattr(manager, "build_label_id_map", lambda: calls.append("labels") or {"seafood": "label-1"})
    created_payloads: list[dict] = []
    monkeypatch.setattr(manager, "create_cookbook", lambda payload: created_payloads.append(payload) or True)

    manager.sync_cookbooks([{"name": "Top Rated", "queryFilterString": "rating >= 4", "position": 1}])
    assert calls == []

    manager.sync_cookbooks(
        [{"name": "Seafood", "queryFilterString": 'recipeIngredient.food.label.name IN ["Seafood"]', "position": 2}]
    )
    assert calls == ["labels"]
    assert created_payloads[-1]["queryFilterString"] == 'recipe_ingredient.food.label_id IN ["label-1"]'


def test_create_cookbook_failure_hints_at_mealie_version(monkeypatch, capsys):
    manager = MealieCookbookManager("http://example/api", "token")

    class _Response:
        status_code = 422
        text = '{"detail":"Invalid query filter string"}'

    monkeypatch.setattr(manager.session, "post", lambda *args, **kwargs: _Response())

    ok = manager.create_cookbook(
        {"name": "Seafood 4+", "queryFilterString": 'rating >= 4 AND recipe_ingredient.food.label_id IN ["l"]'}
    )

    assert ok is False
    out = capsys.readouterr().out
    assert "rating clauses need Mealie v3.25+" in out
    assert "food-label clauses need Mealie v3.28+" in out


def test_filter_compatibility_hint_is_empty_for_classic_filters():
    from cookdex.cookbook_manager import filter_compatibility_hint

    assert filter_compatibility_hint('tags.name IN ["Quick"]') == ""
