"""Validate dependencies before any staged organizer changes are written."""
from typing import Any


def validate_dependencies(changes: list[dict[str, Any]]) -> None:
    removed: set[tuple[str, str]] = set()
    for change in changes:
        key = (str(change.get("kind")), str(change.get("id")))
        if change.get("op") in {"merge", "delete"}:
            removed.add(key)
    for change in changes:
        if change.get("op") == "merge" and (str(change.get("kind")), str(change.get("target_id"))) in removed:
            raise ValueError("A merge target is also being merged or deleted. Keep the target, or choose another one.")
