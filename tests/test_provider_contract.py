"""Contract every recipe-manager adapter must meet (see cookdex.providers.base).

Adding a backend (e.g. Tandoor) means adding a factory to ADAPTERS that
builds it over a fake transport seeded with SEED; the same tests then run.
"""
from __future__ import annotations

import pytest

from cookdex.providers import Capability, MealieProvider, ProviderError, RecipeProvider, Term
from cookdex.webui_server.tasks import TASK_REQUIREMENTS, TaskRegistry

# Terms every fake backend starts with: two spellings of one tag, one unused tag.
SEED = [
    {"id": "t1", "name": "Salad", "count": 3},
    {"id": "t2", "name": "salads", "count": 1},
    {"id": "t3", "name": "Unused", "count": 0},
]


class FakeMealieClient:
    """Just enough of MealieApiClient for the contract."""

    def __init__(self) -> None:
        self.terms = {
            kind: [{"id": t["id"], "name": t["name"], "groupId": "g", "recipeCount": t["count"]} for t in SEED]
            for kind in ("tags", "categories")
        }
        # Like Mealie v3.28: tools report recipeCount 0 however many recipes use them.
        self.terms["tools"] = [{"id": t["id"], "name": t["name"], "groupId": "g", "recipeCount": 0} for t in SEED]
        self.calls: list[tuple] = []

    def get_organizer_items(self, kind):
        return [dict(t) for t in self.terms[kind]]

    def list_tools(self):
        return [dict(t) for t in self.terms["tools"]]

    def rename_organizer_item(self, kind, item_id, name):
        self.calls.append(("rename", kind, item_id, name))

    def merge_organizer_item(self, kind, source, target):
        self.calls.append(("merge", kind, source, target))

    def merge_tool(self, source, target):
        self.calls.append(("merge", "tools", source, target))

    def delete_organizer_item(self, kind, item_id):
        self.calls.append(("delete", kind, item_id))

    def request_json(self, method, path, params=None, **kwargs):
        if (method, path) == ("GET", "/recipes"):
            rule = params.get("queryFilter") or ""
            if rule.startswith("tools.id IN"):
                tool_id = rule.split('"')[1]
                return {"total": next(t["count"] for t in SEED if t["id"] == tool_id), "items": []}
            return {"total": 2, "items": [{"name": "Caesar Salad"}, {"name": "Greek Salad"}][: params["perPage"]]}
        assert (method, path) == ("GET", "/users/self")
        return {"id": "u1", "username": "admin"}

    def list_cookbooks(self):
        return [{"id": "c1", "name": "Salads", "queryFilterString": 'tags.id IN ["t1"]', "position": 1}]

    def get_about(self):
        return {"version": "v3.28.0"}

    labels = [{"id": "l1", "name": "Produce", "color": "#00aa00"}, {"id": "l2", "name": "Veg", "color": "#959595"}]
    foods = [{"id": "f1", "name": "onion", "labelId": "l1"}, {"id": "f2", "name": "leek", "labelId": "l2"}]

    def list_labels(self):
        return [dict(item) for item in self.labels]

    def list_foods(self):
        return [dict(item) for item in self.foods]

    def list_units(self):
        return [{"id": "u1", "name": "tablespoon", "abbreviation": "tbsp", "aliases": [{"name": "Tbs"}]}]

    def update_food(self, food):
        self.calls.append(("food", food["id"], food["labelId"]))

    def delete_label(self, label_id):
        self.calls.append(("delete", "labels", label_id))

    timeout_seconds = 30

    def get_paginated(self, path, **kwargs):
        assert path == "/recipes"
        return [{"name": "Soup", "orgURL": "https://known.example/soup"}, {"name": "Typed in", "orgURL": ""}]

    def request(self, method, path, json=None, **kwargs):
        import requests
        from types import SimpleNamespace

        url = json["url"]
        self.calls.append(("import", url))
        if "slow" in url:
            raise requests.HTTPError("POST failed") from requests.exceptions.ReadTimeout("slow")
        if "known" in url:
            return SimpleNamespace(status_code=409, text="")
        if "broken" in url:
            return SimpleNamespace(status_code=500, text="Unknown Error")
        return SimpleNamespace(status_code=201, text='"new-slug"')


def _mealie():
    client = FakeMealieClient()
    return MealieProvider(client), client.calls


ADAPTERS = {"mealie": _mealie}


@pytest.fixture(params=sorted(ADAPTERS))
def adapter(request) -> tuple[RecipeProvider, list]:
    return ADAPTERS[request.param]()


def test_is_a_recipe_provider(adapter):
    provider, _ = adapter
    assert isinstance(provider, RecipeProvider)
    assert provider.kind and provider.display_name


def test_capabilities_and_wording_are_consistent(adapter):
    provider, _ = adapter
    caps = provider.capabilities()
    assert caps and all(isinstance(c, Capability) for c in caps)
    vocab = provider.vocabulary()
    for key in ("backend", "terms", "term_singular", "collections", "address_label", "token_label"):
        assert key in vocab
    assert set(provider.term_kinds()) == set(vocab["terms"])


def test_health_reports_backend_and_user(adapter):
    provider, _ = adapter
    info = provider.health()
    assert info.kind == provider.kind and info.user


def test_list_terms_returns_counted_terms(adapter):
    provider, _ = adapter
    for kind in provider.term_kinds():
        terms = provider.list_terms(kind)
        assert all(isinstance(t, Term) and t.kind == kind for t in terms)
        assert {t.name: t.count for t in terms} == {s["name"]: s["count"] for s in SEED}


def test_term_changes_reach_the_backend(adapter):
    provider, calls = adapter
    kind = provider.term_kinds()[0]
    provider.rename_term(kind, "t1", "Salads")
    provider.merge_terms(kind, "t2", "t1")
    provider.delete_term(kind, "t3")
    assert [call[0] for call in calls] == ["rename", "merge", "delete"]


def test_unknown_term_kind_is_a_provider_error(adapter):
    provider, _ = adapter
    with pytest.raises(ProviderError):
        provider.list_terms("not-a-kind")


def test_rule_collections_when_advertised(adapter):
    from cookdex.providers import Collection

    provider, _ = adapter
    if Capability.RULE_COLLECTIONS not in provider.capabilities():
        pytest.skip("backend has no rule-based collections")
    collections = provider.list_collections()
    assert collections and all(isinstance(c, Collection) and c.id and c.name for c in collections)
    count, sample = provider.count_rule_matches(collections[0].rule, sample=1)
    assert count == 2 and len(sample) == 1


def test_task_requirements_name_real_tasks_and_capabilities():
    registry = TaskRegistry()
    known = {c.value for c in Capability}
    for task_id, needs in TASK_REQUIREMENTS.items():
        assert task_id in registry.task_ids, task_id
        assert set(needs) <= known, (task_id, needs)


def test_labels_when_advertised(adapter):
    from cookdex.providers import Label

    provider, calls = adapter
    if Capability.LABELS not in provider.capabilities():
        pytest.skip("backend has no food labels")
    labels = provider.list_labels()
    assert all(isinstance(item, Label) and item.id and item.name for item in labels)
    assert {item.name: item.count for item in labels} == {"Produce": 1, "Veg": 1}
    moved = provider.merge_labels("l2", "l1")
    assert moved == 1
    # Foods move before the source label is removed.
    assert calls.index(("food", "f2", "l1")) < calls.index(("delete", "labels", "l2"))


def test_foods_and_units_when_advertised(adapter):
    from cookdex.providers import Food, Unit

    provider, _ = adapter
    caps = provider.capabilities()
    if Capability.FOODS in caps:
        foods = provider.list_foods()
        assert foods and all(isinstance(f, Food) and f.id and f.name for f in foods)
        assert provider.count_ingredient_uses("foods", foods[0].id) >= 0
    if Capability.UNITS in caps:
        units = provider.list_units()
        assert units and all(isinstance(u, Unit) and u.id and u.name for u in units)
        assert units[0].aliases == ["Tbs"] and units[0].abbreviation == "tbsp"
    if not {Capability.FOODS, Capability.UNITS} & caps:
        pytest.skip("backend has no editable foods or units")


def test_url_imports_report_outcomes_when_advertised(adapter):
    provider, _ = adapter
    if Capability.IMPORT_URL not in provider.capabilities():
        pytest.skip("backend doesn't import URLs")
    assert provider.recipe_source_urls() == ["https://known.example/soup"]
    new = provider.import_recipe_url("https://new.example/stew")
    assert (new.imported, new.ref) == (True, "new-slug")
    known = provider.import_recipe_url("https://known.example/soup")
    assert (known.imported, known.duplicate) == (False, True)
    slow = provider.import_recipe_url("https://slow.example/pie")
    assert (slow.imported, slow.retry_later) == (False, True)
    broken = provider.import_recipe_url("https://broken.example/cake")
    assert (broken.imported, broken.retry_later) == (False, False)
    assert broken.error
