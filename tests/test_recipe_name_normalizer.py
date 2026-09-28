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


def test_rename_waits_when_its_slug_is_freed_in_the_same_run() -> None:
    from cookdex.recipe_name_normalizer import NameAction

    patched: dict[str, dict] = {}

    class Client:
        def patch_recipe(self, slug, data):
            patched[slug] = data

    normalizer = RecipeNameNormalizer(Client(), dry_run=False, apply=True, workers=1)
    actions = [
        # A swap: each wants the slug the other still holds.
        NameAction("apple-pie", "apple pie", "Pear Tart"),
        NameAction("pear-tart", "pear tart", "Apple Pie"),
        # Keeping its own slug is fine.
        NameAction("soft-rolls", "SOFT ROLLS", "Soft Rolls"),
    ]
    log, applied, failed = normalizer._apply_concurrent(actions, {"apple-pie", "pear-tart", "soft-rolls"})
    assert (applied, failed) == (1, 0)
    assert patched == {"soft-rolls": {"name": "Soft Rolls", "slug": "soft-rolls"}}
    assert sorted(e["slug"] for e in log if e["status"] == "skipped") == ["apple-pie", "pear-tart"]
