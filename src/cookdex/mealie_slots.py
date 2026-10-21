"""One cap on parallel Mealie requests, shared by every running job.

Jobs run as separate processes, so the cap is a set of lock files: a request
holds one slot file locked while it waits for Mealie, and the operating system
drops the lock if the job dies. The web UI's runner says where the files are
(``COOKDEX_MEALIE_SLOTS_DIR``) and which lane the job is in
(``COOKDEX_MEALIE_LANE``). Outside the runner (a job run by hand) there is no
shared cap.

Out of ``MEALIE_MAX_PARALLEL_REQUESTS`` slots, the last few are kept for light
jobs, so a quick Organize change never waits behind a long job's requests, and
Mealie never sees more requests at once than one long job sent it on its own.

The web UI's own reads (Organize lists, the overview, status checks) take
slots too, through :func:`use_for_web_ui`. They try the kept slots first, like
a light job, but a page never waits long: after ``UI_MAX_WAIT_SECONDS`` the
request goes ahead without a slot (see :class:`RequestSlots`).
"""
from __future__ import annotations

import contextlib
import logging
import os
import random
import threading
import time
from pathlib import Path
from typing import Callable, Iterator

try:
    import fcntl
except ImportError:  # Windows: only the per-job cap applies.
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

SLOTS_DIR_ENV = "COOKDEX_MEALIE_SLOTS_DIR"
LANE_ENV = "COOKDEX_MEALIE_LANE"
LIMIT_ENV = "MEALIE_MAX_PARALLEL_REQUESTS"

DEFAULT_LIMIT = 8
MAX_LIMIT = 32
LIGHT_RESERVED = 2
LIGHT_PER_JOB = 2

UI = "ui"
# The web UI's own requests: at most this many in flight from the server, and
# never more than this long waiting for a slot.
UI_PER_PROCESS = 6
UI_MAX_WAIT_SECONDS = 2.0


def _limit(raw: str | None) -> int:
    try:
        value = int(str(raw or "").strip())
    except ValueError:
        return DEFAULT_LIMIT
    return min(max(value, 1), MAX_LIMIT)


class RequestSlots:
    """Slots for one process.

    With *max_wait* set, a request that can't get a slot in that time goes
    ahead without one, and :attr:`overflowed` counts how often. The web UI
    uses this: a page that loads two seconds late is better than one that
    hangs behind a long job, and a page load only sends a handful of
    requests, so going over the cap that way stays small. Showing old cached
    lists instead was the other choice, but Organize reads them right after
    applying changes, and stale lists would offer to change entries again
    that are already gone.
    """

    def __init__(self, directory: Path | None, limit: int, lane: str, *, max_wait: float | None = None) -> None:
        self.directory = directory
        self.limit = max(int(limit), 1)
        self.lane = lane
        self.max_wait = max_wait
        self.overflowed = 0
        self._reported_at = 0.0
        reserved = min(LIGHT_RESERVED, self.limit - 1)
        if lane in {"light", UI}:
            # Reserved slots first, then any a long job isn't using.
            self.candidates = list(reversed(range(self.limit)))
            per_job = min(LIGHT_PER_JOB if lane == "light" else UI_PER_PROCESS, self.limit)
        else:
            self.candidates = list(range(self.limit - reserved))
            per_job = len(self.candidates)
        self._local = threading.BoundedSemaphore(per_job)
        if directory is not None and fcntl is not None:
            directory.mkdir(parents=True, exist_ok=True)

    def _try(self, index: int) -> int | None:
        fd = os.open(Path(str(self.directory)) / f"slot-{index}.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return None
        return fd

    def _acquire(self, deadline: float | None) -> int | None:
        delay = 0.02
        while True:
            for index in self.candidates:
                fd = self._try(index)
                if fd is not None:
                    return fd
            pause = delay + random.uniform(0, delay)  # nosec B311 - jitter, not security
            if deadline is not None:
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                pause = min(pause, left)
            time.sleep(pause)
            delay = min(delay * 2, 0.25)

    @contextlib.contextmanager
    def hold(self) -> Iterator[None]:
        deadline = None if self.max_wait is None else time.monotonic() + self.max_wait
        shared = self.directory is not None and fcntl is not None
        local = self._local.acquire(timeout=None if deadline is None else max(deadline - time.monotonic(), 0))
        fd = None
        try:
            if local and shared:
                fd = self._acquire(deadline)
            if not local or (shared and fd is None):
                # Waited max_wait without a slot: go ahead anyway.
                self.overflowed += 1
                now = time.monotonic()
                if now - self._reported_at >= 60:
                    self._reported_at = now
                    logger.info(
                        "Mealie request went ahead without a slot after %.1fs (%d so far): every slot was busy",
                        self.max_wait or 0, self.overflowed,
                    )
            yield
        finally:
            if fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
            if local:
                self._local.release()


_shared: RequestSlots | None = None
_shared_key: tuple[str, str, str] | None = None
_shared_lock = threading.Lock()
# Set by the web UI's server for its own requests (see use_for_web_ui).
_web_ui: tuple[Path, Callable[[], str]] | None = None


def use_for_web_ui(directory: Path | None, limit: Callable[[], str] = lambda: "") -> None:
    """Make this process's Mealie requests take slots as the web UI.

    *limit* returns the current ``MEALIE_MAX_PARALLEL_REQUESTS`` setting, so a
    change in Settings applies without a restart. ``None`` turns it off again.
    """
    global _web_ui, _shared, _shared_key
    with _shared_lock:
        _web_ui = None if directory is None else (directory, limit)
        _shared, _shared_key = None, None


def lane() -> str:
    return os.environ.get(LANE_ENV, "").strip().lower()


def shared() -> RequestSlots | None:
    """This process's slots, or None when not run by the web UI or its runner."""
    global _shared, _shared_key
    if _web_ui is not None:
        key = (str(_web_ui[0]), UI, str(_web_ui[1]() or ""))
    else:
        directory = os.environ.get(SLOTS_DIR_ENV, "").strip()
        if not directory:
            return None
        key = (directory, lane(), os.environ.get(LIMIT_ENV, ""))
    with _shared_lock:
        if _shared is None or _shared_key != key:
            max_wait = UI_MAX_WAIT_SECONDS if key[1] == UI else None
            _shared = RequestSlots(Path(key[0]), _limit(key[2]), key[1], max_wait=max_wait)
            _shared_key = key
        return _shared


@contextlib.contextmanager
def request_slot() -> Iterator[None]:
    slots = shared()
    if slots is None:
        yield
        return
    with slots.hold():
        yield
