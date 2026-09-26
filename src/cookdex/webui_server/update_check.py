"""Anonymous, cached release checks; request handlers never wait on GitHub."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from threading import Lock

import requests

from .. import _read_version

RELEASE_API = "https://api.github.com/repos/thekannen/CookDex/releases/latest"
RELEASE_ROOT = "https://github.com/thekannen/CookDex/releases/tag/"
CACHE_SECONDS = 24 * 60 * 60
logger = logging.getLogger(__name__)


def calver(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v?(\d{4})\.(\d{1,2})\.(\d+)", str(value))
    if not match:
        return None
    version = tuple(int(part) for part in match.groups())
    return version if 1 <= version[1] <= 12 else None


class UpdateChecker:
    def __init__(self, enabled, *, current=None):
        self.enabled = enabled
        self.current = current or _read_version()
        self._next_check = 0.0
        self._lock = Lock()
        self._status = self._unknown()

    def _unknown(self):
        return dict(current=self.current, latest=None, update_available=False,
                    release_url=None, checked_at=None)

    def status(self):
        if not self.enabled():
            return self._unknown()
        with self._lock:
            return dict(self._status)

    def check(self):
        if not self.enabled() or time.monotonic() < self._next_check:
            return
        # Only the background loop calls check. Cache failures as well as success.
        self._next_check = time.monotonic() + CACHE_SECONDS
        status = self._unknown()
        status['checked_at'] = datetime.now(timezone.utc).isoformat()
        try:
            with requests.Session() as session:
                # No local credentials, cookies, .netrc, or proxy authentication.
                session.trust_env = False
                response = session.get(RELEASE_API, timeout=5, allow_redirects=False,
                                       headers={'User-Agent': f'CookDex/{self.current}',
                                                'Accept': 'application/vnd.github+json'})
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError('Unexpected release response')
                release = response.json()
            tag = release.get('tag_name', '')
            latest = calver(tag)
            current = calver(self.current)
            if latest is None or current is None or release.get('draft') or release.get('prerelease'):
                raise ValueError('No stable CalVer release')
            status.update(latest=tag.removeprefix('v'), update_available=latest > current,
                          release_url=RELEASE_ROOT + tag)
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            logger.info('Release check unavailable; retrying after cache interval.')
        with self._lock:
            self._status = status

    async def run(self):
        while True:
            await asyncio.to_thread(self.check)
            await asyncio.sleep(60)
