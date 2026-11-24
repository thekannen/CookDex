"""Discover's responsible-use terms, which an owner accepts once.

Discover crawls sites the people running CookDex choose, so they are the ones
responsible for following those sites' terms. Until an owner accepts this,
nothing runs the recipe dredger: not a preview, an import, a schedule or an
automation step. Raising ``TERMS_VERSION`` asks owners to accept again.
"""
from __future__ import annotations

from typing import Any

from .state import StateStore, utc_now_iso

DREDGER_TASK = "recipe-dredger"
TERMS_VERSION = 1
_DOC_KEY = "discover_responsible_use"

NOT_ACCEPTED = "An owner has to accept Discover's responsible-use terms on the Discover page first."


def acceptance(state: StateStore) -> dict[str, Any] | None:
    """Who accepted the current terms and when, or None if no one has."""
    record = state.get_document(_DOC_KEY)
    if not isinstance(record, dict) or int(record.get("version") or 0) < TERMS_VERSION:
        return None
    return record


def is_accepted(state: StateStore) -> bool:
    return acceptance(state) is not None


def accept(state: StateStore, username: str) -> dict[str, Any]:
    record = {"version": TERMS_VERSION, "accepted_by": username, "accepted_at": utc_now_iso()}
    state.set_document(_DOC_KEY, record)
    return record


def uses_dredger(task_id: str, options: dict[str, Any] | None) -> bool:
    """Whether a run, or any step of an automation, is the recipe dredger."""
    if task_id == DREDGER_TASK:
        return True
    spec = (options or {}).get("workflow")
    if not isinstance(spec, dict):
        return False
    return any(isinstance(step, dict) and step.get("task_id") == DREDGER_TASK for step in spec.get("steps") or [])


def blocked_reason(state: StateStore, task_id: str, options: dict[str, Any] | None = None) -> str:
    """Why this run can't start yet, or '' if it can."""
    if uses_dredger(task_id, options) and not is_accepted(state):
        return NOT_ACCEPTED
    return ""
