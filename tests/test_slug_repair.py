from __future__ import annotations

from cookdex import slug_repair


def _m(db_slug, expected, name="X"):
    return {"id": db_slug, "name": name, "db_slug": db_slug, "expected_slug": expected}


def test_slugs_another_recipe_holds_are_left_alone() -> None:
    mismatches = [_m("old-a", "pad-thai"), _m("old-b", "soup"), _m("old-c", "soup")]
    fixable, blocked = slug_repair.split_collisions(mismatches, taken={"pad-thai"})
    # pad-thai belongs to another recipe; the second "soup" would clash with the first fix.
    assert [m["db_slug"] for m in fixable] == ["old-b"]
    assert [m["db_slug"] for m in blocked] == ["old-a", "old-c"]


class FakeClient:
    def __init__(self, regenerated=None):
        self.calls = []
        self.regenerated = regenerated

    def patch_recipe(self, slug, payload):
        self.calls.append((slug, payload))
        name = payload["name"]
        return {"slug": self.regenerated or slug_repair._make_slug(name), "name": name}


def test_api_fix_renames_and_restores_the_name() -> None:
    client = FakeClient()
    applied, failed = slug_repair.apply_api_fixes(client, [_m("mysore-pak-recipe", "mysore-pak", name="Mysore Pak")])
    assert (applied, failed) == (1, 0)
    assert client.calls == [
        ("mysore-pak-recipe", {"name": "Mysore Pak "}),
        ("mysore-pak", {"name": "Mysore Pak"}),
    ]


def test_api_fix_reports_when_mealie_picks_a_different_slug() -> None:
    client = FakeClient(regenerated="mysore-pak-1")
    applied, failed = slug_repair.apply_api_fixes(client, [_m("mysore-pak-recipe", "mysore-pak", name="Mysore Pak")])
    assert (applied, failed) == (0, 1)
    # The name still goes back to normal on the slug Mealie chose.
    assert client.calls[-1] == ("mysore-pak-1", {"name": "Mysore Pak"})


def test_parallel_repairs_do_not_race_for_occupied_slugs():
    fixable, blocked = slug_repair.split_collisions([_m('a', 'b'), _m('b', 'c')], taken=set())
    assert [m['db_slug'] for m in fixable] == ['b']
    assert [m['db_slug'] for m in blocked] == ['a']
    fixable, blocked = slug_repair.split_collisions([_m('a', 'b'), _m('b', 'a')], taken=set())
    assert not fixable and len(blocked) == 2


def test_api_restore_uses_stable_id_when_first_response_is_empty():
    recipe_id = '00000000-0000-4000-8000-000000000001'
    class Client:
        def __init__(self): self.calls = []
        def patch_recipe(self, slug, payload):
            self.calls.append((slug, payload))
            return {} if len(self.calls) == 1 else {'name': 'Soup', 'slug': 'soup'}
    client = Client()
    item = {**_m('old-soup', 'soup', 'Soup'), 'id': recipe_id}
    assert slug_repair._fix_one_via_api(client, item) == (True, '')
    assert [c[0] for c in client.calls] == [recipe_id, recipe_id]


def test_missing_response_never_guesses_another_recipe_address():
    class Client:
        def __init__(self): self.calls = []
        def patch_recipe(self, slug, payload): self.calls.append(slug); return {}
    client = Client()
    ok, _ = slug_repair._fix_one_via_api(client, _m('old-soup', 'soup', 'Soup'))
    assert not ok
    assert client.calls == ['old-soup']


def test_final_response_is_verified():
    class Client(FakeClient):
        def patch_recipe(self, slug, payload):
            result = super().patch_recipe(slug, payload)
            if len(self.calls) == 2: result['slug'] = 'unexpected'
            return result
    assert slug_repair._fix_one_via_api(Client(), _m('old-soup', 'soup', 'Soup'))[0] is False
