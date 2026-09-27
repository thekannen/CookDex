"""Structured run results.

Task modules report what they did with :func:`emit_summary`. It prints the
``[summary] {json}`` line the log view already understands, and when the web
UI's runner has set ``COOKDEX_RESULT_PATH`` it also appends the summary to that
file as one JSON line. The runner reads the file when the run ends and stores
the results with the run, so they don't depend on parsing (or keeping) logs.

Child processes inherit the variable, so every stage of a pipeline run writes
to the same file.

Long steps report how far along they are with :class:`Progress`, which prints
``[progress] {json}`` lines. The runner keeps the latest one per run in memory
(it doesn't go into the log) and the web UI shows it as a progress bar.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from threading import Lock
from typing import Any

RESULT_PATH_ENV = "COOKDEX_RESULT_PATH"
PROGRESS_PREFIX = "[progress] "
APPLY_PLAN_ENV = "COOKDEX_APPLY_PLAN"


def _source() -> str:
    """Name the module that produced a summary, e.g. ``cookdex.recipe_junk_filter``."""
    main = sys.modules.get("__main__")
    spec = getattr(main, "__spec__", None)
    name = getattr(spec, "name", "") or ""
    if name.endswith(".__main__"):
        name = name[: -len(".__main__")]
    return name or Path(sys.argv[0] if sys.argv else "").stem


def _append_entry(entry: dict[str, Any]) -> None:
    path = os.environ.get(RESULT_PATH_ENV, "").strip()
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[warn] Could not record run result: {exc}", flush=True)


def record_summary(summary: dict[str, Any]) -> None:
    """Append *summary* to the run's result file, if the runner asked for one."""
    _append_entry({"source": _source(), "summary": summary})


def emit_items(kind: str, items: list[dict[str, Any]]) -> None:
    """Record the individual changes a run planned or made.

    *kind* names the item shape the UI renders, for example ``recipe_delete``
    (slug, name, reason, group, keep_slug/keep_name for duplicates) or
    ``recipe_rename`` (slug, old_name, new_name). Each item carries a
    ``status``: planned, applied, skipped or error.
    """
    _append_entry({"source": _source(), "kind": kind, "items": list(items)})


def emit_summary(summary: dict[str, Any]) -> None:
    """Print a ``[summary]`` log line and record it as a structured result."""
    line = "[summary] " + json.dumps(summary, default=str)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode(), flush=True)
    record_summary(summary)


def read_results(path: str | Path) -> list[dict[str, Any]]:
    """Read the JSON lines a run recorded. Malformed lines are skipped."""
    results: list[dict[str, Any]] = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return results
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "")
        if isinstance(entry.get("summary"), dict):
            results.append({"source": source, "summary": entry["summary"]})
        elif isinstance(entry.get("items"), list):
            results.append({"source": source, "kind": str(entry.get("kind") or ""), "items": entry["items"]})
    return results


def load_apply_plan(section: str) -> dict[str, Any] | None:
    """Return the approved changes for *section*, or None when no plan was given.

    When the UI applies a reviewed preview it passes exactly the items the
    user approved. Modules then act only on those items, and only if they are
    still candidates, so nothing changes that wasn't reviewed.
    """
    raw = os.environ.get(APPLY_PLAN_ENV, "").strip()
    if not raw:
        return None
    try:
        plan = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError(f"The approved-changes plan is not valid JSON: {exc}") from exc
    if not isinstance(plan, dict):
        raise RuntimeError("The approved-changes plan must be a JSON object.")
    value = plan.get(section)
    if value is None:
        # A plan that omits this section approves nothing in it.
        return {}
    if not isinstance(value, dict):
        raise RuntimeError(f"The approved-changes plan section '{section}' must be an object.")
    return value


class Progress:
    """Report progress through one long step, e.g. checking 12,169 recipes.

    Call :meth:`advance` as items finish (safe from worker threads). A line is
    printed for the first item, the last one, and at most every
    *min_interval* seconds in between.
    """

    def __init__(self, label: str, total: int, *, min_interval: float = 1.0) -> None:
        self.label = label
        self.total = max(0, int(total))
        self.done = 0
        self.min_interval = min_interval
        self._last = 0.0
        self._lock = Lock()
        self._emit()

    def advance(self, count: int = 1) -> None:
        with self._lock:
            self.done = min(self.total, self.done + count) if self.total else self.done + count
            now = time.monotonic()
            if self.done >= self.total or now - self._last >= self.min_interval:
                self._emit(now)

    def _emit(self, now: float | None = None) -> None:
        self._last = now if now is not None else time.monotonic()
        payload = {"label": self.label, "done": self.done, "total": self.total}
        print(PROGRESS_PREFIX + json.dumps(payload), flush=True)
