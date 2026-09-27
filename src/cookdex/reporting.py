"""Structured run results.

Task modules report what they did with :func:`emit_summary`. It prints the
``[summary] {json}`` line the log view already understands, and when the web
UI's runner has set ``COOKDEX_RESULT_PATH`` it also appends the summary to that
file as one JSON line. The runner reads the file when the run ends and stores
the results with the run, so they don't depend on parsing (or keeping) logs.

Child processes inherit the variable, so every stage of a pipeline run writes
to the same file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

RESULT_PATH_ENV = "COOKDEX_RESULT_PATH"


def _source() -> str:
    """Name the module that produced a summary, e.g. ``cookdex.recipe_junk_filter``."""
    main = sys.modules.get("__main__")
    spec = getattr(main, "__spec__", None)
    name = getattr(spec, "name", "") or ""
    if name.endswith(".__main__"):
        name = name[: -len(".__main__")]
    return name or Path(sys.argv[0] if sys.argv else "").stem


def record_summary(summary: dict[str, Any]) -> None:
    """Append *summary* to the run's result file, if the runner asked for one."""
    path = os.environ.get(RESULT_PATH_ENV, "").strip()
    if not path:
        return
    entry = {"source": _source(), "summary": summary}
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[warn] Could not record run result: {exc}", flush=True)


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
        if isinstance(entry, dict) and isinstance(entry.get("summary"), dict):
            results.append({"source": str(entry.get("source") or ""), "summary": entry["summary"]})
    return results
