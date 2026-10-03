"""Recipe Dredger — discover and import recipes from curated sites.

Entry point for ``python -m cookdex.recipe_dredger``.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import random
from typing import Optional, Tuple
from urllib.parse import urlparse

from .crawler import SitemapCrawler
from .importer import ImportManager, build_import_provider
from .rate_limiter import RateLimiter, get_crawl_session
from .sites import DEFAULT_SITES
from .storage import DredgerStore
from .url_utils import canonicalize_url
from .verifier import RecipeVerifier
from ..reporting import emit_items, emit_summary

logger = logging.getLogger("dredger")


# ---------------------------------------------------------------------------
# Logging setup — silence library noise, keep dredger at DEBUG for internal
# use but route all user-facing output through _log() / print().
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.WARNING)
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)
    logging.getLogger("chardet").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _log(tag: str, msg: str) -> None:
    """Print a CookDex-format log line."""
    print(f"[{tag}] {msg}", flush=True)


def _site_label(url: str) -> str:
    """Extract a short label from a site URL."""
    return urlparse(url).hostname or url


def _add_imported(store: DredgerStore, url_key: str, *, dry_run: bool) -> None:
    if not dry_run:
        store.add_imported(url_key)


def _add_reject(store: DredgerStore, url_key: str, reason: str, *, dry_run: bool) -> None:
    if not dry_run:
        store.add_reject(url_key, reason)


def _add_retry(store: DredgerStore, url: str, reason: str, *, dry_run: bool, increment: bool = False) -> int:
    # Takes the URL as found, not its canonical key: the retry fetches it again.
    if dry_run:
        return 0
    return store.add_retry(url, reason, increment=increment)


def _remove_retry(store: DredgerStore, url_key: str, *, dry_run: bool) -> None:
    if not dry_run:
        store.remove_retry(url_key)


# Failed imports in a row, all Mealie's doing, before the run stops.
MEALIE_FAILURE_THRESHOLD = 5


class _MealieBreaker:
    """Stops the run when Mealie keeps failing imports.

    A timeout, connection error or 5xx from an import means Mealie is down or
    struggling rather than anything being wrong with the recipe, so carrying
    on would only fill the retry queue.
    """

    def __init__(self, threshold: int = MEALIE_FAILURE_THRESHOLD) -> None:
        self.threshold = threshold
        self.streak = 0
        self.tripped = False

    def record(self, *, mealie_failed: bool) -> None:
        self.streak = self.streak + 1 if mealie_failed else 0
        if self.threshold > 0 and self.streak >= self.threshold and not self.tripped:
            self.tripped = True
            _log("error", f"Mealie failed {self.streak} imports in a row — stopping the run")


def _site_trouble(error: Optional[str]) -> bool:
    """Verify failures that say the site is blocking or struggling, rather
    than that the page isn't a recipe."""
    return bool(error) and str(error).startswith(("HTTP 403", "HTTP 429", "HTTP 5", "Timeout", "Connection error"))


# ---------------------------------------------------------------------------
# Retry queue processing
# ---------------------------------------------------------------------------

def _process_retry_queue(
    store: DredgerStore,
    verifier: RecipeVerifier,
    importer: ImportManager,
    rate_limiter: RateLimiter,
    max_retry_attempts: int,
    dry_run: bool,
    *,
    cap: int,
    breaker: _MealieBreaker,
    found_items: list[dict[str, str]],
) -> Tuple[int, int]:
    """Retry queued URLs, importing at most ``cap``. Returns (imported, errors)."""
    pending = store.get_retry_queue()
    if not pending:
        return 0, 0

    _log("info", f"Processing retry queue: {len(pending)} URL(s)")
    retried = 0
    errors = 0

    for entry in pending:
        if breaker.tripped:
            break
        url_key = entry["url"]
        # Rows from older versions only have the canonical key.
        url = entry.get("original_url") or url_key
        attempts = entry["attempts"]

        if attempts >= max_retry_attempts:
            _remove_retry(store, url_key, dry_run=dry_run)
            _add_reject(store, url_key, "Max retries exceeded", dry_run=dry_run)
            continue
        if retried >= cap:
            continue  # Left queued for the next run.

        rate_limiter.wait_if_needed(url)
        is_recipe, verify_error, verify_transient = verifier.verify_recipe(url)

        if not is_recipe:
            if verify_transient:
                new_attempts = _add_retry(
                    store,
                    url,
                    verify_error or "Transient verification failure",
                    dry_run=dry_run,
                    increment=True,
                )
                if new_attempts >= max_retry_attempts:
                    _remove_retry(store, url_key, dry_run=dry_run)
                    _add_reject(store, url_key, verify_error or "Max retries exceeded (verify)", dry_run=dry_run)
            else:
                _remove_retry(store, url_key, dry_run=dry_run)
                _add_reject(store, url_key, verify_error or "Verification failed", dry_run=dry_run)
            continue

        imported, import_error, import_transient = importer.import_recipe(url)
        breaker.record(mealie_failed=bool(import_transient and not imported))
        if import_error == "duplicate":
            _add_imported(store, url_key, dry_run=dry_run)
            continue
        if imported:
            _add_imported(store, url_key, dry_run=dry_run)
            found_items.append({"url": url, "site": _site_label(url), "status": "planned" if dry_run else "applied"})
            retried += 1
            continue

        errors += 1
        if import_transient:
            # Mealie's failure, not the URL's: keep it queued without using up an attempt.
            _add_retry(store, url, import_error or "Transient import failure", dry_run=dry_run)
        else:
            _remove_retry(store, url_key, dry_run=dry_run)
            _add_reject(store, url_key, import_error or "Import failed", dry_run=dry_run)

    return retried, errors


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    mealie_url = os.environ.get("MEALIE_URL", "").strip()
    mealie_api_key = os.environ.get("MEALIE_API_KEY", "").strip()

    if not mealie_url:
        _log("error", "MEALIE_URL is not configured. Set it in Settings > Connection.")
        return 1
    if not mealie_api_key:
        _log("error", "MEALIE_API_KEY is not configured. Set it in Settings > Connection.")
        return 1

    target_language = os.environ.get("DREDGER_TARGET_LANGUAGE", "en").strip().lower()
    crawl_delay = float(os.environ.get("DREDGER_CRAWL_DELAY", "2.0"))
    cache_expiry_days = int(os.environ.get("DREDGER_CACHE_EXPIRY_DAYS", "7"))

    dry_run = args.dry_run
    # 0 means no per-site limit, like max_total.
    target_count = args.limit if args.limit and args.limit > 0 else 10**9
    max_total = max(0, int(getattr(args, "max_total", 0) or 0))
    scan_depth = args.depth
    force_refresh = args.no_cache
    import_workers = max(1, min(args.workers, 4))
    precheck_duplicates = args.precheck
    language_filter = args.language_filter
    max_retry_attempts = args.max_retries
    site_failure_threshold = 3

    store = DredgerStore()
    session = get_crawl_session()
    rate_limiter = RateLimiter(default_delay=crawl_delay)
    crawler = SitemapCrawler(session, store, cache_expiry_days=cache_expiry_days)
    verifier = RecipeVerifier(
        session,
        target_language=target_language,
        language_filter_enabled=language_filter,
    )
    provider = build_import_provider(dict(os.environ))
    importer = ImportManager(
        provider=provider,
        store=store,
        rate_limiter=rate_limiter,
        dry_run=dry_run,
        precheck_duplicates=precheck_duplicates,
    )

    # Load sites from DB, auto-seed defaults if empty
    sites_list = store.get_enabled_sites()
    if not sites_list:
        # Suggested sources are added switched off: a first run shouldn't
        # crawl dozens of sites nobody chose.
        seeded = store.seed_defaults(DEFAULT_SITES, enabled=False)
        if seeded:
            _log("info", f"Added {seeded} suggested recipe sites, switched off")

    if not sites_list:
        _log("error", "No recipe sources are switched on. Choose some on the Discover page.")
        return 1

    # One quick request before crawling, so an unreachable Mealie or a bad
    # token fails the run now rather than after minutes of scanning. A dry
    # run doesn't import, so it doesn't need Mealie.
    if not dry_run:
        try:
            provider.health()
        except Exception as exc:
            _log("error", f"Can't use Mealie: {exc}")
            return 1

    mode_label = "DRY RUN" if dry_run else "LIVE"
    lang_label = target_language if language_filter else "off"
    _log("start", f"Recipe Dredger — {mode_label}, {len(sites_list)} sites, limit {args.limit or 'none'}/site, lang={lang_label}")

    found_items: list[dict[str, str]] = []
    breaker = _MealieBreaker()

    # Process the retry queue first. It gets one site's share of imports, and
    # what it imports counts toward the overall limit.
    retry_cap = min(target_count, max_total) if max_total else target_count
    retried, retry_errors = _process_retry_queue(
        store, verifier, importer, rate_limiter, max_retry_attempts, dry_run,
        cap=retry_cap, breaker=breaker, found_items=found_items,
    )
    if retried:
        _log("ok", f"Retry queue: {retried} recovered")

    # Set up concurrent import executor
    import_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
    if import_workers > 1 and not dry_run:
        import_executor = concurrent.futures.ThreadPoolExecutor(max_workers=import_workers)

    total_sites = len(sites_list)
    grand_imported = retried
    grand_rejected = 0
    grand_errors = retry_errors

    try:
        random.shuffle(sites_list)

        for site_idx, site in enumerate(sites_list, 1):
            if breaker.tripped:
                break
            label = _site_label(site)
            site_stats = {"imported": 0, "rejected": 0, "errors": 0}
            # An overall cap keeps one run from flooding the library: each site
            # gets at most what's left of it.
            if max_total and grand_imported >= max_total:
                _log("info", f"Reached the limit of {max_total} new recipes for this run")
                break
            site_target = min(target_count, max_total - grand_imported) if max_total else target_count

            raw_candidates = crawler.get_urls_for_site(site, force_refresh=force_refresh)
            sitemap_error = getattr(crawler, "last_error", "")
            if sitemap_error:
                grand_errors += 1
                _log("error", f"[{site_idx}/{total_sites}] {label} — {sitemap_error}")
            if not raw_candidates:
                if not sitemap_error:
                    _log("skip", f"[{site_idx}/{total_sites}] {label} — no URLs in sitemap")
                continue

            candidates = raw_candidates[:scan_depth]
            random.shuffle(candidates)

            # Loaded once per site rather than queried per candidate; kept in
            # sync below as URLs are marked during this site's scan.
            known_urls = store.known_urls()

            _log("info", f"[{site_idx}/{total_sites}] {label} — scanning {len(candidates)} URLs")

            imported_count = 0
            checked_count = 0
            skipped_count = 0
            site_failure_streak = 0
            abort_site = False
            pending_imports: dict[concurrent.futures.Future[Tuple[bool, Optional[str], bool]], tuple[str, str]] = {}
            progress_interval = 25

            def record_import(url: str, url_key: str, result: Tuple[bool, Optional[str], bool]) -> None:
                nonlocal imported_count
                imported, import_error, import_transient = result
                breaker.record(mealie_failed=bool(import_transient and not imported))
                if import_error == "duplicate":
                    _add_imported(store, url_key, dry_run=dry_run)
                    return
                if imported:
                    _add_imported(store, url_key, dry_run=dry_run)
                    found_items.append({"url": url, "site": label, "status": "planned" if dry_run else "applied"})
                    site_stats["imported"] += 1
                    imported_count += 1
                    return

                site_stats["errors"] += 1
                if import_transient:
                    # Mealie's failure, not the URL's: queue it without using up an attempt.
                    _add_retry(store, url, import_error or "Transient import failure", dry_run=dry_run)
                else:
                    _add_reject(store, url_key, import_error or "Import failed", dry_run=dry_run)

            def drain_imports(block: bool = False) -> None:
                if not pending_imports:
                    return
                if block:
                    done, _ = concurrent.futures.wait(
                        pending_imports.keys(),
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                else:
                    done = {f for f in pending_imports if f.done()}

                for future in done:
                    url, url_key = pending_imports.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = (False, str(exc), False)
                    record_import(url, url_key, result)

            for candidate in candidates:
                if abort_site or breaker.tripped or imported_count >= site_target:
                    break

                url = candidate.url
                url_key = canonicalize_url(url) or url

                if url_key in known_urls:
                    skipped_count += 1
                    continue
                known_urls.add(url_key)

                rate_limiter.wait_if_needed(url)
                is_recipe, error, is_transient = verifier.verify_recipe(url)
                checked_count += 1

                if checked_count % progress_interval == 0:
                    _log("info", f"[{site_idx}/{total_sites}] {label} — checked {checked_count}, {imported_count} {'found' if dry_run else 'imported'}, {skipped_count} known")

                # A site that blocks or errors on every page is left for this
                # run, instead of costing a request (and a backoff) per URL.
                if not is_recipe and _site_trouble(error):
                    site_failure_streak += 1
                    if site_failure_threshold > 0 and site_failure_streak >= site_failure_threshold:
                        _log("warn", f"{label} — aborting, repeated failures ({error})")
                        abort_site = True
                else:
                    site_failure_streak = 0

                if is_recipe:
                    if import_executor is None:
                        record_import(url, url_key, importer.import_recipe(url))
                        continue

                    # Concurrent import
                    while pending_imports and imported_count + len(pending_imports) >= site_target:
                        drain_imports(block=True)
                    if imported_count >= site_target or breaker.tripped:
                        break

                    future = import_executor.submit(importer.import_recipe, url)
                    pending_imports[future] = (url, url_key)
                    drain_imports(block=False)
                elif str(error).startswith("HTTP 403"):
                    # Not recorded: a block says nothing about the page, and
                    # a later scan will offer it again.
                    pass
                elif is_transient:
                    _add_retry(
                        store,
                        url,
                        error or "Transient verification failure",
                        dry_run=dry_run,
                        increment=True,
                    )
                else:
                    _add_reject(store, url_key, error or "Not a recipe", dry_run=dry_run)
                    site_stats["rejected"] += 1

            # Drain remaining concurrent imports
            while pending_imports:
                drain_imports(block=True)

            grand_imported += site_stats["imported"]
            grand_rejected += site_stats["rejected"]
            grand_errors += site_stats["errors"]

            parts = []
            if site_stats["imported"]:
                parts.append(f"{site_stats['imported']} {'found' if dry_run else 'imported'}")
            if site_stats["rejected"]:
                parts.append(f"{site_stats['rejected']} rejected")
            if site_stats["errors"]:
                parts.append(f"{site_stats['errors']} errors")
            status = ", ".join(parts) if parts else "nothing new"
            _log("ok", f"[{site_idx}/{total_sites}] {label} — {status}")

    finally:
        if import_executor is not None:
            import_executor.shutdown(wait=False, cancel_futures=True)

    _log("done", f"Dredge complete — {grand_imported} {'found' if dry_run else 'imported'}, {grand_rejected} rejected, {grand_errors} errors")
    emit_items("recipe_import", found_items)
    emit_summary({
        "__title__": "Recipe Dredger",
        "Mode": "Dry Run" if dry_run else "Live Import",
        "Sites Scanned": total_sites,
        "Recipes Found" if dry_run else "Recipes Imported": grand_imported,
        "Rejected": grand_rejected,
        "Errors": grand_errors,
        "Retry Queue": store.retry_count(),
        "Language": lang_label,
    })
    # Exit 1 when the run failed at its job: Mealie stopped answering, or
    # imports were tried and none worked. A run that imported something, or
    # found nothing new to import, succeeded; the URLs that failed wait in the
    # retry queue or the rejects.
    if breaker.tripped or (grand_errors and not grand_imported):
        return 1
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recipe Dredger")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Scan without importing")
    parser.add_argument("--limit", type=int, default=50, help="Recipes to import per site (0 = no per-site limit)")
    parser.add_argument("--max-total", type=int, default=0, help="Stop after this many recipes across all sites (0 = no overall limit)")
    parser.add_argument("--depth", type=int, default=1000, help="URLs to scan per site")
    parser.add_argument("--no-cache", action="store_true", default=False, help="Force fresh crawl")
    parser.add_argument("--workers", type=int, default=2, help="Concurrent import workers (1-4)")
    parser.add_argument("--no-precheck", action="store_true", default=False, help="Disable duplicate precheck")
    parser.add_argument("--no-language-filter", action="store_true", default=False, help="Disable language filtering")
    parser.add_argument(
        "--max-retries", type=int, default=3,
        help="Failed checks of a URL, the first included, before it is given up on",
    )
    return parser


def main() -> None:
    _configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    # Invert negative flags for clarity
    args.precheck = not args.no_precheck
    args.language_filter = not args.no_language_filter
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
