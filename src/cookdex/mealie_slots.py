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
"""
from __future__ import annotations

import contextlib
import os
import random
import threading
import time
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # Windows: only the per-job cap applies.
    fcntl = None  # type: ignore[assignment]

SLOTS_DIR_ENV = "COOKDEX_MEALIE_SLOTS_DIR"
LANE_ENV = "COOKDEX_MEALIE_LANE"
LIMIT_ENV = "MEALIE_MAX_PARALLEL_REQUESTS"

DEFAULT_LIMIT = 8
MAX_LIMIT = 32
LIGHT_RESERVED = 2
LIGHT_PER_JOB = 2


def _limit(raw: str | None) -> int:
    try:
        value = int(str(raw or "").strip())
    except ValueError:
        return DEFAULT_LIMIT
    return min(max(value, 1), MAX_LIMIT)


class RequestSlots:
    def __init__(self, directory: Path | None, limit: int, lane: str) -> None:
        self.directory = directory
        self.limit = max(int(limit), 1)
        self.lane = lane
        reserved = min(LIGHT_RESERVED, self.limit - 1)
        if lane == "light":
            # Reserved slots first, then any a long job isn't using.
            self.candidates = list(reversed(range(self.limit)))
            per_job = min(LIGHT_PER_JOB, self.limit)
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

    def _acquire(self) -> int:
        delay = 0.02
        while True:
            for index in self.candidates:
                fd = self._try(index)
                if fd is not None:
                    return fd
            time.sleep(delay + random.uniform(0, delay))  # nosec B311 - jitter, not security
            delay = min(delay * 2, 0.25)

    @contextlib.contextmanager
    def hold(self) -> Iterator[None]:
        with self._local:
            if self.directory is None or fcntl is None:
                yield
                return
            fd = self._acquire()
            try:
                yield
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)


_shared: RequestSlots | None = None
_shared_key: tuple[str, str, str] | None = None
_shared_lock = threading.Lock()


def lane() -> str:
    return os.environ.get(LANE_ENV, "").strip().lower()


def shared() -> RequestSlots | None:
    """This process's slots, or None when not run by the web UI's runner."""
    global _shared, _shared_key
    directory = os.environ.get(SLOTS_DIR_ENV, "").strip()
    if not directory:
        return None
    key = (directory, lane(), os.environ.get(LIMIT_ENV, ""))
    with _shared_lock:
        if _shared is None or _shared_key != key:
            _shared = RequestSlots(Path(directory), _limit(key[2]), key[1])
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
