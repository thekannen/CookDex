from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

from cookdex.db_client import build_db_url, db_config, parse_db_url
from cookdex.webui_server.deps import build_runtime_env
from cookdex.webui_server.routers import settings_api
from cookdex.webui_server.security import SecretCipher
from cookdex.webui_server.settings_migration import import_environment_settings
from cookdex.webui_server.state import StateStore


@pytest.fixture
def store(tmp_path):
    state = StateStore(tmp_path / "state.db")
    state.initialize(["mealie-backup"])
    return state, SecretCipher(Fernet.generate_key().decode())


def test_connection_string_round_trips_with_awkward_passwords() -> None:
    fields = parse_db_url("postgresql://mealie:p%40ss%2Fw0rd@postgres:5433/mealie_db")
    assert fields == {
        "kind": "postgres", "host": "postgres", "port": 5433,
        "database": "mealie_db", "user": "mealie", "password": "p@ss/w0rd",
    }
    assert parse_db_url(build_db_url(fields)) == fields
    assert parse_db_url("sqlite:////app/data/mealie.db") == {"kind": "sqlite", "sqlite_path": "/app/data/mealie.db"}


@pytest.mark.parametrize("bad", ["mysql://x@y/z", "postgresql:///mealie", "postgresql://u@h:port/db", "sqlite://"])
def test_unreadable_connection_strings_say_why(bad) -> None:
    with pytest.raises(ValueError):
        parse_db_url(bad)


def test_older_separate_fields_still_configure_the_database() -> None:
    config = db_config({"MEALIE_DB_TYPE": "postgres", "MEALIE_PG_HOST": "db", "MEALIE_PG_PASS": "x"})
    assert (config.kind, config.host, config.password) == ("postgres", "db", "x")
    assert db_config({}) is None
    # The connection string wins over the older fields.
    assert db_config({"MEALIE_DB_URL": "postgresql://a:b@new:1/c", "MEALIE_DB_TYPE": "postgres"}).host == "new"


def test_environment_values_move_into_settings_once(store) -> None:
    state, cipher = store
    environ = {
        "MEALIE_URL": "http://mealie:9000",
        "MEALIE_API_KEY": "token-1",
        "WEB_BIND_PORT": "4999",  # deployment setting: stays in the environment
        "MEALIE_DB_TYPE": "postgres",
        "MEALIE_PG_HOST": "postgres",
        "MEALIE_PG_USER": "mealie",
        "MEALIE_PG_PASS": "s3cret",
        "MEALIE_PG_DB": "mealie",
    }
    moved = import_environment_settings(state, cipher, environ=environ)
    assert moved["imported"] == ["MEALIE_URL", "MEALIE_API_KEY"]
    assert moved["folded_db"] is True
    assert state.list_settings()["MEALIE_URL"] == "http://mealie:9000"
    assert "WEB_BIND_PORT" not in state.list_settings()
    secrets = state.list_encrypted_secrets()
    assert cipher.decrypt(secrets["MEALIE_API_KEY"]) == "token-1"
    assert cipher.decrypt(secrets["MEALIE_DB_URL"]) == "postgresql://mealie:s3cret@postgres:5432/mealie"

    # Later edits in Settings stick: the move never runs again.
    state.set_settings({"MEALIE_URL": "http://elsewhere:9000"})
    assert import_environment_settings(state, cipher, environ=environ) is None
    assert state.list_settings()["MEALIE_URL"] == "http://elsewhere:9000"


def test_values_already_saved_here_are_not_overwritten(store) -> None:
    state, cipher = store
    state.set_settings({"MEALIE_URL": "http://saved:9000"})
    moved = import_environment_settings(state, cipher, environ={"MEALIE_URL": "http://env:9000"})
    assert moved["imported"] == []
    assert state.list_settings()["MEALIE_URL"] == "http://saved:9000"


def test_secrets_wait_when_they_cant_be_stored_safely(store) -> None:
    state, cipher = store
    moved = import_environment_settings(
        state, cipher, can_store_secrets=False, environ={"MEALIE_API_KEY": "t", "MEALIE_URL": "http://m"}
    )
    assert moved["imported"] == ["MEALIE_URL"]
    assert moved["skipped_secrets"] == ["MEALIE_API_KEY"]
    assert "MEALIE_API_KEY" not in state.list_encrypted_secrets()


def test_database_test_leaves_the_server_environment_alone(store, monkeypatch) -> None:
    state, cipher = store
    monkeypatch.delenv("MEALIE_DB_URL", raising=False)
    seen = {}

    class FakeClient:
        def __init__(self, config):
            seen["config"] = config

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        @property
        def _db(self):
            class Cursor:
                def execute(self, sql):
                    return self

                def fetchone(self):
                    return (12169,)

            return Cursor()

    import cookdex.db_client as db_client

    monkeypatch.setattr(db_client, "MealieDBClient", FakeClient)
    env = build_runtime_env(state, cipher)
    env["MEALIE_DB_URL"] = "postgresql://mealie:pw@postgres:5432/mealie"
    ok, detail = settings_api._test_db_connection(env)
    assert ok is True
    assert "12,169 recipes" in detail
    assert "pw" not in detail
    assert seen["config"].host == "postgres"
    assert "MEALIE_DB_URL" not in os.environ


def test_saving_an_unreadable_connection_string_is_refused() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as err:
        settings_api._validate_env_value("MEALIE_DB_URL", "mysql://nope")
    assert err.value.status_code == 422
