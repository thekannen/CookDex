from pathlib import Path

from cookdex.recipe_name_normalizer import RecipeNameNormalizer, normalize_recipe_name


class _DummyClient:
    def get_recipes(self) -> list[dict[str, str]]:
        return [{"slug": "bbq-ribs", "name": "bbq's best ribs"}]

    def patch_recipe(self, slug: str, data: dict[str, str]) -> None:
        raise AssertionError("patch_recipe should not be called in audit mode")


def test_normalize_recipe_name_handles_gaelic_apostrophe() -> None:
    assert normalize_recipe_name("o'brien potato salad") == "O'Brien Potato Salad"


def test_normalize_recipe_name_handles_acronym_possessive() -> None:
    assert normalize_recipe_name("bbq's best ribs") == "BBQ's Best Ribs"


def test_normalize_recipe_name_uses_titlecase_abbreviation_rules() -> None:
    assert normalize_recipe_name("mac and cheese vs. pbj") == "Mac and Cheese vs. PBJ"


def test_audit_scope_uses_lowercase_only_label(tmp_path: Path) -> None:
    report_path = tmp_path / "normalize_report.json"
    normalizer = RecipeNameNormalizer(
        _DummyClient(),
        dry_run=True,
        apply=False,
        force_all=False,
        report_file=report_path,
    )

    report = normalizer.run()

    assert report["summary"]["scope"] == "lowercase-only"


def test_normalize_strips_scraped_seo_decoration() -> None:
    from cookdex.recipe_name_normalizer import normalize_recipe_name

    cases = {
        "instant-pot-beef-stew-recipe": "Instant Pot Beef Stew",
        "banana-bread-2": "Banana Bread",
        "vegan-lentil-soup-recipe-easy": "Vegan Lentil Soup",
        "chicken-tikka-masala-restaurant-style-recipe-video": "Chicken Tikka Masala Restaurant Style",
        "Easy Weeknight Chicken Stir Fry | The Best Recipe!": "Easy Weeknight Chicken Stir Fry",
        "THE BEST Chocolate Chip Cookies (Seriously!)": "Chocolate Chip Cookies",
        "25-best-summer-salads": "25 Best Summer Salads",
    }
    for raw, expected in cases.items():
        assert normalize_recipe_name(raw) == expected, raw


def test_human_names_with_seo_noise_become_candidates() -> None:
    from cookdex.recipe_name_normalizer import _should_normalize

    assert _should_normalize({"name": "THE BEST Chocolate Chip Cookies (Seriously!)", "slug": "c"}, force_all=False)
    assert _should_normalize({"name": "Stir Fry | The Best Recipe!", "slug": "s"}, force_all=False)
    assert not _should_normalize({"name": "Grandma's Apple Pie", "slug": "g"}, force_all=False)
    assert not _should_normalize({"name": "Top 10 Soups", "slug": "t"}, force_all=False)


def test_shouted_words_in_any_script_are_seo_noise() -> None:
    from cookdex.recipe_name_normalizer import _has_seo_noise

    assert _has_seo_noise("EINFACHER APFELKUCHEN mit Streuseln")
    assert _has_seo_noise("Soupe À L'OIGNON GRATINÉE")
    assert _has_seo_noise("ПРОСТОЙ БОРЩ")
    assert _has_seo_noise("Easy Soup (QUICK, EASY!)")
    assert not _has_seo_noise("Äpfel und Birnen")
    assert not _has_seo_noise("BBQ Ribs")


def test_normalize_keeps_mealie_copy_marker() -> None:
    from cookdex.recipe_name_normalizer import normalize_recipe_name

    assert (
        normalize_recipe_name("chicken-tikka-masala-restaurant-style-recipe-video (1)")
        == "Chicken Tikka Masala Restaurant Style (1)"
    )
    assert normalize_recipe_name("banana-bread-2 (3)") == "Banana Bread (3)"


def test_renames_that_repeat_another_recipes_name_are_flagged() -> None:
    from cookdex.recipe_name_normalizer import NameAction, mark_conflicts

    recipes = [
        {"slug": "plum-jam", "name": "Plum Jam"},
        {"slug": "plum-jam-recipe-no-peel", "name": "Plum Jam Recipe (No Peel, No Pectin!)"},
        {"slug": "onion-rings-crispy", "name": "Onion Rings Recipe | Crispy Onion Rings"},
        {"slug": "onion-rings-cheese", "name": "Onion Rings Recipe | Cheese Stuffed Onion Rings"},
        {"slug": "banana-cake", "name": "Banana Cake"},
        {"slug": "banana-cake-recipe", "name": "Banana Cake Recipe | Eggless"},
        {"slug": "soft-rolls", "name": "SOFT ROLLS"},
    ]
    actions = [
        NameAction("plum-jam-recipe-no-peel", "Plum Jam Recipe (No Peel, No Pectin!)", "Plum Jam"),
        NameAction("onion-rings-crispy", "Onion Rings Recipe | Crispy Onion Rings", "Onion Rings"),
        NameAction("onion-rings-cheese", "Onion Rings Recipe | Cheese Stuffed Onion Rings", "Onion Rings"),
        # "Banana Cake" is renamed away in the same batch, so its name is free.
        NameAction("banana-cake", "Banana Cake", "Classic Banana Cake"),
        NameAction("banana-cake-recipe", "Banana Cake Recipe | Eggless", "Banana Cake"),
        NameAction("soft-rolls", "SOFT ROLLS", "Soft Rolls"),  # a case-only fix isn't a clash with itself
    ]
    assert mark_conflicts(actions, recipes) == 3
    by_slug = {a.slug: (a.conflict, a.conflict_with) for a in actions}
    assert by_slug["plum-jam-recipe-no-peel"] == ("existing", "Plum Jam")
    assert by_slug["onion-rings-crispy"][0] == by_slug["onion-rings-cheese"][0] == "duplicate"
    assert by_slug["banana-cake-recipe"] == ("", "")
    assert by_slug["soft-rolls"] == ("", "")


def test_applied_renames_never_reuse_a_taken_slug() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    patched: dict[str, dict] = {}

    class Client:
        def patch_recipe(self, slug, data):
            patched[slug] = data

    normalizer = RecipeNameNormalizer(Client(), dry_run=False, apply=True, workers=1)
    actions = [
        NameAction("plum-jam-recipe-no-peel", "Plum Jam Recipe (No Peel!)", "Plum Jam"),
        NameAction("plum-jam-2019", "plum jam 2019", "Plum Jam"),
    ]
    _log, applied, failed = normalizer._apply_concurrent(actions, {"plum-jam", "plum-jam-recipe-no-peel", "plum-jam-2019"})
    assert (applied, failed) == (2, 0)
    assert sorted(d["slug"] for d in patched.values()) == ["plum-jam-2", "plum-jam-3"]


def test_live_run_skips_names_another_recipe_already_has(tmp_path: Path) -> None:
    patched: dict[str, dict] = {}

    class Client:
        def get_recipes(self):
            return [
                {"slug": "plum-jam", "name": "Plum Jam"},
                {"slug": "plum-jam-recipe-no-peel", "name": "Plum Jam Recipe (No Peel!)"},
                {"slug": "onion-rings-recipe-crispy", "name": "Onion Rings Recipe | Crispy Onion Rings"},
                {"slug": "onion-rings-recipe-stuffed", "name": "Onion Rings Recipe | Stuffed Onion Rings"},
            ]

        def patch_recipe(self, slug, data):
            patched[slug] = data

    normalizer = RecipeNameNormalizer(
        Client(), dry_run=False, apply=True, workers=1, report_file=tmp_path / "names.json"
    )
    report = normalizer.run()

    # Mealie answers "Recipe already exists" for a name another recipe has, so
    # those are skipped, not failed; the first of two same-name renames goes ahead.
    assert report["summary"]["failed"] == 0
    assert list(patched) == ["onion-rings-recipe-crispy"]
    by_slug = {a["slug"]: a for a in report["actions"]}
    assert by_slug["plum-jam-recipe-no-peel"]["status"] == "skipped"
    assert "already called \"Plum Jam\"" in by_slug["plum-jam-recipe-no-peel"]["error"]
    assert by_slug["onion-rings-recipe-stuffed"]["status"] == "skipped"


def test_double_encoded_names_are_repaired():
    from cookdex.recipe_name_normalizer import _should_normalize, normalize_recipe_name

    assert normalize_recipe_name("Ã¢â‚¬Å“Spicy Noodlesâ€") == "Spicy Noodles"
    assert normalize_recipe_name("CafÃ© Latte") == "Café Latte"
    assert normalize_recipe_name("Momâ€™s Pie") == "Mom’s Pie"
    # Real accents are left alone.
    assert normalize_recipe_name("Crème Brûlée") == "Crème Brûlée"
    assert _should_normalize({"name": "CafÃ© Latte", "slug": "cafa-latte"}, force_all=False)


def test_mojibake_repair_never_drops_characters():
    from cookdex.recipe_name_normalizer import repair_mojibake

    # A capital Ã or Â before a letter is real Portuguese or French, not mojibake.
    assert repair_mojibake("PÃO DE QUEIJO") == "PÃO DE QUEIJO"
    assert repair_mojibake("MÂCHE SALAD") == "MÂCHE SALAD"
    assert normalize_recipe_name("PÃO DE QUEIJO") == "Pão De Queijo"
    assert normalize_recipe_name("MÂCHE SALAD") == "Mâche Salad"
    # A real accent next to a garbled one is kept.
    assert repair_mojibake("CafÃ© crème") == "Café crème"
    assert repair_mojibake("CafÃ©") == "Café"
    assert repair_mojibake("crÃ¨me brÃ»lÃ©e") == "crème brûlée"


def test_unrepairable_mojibake_is_left_alone_even_with_all():
    from cookdex.recipe_name_normalizer import _should_normalize

    garbled = "cafÃ©è au lait"
    assert normalize_recipe_name(garbled) == garbled
    assert not _should_normalize({"name": garbled, "slug": "c"}, force_all=True)


def test_non_ascii_capitals_count_as_human_casing():
    from cookdex.recipe_name_normalizer import _should_normalize

    assert not _should_normalize({"name": "Ørred med smør", "slug": "o"}, force_all=False)
    assert not _should_normalize({"name": "Éclair au chocolat", "slug": "e"}, force_all=False)
    assert _should_normalize({"name": "éclair au chocolat", "slug": "e"}, force_all=False)


def test_title_casing_output_is_nfc():
    import unicodedata

    assert normalize_recipe_name("İSKENDER KEBAP") == "İskender Kebap"
    nfd = unicodedata.normalize("NFD", "café latte")
    assert normalize_recipe_name(nfd) == "Café Latte"


def test_nfd_and_nfc_names_conflict():
    import unicodedata

    from cookdex.recipe_name_normalizer import NameAction, mark_conflicts

    nfd = unicodedata.normalize("NFD", "Café Latte")
    actions = [NameAction("cafe-latte-recipe", "café latte recipe", "Café Latte")]
    recipes = [{"slug": "cafe-latte", "name": nfd}, {"slug": "cafe-latte-recipe", "name": "café latte recipe"}]
    assert mark_conflicts(actions, recipes) == 1
    assert actions[0].conflict == "existing"


class _StrictMealie:
    """A recipe store that, like Mealie, never lets two recipes share a name or slug."""

    def __init__(self, recipes: dict[str, str], fail_on: set[tuple[str, str]] | None = None) -> None:
        self.recipes = dict(recipes)  # slug -> name
        self.ids = {slug: f"id-{slug}" for slug in recipes}  # slug -> the recipe's lasting id
        self.fail_on = fail_on or set()  # (address, new name) pairs that fail
        self.calls: list[tuple[str, str, str]] = []

    def name_of(self, original_slug: str) -> str:
        """The current name of the recipe that started at *original_slug*."""
        return next(self.recipes[slug] for slug, rid in self.ids.items() if rid == f"id-{original_slug}")

    def patch_recipe(self, address, data):
        self.calls.append((address, data["name"], data["slug"]))
        if (address, data["name"]) in self.fail_on:
            raise RuntimeError("PATCH failed (500)")
        if address not in self.recipes:
            raise RuntimeError("PATCH failed (404)")
        for slug, name in self.recipes.items():
            if slug != address and (slug == data["slug"] or name.lower() == data["name"].lower()):
                raise RuntimeError("PATCH failed (400): Recipe already exists")
        del self.recipes[address]
        self.recipes[data["slug"]] = data["name"]
        self.ids[data["slug"]] = self.ids.pop(address)


def _run(store: _StrictMealie, actions):
    normalizer = RecipeNameNormalizer(store, dry_run=False, apply=True, workers=1)
    return normalizer._apply_concurrent(actions, set(store.recipes))


def test_two_recipes_swap_names_through_a_temporary_name() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    store = _StrictMealie({"apple-pie": "Apple Pie", "pear-tart": "Pear Tart", "soft-rolls": "SOFT ROLLS"})
    log, applied, failed = _run(store, [
        NameAction("apple-pie", "Apple Pie", "Pear Tart"),
        NameAction("pear-tart", "Pear Tart", "Apple Pie"),
        NameAction("soft-rolls", "SOFT ROLLS", "Soft Rolls"),  # keeping its own slug is fine
    ])
    assert (applied, failed) == (3, 0)
    # The recipes really swapped: each one now has the other's name and slug.
    assert store.name_of("apple-pie") == "Pear Tart" and store.ids["pear-tart"] == "id-apple-pie"
    assert store.name_of("pear-tart") == "Apple Pie" and store.ids["apple-pie"] == "id-pear-tart"
    assert store.name_of("soft-rolls") == "Soft Rolls"
    assert any(name == "Apple Pie (renaming)" for _a, name, _s in store.calls)  # the temporary step
    assert all(e["status"] == "ok" for e in log)


def test_a_chain_goes_in_order_in_one_run() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    store = _StrictMealie({"banana-bread-recipe": "Banana Bread Recipe", "banana-bread": "banana bread"})
    _log, applied, failed = _run(store, [
        NameAction("banana-bread-recipe", "Banana Bread Recipe", "Banana Bread"),  # wants the other's slug
        NameAction("banana-bread", "banana bread", "Banana Bread (Grandma's)"),
    ])
    assert (applied, failed) == (2, 0)
    assert sorted(store.recipes.values()) == ["Banana Bread", "Banana Bread (Grandma's)"]


def test_three_way_cycle_and_a_chain_waiting_on_it() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    store = _StrictMealie({"a": "A", "b": "B", "c": "C", "d-recipe": "D Recipe"})
    _log, applied, failed = _run(store, [
        NameAction("a", "A", "B"), NameAction("b", "B", "C"), NameAction("c", "C", "A"),
        NameAction("d-recipe", "D Recipe", "A Classic"),  # unrelated, goes in the first pass
    ])
    assert (applied, failed) == (4, 0)
    assert [store.name_of(s) for s in ("a", "b", "c", "d-recipe")] == ["B", "C", "A", "A Classic"]


def test_a_failed_swap_puts_both_recipes_back() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    original = {"apple-pie": "Apple Pie", "pear-tart": "Pear Tart"}
    store = _StrictMealie(original, fail_on={("pear-tart", "Apple Pie")})
    log, applied, failed = _run(store, [
        NameAction("apple-pie", "Apple Pie", "Pear Tart"),
        NameAction("pear-tart", "Pear Tart", "Apple Pie"),
    ])
    assert (applied, failed) == (0, 2)
    assert store.recipes == original and store.name_of("apple-pie") == "Apple Pie"
    assert all("put back the way it was" in e["error"] for e in log)


def test_a_failed_last_step_undoes_the_whole_swap() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    original = {"apple-pie": "Apple Pie", "pear-tart": "Pear Tart"}
    store = _StrictMealie(original, fail_on={("apple-pie-renaming", "Pear Tart")})
    log, applied, failed = _run(store, [
        NameAction("apple-pie", "Apple Pie", "Pear Tart"),
        NameAction("pear-tart", "Pear Tart", "Apple Pie"),
    ])
    assert (applied, failed) == (0, 2)
    assert store.recipes == original
    assert store.name_of("apple-pie") == "Apple Pie" and store.name_of("pear-tart") == "Pear Tart"
    assert all("put back the way it was" in e["error"] for e in log)


def test_a_rename_waiting_on_a_failed_one_is_skipped_with_a_reason() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    store = _StrictMealie({"x-recipe": "X Recipe", "x": "x"}, fail_on={("x", "X Plain")})
    log, applied, failed = _run(store, [
        NameAction("x-recipe", "X Recipe", "X"),
        NameAction("x", "x", "X Plain"),
    ])
    assert (applied, failed) == (0, 1)
    skipped = [e for e in log if e["status"] == "skipped"]
    assert [e["slug"] for e in skipped] == ["x-recipe"] and "couldn't be renamed" in skipped[0]["error"]
    assert store.recipes == {"x-recipe": "X Recipe", "x": "x"}


def test_a_chain_hanging_off_a_swap_waits_for_it() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    store = _StrictMealie({"a": "A", "b": "B", "a-recipe": "A Recipe"})
    _log, applied, failed = _run(store, [
        NameAction("a", "A", "B"), NameAction("b", "B", "A Two"),  # b -> "A Two" is free; not a cycle
        NameAction("a-recipe", "A Recipe", "A"),  # waits for "a" to move
    ])
    assert (applied, failed) == (3, 0)
    assert [store.name_of(s) for s in ("a", "b", "a-recipe")] == ["B", "A Two", "A"]
