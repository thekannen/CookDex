from __future__ import annotations

from typing import Any

import pytest

from cookdex.webui_server.env_catalog import ENV_SPEC_BY_KEY
from cookdex.webui_server.routers import settings_api


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    models = {"data": [{"id": "gpt-4o-mini"}, {"id": "llama3.1:8b"}, {"id": "qwen3"}]}

    def fake_get(url: str, **_kwargs: Any) -> _Response:
        seen.append(url)
        return _Response(models)

    def fake_post(url: str, **_kwargs: Any) -> _Response:
        seen.append(url)
        return _Response({"choices": []})

    monkeypatch.setattr(settings_api.requests, "get", fake_get)
    monkeypatch.setattr(settings_api.requests, "post", fake_post)
    monkeypatch.setattr(settings_api, "_validate_service_url", lambda url, allow_private=False: url)
    return seen


def test_base_url_is_a_settings_field() -> None:
    spec = ENV_SPEC_BY_KEY["OPENAI_BASE_URL"]
    assert spec.group == "AI"
    assert not spec.secret
    assert spec.default == ""


def test_openai_defaults_to_openai(calls: list[str]) -> None:
    ok, detail = settings_api._test_openai_connection("sk-test", "gpt-4o-mini", "")
    assert ok
    assert detail == "OpenAI API key validated."
    assert settings_api._list_openai_models("sk-test") == ["gpt-4o-mini"]
    assert calls == ["https://api.openai.com/v1/chat/completions", "https://api.openai.com/v1/models"]


def test_compatible_gateway_is_tested_and_listed(calls: list[str]) -> None:
    ok, detail = settings_api._test_openai_connection("sk-test", "qwen3", "http://litellm:4000/v1/")
    assert ok
    assert "litellm:4000" in detail and "qwen3" in detail
    # A gateway's own model names are all listed, not filtered to OpenAI's.
    assert settings_api._list_openai_models("sk-test", "http://litellm:4000/v1") == ["gpt-4o-mini", "llama3.1:8b", "qwen3"]
    assert calls == ["http://litellm:4000/v1/chat/completions", "http://litellm:4000/v1/models"]


def test_rejected_base_url_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(url: str, allow_private: bool = False) -> str:
        raise ValueError("Requests to cloud metadata endpoints are not allowed.")

    monkeypatch.setattr(settings_api, "_validate_service_url", reject)
    ok, detail = settings_api._test_openai_connection("sk-test", "m", "http://169.254.169.254/v1")
    assert not ok
    assert "metadata" in detail
    assert settings_api._list_openai_models("sk-test", "http://169.254.169.254/v1") == []
