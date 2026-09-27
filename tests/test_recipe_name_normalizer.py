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
