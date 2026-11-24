"""Leave as is: recipes a cleanup flagged that someone chose to keep as they are."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from cookdex import kept_recipes
from tests.test_webui_app import _CSRF
from tests.test_webui_library import _login, _make_app


def test_a_kept_recipe_stays_kept_until_it_changes():
    kept = {"pancakes": "2026-11-01T10:00:00", "waffles": ""}
    assert kept_recipes.is_kept({"slug": "pancakes", "updatedAt": "2026-11-01T10:00:00"}, kept)
    assert not kept_recipes.is_kept({"slug": "pancakes", "updatedAt": "2026-11-20T09:00:00"}, kept)
    assert kept_recipes.is_kept({"slug": "waffles", "updatedAt": "2026-11-20T09:00:00"}, kept)
    assert not kept_recipes.is_kept({"slug": "toast"}, kept)


def test_load_reads_the_job_environment():
    env = {kept_recipes.ENV_KEY: json.dumps({"a": "x"})}
    assert kept_recipes.load(env) == {"a": "x"}
    assert kept_recipes.load({kept_recipes.ENV_KEY: "not json"}) == {}
    assert kept_recipes.load({}) == {}


class _Recipes:
    def __init__(self, recipes):
        self.recipes = recipes

    def get_recipes(self):
        return [dict(r) for r in self.recipes]


def test_junk_filter_leaves_kept_recipes_alone(tmp_path, monkeypatch):
    from cookdex.recipe_junk_filter import RecipeJunkFilter

    recipes = [
        {"slug": "forked-uat-batch-1", "name": "Forked UAT Batch 1", "updatedAt": "t1", "recipeIngredient": [], "recipeInstructions": []},
        {"slug": "about-us", "name": "About Us", "updatedAt": "t1", "recipeIngredient": [], "recipeInstructions": []},
    ]
    client = _Recipes(recipes)
    client.get_recipe = lambda slug: next(dict(r) for r in recipes if r["slug"] == slug)
    monkeypatch.setenv(kept_recipes.ENV_KEY, json.dumps({"forked-uat-batch-1": "t1"}))
    report = RecipeJunkFilter(client, apply=False, dry_run=True, report_file=tmp_path / "r.json").run()
    assert [a["slug"] for a in report["actions"]] == ["about-us"]
    assert report["actions"][0]["updated_at"] == "t1"


def test_name_normalizer_leaves_kept_recipes_alone(tmp_path, monkeypatch):
    from cookdex.recipe_name_normalizer import RecipeNameNormalizer

    client = _Recipes([
        {"slug": "plum-jam-recipe", "name": "plum jam recipe (no peel)", "updatedAt": "t1"},
        {"slug": "hummus-recipe", "name": "hummus recipe", "updatedAt": "t2"},
    ])
    monkeypatch.setenv(kept_recipes.ENV_KEY, json.dumps({"plum-jam-recipe": "t1"}))
    report = RecipeNameNormalizer(client, dry_run=True, apply=False, report_file=tmp_path / "n.json").run()
    slugs = [a["slug"] for a in report["actions"]]
    assert "plum-jam-recipe" not in slugs and "hummus-recipe" in slugs


def _library_app(tmp_path, monkeypatch):
    app, services_holder = _make_app(tmp_path, monkeypatch)
    return app


def _preview_with(state, items):
    state.create_run("p1", "clean-recipes", {"dry_run": True}, "admin", None, "p1.log")
    state.update_run_status("p1", status="succeeded", finished_at="2026-11-24T10:00:00Z")
    state.set_run_results("p1", [{"source": "x", "kind": "recipe_delete", "items": items}])


def test_library_hides_kept_recipes_until_they_change(tmp_path, monkeypatch):
    app = _library_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        state = app.state.services.state
        item = {"slug": "forked-uat-batch-1", "name": "Forked UAT Batch 1", "group": "junk", "status": "planned", "updated_at": "t1"}
        _preview_with(state, [item])
        ids = lambda: [f["id"] for f in client.get("/cookdex/api/v1/library").json()["findings"]]
        assert "not-recipes" in ids()

        kept = client.post("/cookdex/api/v1/library/kept", headers=_CSRF,
                           json={"items": [{"slug": item["slug"], "name": item["name"], "kind": "junk", "updated_at": "t1"}]})
        assert kept.json() == {"kept": 1}
        body = client.get("/cookdex/api/v1/library").json()
        assert "not-recipes" not in [f["id"] for f in body["findings"]]
        assert body["kept"] == {"forked-uat-batch-1": "t1"}
        listed = client.get("/cookdex/api/v1/library/kept").json()["items"]
        assert listed[0]["slug"] == "forked-uat-batch-1" and listed[0]["by"] == "admin"

        # Changed in Mealie since: flagged again.
        state.set_run_results("p1", [{"source": "x", "kind": "recipe_delete", "items": [{**item, "updated_at": "t2"}]}])
        assert "not-recipes" in ids()

        forgot = client.post("/cookdex/api/v1/library/kept/forget", headers=_CSRF, json={"slugs": ["forked-uat-batch-1"]})
        assert forgot.json() == {"forgotten": 1}
        assert client.get("/cookdex/api/v1/library").json()["kept"] == {}


def test_jobs_get_the_kept_list(tmp_path):
    from cookdex.webui_server import kept
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    state.initialize([])
    kept.keep(state, [{"slug": "a", "name": "A", "kind": "junk", "updated_at": "t1"}], "admin")
    assert kept.job_env(state) == {"a": "t1"}
