"""Recipe times across Mealie versions.

Up to 3.28 Mealie keeps prep, total, perform and cook time as text, such as
"PT15M" or "15 minutes". 3.29 adds ``prepTimeSeconds``, ``totalTimeSeconds``
and ``performTimeSeconds``: its migration moves every time it can parse into
seconds and clears the text, and new imports store parseable times only as
seconds. ``cookTime`` stays text.

So a recipe has a time when either form is set, and writes to a 3.29 recipe
set the seconds and clear the text, the way Mealie's own importer does.
Nothing here assumes a version: 3.29 is recognised by the fields being there.
"""

from __future__ import annotations

import re
from typing import Any

TEXT_FIELDS = ("prepTime", "totalTime", "performTime", "cookTime")
# Text field -> its 3.29 seconds field. cookTime has none.
SECONDS_FIELDS = {"prepTime": "prepTimeSeconds", "totalTime": "totalTimeSeconds", "performTime": "performTimeSeconds"}

_ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<d>\d+(?:\.\d+)?)D)?(?:T(?:(?P<h>\d+(?:\.\d+)?)H)?(?:(?P<m>\d+(?:\.\d+)?)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?)?$",
    re.IGNORECASE,
)
_MAX_SECONDS = 2**31 - 1  # Mealie's limit (PostgreSQL INTEGER)


def _seconds_value(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def has_time(recipe: dict[str, Any]) -> bool:
    """True when any time is set, as text (any version) or seconds (3.29+)."""
    if any(str(recipe.get(key) or "").strip() for key in TEXT_FIELDS):
        return True
    return any(_seconds_value(recipe.get(key)) for key in SECONDS_FIELDS.values())


def uses_seconds(recipe: dict[str, Any]) -> bool:
    """True when the recipe comes from a Mealie that has structured times (3.29+)."""
    return any(key in recipe for key in SECONDS_FIELDS.values())


def duration_seconds(text: Any) -> int | None:
    """Seconds for an ISO 8601 duration ("PT1H30M") or a bare number of minutes."""
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        seconds = int(raw) * 60
    else:
        match = _ISO_DURATION_RE.match(raw)
        if not match or not any(match.group(k) for k in "dhms"):
            return None
        parts = {k: float(match.group(k) or 0) for k in "dhms"}
        seconds = round(parts["d"] * 86400 + parts["h"] * 3600 + parts["m"] * 60 + parts["s"])
    return seconds if 0 < seconds <= _MAX_SECONDS else None


def time_fields(field: str, value: str, *, structured: bool) -> dict[str, Any]:
    """The fields to send for one time, given whether the recipe has seconds fields.

    On 3.29+ a parseable time goes in as seconds with the text cleared, and an
    unparseable one as text with the seconds cleared, so the two never disagree.
    Older Mealie gets the text, as before.
    """
    seconds_field = SECONDS_FIELDS.get(field)
    if not structured or seconds_field is None:
        return {field: value}
    seconds = duration_seconds(value)
    if seconds is not None:
        return {seconds_field: seconds, field: None}
    return {field: value, seconds_field: None}
