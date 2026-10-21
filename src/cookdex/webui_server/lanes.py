"""Which lane a run uses and what it writes in Mealie.

Runs in the heavy lane go one at a time, as every run used to. The light lane
lets short changes (Organize's deletes and new entries) go while a long job
runs, but only when the two don't write the same things.

A write scope is a set of tokens:

- ``"*"``: anything; overlaps every non-empty scope.
- ``"tags"``: every tag (likewise categories, tools, foods, units, labels,
  cookbooks, recipes, backups).
- ``"tags:dinner"``: the one tag named "dinner" (names are compared lowercase).

An empty scope writes nothing (a preview) and overlaps nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

HEAVY = "heavy"
LIGHT = "light"

EVERYTHING = "*"

# Organize kinds that recipes point at. Anything other than adding one or
# removing one no recipe uses changes what recipes carry, so it waits for jobs
# that write recipes.
_RECIPE_LINKED = {"tags", "categories", "tools", "foods", "units"}


@dataclass(frozen=True)
class RunLane:
    lane: str
    writes: frozenset[str]


def item(kind: str, name: object) -> str:
    return f"{kind}:{str(name or '').strip().lower()}"


def scope(*tokens: str | Iterable[str]) -> frozenset[str]:
    out: set[str] = set()
    for token in tokens:
        if isinstance(token, str):
            out.add(token)
        else:
            out.update(token)
    return frozenset(out)


def _overlap(a: str, b: str) -> bool:
    if a == b:
        return True
    kind_a, _, name_a = a.partition(":")
    kind_b, _, name_b = b.partition(":")
    # "tags" covers "tags:dinner"; two different named tags don't meet.
    return kind_a == kind_b and (not name_a or not name_b)


def overlaps(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    if EVERYTHING in a or EVERYTHING in b:
        return True
    return any(_overlap(x, y) for x in a for y in b)


def organize_writes(changes: list[dict[str, Any]]) -> frozenset[str]:
    """What a list of staged Organize changes writes (see cookdex.organize_apply)."""
    out: set[str] = set()
    for change in changes:
        op, kind = str(change.get("op") or ""), str(change.get("kind") or "")
        out.add(item(kind, change.get("name")))
        to = change.get("to")
        new_name = to.get("name") if isinstance(to, dict) else to
        if new_name:
            out.add(item(kind, new_name))
        if change.get("target_name"):
            out.add(item(kind, change.get("target_name")))
        quiet = op == "create" or (op == "delete" and change.get("unused"))
        if quiet:
            continue
        if kind in _RECIPE_LINKED:
            out.add("recipes")
        if op == "merge":
            # Merges repoint cookbook filters; label merges move foods.
            out.add("cookbooks")
        if kind == "labels" and op in {"merge", "delete"}:
            out.add("foods")
    return frozenset(out)
