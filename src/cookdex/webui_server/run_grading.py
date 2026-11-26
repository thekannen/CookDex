"""Whether a run that exited cleanly did everything it set out to.

Jobs mark what needs a person's attention in their log and results:
``[error]`` and ``[warn]`` lines, items they skipped or couldn't change (with
the reason), and a ``__warning__`` in their summary. Retries that may still
succeed are logged as ``[retry]`` instead, so they don't count.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_LINE = re.compile(r"^\[(error|warn|warning)\]\s*(.*)$")
_MAX_LOG_BYTES = 50 * 1024 * 1024


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _log_problems(log_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if not log_path.is_file() or log_path.stat().st_size > _MAX_LOG_BYTES:
            return errors, warnings
        with log_path.open(encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                match = _LINE.match(raw.strip())
                if not match or not match.group(2).strip():
                    continue
                (errors if match.group(1) == "error" else warnings).append(match.group(2).strip())
    except OSError:
        pass
    return errors, warnings


def grade_run(log_path: Path, results: list[dict[str, Any]] | None) -> dict[str, Any]:
    """``{"errors": n, "error_text": str, "warning_text": str}`` for a finished run."""
    errors, log_warnings = _log_problems(log_path)
    declared: list[str] = []
    item_problems = 0
    for entry in results or []:
        summary = entry.get("summary")
        if isinstance(summary, dict) and str(summary.get("__warning__") or "").strip():
            declared.append(str(summary["__warning__"]).strip())
        for item in entry.get("items") or []:
            if not isinstance(item, dict):
                continue
            # A skip the person chose (left unticked) isn't a problem; one with a reason is.
            if item.get("status") == "error" or (item.get("status") == "skipped" and item.get("error")):
                item_problems += 1

    error_text = ""
    if errors:
        error_text = f"Finished, but reported {_plural(len(errors), 'error', 'errors')}. First: {errors[0]}"

    parts = list(dict.fromkeys(declared))
    if item_problems:
        parts.append(f"{_plural(item_problems, 'change was', 'changes were')} skipped or didn't go through.")
    if log_warnings:
        parts.append(f"{_plural(len(log_warnings), 'warning', 'warnings')} in the log. First: {log_warnings[0]}")
    return {"errors": len(errors), "error_text": error_text, "warning_text": " ".join(parts)}
