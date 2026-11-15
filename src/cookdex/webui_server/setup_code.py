"""One-time code that proves host access during first-time setup.

While no account exists, anyone who can reach CookDex could otherwise create
the owner account. The code is printed only to the server log, which only
someone with access to the host (a terminal, or the Logs tab in Docker
Desktop, Portainer or Unraid) can read.
"""

from __future__ import annotations

import hmac
import secrets
import time
from threading import Lock

# No 0/O or 1/I/L, so the code survives being read off a screen and typed.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LENGTH = 12  # about 59 bits: far beyond guessing over the network
GROUP = 4
REPRINT_SECONDS = 60


def _normalize(value: str) -> str:
    # Ignore case and the separators people type or paste; keep everything
    # else so stray characters make the code wrong rather than vanish.
    return "".join(ch for ch in str(value or "").upper() if ch not in " -\t")


class SetupCode:
    def __init__(self) -> None:
        self._value = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
        self._lock = Lock()
        self._last_printed = float("-inf")

    @property
    def display(self) -> str:
        return "-".join(self._value[i : i + GROUP] for i in range(0, LENGTH, GROUP))

    def matches(self, supplied: str) -> bool:
        return hmac.compare_digest(_normalize(supplied).encode("utf-8"), self._value.encode("utf-8"))

    def announce(self, *, force: bool = False) -> bool:
        """Print the code to the log. Throttled unless ``force``."""
        with self._lock:
            now = time.monotonic()
            if not force and now - self._last_printed < REPRINT_SECONDS:
                return False
            self._last_printed = now
        print(
            "[webui] ==============================================\n"
            "[webui]  First-time setup\n"
            f"[webui]  Setup code: {self.display}\n"
            "[webui]  Enter it on the CookDex setup page to create\n"
            "[webui]  the owner account. It changes on every restart.\n"
            "[webui] ==============================================",
            flush=True,
        )
        return True
