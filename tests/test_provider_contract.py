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
            for kind in ("tags", "categories", "tools")
        }
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

    def request_json(self, method, path, **kwargs):
        assert (method, path) == ("GET", "/users/self")
        return {"id": "u1", "username": "admin"}

    def get_about(self):
        return {"version": "v3.28.0"}


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


def test_task_requirements_name_real_tasks_and_capabilities():
    registry = TaskRegistry()
    known = {c.value for c in Capability}
    for task_id, needs in TASK_REQUIREMENTS.items():
        assert task_id in registry.task_ids, task_id
        assert set(needs) <= known, (task_id, needs)
