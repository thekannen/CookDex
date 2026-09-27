import argparse
import json

import pytest
import requests

from cookdex.taxonomy_duplicates import (
    TaxonomyDuplicatesManager,
    build_duplicate_groups,
    choose_canonical,
    normalize_name,
    parse_kinds,
)


def _http_error(status: int, body: bytes) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response._content = body
    return requests.HTTPError(f"failed ({status})", response=response)


class FakeOrganizerClient:
    def __init__(self, items=None, recipes=None, merge_error=None, cookbooks=None):
        self._items = items or {}
        self.cookbooks = cookbooks or []
        self.cookbook_updates: list[dict] = []
        self._recipes = recipes or []
        self.merge_error = merge_error
        self.merges: list[tuple[str, str, str]] = []
        self.recipe_fetches = 0

    def get_organizer_items(self, endpoint, per_page=1000):
        return list(self._items.get(endpoint, []))

    def get_recipes(self, per_page=1000):
        self.recipe_fetches += 1
        return list(self._recipes)

    def list_cookbooks(self, per_page=1000):
        return list(self.cookbooks)

    def update_cookbook(self, cookbook):
        self.cookbook_updates.append(cookbook)
        return cookbook

    def merge_organizer_item(self, endpoint, source_id, target_id):
        self.merges.append((endpoint, source_id, target_id))
        if self.merge_error is not None:
            raise self.merge_error
        return {}


def _item(item_id, name, count=None, group="g1"):
    item = {"id": item_id, "name": name, "groupId": group}
    if count is not None:
        item["recipeCount"] = count
    return item


def _names(groups):
    return sorted(sorted(item["name"] for item in members) for members in groups.values())


def test_normalize_name_folds_cosmetic_differences():
    assert normalize_name("  Gluten-Free ") == "gluten free"
    assert normalize_name("gluten  free") == "gluten free"
    assert normalize_name("Mac & Cheese") == normalize_name("mac and cheese")
    assert normalize_name("Jalapeño") == "jalapeno"
    assert normalize_name("Chef's Choice") == normalize_name("Chefs Choice")


def test_groups_include_plural_only_when_singular_exists():
    items = [
        _item("1", "Cookie"),
        _item("2", "Cookies"),
        _item("3", "Berries"),
        _item("4", "berry"),
        _item("5", "Brownies"),
        _item("6", "Glass"),
        _item("7", "Dishes"),
        _item("8", "Dish"),
        _item("9", "Side Dishes"),
    ]
    assert _names(build_duplicate_groups(items)) == [
        ["Berries", "berry"],
        ["Cookie", "Cookies"],
        ["Dish", "Dishes"],
    ]


def test_groups_do_not_merge_distinct_concepts_or_other_groups():
    items = [
        _item("1", "Chicken"),
        _item("2", "Chicken Soup"),
        _item("3", "Stir Fry"),
        _item("4", "Stirfry"),
        _item("5", "Vegan", group="g1"),
        _item("6", "vegan", group="g2"),
    ]
    assert build_duplicate_groups(items) == {}


def test_choose_canonical_prefers_usage_then_tidy_name():
    candidates = [_item("b", "quick  meal"), _item("a", "Quick Meal"), _item("c", "QUICK MEAL")]
    assert choose_canonical(candidates, {"a": 3, "b": 9, "c": 3})["id"] == "b"
    assert choose_canonical(candidates, {"a": 3, "b": 3, "c": 3})["id"] == "a"
    assert choose_canonical(candidates, {"b": 3, "c": 3})["id"] == "c"


def test_run_dry_run_plans_without_merging(tmp_path):
    client = FakeOrganizerClient(
        items={
            "tags": [_item("t1", "Gluten Free", 5), _item("t2", "gluten-free", 2), _item("t3", "Vegan", 4)],
            "categories": [_item("c1", "Desserts", 1), _item("c2", "Dessert", 7)],
        }
    )
    manager = TaxonomyDuplicatesManager(client, dry_run=True, apply=True, report_file=tmp_path / "r.json")
    report = manager.run()
    assert client.merges == []
    assert client.recipe_fetches == 0
    assert report["summary"]["mode"] == "audit"
    assert report["summary"]["merge_candidates_total"] == 2
    planned = [(a["kind"], a["source_id"], a["target_id"]) for a in report["attempted_actions"]]
    assert planned == [("tags", "t2", "t1"), ("categories", "c1", "c2")]
    assert json.loads((tmp_path / "r.json").read_text())["summary"]["mode"] == "audit"


def test_run_apply_merges_into_most_used_and_respects_max_actions(tmp_path):
    client = FakeOrganizerClient(
        items={"tags": [_item("t1", "Dinner", 1), _item("t2", "dinner", 8), _item("t3", "DINNER ", 0)]}
    )
    manager = TaxonomyDuplicatesManager(
        client, kinds=["tags"], apply=True, max_actions=1, report_file=tmp_path / "r.json"
    )
    report = manager.run()
    assert client.merges == [("tags", "t3", "t2")]
    assert report["summary"]["actions_applied"] == 1
    assert report["by_kind"]["tags"]["merge_supported"] is True


def test_run_apply_repoints_cookbooks_at_the_kept_organizer(tmp_path):
    cookbooks = [
        {"id": "cb1", "name": "Pies", "queryFilterString": 'tags.id IN ["T2","t9"] AND recipe_category.id IN ["c1"]'},
        {"id": "cb2", "name": "Other", "queryFilterString": 'tags.id IN ["t9"]'},
    ]
    client = FakeOrganizerClient(
        items={"tags": [_item("t1", "Pie", 5), _item("T2", "Pies", 1)], "categories": [_item("c1", "Dessert", 2)]},
        cookbooks=cookbooks,
    )
    report = TaxonomyDuplicatesManager(client, apply=True, report_file=tmp_path / "r.json").run()
    assert client.cookbook_updates == [
        {**cookbooks[0], "queryFilterString": 'tags.id IN ["t1","t9"] AND recipe_category.id IN ["c1"]'}
    ]
    assert report["summary"]["cookbooks_repointed"] == 1


def test_run_dry_run_plans_cookbook_repoints_without_writing(tmp_path):
    client = FakeOrganizerClient(
        items={"tags": [_item("t1", "Pie", 5), _item("t2", "Pies", 1)]},
        cookbooks=[{"id": "cb1", "name": "Pies", "queryFilterString": 'tags.id IN ["t2"]'}],
    )
    report = TaxonomyDuplicatesManager(client, kinds=["tags"], report_file=tmp_path / "r.json").run()
    assert client.cookbook_updates == []
    assert report["summary"]["cookbooks_repointed"] == 1


def test_run_falls_back_to_recipe_scan_without_recipe_count(tmp_path):
    client = FakeOrganizerClient(
        items={"categories": [_item("c1", "Soup"), _item("c2", "Soups")]},
        recipes=[{"recipeCategory": [{"id": "c2"}]}, {"recipeCategory": [{"id": "c2"}, {"id": "c1"}]}],
    )
    manager = TaxonomyDuplicatesManager(client, kinds=["categories"], apply=True, report_file=tmp_path / "r.json")
    manager.run()
    assert client.recipe_fetches == 1
    assert client.merges == [("categories", "c1", "c2")]


def test_run_reports_missing_merge_route_without_failing(tmp_path):
    client = FakeOrganizerClient(
        items={
            "tags": [_item("t1", "Kid Friendly", 3), _item("t2", "kid-friendly", 1), _item("t3", "KID FRIENDLY", 0)],
        },
        merge_error=_http_error(405, b'{"detail":"Method Not Allowed"}'),
    )
    manager = TaxonomyDuplicatesManager(client, kinds=["tags"], apply=True, report_file=tmp_path / "r.json")
    report = manager.run()
    # The first 405 marks the route missing; the remaining merges are not attempted.
    assert len(client.merges) == 1
    assert report["summary"]["unsupported_kinds"] == ["tags"]
    assert report["summary"]["actions_failed"] == 0
    assert [a["status"] for a in report["attempted_actions"]] == ["unsupported", "unsupported"]


def test_run_counts_record_errors_as_failures(tmp_path):
    client = FakeOrganizerClient(
        items={"tags": [_item("t1", "Spicy", 3), _item("t2", "spicy", 1)]},
        merge_error=_http_error(404, b'{"detail":"from_id tag not found"}'),
    )
    manager = TaxonomyDuplicatesManager(client, kinds=["tags"], apply=True, report_file=tmp_path / "r.json")
    report = manager.run()
    assert report["summary"]["actions_failed"] == 1
    assert report["summary"]["unsupported_kinds"] == []


def test_parse_kinds_validates_and_dedupes():
    assert parse_kinds("tags, categories,tags") == ["tags", "categories"]
    with pytest.raises(argparse.ArgumentTypeError, match="tools"):
        parse_kinds("tools")


def test_choose_canonical_prefers_clean_singular_names_without_counts():
    def pick(*names):
        return choose_canonical([{"id": str(i), "name": n} for i, n in enumerate(names)], {})["name"]

    assert pick("salt", "Salt +") == "salt"
    assert pick("eggs (*)", "egg") == "egg"
    assert pick("anchovy", "anchovies") == "anchovy"
    assert pick("SPAM\u00ae", "spam") == "spam"
    assert pick("Salad", "salads") == "Salad"
