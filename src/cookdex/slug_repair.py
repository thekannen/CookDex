"""Repair recipe slug mismatches in Mealie's database.

When CookDex normalizes recipe names via PATCH without including the slug
field, Mealie keeps the old slug in the database while the Pydantic model
regenerates a different slug from the new name.  This breaks subsequent
PATCH calls (403 Permission Denied) because Mealie's ``can_update()``
permission check queries by the regenerated slug, which no longer matches
any row.

Current Mealie versions no longer refuse those edits, but the recipe keeps
an address that doesn't match its name. This module detects the mismatches
and fixes them: through the database when it's connected, otherwise through
the API. Mealie makes a new slug whenever a name changes, so the API fix
saves the name with a trailing space and then saves it back.

Usage
-----
    # Scan only
    python -m cookdex.slug_repair

    # Scan and fix (uses the database when it's connected)
    python -m cookdex.slug_repair --apply
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

from slugify import slugify

from .api_client import MealieApiClient
from .config import resolve_mealie_api_key, resolve_mealie_url
from .db_client import wants_db
from .reporting import emit_summary


def _make_slug(name: str) -> str:
    """Generate a slug matching Mealie's create_recipe_slug()."""
    s = slugify(name)
    if len(s) > 250:
        s = s[:250]
    return s


def _safe_print(text: str) -> None:
    """Print text safely on Windows terminals that choke on Unicode."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode(), flush=True)


def scan_mismatches(
    client: MealieApiClient, recipes: list[dict[str, Any]] | None = None
) -> tuple[int, list[dict[str, Any]]]:
    """Return (total_count, mismatches) for *recipes*, fetching them if not given."""
    if recipes is None:
        _safe_print("[info] Fetching all recipes from Mealie...")
        recipes = client.get_recipes()
    total = len(recipes)
    _safe_print(f"[info] Scanning {total} recipes for slug mismatches...")

    mismatches: list[dict[str, Any]] = []
    for r in recipes:
        name = str(r.get("name") or "").strip()
        db_slug = str(r.get("slug") or "").strip()
        recipe_id = str(r.get("id") or "").strip()
        if not name or not db_slug:
            continue

        expected_slug = _make_slug(name)
        if expected_slug and expected_slug != db_slug:
            mismatches.append({
                "id": recipe_id,
                "name": name,
                "db_slug": db_slug,
                "expected_slug": expected_slug,
            })

    return total, mismatches


def apply_db_fixes(mismatches: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Apply slug fixes directly via DB connection, emitting progress.

    Returns (applied, skipped, failed).  Uses SAVEPOINTs so one failure
    does not abort the entire transaction.
    """
    from .db_client import MealieDBClient

    applied = 0
    skipped = 0
    failed = 0
    total = len(mismatches)

    with MealieDBClient() as db:
        p = db._db.placeholder
        native = db._db.native_id

        # Slugs are unique per group, so collisions are checked per group:
        # the same slug in another group (household server) is no conflict.
        db._db.execute("SELECT id, group_id, slug FROM recipes")
        group_of: dict[str, str] = {}
        taken: set[tuple[str, str]] = set()
        for rid, gid, slug in db._db.fetchall():
            group_of[native(rid)] = native(gid)
            taken.add((native(gid), str(slug)))

        for idx, m in enumerate(mismatches, 1):
            expected = m["expected_slug"]
            rid = native(m["id"])  # the API gives dashed ids; SQLite stores hex
            gid = group_of.get(rid)
            if gid is None:
                failed += 1
                _safe_print(f"[error] {m['db_slug']}: not found in the database")
                continue
            # Skip if the target slug already belongs to a different recipe.
            if (gid, expected) in taken and expected != m["db_slug"]:
                skipped += 1
                _safe_print(
                    f"[skip] {idx}/{total} {expected} "
                    f"already exists (collision with another recipe)"
                )
                continue

            t0 = time.monotonic()
            try:
                with db._db.savepoint("slug_fix"):
                    db._db.execute(f"UPDATE recipes SET slug = {p} WHERE id = {p}", (expected, rid))
                    if db._db.rowcount != 1:
                        raise RuntimeError("Recipe was not updated; it may have been removed since the scan.")
                # Update the lookup set so subsequent iterations see the change.
                taken.discard((gid, m["db_slug"]))
                taken.add((gid, expected))
                applied += 1
                elapsed = time.monotonic() - t0
                _safe_print(
                    f"[ok] {idx}/{total} {expected} "
                    f"was={m['db_slug']} duration={elapsed:.2f}s"
                )
            except Exception as exc:
                failed += 1
                _safe_print(f"[error] {m['db_slug']}: {exc}")

    return applied, skipped, failed


def split_collisions(
    mismatches: list[dict[str, Any]], taken: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(fixable, blocked): blocked ones want a slug another recipe already has."""
    # API workers run concurrently. A slug another mismatch holds is still
    # occupied until its update commits; never race chains or swaps for it.
    claimed = set(taken) | {m["db_slug"] for m in mismatches}
    fixable: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for m in mismatches:
        if m["expected_slug"] in claimed:
            blocked.append(m)
            continue
        claimed.add(m["expected_slug"])
        fixable.append(m)
    return fixable, blocked


def _fix_one_via_api(client: MealieApiClient, m: dict[str, Any]) -> tuple[bool, str]:
    """Rename to 'name ' (Mealie regenerates the slug), then back to 'name'."""
    try:
        identifier = str(UUID(str(m.get("id") or "")))
    except ValueError:
        identifier = m["db_slug"]
    try:
        first = client.patch_recipe(identifier, {"name": m["name"] + " "})
        new_slug = str((first or {}).get("slug") or "")
        # A missing response is not permission to PATCH the expected address:
        # it could now belong to someone else's recipe. IDs remain stable.
        restore_at = identifier if identifier != m["db_slug"] else new_slug
        if not restore_at:
            return False, "Mealie returned no recipe address; couldn't verify the repair."
        restored = client.patch_recipe(restore_at, {"name": m["name"]})
        if not restored or not restored.get("slug"):
            restored = client.get_recipe(restore_at)
    except Exception as exc:  # noqa: BLE001 - reported per recipe
        return False, f"{type(exc).__name__}: {exc}"
    if restored.get("slug") != m["expected_slug"]:
        return False, f"Mealie gave it {restored.get('slug')} instead"
    if restored.get("name") != m["name"]:
        return False, "Mealie didn't restore the recipe's original name."
    return True, ""


def apply_api_fixes(client: MealieApiClient, mismatches: list[dict[str, Any]], workers: int = 6) -> tuple[int, int]:
    """Fix each mismatch through the API. Returns (applied, failed)."""
    applied = failed = 0
    total = len(mismatches)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for idx, (m, (ok, why)) in enumerate(
            zip(mismatches, pool.map(lambda item: _fix_one_via_api(client, item), mismatches)), 1
        ):
            if ok:
                applied += 1
                _safe_print(f"[ok] {idx}/{total} {m['expected_slug']} was={m['db_slug']}")
            else:
                failed += 1
                _safe_print(f"[error] {idx}/{total} {m['db_slug']}: {why}")
    return applied, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect and repair recipe slug mismatches in Mealie's database.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Fix the mismatches. Without this flag, only scans.",
    )
    parser.add_argument(
        "--use-db", action="store_true",
        help="Fix through Mealie's database (the default whenever it's connected).",
    )
    args = parser.parse_args(argv)

    dry_run = not args.apply
    use_db = wants_db(args.use_db)
    _safe_print(f"[start] Slug Repair -- dry_run={dry_run}" + (" via database" if use_db and not dry_run else ""))

    mealie_url = resolve_mealie_url()
    api_key = resolve_mealie_api_key()
    if not mealie_url or not api_key:
        _safe_print("[error] MEALIE_URL and MEALIE_API_KEY must be set.")
        sys.exit(1)

    client = MealieApiClient(mealie_url, api_key, timeout_seconds=60, retries=3, backoff_seconds=0.4)
    _safe_print("[info] Fetching all recipes from Mealie...")
    recipes = client.get_recipes()
    total_recipes, mismatches = scan_mismatches(client, recipes)
    summary: dict[str, Any] = {
        "__title__": "Slug Repair",
        "Recipes Scanned": total_recipes,
        "Mismatches": len(mismatches),
    }
    if not mismatches:
        _safe_print("[done] Every recipe's slug matches its name.")
        emit_summary(summary)
        return 0

    taken = {str(r.get("slug") or "") for r in recipes} - {m["db_slug"] for m in mismatches}
    fixable, blocked = split_collisions(mismatches, taken)
    _safe_print(
        f"[info] {len(mismatches)} of {total_recipes} recipes have a slug that doesn't match their name"
        + (f"; {len(blocked)} can't change because another recipe already has that slug" if blocked else "")
    )
    for m in blocked:
        _safe_print(f"[skip] {m['db_slug']}: {m['expected_slug']} belongs to another recipe")
    if blocked:
        summary["Skipped (slug taken)"] = len(blocked)

    if dry_run:
        for idx, m in enumerate(fixable, 1):
            _safe_print(f"[plan] {idx}/{len(fixable)} would change {m['db_slug']} -> {m['expected_slug']}")
        summary["Mode"] = "Scan only (dry run)"
        emit_summary(summary)
        return 0

    if use_db:
        _safe_print(f"[info] Fixing {len(fixable)} through the database...")
        try:
            applied, skipped, failed = apply_db_fixes(fixable)
        except Exception as exc:
            _safe_print(f"[warn] Couldn't reach the database ({type(exc).__name__}); fixing through Mealie's API instead.")
            use_db = False
        else:
            summary.update({"Applied": applied, "Failed": failed})
            if skipped:
                summary["Skipped (slug taken)"] = summary.get("Skipped (slug taken)", 0) + skipped
    if not use_db:
        _safe_print(f"[info] Fixing {len(fixable)} through Mealie's API...")
        applied, failed = apply_api_fixes(client, fixable)
        summary.update({"Applied": applied, "Failed": failed})
    emit_summary(summary)
    return 1 if summary.get("Failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
