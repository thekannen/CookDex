from __future__ import annotations


from cookdex.rule_tagger import RecipeRuleTagger, _TAG, _CAT


def test_db_resolve_tag_id_skip_mode_does_not_create() -> None:
    class _FakeDB:
        def lookup_tag_id(self, name: str, group_id: str):
            return None

        def ensure_tag(self, name: str, group_id: str, *, dry_run: bool = True):
            raise AssertionError("ensure_tag should not be called in skip mode")

    tagger = RecipeRuleTagger(dry_run=True, use_db=True, missing_targets="skip")
    tagger._missing_target_skips = 0
    resolved = tagger._db_resolve_tag_id(_FakeDB(), "group-1", "Missing Tag")
    assert resolved is None
    assert tagger._missing_target_skips == 1


def test_db_resolve_tag_id_create_mode_uses_ensure() -> None:
    class _FakeDB:
        def lookup_tag_id(self, name: str, group_id: str):
            return None

        def ensure_tag(self, name: str, group_id: str, *, dry_run: bool = True):
            return "tag-123"

    tagger = RecipeRuleTagger(dry_run=True, use_db=True, missing_targets="create")
    resolved = tagger._db_resolve_tag_id(_FakeDB(), "group-1", "Created Tag")
    assert resolved == "tag-123"


def test_db_text_rule_passes_match_on_to_db() -> None:
    class _FakeDB:
        def __init__(self) -> None:
            self.match_on = None

        def find_recipe_ids_by_text(self, group_id: str, pattern: str, *, match_on: str = "both"):
            self.match_on = match_on
            return ["r1"]

        def link_tag(self, recipe_id: str, tag_id: str, *, dry_run: bool = True):
            return None

    tagger = RecipeRuleTagger(dry_run=True, use_db=True, missing_targets="skip")
    db = _FakeDB()
    tagger._db_resolve_tag_id = lambda *_args, **_kwargs: "tag-1"  # type: ignore[method-assign]

    matched_count = tagger._db_apply_text_rule(
        db=db,  # type: ignore[arg-type]
        group_id="group-1",
        rule={"tag": "Breakfast", "pattern": "breakfast", "match_on": "description"},
        spec=_TAG,
    )
    assert matched_count == 1
    assert db.match_on == "description"


def test_db_text_category_rule_uses_cat_spec() -> None:
    class _FakeDB:
        def find_recipe_ids_by_text(self, group_id: str, pattern: str, *, match_on: str = "both"):
            return ["r1"]

        def link_category(self, recipe_id: str, cat_id: str, *, dry_run: bool = True):
            return None

    tagger = RecipeRuleTagger(dry_run=True, use_db=True, missing_targets="skip")
    db = _FakeDB()
    tagger._db_resolve_category_id = lambda *_args, **_kwargs: "cat-1"  # type: ignore[method-assign]

    matched_count = tagger._db_apply_text_rule(
        db=db,  # type: ignore[arg-type]
        group_id="group-1",
        rule={"category": "Dinner", "pattern": "dinner"},
        spec=_CAT,
    )
    assert matched_count == 1


class _TermsProvider:
    def __init__(self, terms: dict[str, list[str]]) -> None:
        self.terms = terms

    def term_kinds(self) -> list[str]:
        return ["tags", "categories", "tools"]

    def list_terms(self, kind: str):
        from cookdex.providers import Term

        return [Term(id=f"{kind}-{i}", name=name, kind=kind) for i, name in enumerate(self.terms.get(kind, []))]


def test_from_taxonomy_derives_rules_from_live_terms() -> None:
    """from_taxonomy reads the backend's current tags, categories and tools."""
    provider = _TermsProvider({"tags": ["Quick", "Vegan"], "categories": ["Dinner"], "tools": ["Air Fryer"]})
    tagger = RecipeRuleTagger.from_taxonomy(dry_run=True, provider=provider)
    assert tagger._preloaded_rules is not None
    assert len(tagger._preloaded_rules.get("text_tags", [])) == 2
    assert len(tagger._preloaded_rules.get("text_categories", [])) == 1
    assert len(tagger._preloaded_rules.get("tool_tags", [])) == 1


def test_from_taxonomy_empty_library_has_no_rules() -> None:
    """An empty library produces zero rules without crashing."""
    tagger = RecipeRuleTagger.from_taxonomy(dry_run=True, provider=_TermsProvider({}))
    assert tagger._preloaded_rules is not None
    for section in tagger._preloaded_rules.values():
        assert section == []


def test_preloaded_rules_skip_file_loading() -> None:
    """When _rules is provided, run() should use them instead of loading a file."""
    rules = {
        "ingredient_tags": [],
        "ingredient_categories": [],
        "text_tags": [{"tag": "Test", "pattern": "test"}],
        "text_categories": [],
        "tool_tags": [],
    }
    tagger = RecipeRuleTagger(dry_run=True, _rules=rules)
    assert tagger._preloaded_rules is rules


class _FakeMealie:
    """Enough of MealieApiClient for API-mode runs."""

    def __init__(self, recipes, terms=None, full=None) -> None:
        self.recipes = recipes
        self.terms = terms or {}
        self.full = full or {}
        self.patched: dict[str, dict] = {}
        self.opened: list[str] = []

    def get_recipes(self, per_page=1000):
        return self.recipes

    def get_organizer_items(self, endpoint):
        return list(self.terms.get(endpoint, []))

    def create_organizer_item(self, endpoint, payload):
        raise AssertionError("should not create in skip mode")

    def get_recipe(self, slug):
        self.opened.append(slug)
        return self.full[slug]

    def patch_recipe(self, slug, payload):
        self.patched[slug] = payload
        # Mealie answers with the full, saved recipe and a new updatedAt.
        summary = next((r for r in self.recipes if r["slug"] == slug), {})
        return {**summary, **self.full.get(slug, {}), **payload, "slug": slug, "updatedAt": "saved"}


def _api_run(monkeypatch, tmp_path, client, rules, *, dry_run=False, missing_targets="skip"):
    import cookdex.recipe_text_cache as text_cache
    import cookdex.rule_tagger as rt

    monkeypatch.setattr(rt, "MealieApiClient", lambda **_kw: client)
    monkeypatch.setattr(rt, "resolve_mealie_url", lambda: "http://mealie")
    monkeypatch.setattr(rt, "resolve_mealie_api_key", lambda: "key")
    monkeypatch.setattr(text_cache, "default_cache_path", lambda: tmp_path / "texts.json")
    full = {kind: [] for kind in ("ingredient_tags", "text_tags", "text_categories", "ingredient_categories", "tool_tags")}
    full.update(rules)
    tagger = RecipeRuleTagger(dry_run=dry_run, use_db=False, missing_targets=missing_targets, _rules=full)
    return tagger, tagger.run()


BREAKFAST = {"id": "t1", "name": "Breakfast", "slug": "breakfast"}


def test_api_rule_skips_when_target_missing_in_skip_mode(monkeypatch, tmp_path) -> None:
    client = _FakeMealie([{"slug": "r1", "name": "breakfast bowl", "description": "", "tags": []}])
    tagger, stats = _api_run(monkeypatch, tmp_path, client, {"text_tags": [{"tag": "Breakfast", "pattern": "breakfast"}]})
    assert tagger._missing_target_skips == 1
    assert client.patched == {}


def test_api_text_rule_respects_match_on_name(monkeypatch, tmp_path) -> None:
    client = _FakeMealie(
        [
            {"slug": "r1", "name": "Veggie Bowl", "description": "great breakfast", "tags": []},
            {"slug": "r2", "name": "Breakfast Casserole", "description": "", "tags": []},
        ],
        terms={"tags": [BREAKFAST]},
    )
    _tagger, stats = _api_run(
        monkeypatch, tmp_path, client, {"text_tags": [{"tag": "Breakfast", "pattern": "breakfast", "match_on": "name"}]}
    )
    assert stats["text_tags"]["Breakfast"] == 1
    assert set(client.patched) == {"r2"}


def test_api_text_rule_disabled_is_skipped(monkeypatch, tmp_path) -> None:
    client = _FakeMealie([{"slug": "r1", "name": "Breakfast Bowl", "description": "", "tags": []}], terms={"tags": [BREAKFAST]})
    _tagger, stats = _api_run(
        monkeypatch, tmp_path, client, {"text_tags": [{"tag": "Breakfast", "pattern": "breakfast", "enabled": False}]}
    )
    assert client.patched == {}
    assert stats["text_tags"] == {}


def test_api_saves_each_recipe_once_with_only_the_new_links(monkeypatch, tmp_path) -> None:
    dinner = {"id": "c1", "name": "Dinner", "slug": "dinner"}
    quick = {"id": "t2", "name": "Quick", "slug": "quick"}
    client = _FakeMealie(
        [
            {"slug": "r1", "name": "Quick Breakfast Hash", "description": "", "tags": [quick], "recipeCategory": []},
            {"slug": "r2", "name": "Quick Dinner", "description": "", "tags": [quick], "recipeCategory": [dinner]},
        ],
        terms={"tags": [BREAKFAST, quick], "categories": [dinner]},
    )
    _tagger, stats = _api_run(
        monkeypatch,
        tmp_path,
        client,
        {
            "text_tags": [{"tag": "Breakfast", "pattern": "breakfast"}, {"tag": "Quick", "pattern": "quick"}],
            "text_categories": [{"category": "Dinner", "pattern": "dinner|hash"}],
        },
    )
    # r1 gains a tag and a category in one PATCH; r2 already has everything.
    assert set(client.patched) == {"r1"}
    assert client.patched["r1"] == {
        "tags": [quick, BREAKFAST],
        "recipeCategory": [dinner],
    }
    assert client.opened == []  # text rules never open full recipes


def test_api_tool_and_ingredient_rules_read_steps_and_foods_once(monkeypatch, tmp_path) -> None:
    fryer = {"id": "tool1", "name": "Air Fryer", "slug": "air-fryer"}
    thai = {"id": "t3", "name": "Thai", "slug": "thai"}
    recipes = [
        {"slug": "r1", "name": "Wings", "description": "", "tags": [], "tools": [], "updatedAt": "1"},
        {"slug": "r2", "name": "Curry", "description": "", "tags": [], "tools": [], "updatedAt": "1"},
    ]
    full = {
        "r1": {"recipeIngredient": [{"food": {"name": "chicken wings"}}], "recipeInstructions": [{"text": "Heat the air fryer."}]},
        "r2": {
            "recipeIngredient": [{"food": {"name": "lemongrass"}}, {"food": {"name": "fish sauce"}}],
            "recipeInstructions": [{"text": "Simmer."}],
        },
    }
    rules = {
        "tool_tags": [{"tool": "Air Fryer", "pattern": "air fryer"}],
        "ingredient_tags": [{"tag": "Thai", "pattern": "lemongrass|fish sauce", "min_matches": 2}],
    }
    client = _FakeMealie(recipes, terms={"tools": [fryer], "tags": [thai]}, full=full)
    _api_run(monkeypatch, tmp_path, client, rules)
    assert client.patched == {"r1": {"tools": [fryer]}, "r2": {"tags": [thai]}}
    assert sorted(client.opened) == ["r1", "r2"]

    # A second run reuses the cached text, including for the recipes the first
    # run saved (their updatedAt moved, and the cache followed).
    saved = [{**r, "updatedAt": "saved", "tools": [fryer] if r["slug"] == "r1" else [], "tags": [thai] if r["slug"] == "r2" else []} for r in recipes]
    again = _FakeMealie(saved, terms={"tools": [fryer], "tags": [thai]}, full=full)
    _api_run(monkeypatch, tmp_path, again, rules, dry_run=True)
    assert again.opened == []
    assert again.patched == {}



def test_api_retries_a_rejected_save_from_a_fresh_copy(monkeypatch, tmp_path) -> None:
    class Flaky(_FakeMealie):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.fails = {"r1"}

        def patch_recipe(self, slug, payload):
            if slug in self.fails:
                self.fails.discard(slug)
                import requests

                response = requests.Response()
                response.status_code = 400
                raise requests.HTTPError(response=response)
            return super().patch_recipe(slug, payload)

    client = Flaky(
        [{"slug": "r1", "name": "Breakfast Hash", "description": "", "tags": []}],
        terms={"tags": [BREAKFAST]},
        # By the retry, Mealie shows the tag already there.
        full={"r1": {"slug": "r1", "tags": [BREAKFAST]}},
    )
    _api_run(monkeypatch, tmp_path, client, {"text_tags": [{"tag": "Breakfast", "pattern": "breakfast"}]})
    assert client.opened == ["r1"]
    assert client.patched["r1"] == {"tags": [BREAKFAST]}
