"""Tests for the recipe_dredger package."""

from __future__ import annotations

import sqlite3
import socket
import tempfile
from argparse import Namespace
from pathlib import Path

import pytest
from urllib.parse import urlsplit


# ---------------------------------------------------------------------------
# url_utils
# ---------------------------------------------------------------------------

from cookdex.recipe_dredger.url_utils import canonicalize_url


class TestCanonicalizeUrl:
    def test_strips_www(self):
        assert canonicalize_url("https://www.example.com/foo") == "https://example.com/foo"

    def test_strips_trailing_slash(self):
        assert canonicalize_url("https://example.com/foo/") == "https://example.com/foo"

    def test_root_keeps_slash(self):
        assert canonicalize_url("https://example.com/") == "https://example.com/"

    def test_strips_utm(self):
        result = canonicalize_url("https://example.com/page?utm_source=foo&real=1")
        assert "utm_source" not in result
        assert "real=1" in result

    def test_strips_tracking_keys(self):
        result = canonicalize_url("https://example.com/page?fbclid=abc&q=test")
        assert "fbclid" not in result
        assert "q=test" in result

    def test_empty_returns_empty(self):
        assert canonicalize_url("") == ""
        assert canonicalize_url(None) == ""

    def test_lowercases_scheme_and_host(self):
        assert canonicalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"


# ---------------------------------------------------------------------------
# DredgerStore
# ---------------------------------------------------------------------------

from cookdex.recipe_dredger.storage import DredgerStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_state.db"
        yield DredgerStore(db_path=db_path)


class TestDredgerStoreImported:
    def test_add_and_check(self, store):
        assert not store.is_imported("https://example.com/recipe-1")
        store.add_imported("https://example.com/recipe-1")
        assert store.is_imported("https://example.com/recipe-1")

    def test_count(self, store):
        assert store.imported_count() == 0
        store.add_imported("https://example.com/a")
        store.add_imported("https://example.com/b")
        assert store.imported_count() == 2

    def test_add_removes_from_retry(self, store):
        store.add_retry("https://example.com/a", "transient", increment=True)
        assert store.is_in_retry("https://example.com/a")
        store.add_imported("https://example.com/a")
        assert not store.is_in_retry("https://example.com/a")


class TestDredgerStoreRejects:
    def test_add_and_check(self, store):
        store.add_reject("https://example.com/junk", reason="Not a recipe")
        assert store.is_rejected("https://example.com/junk")
        assert store.rejected_count() == 1

    def test_add_removes_from_retry(self, store):
        store.add_retry("https://example.com/a", "transient")
        store.add_reject("https://example.com/a", "permanent")
        assert not store.is_in_retry("https://example.com/a")


class TestDredgerStoreRetry:
    def test_add_and_increment(self, store):
        attempts = store.add_retry("https://example.com/a", "err", increment=True)
        assert attempts == 1
        attempts = store.add_retry("https://example.com/a", "err2", increment=True)
        assert attempts == 2

    def test_get_retry_queue(self, store):
        store.add_retry("https://example.com/a", "err", increment=True)
        store.add_retry("https://example.com/b", "err2", increment=True)
        queue = store.get_retry_queue()
        assert len(queue) == 2
        urls = {entry["url"] for entry in queue}
        assert "https://example.com/a" in urls or any("example.com/a" in u for u in urls)


class TestDredgerStoreIsKnown:
    def test_imported_is_known(self, store):
        store.add_imported("https://example.com/a")
        assert store.is_known("https://example.com/a")

    def test_rejected_is_known(self, store):
        store.add_reject("https://example.com/b")
        assert store.is_known("https://example.com/b")

    def test_retry_is_known(self, store):
        store.add_retry("https://example.com/c", "err")
        assert store.is_known("https://example.com/c")

    def test_unknown(self, store):
        assert not store.is_known("https://example.com/unknown")


class TestDredgerStoreSitemapCache:
    def test_cache_and_retrieve(self, store):
        store.cache_sitemap("https://example.com", "https://example.com/sitemap.xml", ["url1", "url2"])
        cached = store.get_cached_sitemap("https://example.com")
        assert cached is not None
        assert cached["urls"] == ["url1", "url2"]

    def test_expired_cache_returns_none(self, store):
        store.cache_sitemap("https://example.com", "https://example.com/sitemap.xml", ["url1"])
        result = store.get_cached_sitemap("https://example.com", cache_expiry_days=0)
        # With 0 day expiry, should be expired immediately
        assert result is None


class TestDredgerStoreSites:
    def test_add_and_list(self, store):
        site_id = store.add_site("https://example.com", label="Test", group="General")
        assert site_id > 0
        sites = store.get_all_sites()
        assert len(sites) == 1
        assert sites[0]["url"] == "https://example.com"
        assert sites[0]["group"] == "General"

    def test_strips_trailing_slash(self, store):
        store.add_site("https://example.com/")
        sites = store.get_all_sites()
        assert sites[0]["url"] == "https://example.com"

    def test_duplicate_raises(self, store):
        store.add_site("https://example.com")
        with pytest.raises(sqlite3.IntegrityError):
            store.add_site("https://example.com")

    def test_update(self, store):
        site_id = store.add_site("https://example.com")
        assert store.update_site(site_id, enabled=False)
        sites = store.get_all_sites()
        assert sites[0]["enabled"] == 0

    def test_delete(self, store):
        site_id = store.add_site("https://example.com")
        assert store.delete_site(site_id)
        assert store.sites_count() == 0

    def test_get_enabled_sites(self, store):
        store.add_site("https://enabled.example.com")
        disabled_id = store.add_site("https://disabled.example.com")
        store.update_site(disabled_id, enabled=False)
        enabled = store.get_enabled_sites()
        assert len(enabled) == 1
        assert enabled[0] == "https://enabled.example.com"

    def test_seed_defaults(self, store):
        defaults = [
            {"url": "https://a.com", "group": "General"},
            {"url": "https://b.com", "group": "Asian"},
        ]
        inserted = store.seed_defaults(defaults)
        assert inserted == 2
        assert store.sites_count() == 2

    def test_seed_skips_when_not_empty(self, store):
        store.add_site("https://existing.com")
        inserted = store.seed_defaults([{"url": "https://new.com"}])
        assert inserted == 0
        assert store.sites_count() == 1

    def test_seed_force_replaces(self, store):
        store.add_site("https://existing.example.com")
        inserted = store.seed_defaults([{"url": "https://new.example.com"}], force=True)
        assert inserted == 1
        sites = store.get_enabled_sites()
        assert sites == ["https://new.example.com"]


# ---------------------------------------------------------------------------
# patterns
# ---------------------------------------------------------------------------

from cookdex.recipe_dredger.patterns import (
    LISTICLE_REGEX,
    HOW_TO_COOK_REGEX,
    NON_RECIPE_DIGEST_REGEX,
)


class TestPatterns:
    def test_listicle_matches(self):
        assert LISTICLE_REGEX.search("top 10 recipes for dinner")
        assert LISTICLE_REGEX.search("best appetizer ideas")

    def test_listicle_no_match(self):
        assert not LISTICLE_REGEX.search("chicken tikka masala")

    def test_how_to_matches(self):
        assert HOW_TO_COOK_REGEX.search("how to cook rice")
        assert HOW_TO_COOK_REGEX.search("how to make bread")

    def test_how_to_no_match(self):
        assert not HOW_TO_COOK_REGEX.search("easy chicken recipe")

    def test_digest_matches(self):
        assert NON_RECIPE_DIGEST_REGEX.search("friday finds this week")
        assert NON_RECIPE_DIGEST_REGEX.search("monthly report")


# ---------------------------------------------------------------------------
# Verifier pre-filter
# ---------------------------------------------------------------------------

from cookdex.recipe_dredger.crawler import SitemapCrawler
from cookdex.recipe_dredger.rate_limiter import RateLimiter
from cookdex.recipe_dredger.verifier import RecipeVerifier


class TestVerifierPreFilter:
    def test_rejects_image_url(self):
        v = RecipeVerifier.__new__(RecipeVerifier)
        assert v.pre_filter_candidate("https://example.com/photo.jpg") is not None

    def test_rejects_wp_uploads(self):
        v = RecipeVerifier.__new__(RecipeVerifier)
        assert v.pre_filter_candidate("https://example.com/wp-content/uploads/file") is not None

    def test_accepts_recipe_url(self):
        v = RecipeVerifier.__new__(RecipeVerifier)
        assert v.pre_filter_candidate("https://example.com/chicken-tikka-masala") is None

    def test_rejects_blog_index(self):
        v = RecipeVerifier.__new__(RecipeVerifier)
        assert v.pre_filter_candidate("https://example.com/blog") is not None


class TestVerifierParanoidSkip:
    def test_how_to_slug(self):
        v = RecipeVerifier.__new__(RecipeVerifier)
        assert v.is_paranoid_skip("https://example.com/how-to-cook-rice") is not None

    def test_listicle_slug(self):
        v = RecipeVerifier.__new__(RecipeVerifier)
        assert v.is_paranoid_skip("https://example.com/top-10-recipes") is not None

    def test_normal_recipe_passes(self):
        v = RecipeVerifier.__new__(RecipeVerifier)
        assert v.is_paranoid_skip("https://example.com/chicken-tikka-masala") is None


class TestVerifierRecipeScrapers:
    def test_accepts_recipe_scrapers_payload_without_hand_rolled_signals(self, monkeypatch):
        monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
        calls = []

        class _Scraper:
            def to_json(self):
                return {
                    "ingredients": ["1 cup flour"],
                    "instructions": "Mix well.",
                }

        def _scrape_html(html, *, org_url, supported_only):
            calls.append((html, org_url, supported_only))
            return _Scraper()

        monkeypatch.setattr("cookdex.recipe_dredger.verifier.scrape_html", _scrape_html, raising=False)
        html = "<html><head><title>Plain Recipe</title></head><body><h1>Plain Recipe</h1></body></html>"
        verifier = RecipeVerifier(
            _FakeSession(_FakeResponse(200, html, url="https://example.com/plain-recipe")),
            language_filter_enabled=False,
        )

        ok, error, transient = verifier.verify_recipe("https://example.com/plain-recipe")

        assert (ok, error, transient) == (True, None, False)
        assert calls == [(html, "https://example.com/plain-recipe", False)]


def _fake_getaddrinfo(host, *_args, **_kwargs):
    ip = "127.0.0.1" if host in {"127.0.0.1", "localhost"} else "8.8.8.8"
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", *, url: str = "https://example.com/sitemap.xml", headers=None):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.url = url
        self.headers = headers or {}

    def close(self):
        pass


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **_kwargs):
        self.calls.append((method, url))
        return self.response


class _RoutingSession:
    def __init__(self, routes: dict[tuple[str, str], _FakeResponse], default: _FakeResponse | None = None):
        self.routes = routes
        self.default = default or _FakeResponse(404)
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **_kwargs):
        self.calls.append((method, url))
        return self.routes.get((method, url), self.default)


def test_rate_limiter_uses_robotparser_crawl_delay_for_matching_user_agent(monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    robots = "User-agent: *\nCrawl-delay: 9\n\nUser-agent: CookDex\nCrawl-delay: 3\n"
    limiter = RateLimiter(default_delay=1.0)
    limiter._session = _FakeSession(_FakeResponse(200, robots, url="https://example.com/robots.txt"))

    assert limiter._get_crawl_delay("example.com") == 3


def test_rate_limiter_does_not_lower_default_delay_from_robots(monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    robots = "User-agent: *\nCrawl-delay: 0.25\n"
    limiter = RateLimiter(default_delay=2.0)
    limiter._session = _FakeSession(_FakeResponse(200, robots, url="https://example.com/robots.txt"))

    assert limiter._get_crawl_delay("example.com") == 2.0


def test_rate_limiter_accepts_decimal_robotparser_crawl_delay(monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    robots = "User-agent: CookDex\nCrawl-delay: 2.5\n"
    limiter = RateLimiter(default_delay=1.0)
    limiter._session = _FakeSession(_FakeResponse(200, robots, url="https://example.com/robots.txt"))

    assert limiter._get_crawl_delay("example.com") == 2.5


def test_crawler_filters_private_urls_from_sitemaps(store, monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    xml = """
    <urlset>
      <url><loc>http://127.0.0.1/admin</loc></url>
      <url><loc>https://example.com/recipe</loc></url>
    </urlset>
    """
    crawler = SitemapCrawler(_FakeSession(_FakeResponse(200, xml)), store)

    urls = crawler.fetch_sitemap_urls("https://example.com/sitemap.xml")

    assert urls == ["https://example.com/recipe"]


def test_crawler_uses_next_valid_robotparser_sitemap(store, monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    robots = "Sitemap: http://127.0.0.1/admin.xml\nSitemap: https://example.com/recipes.xml\n"
    session = _RoutingSession({
        ("GET", "https://example.com/robots.txt"): _FakeResponse(200, robots, url="https://example.com/robots.txt"),
    })
    crawler = SitemapCrawler(session, store)

    assert crawler.find_sitemap("https://example.com") == "https://example.com/recipes.xml"


def test_verifier_rejects_private_urls_before_request():
    class _FailingSession:
        def request(self, *_args, **_kwargs):
            raise AssertionError("private URL should not be requested")

    verifier = RecipeVerifier(_FailingSession())

    ok, error, transient = verifier.verify_recipe("http://127.0.0.1/admin")

    assert ok is False
    assert transient is False
    assert "private/internal" in str(error)


def test_safe_request_blocks_redirect_to_private(monkeypatch):
    from cookdex.url_security import request_with_url_validation

    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    response = _FakeResponse(302, headers={"location": "http://127.0.0.1/admin"})
    session = _FakeSession(response)

    with pytest.raises(ValueError, match="private/internal"):
        request_with_url_validation(session, "GET", "https://example.com/start", timeout=5)


# ---------------------------------------------------------------------------
# Default sites list
# ---------------------------------------------------------------------------

from cookdex.recipe_dredger.sites import DEFAULT_SITES
from cookdex.recipe_dredger import sites as dredger_sites_module


class TestDefaultSites:
    def test_not_empty(self):
        assert len(DEFAULT_SITES) > 50

    def test_all_have_url(self):
        for entry in DEFAULT_SITES:
            assert entry["url"].startswith("https://")

    def test_all_have_group(self):
        for entry in DEFAULT_SITES:
            assert entry.get("group"), f"Missing group for {entry['url']}"

    def test_load_default_sites_uses_cookdex_root_when_module_path_is_installed(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        (config_dir / "default_sites.json").write_text(
            '[{"url":"https://example.com","group":"General"}]',
            encoding="utf-8",
        )
        monkeypatch.setenv("COOKDEX_ROOT", str(tmp_path))
        monkeypatch.setattr(dredger_sites_module, "_SITES_JSON", tmp_path / "site-packages" / "missing.json")

        assert dredger_sites_module.load_default_sites() == [
            {"url": "https://example.com", "group": "General"}
        ]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

from cookdex.recipe_dredger.models import RecipeCandidate


class TestRecipeCandidate:
    def test_equality(self):
        a = RecipeCandidate(url="https://example.com/a")
        b = RecipeCandidate(url="https://example.com/a")
        assert a == b

    def test_hash(self):
        a = RecipeCandidate(url="https://example.com/a")
        b = RecipeCandidate(url="https://example.com/a")
        assert hash(a) == hash(b)
        assert len({a, b}) == 1


# ---------------------------------------------------------------------------
# Dry-run persistence
# ---------------------------------------------------------------------------

from cookdex.recipe_dredger import __main__ as dredger_main


class _NoopRateLimiter:
    def wait_if_needed(self, _url: str) -> None:
        return None


class _OneUrlCrawler:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def get_urls_for_site(self, _site_url: str, force_refresh: bool = False):
        return [RecipeCandidate(url="https://example.com/recipe")]


class _SuccessfulImporter:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def import_recipe(self, _url: str):
        return True, None, False


class _RecipeVerifier:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def verify_recipe(self, _url: str):
        return True, None, False


class _RejectingVerifier:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def verify_recipe(self, _url: str):
        return False, "Not a recipe", False


def _dredger_args(**overrides):
    values = {
        "dry_run": True,
        "limit": 1,
        "depth": 10,
        "no_cache": False,
        "workers": 1,
        "precheck": True,
        "language_filter": True,
        "max_retries": 3,
    }
    values.update(overrides)
    return Namespace(**values)


def _patch_dredger_runtime(monkeypatch, store: DredgerStore, verifier_cls) -> None:
    monkeypatch.setenv("MEALIE_URL", "https://mealie.example.com/api")
    monkeypatch.setenv("MEALIE_API_KEY", "test-key")
    monkeypatch.setattr(dredger_main, "DredgerStore", lambda: store)
    monkeypatch.setattr(dredger_main, "get_crawl_session", lambda: object())
    monkeypatch.setattr(dredger_main, "RateLimiter", lambda default_delay: _NoopRateLimiter())
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _OneUrlCrawler)
    monkeypatch.setattr(dredger_main, "RecipeVerifier", verifier_cls)
    monkeypatch.setattr(dredger_main, "ImportManager", _SuccessfulImporter)
    monkeypatch.setattr(dredger_main, "build_import_provider", lambda _env: _HealthyProvider())


class _HealthyProvider:
    def health(self):
        return None


def test_dredger_dry_run_does_not_mark_found_urls_imported(store, monkeypatch):
    store.add_site("https://example.com")
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)

    assert dredger_main.run(_dredger_args(dry_run=True)) == 0

    assert store.imported_count() == 0
    assert not store.is_known("https://example.com/recipe")


def test_dredger_dry_run_does_not_persist_rejects(store, monkeypatch):
    store.add_site("https://example.com")
    _patch_dredger_runtime(monkeypatch, store, _RejectingVerifier)

    assert dredger_main.run(_dredger_args(dry_run=True)) == 0

    assert store.rejected_count() == 0
    assert not store.is_known("https://example.com/recipe")


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------

from cookdex.webui_server.tasks import TaskRegistry


class TestDredgerTaskRegistration:
    def test_recipe_dredger_task_exists(self):
        registry = TaskRegistry()
        assert "recipe-dredger" in registry.task_ids

    def test_build_dry_run(self):
        registry = TaskRegistry()
        execution = registry.build_execution("recipe-dredger", {"dry_run": True})
        assert "--dry-run" in execution.command
        assert not execution.dangerous_requested

    def test_build_live_run(self):
        registry = TaskRegistry()
        execution = registry.build_execution("recipe-dredger", {"dry_run": False})
        assert "--dry-run" not in execution.command
        assert execution.dangerous_requested

    def test_build_with_options(self):
        registry = TaskRegistry()
        execution = registry.build_execution("recipe-dredger", {
            "dry_run": True,
            "limit": 10,
            "depth": 500,
            "no_cache": True,
            "import_workers": 4,
            "precheck_duplicates": False,
            "language_filter": False,
            "max_retry_attempts": 5,
        })
        cmd = execution.command
        assert "--limit" in cmd
        assert "10" in cmd
        assert "--depth" in cmd
        assert "500" in cmd
        assert "--no-cache" in cmd
        assert "--workers" in cmd
        assert "4" in cmd
        assert "--no-precheck" in cmd
        assert "--no-language-filter" in cmd
        assert "--max-retries" in cmd
        assert "5" in cmd

    def test_describe_includes_dredger(self):
        registry = TaskRegistry()
        descriptions = registry.describe_tasks()
        dredger = next((t for t in descriptions if t["task_id"] == "recipe-dredger"), None)
        assert dredger is not None
        assert dredger["group"] == "Data Pipeline"
        assert len(dredger["options"]) == 9


# ---------------------------------------------------------------------------
# The provider the dredger imports through
# ---------------------------------------------------------------------------


class TestImportProviderUrl:
    def _client(self, url: str):
        from cookdex.recipe_dredger.importer import build_import_provider

        return build_import_provider({"MEALIE_URL": url, "MEALIE_API_KEY": "test-key"}).client

    def test_keeps_api_suffix(self):
        assert self._client("http://host:9000/api").base_url == "http://host:9000/api"

    def test_trailing_slash(self):
        assert self._client("http://host:9000/api/").base_url == "http://host:9000/api"

    def test_adds_api_suffix(self):
        assert self._client("http://host:9000").base_url == "http://host:9000/api"

    def test_client_does_not_retry(self):
        client = self._client("http://host:9000")
        assert client.retries == 0
        assert client.timeout_seconds == 20


def test_known_urls_matches_per_url_lookups(tmp_path):
    """Batched known-URL loading must agree with the per-URL check."""
    from cookdex.recipe_dredger.storage import DredgerStore

    store = DredgerStore(tmp_path / "dredger.db")
    store.add_imported("https://example.com/imported")
    store.add_reject("https://example.com/rejected", "junk")
    store.add_retry("https://example.com/retry", "timeout")

    known = store.known_urls()
    for url in (
        "https://example.com/imported",
        "https://example.com/rejected",
        "https://example.com/retry",
    ):
        assert store.is_known(url) is True
        assert (canonicalize_url(url) or url) in known

    unseen = "https://example.com/brand-new"
    assert store.is_known(unseen) is False
    assert (canonicalize_url(unseen) or unseen) not in known


@pytest.mark.parametrize('workers', [1, 2])
def test_dredger_duplicate_does_not_consume_limit(store, monkeypatch, workers, capsys):
    store.add_site('https://example.com')
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    monkeypatch.setattr(dredger_main.random, 'shuffle', lambda _: None)

    class Crawler(_OneUrlCrawler):
        def get_urls_for_site(self, *args, **kwargs):
            return [RecipeCandidate('https://example.com/' + name) for name in ('old', 'new', 'later')]

    seen = []

    class Importer(_SuccessfulImporter):
        def import_recipe(self, url):
            seen.append(url)
            return (False, 'duplicate', False) if url.endswith('/old') else (True, None, False)

    monkeypatch.setattr(dredger_main, 'SitemapCrawler', Crawler)
    monkeypatch.setattr(dredger_main, 'ImportManager', Importer)
    assert dredger_main.run(_dredger_args(dry_run=False, workers=workers)) == 0
    assert seen == ['https://example.com/old', 'https://example.com/new']
    assert store.is_imported('https://example.com/old')
    assert store.is_imported('https://example.com/new')
    assert '"Recipes Imported": 1' in capsys.readouterr().out


def test_importer_distinguishes_prechecked_and_http_duplicates(store, monkeypatch):
    from types import SimpleNamespace
    from cookdex.providers import ImportOutcome
    from cookdex.recipe_dredger.importer import ImportManager

    provider = SimpleNamespace(import_recipe_url=lambda url: ImportOutcome(imported=False, duplicate=True))
    importer = ImportManager(provider, store=store, rate_limiter=_NoopRateLimiter(), dry_run=False)
    monkeypatch.setattr(importer, '_is_duplicate_source', lambda _: True)
    assert importer.import_recipe('https://example.com/old') == (False, 'duplicate', False)
    monkeypatch.setattr(importer, '_is_duplicate_source', lambda _: False)
    assert importer.import_recipe('https://example.com/old') == (False, 'duplicate', False)


class _ManyUrlCrawler:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def get_urls_for_site(self, site_url: str, force_refresh: bool = False):
        return [RecipeCandidate(url=f"{site_url}/recipe-{n}") for n in range(5)]


def test_dredger_overall_cap_stops_across_sites(store, monkeypatch):
    for host in ("https://a.example.com", "https://b.example.com", "https://c.example.com"):
        store.add_site(host)
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _ManyUrlCrawler)

    assert dredger_main.run(_dredger_args(dry_run=False, limit=5, max_total=2)) == 0

    assert store.imported_count() == 2


def test_suggested_sources_are_seeded_switched_off(store):
    from cookdex.recipe_dredger.sites import DEFAULT_SITES

    store.seed_defaults(DEFAULT_SITES[:3], enabled=False)
    assert len(store.get_all_sites()) == 3
    assert store.get_enabled_sites() == []


def test_site_stats_groups_by_host(store):
    store.add_imported("https://www.example.com/recipes/a")
    store.add_imported("https://example.com/recipes/b")
    store.add_reject("https://other.example.org/x", "Not a recipe")
    stats = store.site_stats()
    assert stats["example.com"]["imported"] == 2
    assert stats["other.example.org"]["rejected"] == 1


def test_dredger_task_has_a_default_overall_cap():
    registry = TaskRegistry()
    cmd = registry.build_execution("recipe-dredger", {"dry_run": False}).command
    assert cmd[cmd.index("--max-total") + 1] == "25"
    assert "--max-total" not in registry.build_execution("recipe-dredger", {"max_total": 0}).command


def test_dredger_state_moves_out_of_state_db_once(tmp_path):
    """Older versions kept dredger tables in state.db; they're copied to dredger.db once."""
    import sqlite3

    from cookdex.recipe_dredger.storage import DredgerStore

    legacy = sqlite3.connect(tmp_path / "state.db")
    legacy.execute("PRAGMA journal_mode = WAL;")
    legacy.executescript("""
        CREATE TABLE dredger_imported (url TEXT PRIMARY KEY, imported_at TEXT NOT NULL);
        CREATE TABLE dredger_sites (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE,
            label TEXT DEFAULT '', region TEXT DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1, added_at TEXT NOT NULL);
        INSERT INTO dredger_imported VALUES ('https://example.com/a', '2026-01-01T00:00:00Z');
        INSERT INTO dredger_sites (url, label, region, enabled, added_at)
            VALUES ('https://example.com', 'Example', 'Italian', 1, '2026-01-01T00:00:00Z');
    """)
    legacy.commit()
    legacy.close()

    store = DredgerStore(tmp_path / "dredger.db")
    assert store.is_imported("https://example.com/a")
    sites = store.get_all_sites()
    assert [(s["url"], s.get("site_group") or s.get("group")) for s in sites] == [("https://example.com", "Italian")]

    # Only once: removing it here isn't undone by opening the store again.
    store.delete_site(sites[0]["id"])
    assert DredgerStore(tmp_path / "dredger.db").get_all_sites() == []

    # The job and the server share it without WAL.
    conn = sqlite3.connect(tmp_path / "dredger.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
    conn.close()


# ---------------------------------------------------------------------------
# importer (goes through the provider and MealieApiClient)
# ---------------------------------------------------------------------------

import requests  # noqa: E402

from cookdex.recipe_dredger.importer import ImportManager, build_import_provider  # noqa: E402


class _Resp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.url = ""

    def json(self):
        return self._payload


def _importer(monkeypatch, store, handler, *, precheck=False, url="http://mealie:9000"):
    calls = []

    def fake_request(self, method, url, **kwargs):
        calls.append((method, url))
        return handler(method, url, **kwargs)

    monkeypatch.setattr(requests.Session, "request", fake_request)
    provider = build_import_provider({"MEALIE_URL": url, "MEALIE_API_KEY": "token"})
    manager = ImportManager(provider, store, rate_limiter=None, dry_run=False, precheck_duplicates=precheck)
    return manager, calls


def test_import_uses_the_api_path_once(monkeypatch, store):
    manager, calls = _importer(monkeypatch, store, lambda m, u, **k: _Resp(201, "slug"), url="http://mealie:9000/api/")
    assert manager.import_recipe("https://example.com/soup") == (True, None, False)
    assert calls == [("POST", "http://mealie:9000/api/recipes/create/url")]


def test_import_falls_back_to_the_older_endpoint(monkeypatch, store):
    def handler(method, url, **kwargs):
        return _Resp(404) if url.endswith("/create/url") else _Resp(201, "slug")

    manager, calls = _importer(monkeypatch, store, handler)
    assert manager.import_recipe("https://example.com/soup")[0] is True
    assert manager.import_recipe("https://example.com/stew")[0] is True
    # The working endpoint is remembered and tried first afterwards.
    assert [u.rsplit("/", 1)[-1] for _, u in calls] == ["url", "create-url", "create-url"]


def test_import_reports_conflict_as_duplicate(monkeypatch, store):
    manager, _ = _importer(monkeypatch, store, lambda m, u, **k: _Resp(409))
    assert manager.import_recipe("https://example.com/soup") == (False, "duplicate", False)


def test_import_timeout_is_transient(monkeypatch, store):
    def handler(method, url, **kwargs):
        raise requests.exceptions.ReadTimeout("slow")

    manager, _ = _importer(monkeypatch, store, handler)
    ok, error, transient = manager.import_recipe("https://example.com/soup")
    assert (ok, transient) == (False, True)
    assert error.startswith("Timeout")


def test_import_permanent_mealie_500_is_not_retried(monkeypatch, store):
    manager, _ = _importer(monkeypatch, store, lambda m, u, **k: _Resp(500, text="Unknown Error"))
    ok, error, transient = manager.import_recipe("https://example.com/soup")
    assert (ok, transient) == (False, False)
    assert "Unknown Error" in error


def test_import_skips_sources_already_in_mealie(monkeypatch, store):
    def handler(method, url, **kwargs):
        if method == "GET":
            return _Resp(200, {"items": [{"orgURL": "https://www.example.com/soup/"}], "next": None})
        return _Resp(201, "slug")

    manager, calls = _importer(monkeypatch, store, handler, precheck=True)
    assert manager.import_recipe("https://example.com/soup") == (False, "duplicate", False)
    assert all(method == "GET" for method, _ in calls)


# ---------------------------------------------------------------------------
# Run outcome, Mealie outages, and the retry queue
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402


def _scripted_importer(results):
    """An importer that answers each URL with ``results(url)``, and the URLs it was given."""
    seen: list[str] = []

    class Importer(_SuccessfulImporter):
        def import_recipe(self, url):
            seen.append(url)
            return results(url)

    return Importer, seen


def _no_crawl(*_args, **_kwargs):
    return SimpleNamespace(get_urls_for_site=lambda *_a, **_k: [])


def test_dredger_exits_nonzero_when_every_import_fails(store, monkeypatch):
    store.add_site("https://example.com")
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    importer, _ = _scripted_importer(lambda _url: (False, "HTTP 400 - bad page", False))
    monkeypatch.setattr(dredger_main, "ImportManager", importer)

    assert dredger_main.run(_dredger_args(dry_run=False)) == 1


def test_dredger_exits_zero_when_some_imports_succeed(store, monkeypatch):
    store.add_site("https://example.com")
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _ManyUrlCrawler)
    monkeypatch.setattr(dredger_main.random, "shuffle", lambda _: None)
    importer, _ = _scripted_importer(
        lambda url: (True, None, False) if url.endswith("-1") else (False, "HTTP 400 - bad page", False)
    )
    monkeypatch.setattr(dredger_main, "ImportManager", importer)

    assert dredger_main.run(_dredger_args(dry_run=False, limit=5)) == 0


def test_dredger_fails_fast_when_mealie_is_unreachable(store, monkeypatch):
    store.add_site("https://example.com")
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)

    class DownProvider:
        def health(self):
            raise RuntimeError("Mealie didn't answer")

    class NoCrawler(_OneUrlCrawler):
        def get_urls_for_site(self, *_args, **_kwargs):
            raise AssertionError("shouldn't crawl when Mealie is down")

    monkeypatch.setattr(dredger_main, "build_import_provider", lambda _env: DownProvider())
    monkeypatch.setattr(dredger_main, "SitemapCrawler", NoCrawler)

    assert dredger_main.run(_dredger_args(dry_run=False)) == 1


def test_dredger_dry_run_skips_the_mealie_check(store, monkeypatch):
    store.add_site("https://example.com")
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)

    class DownProvider:
        def health(self):
            raise AssertionError("a dry run shouldn't need Mealie")

    monkeypatch.setattr(dredger_main, "build_import_provider", lambda _env: DownProvider())

    assert dredger_main.run(_dredger_args(dry_run=True)) == 0


@pytest.mark.parametrize("workers", [1, 2])
def test_dredger_stops_the_run_when_mealie_keeps_failing(store, monkeypatch, workers):
    for host in ("https://a.example.com", "https://b.example.com", "https://c.example.com"):
        store.add_site(host)
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _ManyUrlCrawler)
    importer, seen = _scripted_importer(lambda _url: (False, "Connection error: refused", True))
    monkeypatch.setattr(dredger_main, "ImportManager", importer)

    assert dredger_main.run(_dredger_args(dry_run=False, limit=5, workers=workers)) == 1

    # Stopped at the breaker rather than trying all 15 URLs; with workers,
    # imports already in flight still finish.
    assert dredger_main.MEALIE_FAILURE_THRESHOLD <= len(seen) < 15
    queue = store.get_retry_queue()
    assert len(queue) == len(seen)
    # Mealie being down doesn't count against the URLs.
    assert all(entry["attempts"] == 0 for entry in queue)


def test_mealie_outage_does_not_use_up_retry_attempts(store, monkeypatch):
    store.add_site("https://example.com")
    store.add_retry("https://example.com/queued", "Timeout", increment=True)
    store.add_retry("https://example.com/queued", "Timeout", increment=True)
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _no_crawl)
    importer, _ = _scripted_importer(lambda _url: (False, "HTTP 503", True))
    monkeypatch.setattr(dredger_main, "ImportManager", importer)

    for _ in range(3):
        assert dredger_main.run(_dredger_args(dry_run=False, max_retries=3)) == 1

    assert not store.is_rejected("https://example.com/queued")
    [entry] = store.get_retry_queue()
    assert entry["attempts"] == 2


def test_retry_queue_counts_toward_limits_and_summary(store, monkeypatch, capsys):
    store.add_site("https://example.com")
    for n in range(3):
        store.add_retry(f"https://queued.example.com/recipe-{n}", "Timeout", increment=True)
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _ManyUrlCrawler)
    importer, seen = _scripted_importer(lambda _url: (True, None, False))
    monkeypatch.setattr(dredger_main, "ImportManager", importer)
    items: list[dict] = []
    monkeypatch.setattr(dredger_main, "emit_items", lambda _kind, found: items.extend(found))

    assert dredger_main.run(_dredger_args(dry_run=False, limit=5, max_total=2)) == 0

    assert len(seen) == 2
    assert {urlsplit(url).hostname for url in seen} == {"queued.example.com"}
    assert [item["url"] for item in items] == seen
    assert '"Recipes Imported": 2' in capsys.readouterr().out
    assert store.retry_count() == 1


def test_retry_queue_fetches_the_url_as_found(store, monkeypatch):
    store.add_site("https://example.com")
    original = "https://www.example.com/recipes/soup/?s=1"
    store.add_retry(original, "Timeout", increment=True)
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _no_crawl)
    verified = []

    class Verifier(_RecipeVerifier):
        def verify_recipe(self, url):
            verified.append(url)
            return True, None, False

    monkeypatch.setattr(dredger_main, "RecipeVerifier", Verifier)
    importer, seen = _scripted_importer(lambda _url: (True, None, False))
    monkeypatch.setattr(dredger_main, "ImportManager", importer)

    assert dredger_main.run(_dredger_args(dry_run=False)) == 0

    assert verified == [original]
    assert seen == [original]
    assert store.is_imported(original)
    assert store.retry_count() == 0


def test_retry_queue_gains_original_url_column_for_old_databases(tmp_path):
    db_path = tmp_path / "dredger.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE dredger_retry_queue (url TEXT PRIMARY KEY, reason TEXT DEFAULT '',"
        " attempts INTEGER DEFAULT 0, last_attempt TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO dredger_retry_queue VALUES ('https://example.com/old', 'Timeout', 1, '2026-01-01T00:00:00Z')")
    conn.commit()
    conn.close()

    store = DredgerStore(db_path)
    # Old rows fall back to the key.
    assert [e["original_url"] for e in store.get_retry_queue()] == ["https://example.com/old"]
    store.add_retry("https://www.example.com/new", "Timeout")
    urls = {e["url"]: e["original_url"] for e in store.get_retry_queue()}
    assert urls["https://example.com/new"] == "https://www.example.com/new"


# ---------------------------------------------------------------------------
# Sites that block or fail
# ---------------------------------------------------------------------------


def _failing_verifier(error, transient, calls):
    class Verifier(_RecipeVerifier):
        def verify_recipe(self, url):
            calls.append(url)
            return False, error, transient

    return Verifier


def test_site_blocking_the_crawler_is_left_and_nothing_is_rejected(store, monkeypatch):
    store.add_site("https://example.com")
    calls: list[str] = []
    _patch_dredger_runtime(monkeypatch, store, _failing_verifier("HTTP 403", True, calls))
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _ManyUrlCrawler)

    assert dredger_main.run(_dredger_args(dry_run=False, limit=5)) == 0

    assert len(calls) == 3
    assert store.rejected_count() == 0
    assert store.retry_count() == 0


def test_site_failing_with_5xx_is_left_after_the_threshold(store, monkeypatch):
    store.add_site("https://example.com")
    calls: list[str] = []
    _patch_dredger_runtime(monkeypatch, store, _failing_verifier("HTTP 503", True, calls))
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _ManyUrlCrawler)

    dredger_main.run(_dredger_args(dry_run=False, limit=5))

    assert len(calls) == 3
    assert store.retry_count() == 3
    assert store.rejected_count() == 0


def test_verifier_treats_403_as_temporary_and_bad_urls_as_permanent(monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    verifier = RecipeVerifier(_FakeSession(_FakeResponse(403, url="https://example.com/soup")))
    assert verifier.verify_recipe("https://example.com/soup") == (False, "HTTP 403", True)

    class RedirectLoop:
        def request(self, *_args, **_kwargs):
            raise requests.exceptions.TooManyRedirects("loop")

    ok, error, transient = RecipeVerifier(RedirectLoop()).verify_recipe("https://example.com/soup")
    assert (ok, transient) == (False, False)
    assert "loop" in error


# ---------------------------------------------------------------------------
# Sitemap fetch failures and gzip sitemaps
# ---------------------------------------------------------------------------


class _BytesResponse(_FakeResponse):
    def __init__(self, status_code: int, content: bytes, *, url: str):
        super().__init__(status_code, url=url)
        self.content = content


def _sitemap_session(routes):
    index_url = "https://example.com/sitemap_index.xml"
    return _RoutingSession({("HEAD", index_url): _FakeResponse(200, url=index_url), **routes})


def test_failed_sitemap_fetch_is_not_cached(store, monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    session = _sitemap_session({("GET", "https://example.com/sitemap_index.xml"): _FakeResponse(503)})

    assert SitemapCrawler(session, store).get_urls_for_site("https://example.com") == []
    assert store.get_cached_sitemap("https://example.com") is None


def test_partly_failed_sitemap_index_is_used_but_not_cached(store, monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    index = """<sitemapindex>
      <sitemap><loc>https://example.com/post-sitemap1.xml</loc></sitemap>
      <sitemap><loc>https://example.com/post-sitemap2.xml</loc></sitemap>
    </sitemapindex>"""
    good = "<urlset><url><loc>https://example.com/soup</loc></url></urlset>"
    session = _sitemap_session({
        ("GET", "https://example.com/sitemap_index.xml"): _FakeResponse(200, index),
        ("GET", "https://example.com/post-sitemap1.xml"): _FakeResponse(200, good),
        ("GET", "https://example.com/post-sitemap2.xml"): _FakeResponse(503),
    })

    candidates = SitemapCrawler(session, store).get_urls_for_site("https://example.com")
    assert [c.url for c in candidates] == ["https://example.com/soup"]
    assert store.get_cached_sitemap("https://example.com") is None


def test_complete_sitemap_is_cached(store, monkeypatch):
    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    good = "<urlset><url><loc>https://example.com/soup</loc></url></urlset>"
    session = _sitemap_session({("GET", "https://example.com/sitemap_index.xml"): _FakeResponse(200, good)})

    SitemapCrawler(session, store).get_urls_for_site("https://example.com")
    assert store.get_cached_sitemap("https://example.com")["urls"] == ["https://example.com/soup"]


def test_gzip_sitemap_is_read(store, monkeypatch):
    import gzip

    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    xml = b"<urlset><url><loc>https://example.com/soup</loc></url></urlset>"
    url = "https://example.com/sitemap.xml.gz"
    crawler = SitemapCrawler(_FakeSession(_BytesResponse(200, gzip.compress(xml), url=url)), store)

    assert crawler.fetch_sitemap_urls(url) == ["https://example.com/soup"]


def test_oversized_gzip_sitemap_is_refused(store, monkeypatch):
    import gzip

    from cookdex.recipe_dredger import crawler as crawler_module

    monkeypatch.setattr("cookdex.url_security.socket.getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(crawler_module, "MAX_SITEMAP_BYTES", 1024)
    xml = b"<urlset>" + b"<url><loc>https://example.com/soup</loc></url>" * 200 + b"</urlset>"
    url = "https://example.com/sitemap.xml.gz"
    crawler = SitemapCrawler(_FakeSession(_BytesResponse(200, gzip.compress(xml), url=url)), store)

    assert crawler.fetch_sitemap_urls(url) == []


def test_per_site_limit_of_zero_means_no_limit(store, monkeypatch):
    store.add_site("https://example.com")
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    monkeypatch.setattr(dredger_main, "SitemapCrawler", _ManyUrlCrawler)
    importer, seen = _scripted_importer(lambda _url: (True, None, False))
    monkeypatch.setattr(dredger_main, "ImportManager", importer)

    assert dredger_main.run(_dredger_args(dry_run=False, limit=0, max_total=3)) == 0
    assert len(seen) == 3


def test_unreadable_source_is_not_a_successful_empty_run(store, monkeypatch):
    store.add_site('https://example.com')
    _patch_dredger_runtime(monkeypatch, store, _RecipeVerifier)
    class UnreadableCrawler(_OneUrlCrawler):
        last_error = "Couldn't read the source sitemap."
        def get_urls_for_site(self, *args, **kwargs): return []
    monkeypatch.setattr(dredger_main, 'SitemapCrawler', UnreadableCrawler)
    assert dredger_main.run(_dredger_args(dry_run=False)) == 1
