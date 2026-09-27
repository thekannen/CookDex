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

Cookbooks, labels, foods and units use ``create``/``update`` with the new
fields in ``to``. Food and unit merges keep the old name as an alias on the
kept item, so new recipes parse to it; foods and units still used by recipes
can't be deleted, only merged.

Merges move every recipe to the target (Mealie's merge endpoint) and repoint
cookbook filters. With DRY_RUN=true nothing is written; the plan is only
checked and reported.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, replace
from typing import Any, Callable

import requests

from .api_client import MealieApiClient
from .cookbook_filters import (
    ID_FIELDS,
    CookbookFilterClause,
    CookbookFilterParseError,
    normalize_query_filter_string,
    parse_cookbook_filter,
    serialize_cookbook_filter,
)
from .config import env_or_config, resolve_mealie_api_key, resolve_mealie_url, to_bool
from .providers import Collection, Food, MealieProvider, ProviderError, RecipeProvider, Unit
from .reporting import emit_items, emit_summary, load_apply_plan
from .taxonomy_duplicates import TaxonomyDuplicatesManager, normalize_name, singular_candidates

KINDS = {"tags": "tags", "categories": "categories", "tools": "tools"}
OPS = {"create", "rename", "merge", "delete"}
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


def _rule_names_to_ids(provider: RecipeProvider, rule: str) -> str:
    """Resolve ``tags.name IN [...]``-style clauses (from an imported file) to ids.

    Runs at apply time, after terms and labels, so a cookbook can name tags
    created in the same batch.
    """
    try:
        clauses = parse_cookbook_filter(normalize_query_filter_string(rule))
    except CookbookFilterParseError:
        return rule
    if not any(c.identifier == "name" and c.resource in ID_FIELDS for c in clauses):
        return rule
    compiled: list[CookbookFilterClause] = []
    for clause in clauses:
        if clause.identifier != "name" or clause.resource not in ID_FIELDS:
            compiled.append(clause)
            continue
        items = provider.list_labels() if clause.resource == "labels" else provider.list_terms(clause.resource)
        ids_by_name = {item.name.lower(): item.id for item in items}
        missing = [value for value in clause.values if value.strip().lower() not in ids_by_name]
        if missing:
            raise ProviderError(f"The filter names {clause.resource} that don't exist: {', '.join(missing)}.")
        compiled.append(CookbookFilterClause(
            resource=clause.resource, field=ID_FIELDS[clause.resource], identifier="id", operator=clause.operator,
            values=tuple(ids_by_name[value.strip().lower()] for value in clause.values),
        ))
    return serialize_cookbook_filter(compiled, compact_lists=True)


def _apply_cookbook(provider: RecipeProvider, change: dict[str, Any], current: dict[str, dict[str, Any]]) -> None:
    op = change["op"]
    if op == "delete":
        provider.delete_collection(str(change["id"]))
        current.pop(str(change["id"]), None)
        return
    fields = _cookbook_fields(change)
    fields["rule"] = _rule_names_to_ids(provider, fields["rule"])
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


INGREDIENT_OPS = {"foods": {"update", "merge", "delete"}, "units": {"create", "update", "merge", "delete"}}


def _clean_aliases(raw: Any, *exclude: str) -> list[str]:
    skip = {normalize_name(name) for name in exclude if name}
    aliases: list[str] = []
    for value in raw if isinstance(raw, list) else []:
        alias = str(value or "").strip()
        key = normalize_name(alias)
        if alias and key and key not in skip:
            skip.add(key)
            aliases.append(alias)
    return aliases


def _ingredient_fields(change: dict[str, Any]) -> dict[str, Any]:
    raw = change.get("to") if isinstance(change.get("to"), dict) else {}
    name = str(raw.get("name") or "").strip()
    fields: dict[str, Any] = {"name": name, "plural_name": str(raw.get("plural_name") or "").strip()}
    if change["kind"] == "foods":
        fields["label_id"] = str(raw.get("label_id") or "").strip()
    else:
        fields["abbreviation"] = str(raw.get("abbreviation") or "").strip()
    fields["aliases"] = _clean_aliases(raw.get("aliases"), name)
    return fields


def _list_ingredients(provider: RecipeProvider, kind: str) -> dict[str, dict[str, Any]]:
    items = provider.list_foods() if kind == "foods" else provider.list_units()
    return {item.id: {"id": item.id, "name": item.name, "obj": item} for item in items}


def _known_names(item: Food | Unit) -> list[str]:
    return [item.name, item.plural_name, getattr(item, "abbreviation", ""), *item.aliases]


def _check_ingredient(provider: RecipeProvider, change: dict[str, Any], current: dict[str, dict[str, Any]]) -> str:
    op, noun = change["op"], change["kind"][:-1]
    if op in {"update", "delete", "merge"}:
        item = current.get(str(change.get("id")))
        if item is None:
            return f"This {noun} no longer exists in Mealie."
        if str(item.get("name")) != str(change.get("name")):
            return f"It was renamed to \"{item.get('name')}\" since this change was staged."
    if op == "merge":
        if str(change.get("target_id")) == str(change.get("id")):
            return "It can't be merged into itself."
        if str(change.get("target_id")) not in current:
            return f"The {noun} to merge into no longer exists."
    if op == "delete":
        uses = provider.count_ingredient_uses(change["kind"], str(change["id"]))
        if uses:
            return f"{uses} recipe{'s' if uses != 1 else ''} still use it. Merge it into another {noun} instead."
    if op in {"create", "update"}:
        name = _ingredient_fields(change)["name"]
        if not name:
            return f"The {noun} needs a name."
        if any(str(o.get("name")).lower() == name.lower() and oid != str(change.get("id")) for oid, o in current.items()):
            return f"A {noun} named \"{name}\" already exists. Merge into it instead."
    return ""


def _apply_ingredient(provider: RecipeProvider, change: dict[str, Any], current: dict[str, dict[str, Any]]) -> None:
    op, kind, item_id = change["op"], change["kind"], str(change.get("id"))
    foods = kind == "foods"
    if op == "delete":
        (provider.delete_food if foods else provider.delete_unit)(item_id)
        current.pop(item_id, None)
        return
    if op == "merge":
        source = current[item_id]["obj"]
        target_id = str(change["target_id"])
        (provider.merge_foods if foods else provider.merge_units)(item_id, target_id)
        current.pop(item_id, None)
        # Keep the old spellings so new recipes parse to the kept item: a plural
        # fills an empty plural field, anything else becomes an alias.
        target = current[target_id]["obj"]
        kept = target
        if not target.plural_name and normalize_name(target.name) in singular_candidates(normalize_name(source.name)):
            target = replace(target, plural_name=source.name)
        extra = _clean_aliases([source.name, source.plural_name, *source.aliases], *_known_names(target))
        if extra:
            target = replace(target, aliases=[*target.aliases, *extra])
        if target != kept:
            target = (provider.update_food if foods else provider.update_unit)(target) or target
            current[target_id]["obj"] = target
            print(f"[info] kept the old name(s) on '{target.name}'", flush=True)
        return
    fields = _ingredient_fields(change)
    if op == "create":
        saved = provider.create_unit(Unit(id="", **fields))
    elif foods:
        saved = provider.update_food(replace(current[item_id]["obj"], **fields))
    else:
        saved = provider.update_unit(replace(current[item_id]["obj"], **fields))
    current.pop(item_id, None)
    current[saved.id or item_id] = {"id": saved.id or item_id, "name": saved.name, "obj": saved}


@dataclass
class _Section:
    """How to check and apply one kind of staged change."""

    noun: str
    ops: set[str]
    load: Callable[[RecipeProvider], dict[str, dict[str, Any]]]
    check: Callable[[RecipeProvider, dict[str, Any], dict[str, dict[str, Any]]], str]
    apply: Callable[[RecipeProvider, dict[str, Any], dict[str, dict[str, Any]]], None]


SECTIONS: dict[str, _Section] = {
    "labels": _Section("label", LABEL_OPS, _list_labels, lambda _p, c, cur: _check_label(c, cur), _apply_label),
    "foods": _Section("food", INGREDIENT_OPS["foods"], lambda p: _list_ingredients(p, "foods"), _check_ingredient, _apply_ingredient),
    "units": _Section("unit", INGREDIENT_OPS["units"], lambda p: _list_ingredients(p, "units"), _check_ingredient, _apply_ingredient),
    "cookbooks": _Section("cookbook", COOKBOOK_OPS, _list_cookbooks, lambda _p, c, cur: _check_cookbook(c, cur), _apply_cookbook),
}
# Terms first, then labels (foods may point at them), foods and units, and
# cookbooks last so their filters see the final tags and categories.
KIND_ORDER = {"labels": 1, "foods": 2, "units": 2, "cookbooks": 3}


def _list_items(provider: RecipeProvider, kind: str) -> dict[str, dict[str, Any]]:
    return {term.id: {"id": term.id, "name": term.name} for term in provider.list_terms(kind)}


def _same_name(a: str, b: str) -> bool:
    """True for spellings a library would treat as one term (case, punctuation, plural)."""
    key_a, key_b = normalize_name(a), normalize_name(b)
    return key_a == key_b or key_a in singular_candidates(key_b) or key_b in singular_candidates(key_a)


def _check(change: dict[str, Any], current: dict[str, dict[str, Any]]) -> str:
    """Return why a change can't be applied now, or '' when it can."""
    if change["op"] == "create":
        name = _term_name(change)
        if not name:
            return "The new name is empty."
        existing = next((o for o in current.values() if _same_name(str(o.get("name")), name)), None)
        return f"\"{existing['name']}\" already exists." if existing else ""
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


def _term_name(change: dict[str, Any]) -> str:
    to = change.get("to")
    return str((to.get("name") if isinstance(to, dict) else to) or "").strip()


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
    # See KIND_ORDER for the order between kinds.
    order = {"rename": 0, "merge": 1, "delete": 2}
    for change in sorted(
        changes,
        key=lambda c: (KIND_ORDER.get(str(c.get("kind")), 0), order.get(str(c.get("op")), 3)),
    ):
        op, kind = str(change.get("op")), str(change.get("kind"))
        item = {
            "op": op, "kind": kind, "id": change.get("id"), "name": change.get("name"),
            "to": change.get("to"), "target_id": change.get("target_id"), "target_name": change.get("target_name"),
        }
        section = SECTIONS.get(kind)
        if section is not None:
            if op not in section.ops:
                items.append({**item, "status": "skipped", "error": "Unknown change."})
                continue
            try:
                if kind not in current:
                    current[kind] = section.load(provider)
                problem = section.check(provider, change, current[kind])
            except (requests.RequestException, ProviderError) as exc:
                problem = str(exc)
            if problem:
                items.append({**item, "status": "skipped", "error": problem})
                print(f"[skip] {op} {section.noun} '{change.get('name')}': {problem}", flush=True)
                continue
            if dry_run:
                items.append({**item, "status": "planned"})
                print(f"[plan] {op} {section.noun} '{change.get('name')}'", flush=True)
                continue
            try:
                section.apply(provider, change, current[kind])
                items.append({**item, "status": "applied"})
                applied.append(change)
                print(f"[ok] {op} {section.noun} '{change.get('name')}'", flush=True)
            except (requests.RequestException, ProviderError) as exc:
                failed += 1
                items.append({**item, "status": "error", "error": str(exc)})
                print(f"[error] {op} {section.noun} '{change.get('name')}': {exc}", flush=True)
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
            if op == "create":
                term = provider.create_term(kind, _term_name(change))
                current[kind][term.id or str(change["id"])] = {"id": term.id, "name": term.name}
            elif op == "rename":
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
            applied.append({**change, "to": _term_name(change), "target_name": str(change.get("target_name") or "")})
            print(f"[ok] {op} {kind} '{change.get('name')}'", flush=True)
        except (requests.RequestException, ProviderError) as exc:
            failed += 1
            items.append({**item, "status": "error", "error": str(exc)})
            print(f"[error] {op} {kind} '{change.get('name')}': {exc}", flush=True)

    cookbooks = {"repointed": 0, "failed": 0}
    if merged_ids:
        manager = TaxonomyDuplicatesManager(client, kinds=["tags", "categories"])
        cookbooks = manager.repoint_cookbooks(merged_ids, executable=True)

    emit_items("taxonomy_change", items)
    emit_summary({
        "__title__": "Organize",
        "Changes": len(changes),
        "Applied": len(applied),
        "Skipped": sum(1 for i in items if i["status"] == "skipped"),
        "Failed": failed,
        "Cookbooks Repointed": cookbooks["repointed"],
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
