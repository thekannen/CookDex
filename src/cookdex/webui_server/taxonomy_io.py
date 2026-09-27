"""Export the live taxonomy to JSON, and turn a JSON file into staged changes.

The bundle's sections use the same names and shapes as the managed files in
``configs/taxonomy`` (``tags``, ``categories``, ``tools``, ``labels``,
``units_aliases``, ``cookbooks``), so each section can be kept in git as its
own file. Cookbook filters are written with names instead of ids, so they work
on another Mealie too.

Importing never writes anything by itself. It compares the file with the
backend and returns ``create``/``update`` changes for Organize to stage, which
the person reviews and applies like any other batch. Nothing is deleted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..organize_apply import _clean_aliases, _same_name
from ..providers import Capability, RecipeProvider
from ..taxonomy_duplicates import normalize_name
from .taxonomy_workspace import STARTER_PACK_FILES, _filter_ids_to_names, _normalize_payload

FORMAT = "cookdex-taxonomy"
SECTIONS = tuple(STARTER_PACK_FILES)  # categories, tags, cookbooks, labels, tools, units_aliases
TERM_SECTIONS = ("tags", "categories", "tools")
MAX_ITEMS = 5000


def _sections(provider: RecipeProvider) -> list[str]:
    caps = provider.capabilities()
    wanted = [kind for kind in TERM_SECTIONS if kind in provider.term_kinds()]
    if Capability.LABELS in caps:
        wanted.append("labels")
    if Capability.UNITS in caps:
        wanted.append("units_aliases")
    if Capability.RULE_COLLECTIONS in caps:
        wanted.append("cookbooks")
    return wanted


def export_taxonomy(provider: RecipeProvider) -> dict[str, Any]:
    info = provider.health()
    document: dict[str, Any] = {
        "format": FORMAT,
        "version": 1,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": f"{info.name} {info.version}".strip(),
    }
    sections = _sections(provider)
    names_by_id: dict[str, dict[str, str]] = {}
    for kind in TERM_SECTIONS:
        if kind in sections:
            terms = sorted(provider.list_terms(kind), key=lambda t: t.name.lower())
            document[kind] = [{"name": t.name} for t in terms]
            names_by_id[kind] = {t.id.lower(): t.name for t in terms}
    if "labels" in sections:
        labels = provider.list_labels()
        document["labels"] = [{"name": label.name, "color": label.color} for label in labels]
        names_by_id["labels"] = {label.id.lower(): label.name for label in labels}
    if "units_aliases" in sections:
        units = []
        for unit in provider.list_units():
            entry: dict[str, Any] = {"name": unit.name}
            if unit.abbreviation:
                entry["abbreviation"] = unit.abbreviation
            if unit.plural_name:
                entry["pluralName"] = unit.plural_name
            entry["aliases"] = list(unit.aliases)
            units.append(entry)
        document["units_aliases"] = units
    if "cookbooks" in sections:
        document["cookbooks"] = [
            {
                "name": c.name,
                "description": c.description,
                "queryFilterString": _filter_ids_to_names(c.rule, names_by_id) if c.rule else "",
                "public": c.public,
                "position": c.position,
            }
            for c in sorted(provider.list_collections(), key=lambda c: (c.position, c.name.lower()))
        ]
        # Filters that still hold ids name something that no longer exists.
        stale = [c["name"] for c in document["cookbooks"] if ".id " in c["queryFilterString"]]
        if stale:
            document["warnings"] = [
                f"{len(stale)} cookbook filter(s) point at tags, categories, tools or labels that no longer exist, "
                f"so they were exported with ids and won't work on another server: {', '.join(stale)}."
            ]
    return document


def read_document(document: Any, filename: str = "") -> dict[str, list[dict[str, Any]]]:
    """Normalize an uploaded bundle, or one managed file named like ``tags.json``."""
    if isinstance(document, list):
        stem = filename.rsplit("/", 1)[-1].removesuffix(".json")
        if stem not in SECTIONS:
            raise ValueError(
                f"Couldn't tell what \"{filename or 'this file'}\" holds. Name it after a section "
                f"({', '.join(f'{s}.json' for s in SECTIONS)}), or export a bundle from Organize."
            )
        document = {stem: document}
    if not isinstance(document, dict):
        raise ValueError("That isn't a CookDex taxonomy file.")
    found = {section: document[section] for section in SECTIONS if section in document}
    if not found:
        raise ValueError(f"No taxonomy sections found. Expected one of: {', '.join(SECTIONS)}.")
    sections = {section: _normalize_payload(section, raw) for section, raw in found.items()}
    if sum(len(items) for items in sections.values()) > MAX_ITEMS:
        raise ValueError(f"That file has more than {MAX_ITEMS} entries. Import it in parts.")
    return sections


def _slug(kind: str, name: str) -> str:
    return f"new-{kind}-{normalize_name(name).replace(' ', '-')}"


def plan_import(provider: RecipeProvider, sections: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Changes that would bring the backend in line with the file, without deleting anything."""
    supported = _sections(provider)
    changes: list[dict[str, Any]] = []
    summary: dict[str, dict[str, int]] = {}
    skipped = [section for section in sections if section not in supported]

    def tally(kind: str, key: str) -> None:
        summary.setdefault(kind, {"new": 0, "updated": 0, "unchanged": 0})[key] += 1

    for kind in TERM_SECTIONS:
        if kind not in sections or kind not in supported:
            continue
        existing = [t.name for t in provider.list_terms(kind)]
        for entry in sections[kind]:
            if any(_same_name(name, entry["name"]) for name in existing):
                tally(kind, "unchanged")
                continue
            existing.append(entry["name"])
            changes.append({"op": "create", "kind": kind, "id": _slug(kind, entry["name"]), "name": entry["name"],
                            "to": {"name": entry["name"]}})
            tally(kind, "new")

    if "labels" in sections and "labels" in supported:
        by_key = {normalize_name(label.name): label for label in provider.list_labels()}
        seen: set[str] = set()
        for entry in sections["labels"]:
            key = normalize_name(entry["name"])
            label = by_key.get(key)
            if key in seen:
                continue
            seen.add(key)
            if label is None:
                changes.append({"op": "create", "kind": "labels", "id": _slug("labels", entry["name"]), "name": entry["name"],
                                "to": {"name": entry["name"], "color": entry["color"]}})
                tally("labels", "new")
            elif label.color.lower() != str(entry["color"]).lower():
                changes.append({"op": "update", "kind": "labels", "id": label.id, "name": label.name,
                                "to": {"name": label.name, "color": entry["color"]}})
                tally("labels", "updated")
            else:
                tally("labels", "unchanged")

    if "units_aliases" in sections and "units_aliases" in supported:
        units = {normalize_name(unit.name): unit for unit in provider.list_units()}
        seen = set()
        for entry in sections["units_aliases"]:
            key = normalize_name(entry["name"])
            unit = units.get(key)
            if key in seen:
                continue
            seen.add(key)
            abbreviation = str(entry.get("abbreviation") or "")
            plural = str(entry.get("pluralName") or "")
            if unit is None:
                aliases = _clean_aliases(entry.get("aliases"), entry["name"], abbreviation, plural)
                changes.append({"op": "create", "kind": "units", "id": _slug("units", entry["name"]), "name": entry["name"],
                                "to": {"name": entry["name"], "abbreviation": abbreviation, "plural_name": plural, "aliases": aliases}})
                tally("units", "new")
                continue
            # Fill gaps and add aliases; never clear what the unit already has.
            new_abbreviation = unit.abbreviation or abbreviation
            new_plural = unit.plural_name or plural
            aliases = _clean_aliases([*unit.aliases, *(entry.get("aliases") or [])], unit.name, new_abbreviation, new_plural)
            if (new_abbreviation, new_plural, aliases) != (unit.abbreviation, unit.plural_name, unit.aliases):
                changes.append({"op": "update", "kind": "units", "id": unit.id, "name": unit.name,
                                "to": {"name": unit.name, "abbreviation": new_abbreviation, "plural_name": new_plural, "aliases": aliases}})
                tally("units", "updated")
            else:
                tally("units", "unchanged")

    if "cookbooks" in sections and "cookbooks" in supported:
        collections = provider.list_collections()
        names_by_id: dict[str, dict[str, str]] = {
            kind: {t.id.lower(): t.name for t in provider.list_terms(kind)} for kind in TERM_SECTIONS if kind in supported
        }
        if "labels" in supported:
            names_by_id["labels"] = {label.id.lower(): label.name for label in provider.list_labels()}
        by_key = {normalize_name(c.name): c for c in collections}
        for entry in sections["cookbooks"]:
            fields = {
                "name": entry["name"],
                "description": str(entry.get("description") or ""),
                "rule": str(entry.get("queryFilterString") or ""),
                "public": bool(entry.get("public")),
                "position": int(entry.get("position") or 0),
            }
            current = by_key.get(normalize_name(entry["name"]))
            if current is None:
                changes.append({"op": "create", "kind": "cookbooks", "id": _slug("cookbooks", entry["name"]),
                                "name": entry["name"], "to": fields})
                tally("cookbooks", "new")
                continue
            live_rule = _filter_ids_to_names(current.rule, names_by_id) if current.rule else ""
            if (live_rule, current.description, current.public) != (fields["rule"], fields["description"], fields["public"]):
                changes.append({"op": "update", "kind": "cookbooks", "id": current.id, "name": current.name,
                                "to": {**fields, "name": current.name, "position": current.position}})
                tally("cookbooks", "updated")
            else:
                tally("cookbooks", "unchanged")

    return {"changes": changes, "summary": summary, "skipped_sections": skipped}
