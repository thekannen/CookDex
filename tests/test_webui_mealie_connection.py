from __future__ import annotations

import pytest

from cookdex.config import normalize_mealie_url, require_mealie_url
from cookdex.webui_server.routers import settings_api


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://mealie:9000", "http://mealie:9000/api"),
        ("http://mealie:9000/", "http://mealie:9000/api"),
        ("http://mealie:9000/api", "http://mealie:9000/api"),
        ("http://mealie:9000/api/", "http://mealie:9000/api"),
        ("https://home.example/mealie", "https://home.example/mealie/api"),
        ("  http://10.0.0.5:9925/API  ", "http://10.0.0.5:9925/API"),
        ("", ""),
    ],
)
def test_normalize_mealie_url(raw: str, expected: str) -> None:
    assert normalize_mealie_url(raw) == expected


def test_require_mealie_url_appends_api() -> None:
    assert require_mealie_url("http://mealie:9000/") == "http://mealie:9000/api"


class _Response:
    text = ""

    def __init__(self, status_code: int, payload=None, *, html: bool = False) -> None:
        self.status_code = status_code
        self._payload = payload
        self._html = html

    def json(self):
        if self._html:
            raise ValueError("not json")
        return self._payload


def _patch(monkeypatch, responses: dict[str, _Response]) -> list[str]:
    seen: list[str] = []

    def fake_request(self, method, url, **kwargs):
        seen.append(url)
        for suffix, response in responses.items():
            if url.endswith(suffix):
                return response
        return _Response(404, {"detail": "Not found"})

    monkeypatch.setattr(settings_api, "_validate_service_url", lambda url, allow_private=False: url)
    monkeypatch.setattr(settings_api.requests.Session, "request", fake_request)
    return seen


def test_mealie_test_rejects_html_frontend(monkeypatch) -> None:
    # Mealie's web UI answers any path with 200 and an HTML page.
    monkeypatch.setattr(settings_api, "normalize_mealie_url", lambda url: url)
    _patch(monkeypatch, {"/users/self": _Response(200, html=True)})
    ok, detail, _ = settings_api._test_mealie_connection("http://mealie:9000", "token")
    assert ok is False
    assert "isn't the Mealie API" in detail


def test_mealie_test_adds_api_and_reports_user(monkeypatch) -> None:
    seen = _patch(
        monkeypatch,
        {
            "/api/users/self": _Response(200, {"id": "u1", "username": "admin"}),
            "/api/about": _Response(200, {"version": "v3.28.0"}),
        },
    )
    ok, detail, capabilities = settings_api._test_mealie_connection("http://mealie:9000", "token")
    assert ok is True
    assert seen[0] == "http://mealie:9000/api/users/self"
    assert detail == "Connected to Mealie v3.28.0 as admin."
    assert capabilities["username"] == "admin"


def test_mealie_test_explains_bad_token(monkeypatch) -> None:
    _patch(monkeypatch, {"/api/users/self": _Response(401, {"detail": "Unauthorized"})})
    ok, detail, _ = settings_api._test_mealie_connection("http://mealie:9000/api", "bad")
    assert ok is False
    assert "rejected the API token" in detail


def test_unreachable_mealie_names_the_address_and_the_docker_localhost_trap(monkeypatch):
    import requests

    from cookdex.webui_server.routers import settings_api

    monkeypatch.setattr(settings_api, "_in_container", lambda: True)
    message = settings_api._unreachable_message("http://localhost:9925/api", requests.exceptions.ConnectionError())
    assert "localhost:9925" in message
    assert "localhost means CookDex itself" in message
    other = settings_api._unreachable_message("http://192.168.1.5:9925/api", requests.exceptions.ConnectTimeout())
    assert other.startswith("192.168.1.5:9925 didn't answer")


def test_unreachable_mealie_reports_the_underlying_failure(monkeypatch) -> None:
    import requests

    def refuse(self, method, url, **kwargs):
        raise requests.exceptions.ConnectTimeout("timed out")

    monkeypatch.setattr(settings_api, "_validate_service_url", lambda url, allow_private=False: url)
    monkeypatch.setattr(settings_api.requests.Session, "request", refuse)
    ok, detail, _ = settings_api._test_mealie_connection("http://192.168.1.5:9925", "token")
    assert ok is False
    assert "didn't answer within 12 seconds" in detail
