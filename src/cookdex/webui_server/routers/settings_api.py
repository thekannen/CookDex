from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, Depends, HTTPException

from ...config import normalize_mealie_url
from ...db_client import build_db_url, legacy_db_fields, parse_db_url
from ...url_security import request_with_url_validation, validate_service_url
from ..db_detect import (
    _HostKeyChangedError,
    _detect_db_credentials,
    _parse_mealie_env,  # noqa: F401  -- re-exported for tests
)
from ..deps import (
    Services,
    build_runtime_env,
    env_payload,
    is_catalog_env_key,
    require_editor_session,
    require_owner_session,
    resolve_runtime_value,
    require_services,
)
from ..env_catalog import ENV_SPEC_BY_KEY, MAX_RUN_DURATION_SECONDS_CAP, EnvVarSpec
from ..schemas import (
    DbDetectRequest,
    DbTestRequest,
    DredgerSiteCreateRequest,
    DredgerSitesSeedRequest,
    DredgerSitesValidateRequest,
    DredgerSiteUpdateRequest,
    ProviderConnectionTestRequest,
    SettingsUpdateRequest,
)
from ..settings_migration import MIGRATION_DOC

router = APIRouter(tags=["settings"])


def _validate_service_url(url: str, *, allow_private: bool = False) -> str:
    """Validate that a URL is safe for server-side requests (SSRF protection).

    Checks scheme, resolves DNS, and blocks private/link-local/loopback IPs
    unless *allow_private* is True (e.g. for user-configured Mealie/Ollama on LAN).
    """
    return validate_service_url(url, allow_private=allow_private)


def _safe_request_error(exc: requests.RequestException) -> str:
    """Return a user-friendly error without leaking stack traces."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None:
        return f"Request failed with HTTP {status}."
    return f"Connection failed: {type(exc).__name__}."


def _in_container() -> bool:
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")


def _unreachable_message(base_url: str, exc: requests.RequestException) -> str:
    """Say which address was tried and the likely fix, without internals."""
    parts = urlsplit(base_url)
    where = parts.netloc or base_url
    if isinstance(exc, requests.exceptions.SSLError):
        return f"{where} answered, but its HTTPS certificate wasn't accepted. If Mealie uses plain http, change the address to http://."
    if isinstance(exc, requests.exceptions.Timeout):
        return f"{where} didn't answer within 12 seconds. Check the address, and that Mealie is running."
    message = f"Couldn't reach Mealie at {where}. Check the address and port, and that Mealie is running."
    if (parts.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"} and _in_container():
        message += (
            " CookDex runs in a container, where localhost means CookDex itself. Use your server's address,"
            " or Mealie's container name if they share a Docker network (like http://mealie:9000)."
        )
    return message


def _test_mealie_connection(url: str, api_key: str) -> tuple[bool, str, dict[str, Any]]:
    """Test Mealie connection and return (ok, message, capabilities)."""
    base_url = _validate_service_url(normalize_mealie_url(url), allow_private=True)
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    capabilities: dict[str, Any] = {}
    try:
        response = requests.get(f"{base_url}/users/self", headers=headers, timeout=12)
    except requests.RequestException as exc:
        return False, _unreachable_message(base_url, exc), capabilities
    if response.status_code in (401, 403):
        return False, "Mealie rejected the API token. Create a new one in Mealie (your profile, then API Tokens) and paste it here.", capabilities
    if response.status_code == 404:
        return False, "No Mealie API at this address. Check the host and port you use to open Mealie.", capabilities
    if response.status_code >= 400:
        return False, f"Mealie answered with HTTP {response.status_code}.", capabilities
    # Mealie's web frontend answers unknown paths with 200 and an HTML page, so a
    # 2xx alone doesn't prove this is the API. Require the user object.
    try:
        user = response.json()
    except ValueError:
        user = None
    if not isinstance(user, dict) or not (user.get("id") or user.get("username")):
        return False, "That address answered, but it isn't the Mealie API. Check the host and port you use to open Mealie.", capabilities
    capabilities["username"] = str(user.get("username") or user.get("email") or "")

    # Probe /about for server capabilities (version, features).
    for about_path in ("/about", "/admin/about"):
        try:
            about_resp = requests.get(f"{base_url}{about_path}", headers=headers, timeout=8)
            if about_resp.status_code < 400:
                about = about_resp.json()
                if isinstance(about, dict):
                    capabilities["version"] = about.get("version") or about.get("versionLatest") or ""
                    capabilities["enableOpenaiTranscription"] = bool(about.get("enableOpenaiTranscriptionServices", False) or about.get("enable_openai_transcription_services", False))
                    break
        except Exception:
            pass

    who = f" as {capabilities['username']}" if capabilities.get("username") else ""
    detail = f"Connected to Mealie{who}."
    if capabilities.get("version"):
        detail = f"Connected to Mealie {capabilities['version']}{who}."
    return True, detail, capabilities


def _test_openai_connection(api_key: str, model: str) -> tuple[bool, str]:
    if not api_key:
        return False, "OpenAI API key is required."
    endpoint = "https://api.openai.com/v1/chat/completions"
    body = {
        "model": model or "gpt-4o-mini",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(endpoint, headers=headers, json=body, timeout=15)
        response.raise_for_status()
        return True, "OpenAI API key validated."
    except requests.RequestException as exc:
        return False, _safe_request_error(exc)


def _test_anthropic_connection(api_key: str, model: str) -> tuple[bool, str]:
    if not api_key:
        return False, "Anthropic API key is required."
    if not model:
        return False, "Anthropic model is required."
    endpoint = "https://api.anthropic.com/v1/messages"
    body = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(endpoint, headers=headers, json=body, timeout=15)
        response.raise_for_status()
        return True, "Anthropic API key validated."
    except requests.RequestException as exc:
        return False, _safe_request_error(exc)


def _test_ollama_connection(url: str, model: str) -> tuple[bool, str]:
    try:
        base_url = _validate_service_url(url.strip().rstrip("/"), allow_private=True)
    except ValueError:
        return False, "Ollama URL is invalid or unreachable."
    if not base_url:
        return False, "Ollama URL is required."

    if base_url.endswith("/api"):
        tags_url = f"{base_url}/tags"
    elif base_url.endswith("/api/tags"):
        tags_url = base_url
    else:
        tags_url = f"{base_url}/api/tags"

    try:
        # URL validated by _validate_service_url above (scheme + metadata block).
        response = requests.get(tags_url, timeout=12)  # nosec B113
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models") if isinstance(payload, dict) else None
        if isinstance(models, list) and model:
            found = any(str(item.get("name") or "").startswith(model) for item in models if isinstance(item, dict))
            if not found:
                return True, f"Connection OK, model '{model}' was not listed by Ollama."
        return True, "Ollama connection validated."
    except ValueError:
        return False, "Invalid response from Ollama server."
    except requests.RequestException as exc:
        return False, _safe_request_error(exc)


@router.get("/settings")
def get_settings(
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    secret_keys = sorted(services.state.list_encrypted_secrets().keys())
    return {
        "settings": services.state.list_settings(),
        "secrets": {key: "********" for key in secret_keys},
        "env": env_payload(services.state, services.cipher),
        # What the one-time move out of the container environment copied.
        "moved_from_environment": services.state.get_document(MIGRATION_DOC),
    }


def _payload_has_secret_values(payload: SettingsUpdateRequest) -> bool:
    """Return True if the payload contains any non-empty secret values to encrypt."""
    for value in payload.secrets.values():
        if value is not None and str(value) != "":
            return True
    for key, value in payload.env.items():
        if value is None or str(value).strip() == "":
            continue
        spec = ENV_SPEC_BY_KEY.get(key.strip().upper())
        if spec is not None and spec.secret:
            return True
    return False


def _require_catalog_spec(key_name: str) -> EnvVarSpec:
    """Return the catalog spec for *key_name* or reject the request.

    Settings and secrets are exported into task subprocess environments, so
    an unknown key would let a caller define PATH, PYTHONPATH, LD_PRELOAD or
    similar and take control of the next task run.
    """
    if not is_catalog_env_key(key_name):
        raise HTTPException(status_code=422, detail=f"Unsupported environment key: {key_name}")
    return ENV_SPEC_BY_KEY[key_name]


def _validate_env_value(key_name: str, value: str) -> str:
    if key_name == "MEALIE_URL":
        return normalize_mealie_url(value)
    if key_name == "MEALIE_DB_URL":
        try:
            parse_db_url(value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return value.strip()
    if key_name != "MAX_RUN_DURATION_SECONDS":
        return value

    try:
        seconds = int(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="MAX_RUN_DURATION_SECONDS must be a whole number of seconds.",
        ) from exc

    if seconds <= 0:
        raise HTTPException(
            status_code=422,
            detail="MAX_RUN_DURATION_SECONDS must be greater than zero.",
        )
    if seconds > MAX_RUN_DURATION_SECONDS_CAP:
        raise HTTPException(
            status_code=422,
            detail="MAX_RUN_DURATION_SECONDS cannot exceed 43200 seconds (12 hours).",
        )
    return str(seconds)


@router.put("/settings")
def put_settings(
    payload: SettingsUpdateRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    if services.settings.weak_master_key and _payload_has_secret_values(payload):
        raise HTTPException(
            status_code=400,
            detail="Cannot store secrets: MO_WEBUI_MASTER_KEY is set to a weak default. "
            "Set a strong key and restart.",
        )

    # Stored settings and secrets are exported into task subprocess
    # environments by build_runtime_env, so every key has to be a known
    # catalog variable — otherwise a caller could define PATH or PYTHONPATH
    # and take over the next task run.
    if payload.settings:
        validated_settings: dict[str, Any] = {}
        for key, value in payload.settings.items():
            key_name = key.strip().upper()
            spec = _require_catalog_spec(key_name)
            if spec.secret:
                raise HTTPException(
                    status_code=422,
                    detail=f"{key_name} is a secret; send it under 'env' or 'secrets' so it is encrypted at rest.",
                )
            validated_settings[key_name] = _validate_env_value(key_name, str(value))
        services.state.set_settings(validated_settings)

    for key, value in payload.secrets.items():
        key_name = key.strip().upper()
        if not key_name:
            continue
        spec = _require_catalog_spec(key_name)
        if not spec.secret:
            raise HTTPException(
                status_code=422,
                detail=f"{key_name} is not a secret; send it under 'env' or 'settings'.",
            )
        if value is None or str(value) == "":
            services.state.delete_secret(key_name)
            continue
        services.state.set_secret(key_name, services.cipher.encrypt(str(value)))

    for key, value in payload.env.items():
        key_name = key.strip().upper()
        if not key_name:
            continue
        spec = _require_catalog_spec(key_name)
        if value is None or str(value).strip() == "":
            if spec.secret:
                services.state.delete_secret(key_name)
            else:
                services.state.delete_setting(key_name)
            continue
        value_text = _validate_env_value(key_name, str(value))
        if spec.secret:
            services.state.set_secret(key_name, services.cipher.encrypt(value_text))
        else:
            services.state.set_settings({key_name: value_text})

    return get_settings(_session, services)


# Recommended chat-capable models for recipe categorization tasks.
# Kept as an ordered list: best value first. The API response is
# cross-referenced so only models the key can actually access appear.
_OPENAI_RECOMMENDED = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-nano",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4-turbo",
    "o4-mini",
    "o3-mini",
    "gpt-3.5-turbo",
)

def _list_openai_models(api_key: str) -> list[str]:
    if not api_key:
        return []
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=12)
        response.raise_for_status()
        data = response.json()
        available = {str(m.get("id", "")) for m in (data.get("data") or []) if isinstance(m, dict)}
        return [m for m in _OPENAI_RECOMMENDED if m in available]
    except requests.RequestException:
        return []


def _list_ollama_models(url: str) -> list[str]:
    base_url = (url or "").strip().rstrip("/")
    if not base_url:
        return []
    try:
        _validate_service_url(base_url, allow_private=True)
    except ValueError:
        return []
    if base_url.endswith("/api"):
        tags_url = f"{base_url}/tags"
    elif base_url.endswith("/api/tags"):
        tags_url = base_url
    else:
        tags_url = f"{base_url}/api/tags"
    try:
        # URL validated by _validate_service_url above (scheme + metadata block).
        response = requests.get(tags_url, timeout=12)  # nosec B113
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            return []
        return sorted(
            str(m.get("name", ""))
            for m in models
            if isinstance(m, dict) and m.get("name")
        )
    except requests.RequestException:
        return []


def _list_anthropic_models(api_key: str) -> list[str]:
    if not api_key:
        return []
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    try:
        response = requests.get("https://api.anthropic.com/v1/models", headers=headers, timeout=12)
        response.raise_for_status()
        data = response.json()
        return sorted(
            str(m.get("id", ""))
            for m in (data.get("data") or [])
            if isinstance(m, dict) and m.get("id")
        )
    except requests.RequestException:
        return []


@router.post("/settings/models/openai")
def list_openai_models(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    api_key = resolve_runtime_value(runtime_env, "OPENAI_API_KEY", payload.openai_api_key)
    models = _list_openai_models(api_key)
    return {"ok": bool(models), "models": models}


@router.post("/settings/models/ollama")
def list_ollama_models(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    ollama_url = resolve_runtime_value(runtime_env, "OLLAMA_URL", payload.ollama_url)
    models = _list_ollama_models(ollama_url)
    return {"ok": bool(models), "models": models}


@router.post("/settings/models/anthropic")
def list_anthropic_models(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    api_key = resolve_runtime_value(runtime_env, "ANTHROPIC_API_KEY", payload.anthropic_api_key)
    models = _list_anthropic_models(api_key)
    return {"ok": bool(models), "models": models}


@router.post("/settings/test/mealie")
def test_mealie_settings(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    mealie_url = normalize_mealie_url(resolve_runtime_value(runtime_env, "MEALIE_URL", payload.mealie_url))
    mealie_api_key = resolve_runtime_value(runtime_env, "MEALIE_API_KEY", payload.mealie_api_key)
    if not mealie_url or not mealie_api_key:
        return {"ok": False, "detail": "Mealie URL and API key are required."}
    ok, detail, capabilities = _test_mealie_connection(mealie_url, mealie_api_key)
    result: dict[str, Any] = {"ok": ok, "detail": detail}
    if capabilities:
        result["capabilities"] = capabilities
    return result


@router.post("/settings/test/openai")
def test_openai_settings(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    openai_api_key = resolve_runtime_value(runtime_env, "OPENAI_API_KEY", payload.openai_api_key)
    openai_model = resolve_runtime_value(runtime_env, "OPENAI_MODEL", payload.openai_model) or "gpt-4o-mini"
    ok, detail = _test_openai_connection(openai_api_key, openai_model)
    return {"ok": ok, "detail": detail, "model": openai_model}


@router.post("/settings/test/ollama")
def test_ollama_settings(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    ollama_url = resolve_runtime_value(runtime_env, "OLLAMA_URL", payload.ollama_url)
    ollama_model = resolve_runtime_value(runtime_env, "OLLAMA_MODEL", payload.ollama_model)
    ok, detail = _test_ollama_connection(ollama_url, ollama_model)
    return {"ok": ok, "detail": detail, "model": ollama_model}


@router.post("/settings/test/anthropic")
def test_anthropic_settings(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    anthropic_api_key = resolve_runtime_value(runtime_env, "ANTHROPIC_API_KEY", payload.anthropic_api_key)
    anthropic_model = resolve_runtime_value(runtime_env, "ANTHROPIC_MODEL", payload.anthropic_model)
    ok, detail = _test_anthropic_connection(anthropic_api_key, anthropic_model)
    return {"ok": ok, "detail": detail, "model": anthropic_model}


def _test_db_connection(runtime_env: dict[str, str]) -> tuple[bool, str]:
    from cookdex.db_client import MealieDBClient, db_config

    try:
        config = db_config(runtime_env)
    except ValueError as exc:
        return False, str(exc)
    if config is None:
        return False, "Add a connection string first."
    try:
        with MealieDBClient(config) as db:
            row = db._db.execute("SELECT COUNT(*) FROM recipes").fetchone()
    except Exception as exc:
        return False, f"Couldn't connect to {config.describe()}: {type(exc).__name__}."
    count = int(row[0]) if row else 0
    return True, f"Connected to {config.describe()}. It holds {count:,} recipes."


@router.post("/settings/test/db")
def test_db_settings(
    payload: DbTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    # Test what's on the page, even before it's saved.
    overrides = {
        "MEALIE_DB_URL": payload.db_url,
        "MEALIE_DB_SSH_HOST": payload.ssh_host,
        "MEALIE_DB_SSH_USER": payload.ssh_user,
        "MEALIE_DB_SSH_KEY": payload.ssh_key,
    }
    for key, value in overrides.items():
        if value is not None:
            runtime_env[key] = value
    ok, detail = _test_db_connection(runtime_env)
    return {"ok": ok, "detail": detail}


# ------------------------------------------------------------------
# DB auto-detect via SSH
# ------------------------------------------------------------------

# Mealie container env vars → CookDex env var names

@router.post("/settings/detect/db")
def detect_db_settings(
    payload: DbDetectRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    ssh_host = resolve_runtime_value(runtime_env, "MEALIE_DB_SSH_HOST", payload.ssh_host)
    ssh_user = resolve_runtime_value(runtime_env, "MEALIE_DB_SSH_USER", payload.ssh_user) or "root"
    ssh_key = resolve_runtime_value(runtime_env, "MEALIE_DB_SSH_KEY", payload.ssh_key) or "~/.ssh/cookdex_mealie"

    if not ssh_host:
        return {"ok": False, "detail": "SSH host is required. Configure it in the fields above.", "detected": {}}

    try:
        ok, detail, detected = _detect_db_credentials(ssh_host, ssh_user, ssh_key)
        fields = legacy_db_fields({"MEALIE_DB_TYPE": "postgres", **detected}) if ok else None
        if fields is None:
            return {"ok": ok, "detail": detail, "detected": {}}
        return {"ok": True, "detail": detail + " Review it, then save.", "detected": {"MEALIE_DB_URL": build_db_url(fields)}}
    except _HostKeyChangedError:
        return {
            "ok": False,
            "detail": (
                "The SSH host key changed since the last connection. "
                "Verify the host is the one you expect, then remove its old known_hosts entry."
            ),
            "detected": {},
        }
    except Exception:
        return {"ok": False, "detail": "Detection failed unexpectedly.", "detected": {}}


# ------------------------------------------------------------------
# Dredger Sites CRUD
# ------------------------------------------------------------------

def _get_dredger_store():
    from cookdex.recipe_dredger.storage import DredgerStore
    return DredgerStore()


@router.get("/settings/dredger-sites")
def list_dredger_sites(
    _session: dict[str, Any] = Depends(require_editor_session),
    _services: Services = Depends(require_services),
) -> dict[str, Any]:
    store = _get_dredger_store()
    sites = store.get_all_sites()
    # Auto-seed defaults on first access if table is empty
    if not sites:
        from cookdex.recipe_dredger.sites import DEFAULT_SITES
        # Suggested sources start switched off; people choose what to crawl.
        store.seed_defaults(DEFAULT_SITES, enabled=False)
        sites = store.get_all_sites()
    return {"sites": sites}


@router.post("/settings/dredger-sites")
def add_dredger_site(
    payload: DredgerSiteCreateRequest,
    _session: dict[str, Any] = Depends(require_editor_session),
    _services: Services = Depends(require_services),
) -> dict[str, Any]:
    import sqlite3 as _sqlite3

    url = payload.url.strip().rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

    # Validate URL is reachable and has a sitemap
    validation = _validate_dredger_site_url(url)
    if not validation["reachable"]:
        raise HTTPException(
            status_code=422,
            detail=f"Site is not reachable: {validation.get('error', 'unknown error')}",
        )
    if not validation["sitemap_found"]:
        raise HTTPException(
            status_code=422,
            detail="No sitemap found. The dredger needs a sitemap to discover recipes. Check that this is a recipe blog with a sitemap.xml.",
        )

    store = _get_dredger_store()
    try:
        site_id = store.add_site(url, label=payload.label, group=payload.group)
    except _sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="This site URL already exists.")

    return {
        "id": site_id,
        "url": url,
        "validation": validation,
    }


@router.put("/settings/dredger-sites/{site_id}")
def update_dredger_site(
    site_id: int,
    payload: DredgerSiteUpdateRequest,
    _session: dict[str, Any] = Depends(require_editor_session),
    _services: Services = Depends(require_services),
) -> dict[str, Any]:
    if payload.url is not None:
        url = payload.url.strip().rstrip("/")
        if not url.startswith("http://") and not url.startswith("https://"):
            raise HTTPException(status_code=422, detail="URL must start with http:// or https://")
        payload.url = url

    store = _get_dredger_store()
    updated = store.update_site(
        site_id,
        url=payload.url,
        label=payload.label,
        group=payload.group,
        enabled=payload.enabled,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Site not found.")
    return {"ok": True}


@router.delete("/settings/dredger-sites/{site_id}")
def delete_dredger_site(
    site_id: int,
    _session: dict[str, Any] = Depends(require_editor_session),
    _services: Services = Depends(require_services),
) -> dict[str, Any]:
    store = _get_dredger_store()
    deleted = store.delete_site(site_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Site not found.")
    return {"ok": True}


@router.post("/settings/dredger-sites/seed")
def seed_dredger_sites(
    payload: DredgerSitesSeedRequest,
    _session: dict[str, Any] = Depends(require_editor_session),
    _services: Services = Depends(require_services),
) -> dict[str, Any]:
    from cookdex.recipe_dredger.sites import DEFAULT_SITES
    store = _get_dredger_store()
    inserted = store.seed_defaults(DEFAULT_SITES, force=payload.force, merge=payload.merge)
    return {"ok": True, "inserted": inserted}


def _validate_dredger_site_url(url: str) -> dict[str, Any]:
    """Check if a site URL is reachable and has a crawlable sitemap."""
    result: dict[str, Any] = {"reachable": False, "sitemap_found": False, "error": ""}
    try:
        validated_url = _validate_service_url(url)
    except ValueError:
        result["error"] = "Site URL is invalid or points to a blocked address."
        return result

    try:
        resp = request_with_url_validation(requests, "HEAD", validated_url, timeout=10)
        result["reachable"] = resp.status_code < 400
        if not result["reachable"]:
            result["error"] = f"HTTP {resp.status_code}"
            return result
    except requests.RequestException as exc:
        result["error"] = _safe_request_error(exc)
        return result

    # Check for sitemap
    sitemap_candidates = [
        f"{validated_url}/sitemap.xml",
        f"{validated_url}/sitemap_index.xml",
        f"{validated_url}/wp-sitemap.xml",
    ]
    for sitemap_url in sitemap_candidates:
        try:
            resp = request_with_url_validation(requests, "HEAD", sitemap_url, timeout=5)
            if resp.status_code == 200:
                result["sitemap_found"] = True
                break
        except requests.RequestException:
            continue

    return result


@router.post("/settings/dredger-sites/validate")
async def validate_dredger_sites(
    payload: DredgerSitesValidateRequest,
    _session: dict[str, Any] = Depends(require_editor_session),
    _services: Services = Depends(require_services),
) -> dict[str, Any]:
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    store = _get_dredger_store()
    all_sites = store.get_all_sites()

    if payload.site_ids:
        target_ids = set(payload.site_ids)
        sites_to_check = [s for s in all_sites if s["id"] in target_ids]
    else:
        sites_to_check = all_sites

    def _check_one(site: dict[str, Any]) -> dict[str, Any]:
        validation = _validate_dredger_site_url(site["url"])
        return {"id": site["id"], "url": site["url"], **validation}

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [loop.run_in_executor(pool, _check_one, s) for s in sites_to_check]
        results = await asyncio.gather(*futures)

    return {"results": list(results)}
