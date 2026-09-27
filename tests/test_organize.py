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
