from __future__ import annotations

import json

from cookdex.recipe_junk_filter import RecipeJunkFilter
from cookdex.reporting import PROGRESS_PREFIX, Progress


def _progress_lines(out: str) -> list[dict]:
    return [json.loads(line[len(PROGRESS_PREFIX):]) for line in out.splitlines() if line.startswith(PROGRESS_PREFIX)]


def test_progress_prints_first_last_and_throttled_updates(capsys):
    progress = Progress("Checking recipes", 5, min_interval=3600)
    for _ in range(5):
        progress.advance()
    lines = _progress_lines(capsys.readouterr().out)
    assert [(p["done"], p["total"]) for p in lines] == [(0, 5), (5, 5)]  # nothing in between within the interval
    assert lines[0]["label"] == "Checking recipes"


def test_runner_keeps_the_latest_progress_per_run(tmp_path):
    from cookdex.webui_server.runner import RunQueueManager

    runner = RunQueueManager(state=None, registry=None, environment_provider=dict, logs_dir=tmp_path)
    runner._record_progress("r1", PROGRESS_PREFIX + '{"label": "Reading the recipe list", "done": 3000, "total": 12169}\n')
    runner._record_progress("r1", PROGRESS_PREFIX + "not json\n")  # ignored
    assert runner.progress("r1") == {"label": "Reading the recipe list", "done": 3000, "total": 12169}
    assert runner.progress("r2") is None


class Mealie:
    """Recipes with an updatedAt stamp; counts full-recipe fetches."""

    def __init__(self) -> None:
        self.recipes = {
            f"r{i}": {"slug": f"r{i}", "name": f"Recipe {i}", "updatedAt": "2026-09-01T00:00:00Z",
                      "recipeIngredient": [{"note": "1 cup flour"}], "recipeInstructions": [{"text": "Mix."}]}
            for i in range(6)
        }
        self.recipes["r5"].update(recipeIngredient=[], recipeInstructions=[])  # junk: nothing in it
        self.fetched: list[str] = []

    def get_recipes(self):
        return [{k: r[k] for k in ("slug", "name", "updatedAt")} for r in self.recipes.values()]

    def get_recipe(self, slug):
        self.fetched.append(slug)
        return dict(self.recipes[slug])


def test_junk_check_reuses_unchanged_recipes_between_scans(tmp_path, capsys):
    mealie = Mealie()
    cache = tmp_path / "junk_scan_cache.json"

    first = RecipeJunkFilter(mealie, dry_run=True, report_file=tmp_path / "r1.json", cache_path=cache).run()
    assert sorted(mealie.fetched) == sorted(mealie.recipes)  # opened every recipe once
    assert first["summary"]["junk_found"] == 1

    mealie.fetched.clear()
    mealie.recipes["r2"]["updatedAt"] = "2026-09-27T00:00:00Z"  # edited since the last scan
    second = RecipeJunkFilter(mealie, dry_run=True, report_file=tmp_path / "r2.json", cache_path=cache).run()
    assert mealie.fetched == ["r2"]
    assert second["summary"]["junk_found"] == 1
    assert _progress_lines(capsys.readouterr().out)[-1]["done"] == 6
