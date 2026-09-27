"""One-time move of settings from the container environment into CookDex.

CookDex is set up from its own Settings page. Older installs put the Mealie
connection, AI keys and database details in the compose file instead. On the
first start after upgrading, those values are copied into CookDex's settings
(secrets encrypted) so the page shows them as set here and people can drop
them from their compose file. Values that only matter to the container itself
(port, base path, TLS) stay in the environment.

The older MEALIE_DB_TYPE / MEALIE_PG_* database fields are folded into the one
MEALIE_DB_URL connection string at the same time.
"""
from __future__ import annotations

import os
from typing import Mapping

from ..db_client import build_db_url, legacy_db_fields
from .env_catalog import ENV_VAR_SPECS
from .security import SecretCipher
from .state import StateStore, utc_now_iso

MIGRATION_DOC = "settings_env_import"
LEGACY_DB_KEYS = (
    "MEALIE_DB_TYPE",
    "MEALIE_PG_HOST",
    "MEALIE_PG_PORT",
    "MEALIE_PG_DB",
    "MEALIE_PG_USER",
    "MEALIE_PG_PASS",
)


def _effective(state: StateStore, cipher: SecretCipher, environ: Mapping[str, str], key: str) -> str:
    """The value a task would see for *key*: saved here first, then the environment."""
    secrets = state.list_encrypted_secrets()
    if key in secrets:
        try:
            return cipher.decrypt(secrets[key]).strip()
        except ValueError:
            return ""
    settings = state.list_settings()
    if key in settings:
        return str(settings[key]).strip()
    return str(environ.get(key, "")).strip()


def _fold_legacy_db(state: StateStore, cipher: SecretCipher, environ: Mapping[str, str]) -> bool:
    if _effective(state, cipher, environ, "MEALIE_DB_URL"):
        return False
    values = {key: _effective(state, cipher, environ, key) for key in (*LEGACY_DB_KEYS, "MEALIE_SQLITE_PATH")}
    fields = legacy_db_fields({key: value for key, value in values.items() if value})
    if fields is None:
        return False
    state.set_secret("MEALIE_DB_URL", cipher.encrypt(build_db_url(fields)))
    for key in LEGACY_DB_KEYS:
        state.delete_setting(key)
        state.delete_secret(key)
    return True


def import_environment_settings(
    state: StateStore,
    cipher: SecretCipher,
    *,
    can_store_secrets: bool = True,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object] | None:
    """Copy environment values into CookDex's settings, once. Returns what moved, or None."""
    if state.get_document(MIGRATION_DOC) is not None:
        return None
    environ = os.environ if environ is None else environ

    settings = state.list_settings()
    secrets = state.list_encrypted_secrets()
    imported: list[str] = []
    skipped_secrets: list[str] = []
    for spec in ENV_VAR_SPECS:
        if spec.hidden:
            continue
        raw = str(environ.get(spec.key, "")).strip()
        if not raw or spec.key in settings or spec.key in secrets:
            continue
        if spec.secret:
            if not can_store_secrets:
                skipped_secrets.append(spec.key)
                continue
            state.set_secret(spec.key, cipher.encrypt(raw))
        else:
            state.set_settings({spec.key: raw})
        imported.append(spec.key)

    folded = can_store_secrets and _fold_legacy_db(state, cipher, environ)
    record = {"imported": imported, "folded_db": folded, "skipped_secrets": skipped_secrets, "at": utc_now_iso()}
    state.set_document(MIGRATION_DOC, record)
    return record
