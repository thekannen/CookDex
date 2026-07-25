from __future__ import annotations

from cookdex.webui_server.routers import settings_api
from cookdex.webui_server.settings import _int_env


def test_int_env_clamps_below_minimum(monkeypatch):
    monkeypatch.setenv("WEB_BIND_PORT", "0")
    result = _int_env("WEB_BIND_PORT", 4820, min_val=1, max_val=65535)
    assert result == 1


def test_int_env_clamps_above_maximum(monkeypatch):
    monkeypatch.setenv("WEB_BIND_PORT", "99999")
    result = _int_env("WEB_BIND_PORT", 4820, min_val=1, max_val=65535)
    assert result == 65535


def test_int_env_returns_default_when_unset(monkeypatch):
    monkeypatch.delenv("WEB_BIND_PORT", raising=False)
    result = _int_env("WEB_BIND_PORT", 4820, min_val=1, max_val=65535)
    assert result == 4820


def test_int_env_accepts_valid_value(monkeypatch):
    monkeypatch.setenv("WEB_BIND_PORT", "8080")
    result = _int_env("WEB_BIND_PORT", 4820, min_val=1, max_val=65535)
    assert result == 8080


def test_ollama_connection_validation_error_returns_failure(monkeypatch):
    def fail_validation(url: str, *, allow_private: bool = False) -> str:
        raise ValueError("Could not resolve hostname: host.docker.internal")

    monkeypatch.setattr(settings_api, "_validate_service_url", fail_validation)

    ok, detail = settings_api._test_ollama_connection("http://host.docker.internal:11434", "llama3")

    assert ok is False
    assert detail == "Ollama URL is invalid or unreachable."
    assert "Could not resolve hostname" not in detail
    assert "host.docker.internal" not in detail


def test_dredger_site_validation_error_is_sanitized(monkeypatch):
    def fail_validation(url: str, *, allow_private: bool = False) -> str:
        raise ValueError("Could not resolve hostname: internal.corp.example")

    monkeypatch.setattr(settings_api, "_validate_service_url", fail_validation)

    result = settings_api._validate_dredger_site_url("http://internal.corp.example")

    assert result["reachable"] is False
    assert result["error"] == "Site URL is invalid or points to a blocked address."
    assert "Could not resolve hostname" not in result["error"]
    assert "internal.corp.example" not in result["error"]


def test_build_runtime_env_ignores_non_catalog_keys(tmp_path):
    """Stored settings/secrets reach task subprocesses — only catalog keys may."""
    from cryptography.fernet import Fernet

    from cookdex.webui_server.deps import build_runtime_env
    from cookdex.webui_server.security import SecretCipher
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    state.initialize(["mealie-backup"])
    cipher = SecretCipher(Fernet.generate_key().decode())

    state.set_settings({"PATH": "/tmp/attacker/bin", "PYTHONPATH": "/tmp/attacker/lib"})
    state.set_secret("LD_PRELOAD", cipher.encrypt("/tmp/attacker/evil.so"))

    env = build_runtime_env(state, cipher)

    assert env.get("PATH") != "/tmp/attacker/bin"
    assert "PYTHONPATH" not in env
    assert "LD_PRELOAD" not in env


def test_verify_password_or_dummy_spends_work_on_unknown_user():
    """Unknown usernames must not return faster than known ones."""
    import time

    from cookdex.webui_server.security import hash_password, verify_password_or_dummy

    encoded = hash_password("correct horse battery staple")

    start = time.perf_counter()
    assert verify_password_or_dummy("wrong", encoded) is False
    known_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    assert verify_password_or_dummy("wrong", None) is False
    unknown_elapsed = time.perf_counter() - start

    # Without the dummy verify the unknown-user path is orders of magnitude
    # faster; allow generous slack for scheduling noise.
    assert unknown_elapsed > known_elapsed / 4


def test_verify_password_rejects_corrupt_hash_without_raising():
    from cookdex.webui_server.security import verify_password

    assert verify_password("x", "pbkdf2_sha256$390000$not-base64!$also-bad!") is False
    assert verify_password("x", "pbkdf2_sha256$notanint$AAAA$AAAA") is False
    assert verify_password("x", "garbage") is False
