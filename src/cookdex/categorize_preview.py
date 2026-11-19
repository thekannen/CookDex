"""Keep the AI categorizer's work so a preview doesn't have to be paid for twice.

Two stores, both next to the categorizer's cache file:

``suggestions_<provider>.json``
    What the AI suggested for each recipe, keyed by everything the prompt was
    built from: the recipe text it saw, the category/tag/tool lists it chose
    from, the provider and model, and the prompt version. A later run whose
    prompt for a recipe would be identical reuses the answer instead of asking
    again. Change the recipe, the lists or the model and the key no longer
    matches, so the AI is asked again.

``categorize_previews/<run_id>.json``
    The changes a preview run planned, recipe by recipe, with a fingerprint of
    each recipe as the preview saw it. Applying a reviewed preview reads this
    file and writes only those changes, after checking each recipe is still
    the one that was previewed. No AI calls are made.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

# Bump when the prompts change, so old answers aren't reused for new prompts.
PROMPT_VERSION = 1
SUGGESTION_MAX_AGE_SECONDS = 90 * 24 * 3600
PREVIEW_MAX_AGE_SECONDS = 30 * 24 * 3600
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")
FIELDS = ("categories", "tags", "tools")


def digest(*parts: Any) -> str:
    text = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def valid_run_id(value: object) -> bool:
    return isinstance(value, str) and bool(RUN_ID_RE.match(value))


def _write_json(path: Path, data: Any) -> None:
    """Write through a temp file so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.replace(tmp, path)


class SuggestionCache:
    """Thread-safe store of AI suggestions, keyed per recipe by prompt input."""

    def __init__(self, path: Path, log=print) -> None:
        self.path = Path(path)
        self.log = log
        self.lock = threading.Lock()
        self.enabled = True
        self.dirty = False
        self.entries: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, ValueError) as exc:
            self.log(f"[warn] Ignoring saved AI suggestions in '{self.path}': {exc}")
            return {}
        if not isinstance(raw, dict):
            return {}
        cutoff = time.time() - SUGGESTION_MAX_AGE_SECONDS
        entries = {}
        for slug, entry in raw.items():
            if isinstance(entry, dict) and isinstance(entry.get("key"), str) and float(entry.get("at") or 0) >= cutoff:
                entries[slug] = entry
        return entries

    def get(self, slug: str, key: str) -> dict[str, list[str]] | None:
        with self.lock:
            entry = self.entries.get(slug)
        if not entry or entry.get("key") != key:
            return None
        return {field: [str(name) for name in entry.get(field) or []] for field in FIELDS}

    def put(self, slug: str, key: str, categories, tags, tools) -> None:
        if not (categories or tags or tools):
            # An empty answer may be a miss; let the next run ask again.
            return
        with self.lock:
            self.entries[slug] = {
                "key": key,
                "at": time.time(),
                "categories": list(categories or []),
                "tags": list(tags or []),
                "tools": list(tools or []),
            }
            self.dirty = True

    def save(self) -> None:
        with self.lock:
            if not self.enabled or not self.dirty:
                return
            try:
                _write_json(self.path, self.entries)
                self.dirty = False
            except OSError as exc:
                self.enabled = False
                self.log(f"[warn] Can't save AI suggestions to '{self.path}', so a later run will ask again: {exc}")


def preview_dir(cache_file: Path) -> Path:
    return Path(cache_file).parent / "categorize_previews"


def save_preview(cache_file: Path, run_id: str, record: dict[str, Any], log=print) -> None:
    if not valid_run_id(run_id):
        return
    folder = preview_dir(cache_file)
    try:
        _write_json(folder / f"{run_id}.json", {**record, "run_id": run_id, "created_at": time.time()})
    except OSError as exc:
        log(f"[warn] Can't save this preview, so it can't be applied from the review: {exc}")
        return
    cutoff = time.time() - PREVIEW_MAX_AGE_SECONDS
    for path in folder.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def load_preview(cache_file: Path, run_id: str) -> dict[str, Any] | None:
    if not valid_run_id(run_id):
        return None
    path = preview_dir(cache_file) / f"{run_id}.json"
    try:
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or not isinstance(record.get("items"), list):
        return None
    return record
