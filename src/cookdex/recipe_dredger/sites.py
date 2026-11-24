"""Suggested recipe sites for the dredger, and the ones no longer suggested.

Loaded from configs/default_sites.json at runtime and seeded into the
dredger_sites table on first use, switched off. Managed from the Discover page.

Every suggestion records what its terms of use say about automated access and
when that was checked. A site whose terms ban it is never suggested. Sites taken
off the list go in configs/retired_sites.json with the reason, so existing
installs can be told and offered to remove them; nothing is removed for them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_CONFIGS = Path(__file__).resolve().parents[3] / "configs"

# What a suggestion's terms say. Anything else (a ban on automated access, or
# terms we couldn't read) keeps a site off the list.
TERMS_VERDICTS = {
    "no-terms": "No terms, or terms that don't address automated access",
    "ai-only": "Terms restrict only AI training, commercial use or republishing",
    "permissive": "Terms allow personal saving or use",
}

RETIRED_REASONS = {
    "terms": "Its terms of use ban automated access.",
    "terms-unverified": "We couldn't read its terms of use to confirm they allow automated access.",
    "blocked": "It refuses requests from CookDex.",
    "gone": "The site is gone or no longer has recipes to find.",
    "moved": "The site moved to a new address.",
}


def _candidate_paths(name: str) -> list[Path]:
    paths: list[Path] = []
    env_root = os.environ.get("COOKDEX_ROOT", "").strip()
    if env_root:
        paths.append(Path(env_root).expanduser().resolve() / "configs" / name)
    paths.append(_CONFIGS / name)
    return paths


def _load(name: str) -> list[dict[str, Any]]:
    for path in _candidate_paths(name):
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return []


def load_default_sites() -> list[dict[str, Any]]:
    """The suggested sites from the bundled JSON file."""
    return _load("default_sites.json")


def load_retired_sites() -> list[dict[str, Any]]:
    """Sites that used to be suggested, with why they aren't any more."""
    return _load("retired_sites.json")


def site_key(url: str) -> str:
    """Host without www. plus path, so http/https, www and a trailing slash match."""
    parts = urlsplit(url if "://" in url else f"https://{url}")
    host = (parts.hostname or "").lower().removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}"


def list_version(defaults: list[dict[str, Any]] | None = None, retired: list[dict[str, Any]] | None = None) -> str:
    """The date of the latest change to the suggestions: an addition or a retirement."""
    defaults = load_default_sites() if defaults is None else defaults
    retired = load_retired_sites() if retired is None else retired
    dates = [str(entry.get("added") or "") for entry in defaults] + [str(entry.get("retired") or "") for entry in retired]
    return max(dates, default="")


# Backwards-compatible alias — existing code imports DEFAULT_SITES directly.
DEFAULT_SITES: list[dict[str, Any]] = load_default_sites()
