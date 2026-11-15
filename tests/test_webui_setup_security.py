"""First-time setup needs the setup code, and stored keys stay with their address."""

from __future__ import annotations

import importlib
import threading
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from cookdex.webui_server import deps
from cookdex.webui_server.setup_code import ALPHABET, SetupCode
from cookdex.webui_server.state import StateStore
from tests.test_webui_app import _CSRF, _seed_config_root

_ENV_KEYS = ("MEALIE_URL", "MEALIE_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "MEALIE_PG_HOST", "MEALIE_PG_PASS")


def _app(tmp_path: Path, monkeypatch, *, bootstrap_password: str | None = None):
    config_root = tmp_path / "repo"
    _seed_config_root(config_root)
    monkeypatch.setenv("MO_WEBUI_MASTER_KEY", Fernet.generate_key().decode("utf-8"))
    if bootstrap_password:
        monkeypatch.setenv("WEB_BOOTSTRAP_PASSWORD", bootstrap_password)
    else:
        monkeypatch.delenv("WEB_BOOTSTRAP_PASSWORD", raising=False)
    monkeypatch.setenv("WEB_BOOTSTRAP_USER", "admin")
    monkeypatch.setenv("WEB_STATE_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("WEB_BASE_PATH", "/cookdex")
    monkeypatch.setenv("WEB_CONFIG_ROOT", str(config_root))
    monkeypatch.setenv("WEB_COOKIE_SECURE", "false")
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    app_module = importlib.import_module("cookdex.webui_server.app")
    importlib.reload(app_module)
    return app_module.create_app()


def _register(client: TestClient, code: str, username: str = "admin"):
    return client.post(
        "/cookdex/api/v1/auth/register",
        json={"username": username, "password": "Secret-pass1", "setup_code": code},
        headers=_CSRF,
    )


# --- the code itself -------------------------------------------------------


def test_setup_code_format_and_matching() -> None:
    code = SetupCode()
    display = code.display
    groups = display.split("-")
    assert [len(g) for g in groups] == [4, 4, 4]
    assert all(ch in ALPHABET for ch in "".join(groups))
    assert not set("01ILO") & set(ALPHABET)

    assert code.matches(display)
    assert code.matches(display.lower().replace("-", ""))
    assert code.matches(f"  {display.replace('-', ' ')} ")
    assert not code.matches("")
    assert not code.matches(display[:-1])
    assert not code.matches(display + "A")
    assert not code.matches("é" + display)


def test_setup_codes_differ() -> None:
    assert len({SetupCode().display for _ in range(50)}) == 50


def test_announce_is_throttled(capsys) -> None:
    code = SetupCode()
    assert code.announce() is True
    assert code.announce() is False
    assert code.announce(force=True) is True
    out = capsys.readouterr().out
    assert out.count(f"Setup code: {code.display}") == 2


# --- registration ----------------------------------------------------------


def test_register_requires_the_setup_code(tmp_path: Path, monkeypatch, capsys) -> None:
    app = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        code = app.state.services.setup_code
        assert code is not None
        assert f"Setup code: {code.display}" in capsys.readouterr().out

        # Opening the setup page reprints the code at the bottom of the log.
        code._last_printed = float("-inf")
        assert client.get("/cookdex/api/v1/auth/bootstrap-status").json()["setup_required"] is True
        assert f"Setup code: {code.display}" in capsys.readouterr().out

        for bad in ("", "AAAA-AAAA-AAAA", code.display[:-1]):
            assert _register(client, bad, "intruder").status_code == 403
        missing = client.post(
            "/cookdex/api/v1/auth/register",
            json={"username": "intruder", "password": "Secret-pass1"},
            headers=_CSRF,
        )
        assert missing.status_code == 403
        assert client.get("/cookdex/api/v1/auth/bootstrap-status").json()["setup_required"] is True

        ok = _register(client, code.display.lower().replace("-", ""))
        assert ok.status_code == 200
        assert ok.json()["role"] == "owner"
        assert "owner account 'admin' created from" in capsys.readouterr().out

        # The code is spent: setup is closed.
        assert _register(client, code.display, "second").status_code == 409


def test_bootstrap_password_skips_the_setup_code(tmp_path: Path, monkeypatch, capsys) -> None:
    app = _app(tmp_path, monkeypatch, bootstrap_password="Secret-pass1")
    with TestClient(app) as client:
        assert app.state.services.setup_code is None
        assert "Setup code" not in capsys.readouterr().out
        assert client.get("/cookdex/api/v1/auth/bootstrap-status").json()["setup_required"] is False
        assert _register(client, "anything").status_code == 409


def test_create_first_owner_only_once_under_a_race(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    store.initialize([])
    results: list[bool] = []
    barrier = threading.Barrier(8)

    def attempt(i: int) -> None:
        barrier.wait()
        results.append(store.create_first_owner(f"user{i}", "hash"))

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1
    assert len(store.list_users()) == 1


# --- stored keys stay with their address -----------------------------------


@pytest.mark.parametrize(
    ("old", "new", "follows"),
    [
        ("http://mealie:9000", "http://mealie:9000/api/", True),
        ("http://Mealie:9000/api", "http://mealie:9000", True),
        ("", "http://anything", True),
        ("http://mealie:9000", "http://evil.example", False),
        ("http://mealie:9000", "", False),
    ],
)
def test_key_follows_mealie_address(old: str, new: str, follows: bool) -> None:
    assert deps.key_follows_address("MEALIE_URL", old, new) is follows


def test_openai_default_address_counts_as_an_address() -> None:
    assert deps.key_follows_address("OPENAI_BASE_URL", "", "https://api.openai.com/v1/")
    assert not deps.key_follows_address("OPENAI_BASE_URL", "", "http://evil.example/v1")


def _owner_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, object]:
    app = _app(tmp_path, monkeypatch, bootstrap_password="Secret-pass1")
    client = TestClient(app)
    client.__enter__()
    login = client.post(
        "/cookdex/api/v1/auth/login", json={"username": "admin", "password": "Secret-pass1"}, headers=_CSRF
    )
    assert login.status_code == 200
    return client, app


def test_changing_the_address_forgets_the_saved_key(tmp_path: Path, monkeypatch) -> None:
    client, app = _owner_client(tmp_path, monkeypatch)
    try:
        saved = client.put(
            "/cookdex/api/v1/settings",
            json={"env": {"MEALIE_URL": "http://mealie:9000", "MEALIE_API_KEY": "real-key"}},
            headers=_CSRF,
        )
        assert saved.status_code == 200
        assert saved.json()["cleared_secrets"] == []

        # Cosmetic change: the key stays.
        same = client.put("/cookdex/api/v1/settings", json={"env": {"MEALIE_URL": "http://mealie:9000/api/"}}, headers=_CSRF)
        assert same.json()["cleared_secrets"] == []

        moved = client.put("/cookdex/api/v1/settings", json={"env": {"MEALIE_URL": "http://evil.example"}}, headers=_CSRF)
        assert moved.json()["cleared_secrets"] == ["MEALIE_API_KEY"]
        services = app.state.services
        assert "MEALIE_API_KEY" not in deps.build_runtime_env(services.state, services.cipher)

        # Moving with a new key keeps the new key.
        both = client.put(
            "/cookdex/api/v1/settings",
            json={"env": {"MEALIE_URL": "http://mealie2:9000", "MEALIE_API_KEY": "new-key"}},
            headers=_CSRF,
        )
        assert both.json()["cleared_secrets"] == []
        assert deps.build_runtime_env(services.state, services.cipher)["MEALIE_API_KEY"] == "new-key"
    finally:
        client.__exit__(None, None, None)


def test_connection_test_wont_send_saved_key_elsewhere(tmp_path: Path, monkeypatch) -> None:
    from cookdex.webui_server.routers import settings_api

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        settings_api, "_test_mealie_connection", lambda url, key: (sent.append((url, key)) or (True, "ok", {}))
    )
    monkeypatch.setattr(settings_api, "_test_openai_connection", lambda key, model, base="": (sent.append((base, key)) or (True, "ok")))
    monkeypatch.setattr(settings_api, "_list_openai_models", lambda key, base="": (sent.append((base, key)) or []))

    client, _app_ = _owner_client(tmp_path, monkeypatch)
    try:
        client.put(
            "/cookdex/api/v1/settings",
            json={"env": {"MEALIE_URL": "http://mealie:9000", "MEALIE_API_KEY": "real-key", "OPENAI_API_KEY": "sk-real"}},
            headers=_CSRF,
        )

        # Saved address: the saved key is used.
        assert client.post("/cookdex/api/v1/settings/test/mealie", json={}, headers=_CSRF).json()["ok"] is True
        assert sent[-1] == ("http://mealie:9000/api", "real-key")
        assert client.post(
            "/cookdex/api/v1/settings/test/mealie", json={"mealie_url": "http://mealie:9000/"}, headers=_CSRF
        ).json()["ok"] is True

        # Another address without a key: refused, nothing sent.
        count = len(sent)
        other = client.post(
            "/cookdex/api/v1/settings/test/mealie", json={"mealie_url": "http://evil.example"}, headers=_CSRF
        ).json()
        assert other["ok"] is False
        assert "different URL" in other["detail"]
        assert len(sent) == count

        for path in ("/cookdex/api/v1/settings/test/openai", "/cookdex/api/v1/settings/models/openai"):
            client.post(path, json={"openai_base_url": "http://evil.example/v1"}, headers=_CSRF)
        assert all(key != "sk-real" for base, key in sent[count:])

        # A key typed on the page may go to any address.
        client.post(
            "/cookdex/api/v1/settings/test/mealie",
            json={"mealie_url": "http://other:9000", "mealie_api_key": "typed"},
            headers=_CSRF,
        )
        assert sent[-1] == ("http://other:9000/api", "typed")
    finally:
        client.__exit__(None, None, None)


def test_environment_key_stays_with_environment_address(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEALIE_URL", "http://mealie:9000")
    monkeypatch.setenv("MEALIE_API_KEY", "env-key")
    store = StateStore(tmp_path / "state.db")
    store.initialize([])
    cipher = deps.SecretCipher(Fernet.generate_key().decode("utf-8"))

    assert deps.build_runtime_env(store, cipher)["MEALIE_API_KEY"] == "env-key"
    store.set_settings({"MEALIE_URL": "http://evil.example"})
    assert "MEALIE_API_KEY" not in deps.build_runtime_env(store, cipher)
