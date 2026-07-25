from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException


class LoginRateLimiter:
    """Sliding-window rate limiter for login attempts.

    Attempts are counted per username and, with a much larger allowance, per
    client IP. Behind a reverse proxy every request carries the proxy's
    address, so a single tight IP bucket would let a few failures lock out
    every user at once. The per-username bucket keeps a targeted lockout on
    the account actually being guessed, while the looser IP bucket still
    caps credential stuffing that sprays many usernames from one source.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        ip_max_attempts: int | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.ip_max_attempts = ip_max_attempts if ip_max_attempts is not None else max_attempts * 10
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _keys(self, client_ip: str, username: str | None) -> list[tuple[str, int]]:
        keys = [(f"ip:{client_ip}", self.ip_max_attempts)]
        if username:
            keys.append((f"user:{username.casefold()}", self.max_attempts))
        return keys

    def _sweep(self, now: float) -> None:
        """Drop buckets with no attempts left in the window.

        Without this the dict grows one permanent entry per distinct client
        IP and username ever seen.
        """
        cutoff = now - self.window_seconds
        for key in [k for k, times in self._attempts.items() if not any(t > cutoff for t in times)]:
            del self._attempts[key]

    def check(self, client_ip: str, username: str | None = None) -> None:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._sweep(now)
            for key, limit in self._keys(client_ip, username):
                attempts = [t for t in self._attempts.get(key, []) if t > cutoff]
                if attempts:
                    self._attempts[key] = attempts
                if len(attempts) >= limit:
                    raise HTTPException(
                        status_code=429,
                        detail="Too many login attempts. Try again later.",
                    )

    def record_failure(self, client_ip: str, username: str | None = None) -> None:
        with self._lock:
            now = time.monotonic()
            for key, _limit in self._keys(client_ip, username):
                self._attempts[key].append(now)

    def clear(self, client_ip: str, username: str | None = None) -> None:
        with self._lock:
            for key, _limit in self._keys(client_ip, username):
                self._attempts.pop(key, None)


class ActionRateLimiter:
    """Simple per-key rate limiter for sensitive operations."""

    def __init__(self, max_per_minute: int = 30) -> None:
        self.max_per_minute = max_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            cutoff = now - 60
            # Drop idle buckets so the dict stays bounded.
            for stale in [k for k, times in self._hits.items() if not any(t > cutoff for t in times)]:
                del self._hits[stale]
            hits = [t for t in self._hits.get(key, []) if t > cutoff]
            hits.append(now)
            self._hits[key] = hits
            if len(hits) > self.max_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please slow down.",
                )
