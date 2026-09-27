"""Apply staged Organize changes to Mealie tags, categories and tools.

The web UI's Organize page stages renames, merges and deletes, then runs this
module with the approved list in ``COOKDEX_APPLY_PLAN`` (section
``organize``)::

    {"organize": {"changes": [
        {"op": "rename", "kind": "tags", "id": "...", "name": "old", "to": "New"},
        {"op": "merge", "kind": "tags", "id": "...", "name": "salads",
         "target_id": "...", "target_name": "Salad"},
        {"op": "delete", "kind": "tools", "id": "...", "name": "Unused tool"}
    ]}}

Merges move every recipe to the target (Mealie's merge endpoint) and repoint
cookbook filters. Each change is mirrored into CookDex's managed taxonomy so a
later Refresh Taxonomy doesn't bring back what was just merged or renamed.
With DRY_RUN=true nothing is written; the plan is only checked and reported.
"""
from __future__ import annotations

import argparse
from typing import Any

import requests

from .api_client import MealieApiClient
from .config import env_or_config, resolve_mealie_api_key, resolve_mealie_url, to_bool
from .providers import MealieProvider, ProviderError, RecipeProvider
from .reporting import emit_items, emit_summary, load_apply_plan
from .taxonomy_duplicates import TaxonomyDuplicatesManager
from .taxonomy_store import read_collection, write_collection

KINDS = {"tags": "tags", "categories": "categories", "tools": "tools"}
OPS = {"rename", "merge", "delete"}


def _list_items(provider: RecipeProvider, kind: str) -> dict[str, dict[str, Any]]:
    return {term.id: {"id": term.id, "name": term.name} for term in provider.list_terms(kind)}


def _check(change: dict[str, Any], current: dict[str, dict[str, Any]]) -> str:
    """Return why a change can't be applied now, or '' when it can."""
    item = current.get(str(change.get("id")))
    if item is None:
        return "It no longer exists in Mealie."
    if str(item.get("name")) != str(change.get("name")):
        return f"It was renamed to \"{item.get('name')}\" since this change was staged."
    if change["op"] == "rename":
        new_name = str(change.get("to") or "").strip()
        if not new_name:
            return "The new name is empty."
        if any(str(other.get("name")).lower() == new_name.lower() and oid != str(change["id"]) for oid, other in current.items()):
            return f"\"{new_name}\" already exists. Merge into it instead."
    if change["op"] == "merge":
        if str(change.get("target_id")) == str(change.get("id")):
            return "It can't be merged into itself."
        if str(change.get("target_id")) not in current:
            return "The item to merge into no longer exists."
    return ""


def mirror_managed_taxonomy(applied: list[dict[str, Any]]) -> int:
    """Apply renames and removals to CookDex's managed taxonomy. Returns edits."""
    edits = 0
    for kind in KINDS:
        changes = [c for c in applied if c["kind"] == kind]
        if not changes:
            continue
        entries = read_collection(kind)
        if not entries:
            continue
        renamed = {c["name"]: c["to"] for c in changes if c["op"] == "rename"}
        removed = {c["name"] for c in changes if c["op"] in {"merge", "delete"}}
        updated: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in entries:
            name = str(entry.get("name") or "")
            if name in removed:
                edits += 1
                continue
            if name in renamed:
                entry = {**entry, "name": renamed[name]}
                edits += 1
            key = str(entry["name"]).lower()
            if key in seen:
                continue
            seen.add(key)
            updated.append(entry)
        for change in changes:
            # A merge target must stay (or become) part of the managed set.
            if change["op"] == "merge" and change["target_name"].lower() not in seen:
                updated.append({"name": change["target_name"]})
                seen.add(change["target_name"].lower())
        write_collection(kind, updated)
    return edits


def run(client: MealieApiClient, *, dry_run: bool, provider: RecipeProvider | None = None) -> dict[str, Any]:
    provider = provider or MealieProvider(client)
    plan = load_apply_plan("organize")
    changes = [c for c in (plan or {}).get("changes") or [] if isinstance(c, dict)]
    print(f"[start] {len(changes)} staged change(s) to apply{' (preview only)' if dry_run else ''}", flush=True)

    current: dict[str, dict[str, dict[str, Any]]] = {}
    items: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    merged_ids: dict[str, str] = {}
    failed = 0

    # Renames first, then merges, then deletes, so a rename can't collide with
    # a name a merge is about to remove.
    order = {"rename": 0, "merge": 1, "delete": 2}
    for change in sorted(changes, key=lambda c: order.get(str(c.get("op")), 9)):
        op, kind = str(change.get("op")), str(change.get("kind"))
        item = {
            "op": op, "kind": kind, "id": change.get("id"), "name": change.get("name"),
            "to": change.get("to"), "target_id": change.get("target_id"), "target_name": change.get("target_name"),
        }
        if op not in OPS or kind not in KINDS:
            items.append({**item, "status": "skipped", "error": "Unknown change."})
            continue
        if kind not in current:
            current[kind] = _list_items(provider, kind)
        problem = _check(change, current[kind])
        if problem:
            items.append({**item, "status": "skipped", "error": problem})
            print(f"[skip] {op} {kind} '{change.get('name')}': {problem}", flush=True)
            continue
        if dry_run:
            items.append({**item, "status": "planned"})
            print(f"[plan] {op} {kind} '{change.get('name')}'", flush=True)
            continue
        try:
            if op == "rename":
                provider.rename_term(kind, str(change["id"]), str(change["to"]).strip())
                current[kind][str(change["id"])]["name"] = str(change["to"]).strip()
            elif op == "merge":
                provider.merge_terms(kind, str(change["id"]), str(change["target_id"]))
                merged_ids[str(change["id"])] = str(change["target_id"])
                current[kind].pop(str(change["id"]), None)
            else:
                provider.delete_term(kind, str(change["id"]))
                current[kind].pop(str(change["id"]), None)
            items.append({**item, "status": "applied"})
            applied.append({**change, "to": str(change.get("to") or "").strip(), "target_name": str(change.get("target_name") or "")})
            print(f"[ok] {op} {kind} '{change.get('name')}'", flush=True)
        except (requests.RequestException, ProviderError) as exc:
            failed += 1
            items.append({**item, "status": "error", "error": str(exc)})
            print(f"[error] {op} {kind} '{change.get('name')}': {exc}", flush=True)

    cookbooks = {"repointed": 0, "failed": 0}
    managed_edits = 0
    if applied:
        if merged_ids:
            manager = TaxonomyDuplicatesManager(client, kinds=["tags", "categories"])
            cookbooks = manager.repoint_cookbooks(merged_ids, executable=True)
        managed_edits = mirror_managed_taxonomy(applied)

    emit_items("taxonomy_change", items)
    emit_summary({
        "__title__": "Organize",
        "Changes": len(changes),
        "Applied": len(applied),
        "Skipped": sum(1 for i in items if i["status"] == "skipped"),
        "Failed": failed,
        "Cookbooks Repointed": cookbooks["repointed"],
        "Managed Taxonomy Edits": managed_edits,
        "Mode": "audit" if dry_run else "apply",
    })
    return {"applied": len(applied), "failed": failed, "items": items}


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Apply staged Organize changes to Mealie.")


def main() -> int:
    build_parser().parse_args()
    dry_run = bool(env_or_config("DRY_RUN", "runtime.dry_run", True, to_bool))
    client = MealieApiClient(resolve_mealie_url(), resolve_mealie_api_key(required=True))
    result = run(client, dry_run=dry_run)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
