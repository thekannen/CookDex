"""Put recipes the junk filter deleted back into Mealie.

Reads the copies in CookDex's Recently deleted folder (see
cookdex.deleted_recipes) and restores the ones named with ``--id``. A restored
recipe's copy is removed; one that couldn't be restored keeps its copy.
"""
from __future__ import annotations

import argparse

from .api_client import MealieApiClient
from .config import resolve_mealie_api_key, resolve_mealie_url
from .deleted_recipes import CopyError, RecipeArchive
from .reporting import emit_items, emit_summary


def run(archive: RecipeArchive, entry_ids: list[str]) -> int:
    items = []
    restored = failed = 0
    for index, entry_id in enumerate(entry_ids, 1):
        meta = archive.get(entry_id) if entry_id else None
        name = str((meta or {}).get("name") or entry_id)
        try:
            result = archive.restore(entry_id)
        except CopyError as exc:
            failed += 1
            print(f"[error] {index}/{len(entry_ids)} {name}: {exc}", flush=True)
            items.append({"id": entry_id, "name": name, "status": "error", "error": str(exc)})
            continue
        restored += 1
        how = "Mealie's zip import" if result["method"] == "zip" else "the saved copy, field by field"
        moved = f" (it was at {meta.get('slug')})" if meta and meta.get("slug") and meta.get("slug") != result["slug"] else ""
        print(f"[ok] {index}/{len(entry_ids)} {result['name']} is back at {result['slug']}{moved}, using {how}.", flush=True)
        items.append({"id": entry_id, "name": result["name"], "slug": result["slug"],
                      "old_slug": (meta or {}).get("slug", ""), "method": result["method"], "status": "applied"})
    emit_items("recipe_restore", items)
    emit_summary({"__title__": "Restore Deleted Recipes", "Restored": restored, "Failed": failed})
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore recipes the junk filter deleted.")
    parser.add_argument("--id", action="append", default=[], dest="ids", help="A saved copy to restore (repeatable).")
    args = parser.parse_args()
    if not args.ids:
        parser.error("Name at least one saved copy with --id.")
    client = MealieApiClient(
        base_url=resolve_mealie_url(),
        api_key=resolve_mealie_api_key(required=True),
        timeout_seconds=60,
        retries=3,
        backoff_seconds=0.4,
    )
    return run(RecipeArchive(client=client), list(dict.fromkeys(args.ids)))


if __name__ == "__main__":
    raise SystemExit(main())
