import pytest

from cookdex.cookbook_filters import (
    CookbookFilterParseError,
    normalize_query_filter_string,
    parse_cookbook_filter,
    serialize_cookbook_filter,
)


def test_parse_cookbook_filter_supports_aliases_foods_and_operators():
    clauses = parse_cookbook_filter(
        'recipeCategory.name IN ["Dinner"] AND '
        'recipe_ingredient.food.name NOT IN ["Beef"] AND '
        'tools.id CONTAINS ALL ["tool-1"]'
    )

    assert [(clause.resource, clause.identifier, clause.operator, clause.values) for clause in clauses] == [
        ("categories", "name", "IN", ("Dinner",)),
        ("foods", "name", "NOT IN", ("Beef",)),
        ("tools", "id", "CONTAINS ALL", ("tool-1",)),
    ]


def test_parse_cookbook_filter_keeps_and_and_brackets_inside_quoted_values():
    clauses = parse_cookbook_filter('tags.name IN ["Salt AND Pepper", "Tag ] Name"]')

    assert clauses[0].values == ("Salt AND Pepper", "Tag ] Name")
    assert serialize_cookbook_filter(clauses) == 'tags.name IN ["Salt AND Pepper", "Tag ] Name"]'


def test_parse_cookbook_filter_single_quotes_preserve_non_ascii_text():
    clauses = parse_cookbook_filter("recipeCategory.name IN ['Crème brûlée']")

    assert clauses[0].values == ("Crème brûlée",)


def test_parse_cookbook_filter_empty_value_list_stays_empty():
    clauses = parse_cookbook_filter("tags.id IN []")

    assert clauses[0].values == ()
    assert serialize_cookbook_filter(clauses) == "tags.id IN []"


def test_normalize_query_filter_string_preserves_contains_any_compatibility():
    assert (
        normalize_query_filter_string(' tags.name   CONTAINS_ANY   ["Quick", "Weeknight"] ')
        == 'tags.name IN ["Quick", "Weeknight"]'
    )


def test_parse_cookbook_filter_rejects_unsupported_fields():
    with pytest.raises(CookbookFilterParseError) as exc:
        parse_cookbook_filter('unknown.field IN ["x"]')

    assert exc.value.code == "cookbook_invalid_field"


@pytest.mark.parametrize(
    "text",
    [
        'recipe_category.id IN ["cat-1"]',
        'recipeCategory.name IN ["Dinner"] AND tags.name NOT IN ["Quick"]',
        'tools.id CONTAINS ALL ["tool-1", "tool-2"]',
        'recipeIngredient.food.name IN ["Beef"]',
        "rating >= 4",
        "rating <> 2.5",
        'recipe_ingredient.food.label_id IN ["label-1"]',
        'recipeIngredient.food.label.name NOT IN ["Seafood"] AND rating < 3',
    ],
)
def test_canonical_filters_round_trip_byte_identical(text):
    assert serialize_cookbook_filter(parse_cookbook_filter(text)) == text
    assert normalize_query_filter_string(text) == text


@pytest.mark.parametrize("operator", ["=", "<>", ">", ">=", "<", "<="])
def test_parse_rating_comparisons(operator):
    clauses = parse_cookbook_filter(f"rating {operator} 4")

    assert [(c.resource, c.field, c.identifier, c.operator, c.values) for c in clauses] == [
        ("rating", "rating", "value", operator, ("4",)),
    ]


def test_rating_accepts_compact_spacing_mixed_case_and_quoted_numbers():
    assert normalize_query_filter_string('Rating>="4.5" AND tags.id IN ["t"]') == 'rating >= 4.5 AND tags.id IN ["t"]'


@pytest.mark.parametrize("text", ["rating >= 6", "rating >= -1", 'rating >= "abc"', 'rating = "nan"'])
def test_rating_rejects_values_outside_zero_to_five(text):
    with pytest.raises(CookbookFilterParseError) as exc:
        parse_cookbook_filter(text)

    assert exc.value.code == "cookbook_invalid_rating"


@pytest.mark.parametrize("text", ['rating IN ["4"]', "rating >= abc", "tags.name >= 4"])
def test_rating_rejects_malformed_comparisons(text):
    with pytest.raises(CookbookFilterParseError):
        parse_cookbook_filter(text)


@pytest.mark.parametrize(
    ("raw_field", "canonical", "identifier"),
    [
        ("recipe_ingredient.food.label_id", "recipe_ingredient.food.label_id", "id"),
        ("recipeIngredient.food.labelId", "recipe_ingredient.food.label_id", "id"),
        ("recipe_ingredient.food.label.id", "recipe_ingredient.food.label_id", "id"),
        ("recipe_ingredient.food.label.name", "recipeIngredient.food.label.name", "name"),
        ("recipeIngredient.food.label.name", "recipeIngredient.food.label.name", "name"),
    ],
)
def test_parse_food_label_field_aliases(raw_field, canonical, identifier):
    clauses = parse_cookbook_filter(f'{raw_field} IN ["x"]')

    assert (clauses[0].resource, clauses[0].field, clauses[0].identifier) == ("labels", canonical, identifier)
