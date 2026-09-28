"""Recipe importer — sends verified URLs to the recipe manager for scraping."""

from __future__ import annotations

import logging
import threading
from typing import Optional, Set, Tuple

from ..providers import RecipeProvider
from .rate_limiter import RateLimiter
from .storage import DredgerStore
from .url_utils import canonicalize_url

logger = logging.getLogger("dredger")


class ImportManager:
    def __init__(
        self,
        provider: RecipeProvider,
        store: DredgerStore,
        rate_limiter: RateLimiter,
        dry_run: bool = True,
        precheck_duplicates: bool = True,
    ) -> None:
        # The provider's client should not retry by itself: a failed import
        # goes to the dredger's own retry queue, which spaces attempts out
        # across runs (see build_import_provider).
        self.provider = provider
        self.store = store
        self.rate_limiter = rate_limiter
        self.dry_run = dry_run
        self.precheck_duplicates = precheck_duplicates

        self._known_source_urls: Set[str] = set()
        self._source_index_loaded = False
        self._source_index_failed = False
        self._source_lock = threading.Lock()

    def _load_existing_sources(self) -> None:
        if self._source_index_loaded or self._source_index_failed:
            return
        try:
            sources = self.provider.recipe_source_urls()
        except Exception as exc:
            logger.warning(f"Duplicate precheck unavailable: {exc}")
            self._source_index_failed = True
            return
        self._known_source_urls = {canonical for canonical in map(canonicalize_url, sources) if canonical}
        self._source_index_loaded = True
        logger.debug(f"Duplicate precheck index loaded: {len(self._known_source_urls)} entries")

    def _is_duplicate_source(self, url: str) -> bool:
        if not self.precheck_duplicates:
            return False
        with self._source_lock:
            self._load_existing_sources()
            if self._source_index_failed:
                return False
            canonical = canonicalize_url(url)
            if canonical and canonical in self._known_source_urls:
                logger.debug(f"Duplicate source URL, skipping: {url}")
                return True
        return False

    def _remember(self, url: str) -> None:
        canonical = canonicalize_url(url)
        if canonical:
            with self._source_lock:
                self._known_source_urls.add(canonical)

    def import_recipe(self, url: str) -> Tuple[bool, Optional[str], bool]:
        """Import a recipe URL.

        Returns (success, error_message, is_transient_error).
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] Would import: {url}")
            return True, None, False

        try:
            if self._is_duplicate_source(url):
                return False, "duplicate", False
            outcome = self.provider.import_recipe_url(url)
        except Exception as exc:
            return False, str(exc), False

        if outcome.imported:
            self._remember(url)
            logger.debug(f"Imported: {url}")
            return True, None, False
        if outcome.duplicate:
            self._remember(url)
            logger.debug(f"Duplicate (already in the library): {url}")
            return False, "duplicate", False
        return False, outcome.error, outcome.retry_later


def build_import_provider(env: dict[str, str], import_timeout: int = 20) -> RecipeProvider:
    """The configured backend, with a client that doesn't retry on its own."""
    from ..providers import get_provider

    return get_provider(env, retries=0, timeout_seconds=import_timeout)
