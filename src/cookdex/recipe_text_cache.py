"""The ingredient foods and instruction text of every recipe, cached.

Mealie's recipe list leaves out ingredients and instructions, so rules that
look at them (a tool mentioned in the steps, a cuisine given away by its
foods) need each full recipe. That's one request per recipe, so the text is
kept here per slug and reused until the recipe's updatedAt changes.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .api_client import MealieApiClient
from .config import env_or_config, resolve_repo_path
from .reporting import Progress

CACHE_VERSION = 1
CACHE_NAME = "recipe_text_cache.json"
DEFAULT_WORKERS = 8


def default_cache_path() -> Path:
    base = env_or_config("CHECKPOINT_DIR", "maintenance.checkpoint_dir", "cache/maintenance")
    return resolve_repo_path(str(base)) / CACHE_NAME


def stamp(recipe: dict[str, Any]) -> str:
    return str(recipe.get("updatedAt") or recipe.get("dateUpdated") or "")


def recipe_text(full: dict[str, Any]) -> dict[str, Any]:
    """The parts of a full recipe that ingredient and tool rules match against."""
    foods: list[str] = []
    for ingredient in full.get("recipeIngredient") or []:
        if not isinstance(ingredient, dict):
            continue
        food = ingredient.get("food")
        name = str(food.get("name") or "").strip() if isinstance(food, dict) else ""
        if name and name not in foods:
            foods.append(name)
    steps: list[str] = []
    raw = full.get("recipeInstructions") or []
    for step in raw if isinstance(raw, list) else [raw]:
        if isinstance(step, dict):
            steps.append(str(step.get("text") or ""))
        elif isinstance(step, str):
            steps.append(step)
    return {"foods": foods, "instructions": "\n".join(s for s in steps if s)}


def _read(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {}
    recipes = data.get("recipes")
    return recipes if isinstance(recipes, dict) else {}


def _write(path: Path, recipes: dict[str, dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": CACHE_VERSION, "recipes": recipes}), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        print(f"[warn] Couldn't save the recipe text cache ({exc}); the next run reads every recipe again.", flush=True)


def load_recipe_texts(
    client: MealieApiClient,
    recipes: list[dict[str, Any]],
    *,
    cache_path: Path | None = None,
    workers: int = DEFAULT_WORKERS,
) -> dict[str, dict[str, Any]]:
    """Foods and instructions per slug, opening only recipes that changed since last time."""
    path = cache_path or default_cache_path()
    cache = _read(path)
    texts: dict[str, dict[str, Any]] = {}
    todo: list[dict[str, Any]] = []
    for recipe in recipes:
        slug = str(recipe.get("slug") or "")
        cached = cache.get(slug)
        if cached and stamp(recipe) and cached.get("updated") == stamp(recipe):
            texts[slug] = cached
        elif slug:
            todo.append(recipe)
    if todo:
        print(
            f"[info] Reading ingredients and steps: {len(texts)} recipe(s) unchanged since last time, opening {len(todo)}.",
            flush=True,
        )
    progress = Progress("Reading ingredients and steps", len(recipes))
    progress.advance(len(texts))

    def fetch(recipe: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        slug = str(recipe.get("slug") or "")
        try:
            return slug, {**recipe_text(client.get_recipe(slug)), "updated": stamp(recipe)}
        except Exception as exc:  # noqa: BLE001 - one unreadable recipe shouldn't stop the run
            print(f"[warn] Couldn't open {slug}: {exc}", flush=True)
            return slug, None

    failed = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for slug, text in pool.map(fetch, todo):
            progress.advance()
            if text is None:
                failed += 1
                continue
            texts[slug] = text
    if failed:
        print(f"[warn] {failed} recipe(s) couldn't be opened; ingredient and tool rules skip them this time.", flush=True)
    if todo:
        _write(path, {slug: t for slug, t in texts.items() if t.get("updated")})
    return texts


def remember_recipe_texts(fulls: list[dict[str, Any]], *, cache_path: Path | None = None) -> None:
    """Refresh cached text from full recipes we already have, e.g. PATCH responses.

    Saving a recipe moves its updatedAt, which would otherwise make the next
    run open it again even though its ingredients and steps didn't change.
    """
    fresh = {
        str(full.get("slug") or ""): {**recipe_text(full), "updated": stamp(full)}
        for full in fulls
        if isinstance(full, dict) and full.get("slug") and stamp(full)
    }
    if not fresh:
        return
    path = cache_path or default_cache_path()
    cache = _read(path)
    cache.update(fresh)
    _write(path, cache)
