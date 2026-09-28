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
