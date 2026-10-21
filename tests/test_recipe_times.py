"""Recipe times in Mealie's text form (all versions) and seconds form (3.29+)."""

from __future__ import annotations

from typing import Any

import pytest

from cookdex.recipe_deduplicator import _completeness
from cookdex.recipe_quality_audit import _has_time
from cookdex.recipe_reimporter import RecipeReimporter
from cookdex.recipe_times import duration_seconds, has_time, time_fields, uses_seconds

# A recipe as Mealie 3.28 and older return it, and the same recipe after 3.29's
# migration moved its parseable times into seconds and cleared the text.
OLD = {"prepTime": "PT15M", "totalTime": "PT45M", "performTime": None, "cookTime": None}
NEW = {
    "prepTime": None, "totalTime": None, "performTime": None, "cookTime": None,
    "prepTimeSeconds": 900, "totalTimeSeconds": 2700, "performTimeSeconds": None,
}
NEW_NO_TIME = {"prepTime": None, "totalTime": None, "prepTimeSeconds": None, "totalTimeSeconds": None, "performTimeSeconds": None}


@pytest.mark.parametrize("recipe, expected", [
    (OLD, True),
    (NEW, True),
    (NEW_NO_TIME, False),
    ({"cookTime": "about an hour"}, True),  # cookTime stays text on 3.29
    ({"totalTime": "  "}, False),
    ({"totalTimeSeconds": 0}, False),
    ({"totalTimeSeconds": True}, False),
])
def test_a_time_counts_in_either_form(recipe, expected):
    assert has_time(recipe) is expected
    assert _has_time(recipe) is expected  # the quality audit's time dimension


def test_seconds_fields_mark_a_3_29_recipe():
    assert uses_seconds(NEW) and uses_seconds(NEW_NO_TIME)
    assert not uses_seconds(OLD)


@pytest.mark.parametrize("text, seconds", [
    ("PT15M", 900), ("PT1H30M", 5400), ("P0DT0H20M", 1200), ("pt45s", 45), ("PT0.5H", 1800), ("45", 2700),
    ("", None), ("PT", None), ("15 minutes", None), ("PT0M", None),
])
def test_iso_durations_and_bare_minutes(text, seconds):
    assert duration_seconds(text) == seconds


def test_writes_match_the_version():
    # 3.28 and older: text, as before.
    assert time_fields("prepTime", "PT15M", structured=False) == {"prepTime": "PT15M"}
    # 3.29+: seconds with the text cleared, or text with the seconds cleared.
    assert time_fields("prepTime", "PT15M", structured=True) == {"prepTimeSeconds": 900, "prepTime": None}
    assert time_fields("totalTime", "about an hour", structured=True) == {"totalTime": "about an hour", "totalTimeSeconds": None}
    assert time_fields("cookTime", "PT30M", structured=True) == {"cookTime": "PT30M"}  # no seconds field


def test_duplicate_completeness_counts_seconds_and_ignores_missing_last_made():
    base = {"description": "A good long description of the dish.", "image": "x", "tags": [1]}
    assert _completeness({**base, **NEW}) == _completeness({**base, **OLD})
    # On 3.29 lastMade is gone for every copy, so it can't favour one over another.
    assert _completeness({**base, **NEW}) == _completeness({**base, **NEW, "lastMade": None})


class _Client:
    def __init__(self, original: dict[str, Any]) -> None:
        self.original = original
        self.patch: dict[str, Any] | None = None

    def get_recipe(self, _slug: str) -> dict[str, Any]:
        return dict(self.original)

    def patch_recipe(self, _slug: str, patch: dict[str, Any]) -> None:
        self.patch = patch


def _reimport(tmp_path, original: dict[str, Any]) -> dict[str, Any]:
    client = _Client(original)
    reimporter = RecipeReimporter(client, dry_run=False, report_file=tmp_path / "report.json")
    reimporter._scrape_with_retry = lambda _s, _u: {  # type: ignore[method-assign]
        "ingredients": ["1 cup flour"], "total_time": "PT1H", "prep_time": 20, "cook_time": "PT40M",
    }
    assert reimporter._process_one(1, 1, "cake", "Cake", "https://source.example/cake")["status"] == "reimported"
    assert client.patch is not None
    return client.patch


def test_reimport_on_3_29_writes_seconds_and_clears_stale_text(tmp_path):
    patch = _reimport(tmp_path, {**NEW, "prepTimeSeconds": 600})
    assert patch["totalTimeSeconds"] == 3600 and patch["totalTime"] is None
    assert patch["prepTimeSeconds"] == 1200 and patch["prepTime"] is None  # the new time, not the old 600
    assert patch["cookTime"] == "PT40M"
    # Like Mealie's importer, the cook time also fills the perform time it shows.
    assert patch["performTimeSeconds"] == 2400 and patch["performTime"] is None


def test_reimport_on_3_28_still_writes_text(tmp_path):
    patch = _reimport(tmp_path, OLD)
    assert patch["totalTime"] == "PT1H" and patch["prepTime"] == "PT20M" and patch["cookTime"] == "PT40M"
    assert patch["performTime"] == "PT40M"
    assert not any(key.endswith("Seconds") for key in patch)
