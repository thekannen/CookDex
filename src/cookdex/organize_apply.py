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
import re
from typing import Any

import requests

from .api_client import MealieApiClient
from .config import env_or_config, resolve_mealie_api_key, resolve_mealie_url, to_bool
from .providers import Collection, MealieProvider, ProviderError, RecipeProvider
from .reporting import emit_items, emit_summary, load_apply_plan
from .taxonomy_duplicates import TaxonomyDuplicatesManager
from .taxonomy_store import read_collection, write_collection

KINDS = {"tags": "tags", "categories": "categories", "tools": "tools"}
OPS = {"rename", "merge", "delete"}
COOKBOOK_OPS = {"create", "update", "delete"}
COOKBOOK_FIELDS = ("name", "description", "rule", "public", "position")


def _cookbook_fields(change: dict[str, Any]) -> dict[str, Any]:
    raw = change.get("to") if isinstance(change.get("to"), dict) else {}
    return {
        "name": str(raw.get("name") or "").strip(),
        "description": str(raw.get("description") or ""),
        "rule": str(raw.get("rule") or ""),
        "public": bool(raw.get("public")),
        "position": int(raw.get("position") or 0),
    }


def _list_cookbooks(provider: RecipeProvider) -> dict[str, dict[str, Any]]:
    return {c.id: {"id": c.id, "name": c.name, "rule": c.rule} for c in provider.list_collections()}


def _check_cookbook(change: dict[str, Any], current: dict[str, dict[str, Any]]) -> str:
    op = change["op"]
    if op in {"update", "delete"}:
        item = current.get(str(change.get("id")))
        if item is None:
            return "This cookbook no longer exists in Mealie."
        if str(item.get("name")) != str(change.get("name")):
            return f"It was renamed to \"{item.get('name')}\" since this change was staged."
    if op in {"create", "update"}:
        name = _cookbook_fields(change)["name"]
        if not name:
            return "The cookbook needs a name."
        if any(str(other.get("name")).lower() == name.lower() and oid != str(change.get("id")) for oid, other in current.items()):
            return f"A cookbook named \"{name}\" already exists."
    return ""


def _apply_cookbook(provider: RecipeProvider, change: dict[str, Any], current: dict[str, dict[str, Any]]) -> None:
    op = change["op"]
    if op == "delete":
        provider.delete_collection(str(change["id"]))
        current.pop(str(change["id"]), None)
        return
    fields = _cookbook_fields(change)
    collection = Collection(id=str(change.get("id")) if op == "update" else "", **fields)
    saved = provider.create_collection(collection) if op == "create" else provider.update_collection(collection)
    key = saved.id or str(change.get("id"))
    if op == "update":
        current.pop(str(change["id"]), None)
    current[key] = {"id": key, "name": fields["name"], "rule": fields["rule"]}


LABEL_OPS = {"create", "update", "delete", "merge"}
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _label_fields(change: dict[str, Any]) -> dict[str, str]:
    raw = change.get("to") if isinstance(change.get("to"), dict) else {}
    color = str(raw.get("color") or "#959595")
    return {"name": str(raw.get("name") or "").strip(), "color": color if _HEX_COLOR.match(color) else "#959595"}


def _list_labels(provider: RecipeProvider) -> dict[str, dict[str, Any]]:
    return {label.id: {"id": label.id, "name": label.name, "color": label.color} for label in provider.list_labels()}


def _check_label(change: dict[str, Any], current: dict[str, dict[str, Any]]) -> str:
    op = change["op"]
    if op in {"update", "delete", "merge"}:
        item = current.get(str(change.get("id")))
        if item is None:
            return "This label no longer exists in Mealie."
        if str(item.get("name")) != str(change.get("name")):
            return f"It was renamed to \"{item.get('name')}\" since this change was staged."
    if op == "merge":
        if str(change.get("target_id")) == str(change.get("id")):
            return "It can't be merged into itself."
        if str(change.get("target_id")) not in current:
            return "The label to merge into no longer exists."
    if op in {"create", "update"}:
        name = _label_fields(change)["name"]
        if not name:
            return "The label needs a name."
        if any(str(o.get("name")).lower() == name.lower() and oid != str(change.get("id")) for oid, o in current.items()):
            return f"A label named \"{name}\" already exists. Merge into it instead."
    return ""


def _apply_label(provider: RecipeProvider, change: dict[str, Any], current: dict[str, dict[str, Any]]) -> None:
    op, label_id = change["op"], str(change.get("id"))
    if op == "delete":
        provider.delete_label(label_id)
        current.pop(label_id, None)
    elif op == "merge":
        moved = provider.merge_labels(label_id, str(change["target_id"]))
        print(f"[info] moved {moved} food(s) to '{change.get('target_name')}'", flush=True)
        current.pop(label_id, None)
    else:
        fields = _label_fields(change)
        saved = provider.create_label(**fields) if op == "create" else provider.update_label(label_id, **fields)
        current.pop(label_id, None)
        current[saved.id or label_id] = {"id": saved.id or label_id, **fields}


def mirror_managed_labels(applied: list[dict[str, Any]]) -> int:
    """Mirror label changes into CookDex's managed labels. Returns edits."""
    changes = [c for c in applied if c["kind"] == "labels"]
    if not changes:
        return 0
    by_name = {str(e.get("name") or "").lower(): e for e in read_collection("labels")}
    edits = 0
    for change in changes:
        old_key = str(change.get("name") or "").lower()
        if change["op"] in {"update", "delete", "merge"} and old_key in by_name:
            by_name.pop(old_key)
            edits += 1
        if change["op"] in {"create", "update"}:
            fields = _label_fields(change)
            by_name[fields["name"].lower()] = {"name": fields["name"], "color": fields["color"]}
            edits += 1
        if change["op"] == "merge" and str(change.get("target_name") or "").lower() not in by_name:
            by_name[str(change["target_name"]).lower()] = {"name": change["target_name"]}
            edits += 1
    if edits:
        write_collection("labels", sorted(by_name.values(), key=lambda e: e["name"].lower()))
    return edits


def mirror_managed_cookbooks(applied: list[dict[str, Any]]) -> int:
    """Mirror cookbook changes into CookDex's managed cookbooks. Returns edits."""
    changes = [c for c in applied if c["kind"] == "cookbooks"]
    if not changes:
        return 0
    entries = read_collection("cookbooks")
    by_name = {str(e.get("name") or "").lower(): e for e in entries}
    edits = 0
    for change in changes:
        old_key = str(change.get("name") or "").lower()
        if change["op"] in {"update", "delete"} and old_key in by_name:
            by_name.pop(old_key)
            edits += 1
        if change["op"] in {"create", "update"}:
            fields = _cookbook_fields(change)
            by_name[fields["name"].lower()] = {
                "name": fields["name"],
                "description": fields["description"],
                "queryFilterString": fields["rule"],
                "public": fields["public"],
                "position": fields["position"],
            }
            edits += 1
    if edits:
        write_collection("cookbooks", sorted(by_name.values(), key=lambda e: (int(e.get("position") or 0), e["name"].lower())))
    return edits


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
    # Cookbooks go last, so cookbook edits see the final tags and categories.
    order = {"rename": 0, "merge": 1, "delete": 2}
    for change in sorted(
        changes,
        key=lambda c: ({"cookbooks": 2, "labels": 1}.get(str(c.get("kind")), 0), order.get(str(c.get("op")), 3)),
    ):
        op, kind = str(change.get("op")), str(change.get("kind"))
        item = {
            "op": op, "kind": kind, "id": change.get("id"), "name": change.get("name"),
            "to": change.get("to"), "target_id": change.get("target_id"), "target_name": change.get("target_name"),
        }
        if kind == "labels":
            if op not in LABEL_OPS:
                items.append({**item, "status": "skipped", "error": "Unknown change."})
                continue
            if kind not in current:
                current[kind] = _list_labels(provider)
            problem = _check_label(change, current[kind])
            if problem:
                items.append({**item, "status": "skipped", "error": problem})
                print(f"[skip] {op} label '{change.get('name')}': {problem}", flush=True)
                continue
            if dry_run:
                items.append({**item, "status": "planned"})
                continue
            try:
                _apply_label(provider, change, current[kind])
                items.append({**item, "status": "applied"})
                applied.append(change)
                print(f"[ok] {op} label '{change.get('name')}'", flush=True)
            except (requests.RequestException, ProviderError) as exc:
                failed += 1
                items.append({**item, "status": "error", "error": str(exc)})
                print(f"[error] {op} label '{change.get('name')}': {exc}", flush=True)
            continue
        if kind == "cookbooks":
            if op not in COOKBOOK_OPS:
                items.append({**item, "status": "skipped", "error": "Unknown change."})
                continue
            if kind not in current:
                current[kind] = _list_cookbooks(provider)
            problem = _check_cookbook(change, current[kind])
            if problem:
                items.append({**item, "status": "skipped", "error": problem})
                print(f"[skip] {op} cookbook '{change.get('name')}': {problem}", flush=True)
                continue
            if dry_run:
                items.append({**item, "status": "planned"})
                print(f"[plan] {op} cookbook '{change.get('name')}'", flush=True)
                continue
            try:
                _apply_cookbook(provider, change, current[kind])
                items.append({**item, "status": "applied"})
                applied.append(change)
                print(f"[ok] {op} cookbook '{change.get('name')}'", flush=True)
            except (requests.RequestException, ProviderError) as exc:
                failed += 1
                items.append({**item, "status": "error", "error": str(exc)})
                print(f"[error] {op} cookbook '{change.get('name')}': {exc}", flush=True)
            continue
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
        term_changes = [c for c in applied if c.get("kind") not in {"cookbooks", "labels"}]
        managed_edits = (
            mirror_managed_taxonomy(term_changes) + mirror_managed_cookbooks(applied) + mirror_managed_labels(applied)
        )

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
