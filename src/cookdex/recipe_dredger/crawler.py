"""Sitemap crawler — discovers recipe URLs from site sitemaps."""

from __future__ import annotations

import logging
import zlib
from typing import List, Optional
from urllib import robotparser
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..url_security import request_with_url_validation, validate_service_url
from .models import RecipeCandidate
from .storage import DredgerStore

logger = logging.getLogger("dredger")

# Sitemaps are capped at 50 MB uncompressed by the sitemaps protocol.
MAX_SITEMAP_BYTES = 50 * 1024 * 1024


def _sitemap_body(content: bytes) -> bytes:
    """The sitemap's XML, gunzipped when it was served as .xml.gz."""
    if not content.startswith(b"\x1f\x8b"):
        return content
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    body = inflater.decompress(content, MAX_SITEMAP_BYTES)
    if inflater.unconsumed_tail:
        raise ValueError(f"gzip sitemap is larger than {MAX_SITEMAP_BYTES} bytes uncompressed")
    return body


class SitemapCrawler:
    def __init__(self, session: requests.Session, store: DredgerStore,
                 cache_expiry_days: int = 7) -> None:
        self.session = session
        self.store = store
        self.cache_expiry_days = cache_expiry_days

    def _sitemaps_from_robots(self, base_url: str) -> List[str]:
        robots_url = f"{base_url.rstrip('/')}/robots.txt"
        try:
            response = request_with_url_validation(self.session, "GET", robots_url, timeout=5)
            if response.status_code != 200:
                return []

            parser = robotparser.RobotFileParser(robots_url)
            parser.parse(response.text.splitlines())
            return parser.site_maps() or []
        except Exception:
            return []

    def find_sitemap(self, base_url: str) -> Optional[str]:
        normalized_base = base_url.rstrip("/")
        for sitemap in self._sitemaps_from_robots(normalized_base):
            try:
                sitemap_url = urljoin(f"{normalized_base}/", sitemap.strip())
                return validate_service_url(sitemap_url)
            except Exception:
                continue

        candidates = [
            f"{normalized_base}/sitemap_index.xml",
            f"{normalized_base}/sitemap.xml",
            f"{normalized_base}/wp-sitemap.xml",
            f"{normalized_base}/post-sitemap.xml",
            f"{normalized_base}/recipe-sitemap.xml",
        ]

        for url in candidates:
            try:
                response = request_with_url_validation(self.session, "HEAD", url, timeout=5)
                if response.status_code == 200:
                    return response.url
                if response.status_code in [405, 501]:
                    fallback = request_with_url_validation(self.session, "GET", url, timeout=5, stream=True)
                    fallback.close()
                    if fallback.status_code == 200:
                        return fallback.url
            except Exception:
                pass

        return None

    def fetch_sitemap_urls(self, url: str, depth: int = 0) -> List[str]:
        return self._collect_sitemap_urls(url, depth, failures=[])

    def _collect_sitemap_urls(self, url: str, depth: int, failures: List[str]) -> List[str]:
        """URLs from a sitemap or sitemap index. Sitemaps that couldn't be
        fetched or read are added to ``failures``, so a partial or empty
        result from a bad fetch isn't mistaken for the site's real list."""
        if depth > 2:
            return []

        try:
            response = request_with_url_validation(self.session, "GET", url, timeout=10)
            if response.status_code != 200:
                failures.append(url)
                return []

            soup = BeautifulSoup(_sitemap_body(response.content), "xml")
            all_urls: List[str] = []

            if soup.find("sitemap"):
                sub_maps: list[str] = []
                for sitemap_tag in soup.find_all("sitemap"):
                    loc_tag = sitemap_tag.find("loc", recursive=False)
                    if loc_tag and loc_tag.text:
                        sub_maps.append(loc_tag.text.strip())

                targets = [s for s in sub_maps if "post" in s or "recipe" in s]
                if not targets:
                    targets = sub_maps

                for sub_map in targets[:3]:
                    all_urls.extend(self._collect_sitemap_urls(sub_map, depth + 1, failures))
                return all_urls

            if soup.find("url"):
                for url_tag in soup.find_all("url"):
                    loc_tag = url_tag.find("loc", recursive=False)
                    if not loc_tag or not loc_tag.text:
                        continue
                    loc = loc_tag.text.strip()
                    if loc.startswith("http://") or loc.startswith("https://"):
                        try:
                            all_urls.append(validate_service_url(loc))
                        except ValueError:
                            continue
                return all_urls

            return []

        except Exception as exc:
            logger.warning(f"Sitemap parse error {url}: {exc}")
            failures.append(url)
            return []

    def get_urls_for_site(self, site_url: str, force_refresh: bool = False) -> List[RecipeCandidate]:
        if not force_refresh:
            cached = self.store.get_cached_sitemap(site_url, self.cache_expiry_days)
            if cached:
                return [RecipeCandidate(url=url) for url in cached["urls"]]

        sitemap_url = self.find_sitemap(site_url)
        if not sitemap_url:
            return []

        failures: List[str] = []
        urls = self._collect_sitemap_urls(sitemap_url, 0, failures)
        # Only a complete, non-empty list is cached: caching a failed fetch
        # would hide the site's recipes until the cache expires.
        if urls and not failures:
            self.store.cache_sitemap(site_url, sitemap_url, urls)
        return [RecipeCandidate(url=url) for url in urls]
