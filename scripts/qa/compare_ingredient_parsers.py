"""Compare CookDex's local ingredient parser with Mealie's own parser.

For each unparsed recipe it reads, the script parses the recipe's lines both
ways and reports, line by line, whether quantity, unit, food and note agree and
whether both would pass the confidence threshold, plus the time each took.

It only reads from Mealie: it lists foods, units and recipes, fetches recipes
one at a time, and calls Mealie's parser endpoint, which changes nothing.  It
never patches a recipe or creates a food.  One Mealie parse request runs at a
time, with ``--delay`` seconds between recipes, so it is safe to point at a
busy server if the delay is generous.

    MEALIE_URL=http://127.0.0.1:9931/api MEALIE_API_KEY=... \\
      python scripts/qa/compare_ingredient_parsers.py --max-recipes 300 --out reports/parser-compare.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cookdex.api_client import MealieApiClient  # noqa: E402
from cookdex.ingredient_parser import (  # noqa: E402
    AlreadyParsed,
    _confidence,
    extract_raw_entries,
    sanitize_raw_entries,
    slim_entity,
)
from cookdex.local_ingredient_parser import LocalIngredientParser, normalize  # noqa: E402

FIELDS = ("quantity", "unit", "food", "note")


def _entity_key(entity: Any) -> str:
    """Matched entities compare by id; new ones by normalized name."""
    if not isinstance(entity, dict):
        return ""
    slim = slim_entity(entity)
    if slim:
        return f"id:{slim['id']}"
    name = str(entity.get("name") or "")
    return f"new:{normalize(name)}" if name else ""


def _entity_label(entity: Any) -> str:
    if not isinstance(entity, dict):
        return ""
    name = str(entity.get("name") or "")
    return name if entity.get("id") else f"{name} (new)" if name else ""


def _summary_of(parsed: dict[str, Any]) -> dict[str, Any]:
    ingredient = parsed.get("ingredient") or {}
    return {
        "quantity": round(float(ingredient.get("quantity") or 0), 3),
        "unit": _entity_label(ingredient.get("unit")),
        "food": _entity_label(ingredient.get("food")),
        "note": str(ingredient.get("note") or "").strip(),
        "confidence": round(_confidence(parsed), 3),
    }


def compare_line(local: dict[str, Any], mealie: dict[str, Any], threshold: float) -> dict[str, bool]:
    li, mi = local.get("ingredient") or {}, mealie.get("ingredient") or {}
    return {
        "quantity": abs(float(li.get("quantity") or 0) - float(mi.get("quantity") or 0)) < 1e-3,
        # Mealie leaves a unit it couldn't match as a bare name, and CookDex drops
        # such units before patching, so only matched units count.
        "unit": _entity_key(slim_entity(li.get("unit"))) == _entity_key(slim_entity(mi.get("unit"))),
        "food": _entity_key(li.get("food")) == _entity_key(mi.get("food")),
        "note": str(li.get("note") or "").strip() == str(mi.get("note") or "").strip(),
        "accepted": (_confidence(local) >= threshold) == (_confidence(mealie) >= threshold),
    }


def _parses(local_parser: LocalIngredientParser, line: str) -> bool:
    try:
        local_parser.parse_one(line)
    except Exception:
        return False
    return True


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "n/a"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default=os.environ.get("MEALIE_URL", ""), help="Mealie API URL, ending in /api")
    parser.add_argument("--max-recipes", type=int, default=100, help="compare at most this many recipes")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to wait between recipes")
    parser.add_argument("--strategy", default="nlp", help="Mealie parser to compare against (default nlp)")
    parser.add_argument("--conf", type=float, default=0.70, help="confidence threshold, 0-1 (default 0.70)")
    parser.add_argument("--sample-seed", type=int, help="pick recipes at random with this seed instead of in order")
    parser.add_argument("--out", type=Path, help="write per-line results as JSON here")
    parser.add_argument("--show", type=int, default=25, help="print up to this many disagreeing lines")
    args = parser.parse_args()

    api_key = os.environ.get("MEALIE_API_KEY", "")
    if not args.url or not api_key:
        parser.error("set MEALIE_URL (or --url) and MEALIE_API_KEY")
    client = MealieApiClient(base_url=args.url, api_key=api_key, timeout_seconds=120, retries=1)

    started = time.monotonic()
    local_parser = LocalIngredientParser.from_client(client)
    local_parser.parse_one("1 cup flour")  # load the model before timing
    load_seconds = time.monotonic() - started
    print(
        f"Loaded {len(local_parser.matcher.foods_by_alias)} food names and "
        f"{len(local_parser.matcher.units_by_alias)} unit names in {load_seconds:.1f}s",
        flush=True,
    )

    recipes = [r for r in client.get_recipes(per_page=500) if r.get("hasParsedIngredients") is not True]
    if args.sample_seed is not None:
        random.Random(args.sample_seed).shuffle(recipes)

    lines_out: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    recipe_rows: list[dict[str, Any]] = []
    for recipe in recipes:
        if len(recipe_rows) >= args.max_recipes:
            break
        slug = str(recipe.get("slug") or "")
        try:
            full = client.get_recipe(slug)
            entries = extract_raw_entries(full)
        except AlreadyParsed:
            continue
        lines, _, _ = sanitize_raw_entries(entries)
        if not lines:
            continue

        t0 = time.monotonic()
        try:
            local = local_parser.parse(lines)
        except Exception as exc:  # the run falls back to Mealie's parser for this recipe
            local = None
            bad = [line for line in lines if not _parses(local_parser, line)]
            print(f"[local error] {slug}: {type(exc).__name__}: {exc} on {bad}", flush=True)
        local_seconds = time.monotonic() - t0
        t0 = time.monotonic()
        try:
            mealie = client.parse_ingredients(lines, strategy=args.strategy)
        except requests.RequestException as exc:
            mealie = None
            print(f"[Mealie error] {slug}: {exc}", flush=True)
        mealie_seconds = time.monotonic() - t0
        if local is None or mealie is None:
            errors.append({"slug": slug, "lines": lines, "local_failed": local is None, "mealie_failed": mealie is None})
            if args.delay > 0:
                time.sleep(args.delay)
            continue

        if len(mealie) != len(lines):
            print(f"[skip] {slug}: Mealie returned {len(mealie)} results for {len(lines)} lines", flush=True)
            continue
        same = True
        for line, lp, mp in zip(lines, local, mealie):
            agree = compare_line(lp, mp, args.conf)
            same = same and all(agree.values())
            lines_out.append(
                {"slug": slug, "line": line, "agree": agree, "local": _summary_of(lp), "mealie": _summary_of(mp)}
            )
        recipe_rows.append(
            {
                "slug": slug,
                "lines": len(lines),
                "local_seconds": local_seconds,
                "mealie_seconds": mealie_seconds,
                "same": same,
                "local_accepts": all(_confidence(p) >= args.conf for p in local),
                "mealie_accepts": all(_confidence(p) >= args.conf for p in mealie),
            }
        )
        print(
            f"[{len(recipe_rows)}] {slug}: {len(lines)} lines, local {local_seconds * 1000:.0f} ms, "
            f"Mealie {mealie_seconds * 1000:.0f} ms, {'same' if same else 'DIFFERENT'}",
            flush=True,
        )
        if args.delay > 0:
            time.sleep(args.delay)

    n_lines, n_recipes = len(lines_out), len(recipe_rows)
    if not n_recipes:
        print("No unparsed recipes to compare.")
        return 1
    print()
    print(f"Compared {n_recipes} recipes, {n_lines} lines, local vs Mealie '{args.strategy}'")
    for key in (*FIELDS, "accepted"):
        agreed = sum(1 for row in lines_out if row["agree"][key])
        label = "accept/reject at threshold" if key == "accepted" else key
        print(f"  {label:<28} agree on {agreed}/{n_lines} lines ({_pct(agreed, n_lines)})")
    all_agree = sum(1 for row in lines_out if all(row["agree"].values()))
    print(f"  {'every field':<28} agree on {all_agree}/{n_lines} lines ({_pct(all_agree, n_lines)})")
    same_recipes = sum(1 for row in recipe_rows if row["same"])
    print(f"  identical result for {same_recipes}/{n_recipes} recipes ({_pct(same_recipes, n_recipes)})")
    local_ok = sum(1 for row in recipe_rows if row["local_accepts"])
    mealie_ok = sum(1 for row in recipe_rows if row["mealie_accepts"])
    print(f"  recipes passing {args.conf:.0%}: local {local_ok}, Mealie {mealie_ok}")
    local_total = sum(row["local_seconds"] for row in recipe_rows)
    mealie_total = sum(row["mealie_seconds"] for row in recipe_rows)
    print(
        f"  time per recipe: local {1000 * local_total / n_recipes:.1f} ms, "
        f"Mealie {1000 * mealie_total / n_recipes:.0f} ms "
        f"(local also spent {load_seconds:.1f}s once loading foods, units and the model)"
    )

    if errors:
        both = sum(1 for e in errors if e["local_failed"] and e["mealie_failed"])
        print(
            f"  errors: {len(errors)} more recipes failed to parse "
            f"(local {sum(e['local_failed'] for e in errors)}, Mealie {sum(e['mealie_failed'] for e in errors)}, "
            f"both {both}); not counted above"
        )

    shown = 0
    for row in lines_out:
        if shown >= args.show:
            break
        if all(row["agree"].values()):
            continue
        shown += 1
        diffs = ", ".join(k for k, v in row["agree"].items() if not v)
        print(f"\n  {row['line']!r}  [{diffs}]\n    local:  {row['local']}\n    Mealie: {row['mealie']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"recipes": recipe_rows, "lines": lines_out, "errors": errors}
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
