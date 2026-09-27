from __future__ import annotations

import json
from pathlib import Path

import pytest

from cookdex import organize_apply, taxonomy_store
from cookdex.reporting import read_results


class FakeMealie:
    def __init__(self) -> None:
        self.items = {
            "tags": [
                {"id": "t1", "name": "Salad", "groupId": "g", "recipeCount": 3},
                {"id": "t2", "name": "salads", "groupId": "g", "recipeCount": 1},
                {"id": "t3", "name": "indian food", "groupId": "g", "recipeCount": 2},
                {"id": "t4", "name": "Parser: Needs Review", "groupId": "g", "recipeCount": 0},
            ],
            "categories": [],
            "tools": [{"id": "x1", "name": "Dutch Oven", "groupId": "g", "recipeCount": 0}],
        }
        self.calls: list[tuple] = []

    def get_organizer_items(self, kind):
        return [dict(i) for i in self.items[kind]]

    def list_tools(self):
        return [dict(i) for i in self.items["tools"]]

    def rename_organizer_item(self, kind, item_id, name):
        self.calls.append(("rename", kind, item_id, name))

    def merge_organizer_item(self, kind, source, target):
        self.calls.append(("merge", kind, source, target))

    def merge_tool(self, source, target):
        self.calls.append(("merge", "tools", source, target))

    def delete_organizer_item(self, kind, item_id):
        self.calls.append(("delete", kind, item_id))

    def list_cookbooks(self):
        return [{"name": "Salads", "queryFilterString": 'tags.id IN ["t2"]'}]

    def update_cookbook(self, cookbook):
        self.calls.append(("cookbook", cookbook["queryFilterString"]))


@pytest.fixture()
def managed_db(tmp_path, monkeypatch) -> Path:
    db = tmp_path / "state.db"
    monkeypatch.setattr(taxonomy_store, "_DEFAULT_DB_PATH", db)
    monkeypatch.setattr(taxonomy_store, "_TAXONOMY_DIR", tmp_path / "none")
    taxonomy_store.write_collection("tags", [{"name": "Salad"}, {"name": "salads"}, {"name": "indian food"}])
    return db


def _plan(monkeypatch, tmp_path, changes) -> Path:
    results = tmp_path / "results.jsonl"
    monkeypatch.setenv("COOKDEX_APPLY_PLAN", json.dumps({"organize": {"changes": changes}}))
    monkeypatch.setenv("COOKDEX_RESULT_PATH", str(results))
    return results


def test_applies_renames_merges_and_deletes_and_mirrors_managed_taxonomy(monkeypatch, tmp_path, managed_db):
    client = FakeMealie()
    results = _plan(monkeypatch, tmp_path, [
        {"op": "delete", "kind": "tags", "id": "t4", "name": "Parser: Needs Review"},
        {"op": "merge", "kind": "tags", "id": "t2", "name": "salads", "target_id": "t1", "target_name": "Salad"},
        {"op": "rename", "kind": "tags", "id": "t3", "name": "indian food", "to": "Indian"},
    ])

    result = organize_apply.run(client, dry_run=False)

    assert result["applied"] == 3
    # Renames run first, then merges, then deletes.
    assert [c[0] for c in client.calls[:3]] == ["rename", "merge", "delete"]
    assert ("cookbook", 'tags.id IN ["t1"]') in client.calls
    assert [e["name"] for e in taxonomy_store.read_collection("tags")] == ["Salad", "Indian"]
    items = next(e["items"] for e in read_results(results) if e.get("kind") == "taxonomy_change")
    assert {i["op"]: i["status"] for i in items} == {"rename": "applied", "merge": "applied", "delete": "applied"}


def test_skips_changes_that_no_longer_fit(monkeypatch, tmp_path, managed_db):
    client = FakeMealie()
    _plan(monkeypatch, tmp_path, [
        {"op": "rename", "kind": "tags", "id": "t3", "name": "old name", "to": "Indian"},
        {"op": "rename", "kind": "tags", "id": "t2", "name": "salads", "to": "salad"},
        {"op": "delete", "kind": "tags", "id": "gone", "name": "Gone"},
    ])

    result = organize_apply.run(client, dry_run=False)

    assert result["applied"] == 0
    reasons = [i["error"] for i in result["items"]]
    assert "renamed" in reasons[0]
    assert "already exists" in reasons[1]
    assert "no longer exists" in reasons[2]
    assert client.calls == []


def test_dry_run_writes_nothing(monkeypatch, tmp_path, managed_db):
    client = FakeMealie()
    _plan(monkeypatch, tmp_path, [{"op": "delete", "kind": "tools", "id": "x1", "name": "Dutch Oven"}])
    result = organize_apply.run(client, dry_run=True)
    assert result["items"][0]["status"] == "planned"
    assert client.calls == []


def test_organize_list_suggests_merges_and_counts(monkeypatch):
    from cookdex.webui_server.routers import organize

    from cookdex.providers import MealieProvider

    client = FakeMealie()
    monkeypatch.setattr(organize, "_provider", lambda services: MealieProvider(client))
    payload = organize.list_organizers("tags", _session={}, services=None)
    by_name = {i["name"]: i for i in payload["items"]}
    assert by_name["salads"]["merge_into"] == {"id": "t1", "name": "Salad"}
    assert by_name["Salad"]["merge_into"] is None
    assert payload["unused"] == 1
    assert payload["suggested_merges"] == 1


def test_organize_apply_task_validates_plan():
    from cookdex.webui_server.tasks import TaskRegistry

    registry = TaskRegistry()
    ok = registry.build_execution("organize-apply", {"dry_run": False, "plan": {"organize": {"changes": [
        {"op": "merge", "kind": "tags", "id": "t2", "name": "salads", "target_id": "t1", "target_name": "Salad"},
    ]}}})
    assert ok.dangerous_requested is True
    assert "COOKDEX_APPLY_PLAN" in ok.env
    with pytest.raises(ValueError):
        registry.build_execution("organize-apply", {"plan": {"organize": {"changes": [{"op": "drop", "kind": "tags"}]}}})


class FakeCookbookMealie(FakeMealie):
    def __init__(self) -> None:
        super().__init__()
        self.cookbooks = [
            {"id": "c1", "name": "Salads", "description": "", "queryFilterString": 'tags.id IN ["t1"]', "public": False, "position": 1},
            {"id": "c2", "name": "Old Book", "description": "", "queryFilterString": 'tags.id IN ["t3"]', "public": False, "position": 2},
        ]

    def list_cookbooks(self):
        return [dict(c) for c in self.cookbooks]

    def request_json(self, method, path, params=None, json=None, timeout=None):
        if method == "GET" and path == "/recipes":
            rule = params["queryFilter"]
            if "bogus" in rule:
                import requests

                response = requests.Response()
                response.status_code = 400
                raise requests.HTTPError(response=response)
            total = 3 if "t1" in rule else 0
            return {"total": total, "items": [{"name": "Caesar Salad"}] * min(total, params["perPage"])}
        if method == "POST" and path == "/households/cookbooks":
            self.calls.append(("cookbook-create", json["name"], json["queryFilterString"]))
            return {"id": "c-new", **json}
        if method == "PUT" and path.startswith("/households/cookbooks/"):
            self.calls.append(("cookbook-update", path.rsplit("/", 1)[1], json["name"]))
            return json
        raise AssertionError((method, path))

    def _request_raw(self, method, path, **kwargs):
        self.calls.append(("cookbook-delete", path.rsplit("/", 1)[1]))


def test_cookbook_changes_apply_and_mirror_managed_cookbooks(monkeypatch, tmp_path, managed_db):
    from cookdex.providers import MealieProvider

    taxonomy_store.write_collection("cookbooks", [{"name": "Salads", "queryFilterString": "old"}, {"name": "Old Book"}])
    client = FakeCookbookMealie()
    _plan(monkeypatch, tmp_path, [
        {"op": "create", "kind": "cookbooks", "id": "new-1", "name": "Weeknight",
         "to": {"name": "Weeknight", "rule": 'tags.id IN ["t2"]', "description": "Fast", "public": True, "position": 3}},
        {"op": "update", "kind": "cookbooks", "id": "c1", "name": "Salads",
         "to": {"name": "Big Salads", "rule": 'tags.id IN ["t1"]', "position": 1}},
        {"op": "delete", "kind": "cookbooks", "id": "c2", "name": "Old Book"},
        {"op": "update", "kind": "cookbooks", "id": "c9", "name": "Gone", "to": {"name": "Gone"}},
    ])

    result = organize_apply.run(client, dry_run=False, provider=MealieProvider(client))

    assert result["applied"] == 3
    assert ("cookbook-create", "Weeknight", 'tags.id IN ["t2"]') in client.calls
    assert ("cookbook-update", "c1", "Big Salads") in client.calls
    assert ("cookbook-delete", "c2") in client.calls
    assert result["items"][-1]["status"] == "skipped"
    managed = {e["name"]: e for e in taxonomy_store.read_collection("cookbooks")}
    assert set(managed) == {"Big Salads", "Weeknight"}
    assert managed["Weeknight"]["queryFilterString"] == 'tags.id IN ["t2"]'


def test_cookbook_list_and_preview_count_matches(monkeypatch):
    from cookdex.providers import MealieProvider
    from cookdex.webui_server.routers import organize

    client = FakeCookbookMealie()
    monkeypatch.setattr(organize, "_provider", lambda services: MealieProvider(client))
    listing = organize.list_cookbooks(_session={}, services=None)
    assert [(c["name"], c["matches"]) for c in listing["items"]] == [("Salads", 3), ("Old Book", 0)]

    preview = organize.preview_cookbook_rule(organize.RulePreviewRequest(rule='tags.id IN ["t1"]'), _session={}, services=None)
    assert preview["matches"] == 3 and preview["sample"] == ["Caesar Salad"] * 3
    bad = organize.preview_cookbook_rule(organize.RulePreviewRequest(rule='bogus.id IN ["x"]'), _session={}, services=None)
    assert bad["matches"] is None and "couldn't read this filter" in bad["error"]


class FakeLabelMealie(FakeMealie):
    def __init__(self) -> None:
        super().__init__()
        self.labels = [
            {"id": "l1", "name": "Produce", "color": "#4caf50"},
            {"id": "l2", "name": "produce", "color": "#00ff00"},
            {"id": "l3", "name": "Unused", "color": "#999999"},
        ]
        self.foods = [
            {"id": "f1", "name": "onion", "labelId": "l1"},
            {"id": "f2", "name": "garlic", "labelId": "l2"},
            {"id": "f3", "name": "salt", "labelId": None},
        ]

    def list_labels(self):
        return [dict(label) for label in self.labels]

    def list_foods(self):
        return [dict(food) for food in self.foods]

    def create_label(self, name, color="#959595"):
        self.calls.append(("label-create", name, color))
        return {"id": "l-new", "name": name, "color": color}

    def update_label(self, label):
        self.calls.append(("label-update", label["id"], label["name"], label["color"]))
        return label

    def delete_label(self, label_id):
        self.calls.append(("label-delete", label_id))

    def update_food(self, food):
        self.calls.append(("food-label", food["id"], food["labelId"]))
        return food


def test_label_changes_apply_merge_foods_and_mirror(monkeypatch, tmp_path, managed_db):
    from cookdex.providers import MealieProvider

    taxonomy_store.write_collection("labels", [{"name": "Produce"}, {"name": "produce"}, {"name": "Unused"}])
    client = FakeLabelMealie()
    _plan(monkeypatch, tmp_path, [
        {"op": "merge", "kind": "labels", "id": "l2", "name": "produce", "target_id": "l1", "target_name": "Produce"},
        {"op": "update", "kind": "labels", "id": "l1", "name": "Produce", "to": {"name": "Fruit & Veg", "color": "#2e7d32"}},
        {"op": "delete", "kind": "labels", "id": "l3", "name": "Unused"},
        {"op": "create", "kind": "labels", "id": "new-1", "name": "Bakery", "to": {"name": "Bakery", "color": "not-a-color"}},
    ])

    result = organize_apply.run(client, dry_run=False, provider=MealieProvider(client))

    assert result["applied"] == 4
    assert ("food-label", "f2", "l1") in client.calls  # garlic moved before its label is deleted
    assert client.calls.index(("food-label", "f2", "l1")) < client.calls.index(("label-delete", "l2"))
    assert ("label-update", "l1", "Fruit & Veg", "#2e7d32") in client.calls
    assert ("label-create", "Bakery", "#959595") in client.calls  # bad color falls back to Mealie's default
    assert sorted(e["name"] for e in taxonomy_store.read_collection("labels")) == ["Bakery", "Fruit & Veg"]


def test_label_list_counts_foods_and_suggests_merges(monkeypatch):
    from cookdex.providers import MealieProvider
    from cookdex.webui_server.routers import organize

    client = FakeLabelMealie()
    monkeypatch.setattr(organize, "_provider", lambda services: MealieProvider(client))
    listing = organize.list_labels(_session={}, services=None)
    by_name = {item["name"]: item for item in listing["items"]}
    assert (by_name["Produce"]["count"], by_name["produce"]["count"], by_name["Unused"]["count"]) == (1, 1, 0)
    assert by_name["produce"]["merge_into"]["name"] in {"Produce", "produce"}
    assert listing["unused"] == 1


class FakeIngredientMealie(FakeMealie):
    """Foods and units, with recipe usage per id."""

    def __init__(self) -> None:
        super().__init__()
        self.food_rows = {
            "f1": {"id": "f1", "name": "onion", "pluralName": "onions", "labelId": None, "aliases": []},
            "f2": {"id": "f2", "name": "onions", "pluralName": None, "labelId": None, "aliases": [{"name": "brown onion"}]},
            "f3": {"id": "f3", "name": "saffron", "pluralName": None, "labelId": None, "aliases": []},
            "f4": {"id": "f4", "name": "unused thing", "pluralName": None, "labelId": None, "aliases": []},
        }
        self.unit_rows = {
            "u1": {"id": "u1", "name": "tablespoon", "abbreviation": "tbsp", "pluralName": "tablespoons", "aliases": []},
            "u2": {"id": "u2", "name": "tbsp", "abbreviation": "", "pluralName": None, "aliases": []},
            "u3": {"id": "u3", "name": "pinch", "abbreviation": "", "pluralName": None, "aliases": []},
        }
        self.uses = {"f1": 5, "f2": 1, "f3": 2, "u1": 4, "u2": 2, "u3": 0}

    def list_foods(self):
        return [dict(row) for row in self.food_rows.values()]

    def list_units(self):
        return [dict(row) for row in self.unit_rows.values()]

    def request_json(self, method, path, params=None, json=None, **kwargs):
        if method == "GET" and path == "/recipes":
            item_id = params["queryFilter"].split('"')[1]
            return {"total": self.uses.get(item_id, 0), "items": []}
        if method == "GET" and path.startswith("/foods/"):
            return dict(self.food_rows[path.rsplit("/", 1)[1]])
        if method == "GET" and path.startswith("/units/"):
            return dict(self.unit_rows[path.rsplit("/", 1)[1]])
        if method == "POST" and path == "/units":
            self.calls.append(("unit-create", json["name"], json["abbreviation"]))
            return {**json, "id": "u-new"}
        raise AssertionError((method, path))

    def update_food(self, food):
        self.calls.append(("food-update", food["id"], food["name"], food["labelId"], [a["name"] for a in food["aliases"]]))
        self.food_rows[food["id"]] = food
        return food

    def update_unit(self, unit):
        self.calls.append(("unit-update", unit["id"], unit["name"], [a["name"] for a in unit["aliases"]]))
        self.unit_rows[unit["id"]] = unit
        return unit

    def merge_food(self, source, target):
        self.calls.append(("food-merge", source, target))
        self.food_rows.pop(source)

    def merge_unit(self, source, target):
        self.calls.append(("unit-merge", source, target))
        self.unit_rows.pop(source)

    def delete_food(self, food_id):
        self.calls.append(("food-delete", food_id))

    def delete_unit(self, unit_id):
        self.calls.append(("unit-delete", unit_id))


def test_food_and_unit_changes_apply_keep_aliases_and_mirror_units(monkeypatch, tmp_path, managed_db):
    from cookdex.providers import MealieProvider

    taxonomy_store.write_collection("units_aliases", [
        {"name": "tablespoon", "fraction": True, "aliases": []}, {"name": "tbsp", "aliases": []},
    ])
    client = FakeIngredientMealie()
    _plan(monkeypatch, tmp_path, [
        {"op": "merge", "kind": "foods", "id": "f2", "name": "onions", "target_id": "f1", "target_name": "onion"},
        {"op": "update", "kind": "foods", "id": "f3", "name": "saffron",
         "to": {"name": "Saffron", "plural_name": "", "label_id": "l1", "aliases": ["zafferano", "saffron"]}},
        {"op": "delete", "kind": "foods", "id": "f3", "name": "saffron"},  # renamed first, and still used
        {"op": "merge", "kind": "units", "id": "u2", "name": "tbsp", "target_id": "u1", "target_name": "tablespoon"},
        {"op": "delete", "kind": "units", "id": "u3", "name": "pinch"},
        {"op": "create", "kind": "units", "id": "new-1", "name": "dash", "to": {"name": "dash", "abbreviation": "ds", "aliases": []}},
    ])

    result = organize_apply.run(client, dry_run=False, provider=MealieProvider(client))

    statuses = {(i["kind"], i["op"], i["name"]): i["status"] for i in result["items"]}
    assert statuses[("foods", "delete", "saffron")] == "skipped"
    assert result["applied"] == 5
    assert ("food-merge", "f2", "f1") in client.calls
    # The merged food's own name and alias stay as aliases of the kept food; "onions" is already its plural.
    assert ("food-update", "f1", "onion", None, ["brown onion"]) in client.calls
    assert ("food-update", "f3", "Saffron", "l1", ["zafferano"]) in client.calls
    # "tbsp" is already the kept unit's abbreviation, so no alias is added.
    assert ("unit-merge", "u2", "u1") in client.calls
    assert not any(c[0] == "unit-update" for c in client.calls)
    assert ("unit-delete", "u3") in client.calls
    assert ("unit-create", "dash", "ds") in client.calls
    managed = {e["name"]: e for e in taxonomy_store.read_collection("units_aliases")}
    assert set(managed) == {"tablespoon", "dash"}
    assert managed["tablespoon"]["aliases"] == ["tbsp"]  # the units cleanup maps "tbsp" to it
    assert managed["dash"]["abbreviation"] == "ds"


def test_food_and_unit_lists_count_recipes_and_suggest_merges(monkeypatch):
    from cookdex.providers import MealieProvider
    from cookdex.webui_server.routers import organize

    client = FakeIngredientMealie()
    client.labels = [{"id": "l1", "name": "Spices", "color": "#ff9800"}]
    client.list_labels = lambda: [dict(label) for label in client.labels]
    client.food_rows["f3"]["labelId"] = "l1"
    monkeypatch.setattr(organize, "_provider", lambda services: MealieProvider(client))

    foods = {item["name"]: item for item in organize.list_foods(_session={}, services=None)["items"]}
    assert foods["onion"]["count"] == 5
    assert foods["onions"]["merge_into"] == {"id": "f1", "name": "onion"}
    assert foods["saffron"]["label"] == {"name": "Spices", "color": "#ff9800"}

    listing = organize.list_units(_session={}, services=None)
    units = {item["name"]: item for item in listing["items"]}
    assert units["tbsp"]["merge_into"] == {"id": "u1", "name": "tablespoon"}  # its name is another unit's abbreviation
    assert units["pinch"]["count"] == 0 and listing["unused"] == 1


def test_organize_apply_task_limits_create_and_update_by_kind():
    from cookdex.webui_server.tasks import TaskRegistry

    registry = TaskRegistry()
    registry.build_execution("organize-apply", {"plan": {"organize": {"changes": [
        {"op": "update", "kind": "foods", "id": "f1", "name": "onion", "to": {"name": "Onion"}},
        {"op": "create", "kind": "units", "id": "new-1", "name": "dash", "to": {"name": "dash"}},
    ]}}})
    with pytest.raises(ValueError):
        registry.build_execution("organize-apply", {"plan": {"organize": {"changes": [
            {"op": "create", "kind": "foods", "id": "new-1", "name": "leek", "to": {"name": "leek"}},
        ]}}})


def test_merging_a_plural_fills_the_empty_plural_field(monkeypatch, tmp_path, managed_db):
    from cookdex.providers import MealieProvider

    client = FakeIngredientMealie()
    client.food_rows["f1"]["pluralName"] = None
    _plan(monkeypatch, tmp_path, [
        {"op": "merge", "kind": "foods", "id": "f2", "name": "onions", "target_id": "f1", "target_name": "onion"},
    ])
    organize_apply.run(client, dry_run=False, provider=MealieProvider(client))
    assert client.food_rows["f1"]["pluralName"] == "onions"
    assert [a["name"] for a in client.food_rows["f1"]["aliases"]] == ["brown onion"]
