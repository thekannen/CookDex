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
