from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException

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


def _test_mealie_connection(url: str, api_key: str) -> tuple[bool, str, dict[str, Any]]:
    """Test Mealie connection and return (ok, message, capabilities)."""
    base_url = _validate_service_url(url.rstrip("/"), allow_private=True)
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    capabilities: dict[str, Any] = {}
    try:
        response = requests.get(f"{base_url}/users/self", headers=headers, timeout=12)
        response.raise_for_status()
    except requests.RequestException as exc:
        return False, _safe_request_error(exc), capabilities

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

    detail = "Mealie connection validated."
    if capabilities.get("version"):
        detail = f"Mealie {capabilities['version']} connected."
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
async def get_settings(
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    secret_keys = sorted(services.state.list_encrypted_secrets().keys())
    return {
        "settings": services.state.list_settings(),
        "secrets": {key: "********" for key in secret_keys},
        "env": env_payload(services.state, services.cipher),
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
async def put_settings(
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

    return await get_settings(_session, services)


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
async def list_openai_models(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    api_key = resolve_runtime_value(runtime_env, "OPENAI_API_KEY", payload.openai_api_key)
    models = _list_openai_models(api_key)
    return {"ok": bool(models), "models": models}


@router.post("/settings/models/ollama")
async def list_ollama_models(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    ollama_url = resolve_runtime_value(runtime_env, "OLLAMA_URL", payload.ollama_url)
    models = _list_ollama_models(ollama_url)
    return {"ok": bool(models), "models": models}


@router.post("/settings/models/anthropic")
async def list_anthropic_models(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    api_key = resolve_runtime_value(runtime_env, "ANTHROPIC_API_KEY", payload.anthropic_api_key)
    models = _list_anthropic_models(api_key)
    return {"ok": bool(models), "models": models}


@router.post("/settings/test/mealie")
async def test_mealie_settings(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    mealie_url = resolve_runtime_value(runtime_env, "MEALIE_URL", payload.mealie_url).rstrip("/")
    mealie_api_key = resolve_runtime_value(runtime_env, "MEALIE_API_KEY", payload.mealie_api_key)
    if not mealie_url or not mealie_api_key:
        return {"ok": False, "detail": "Mealie URL and API key are required."}
    ok, detail, capabilities = _test_mealie_connection(mealie_url, mealie_api_key)
    result: dict[str, Any] = {"ok": ok, "detail": detail}
    if capabilities:
        result["capabilities"] = capabilities
    return result


@router.post("/settings/test/openai")
async def test_openai_settings(
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
async def test_ollama_settings(
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
async def test_anthropic_settings(
    payload: ProviderConnectionTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    anthropic_api_key = resolve_runtime_value(runtime_env, "ANTHROPIC_API_KEY", payload.anthropic_api_key)
    anthropic_model = resolve_runtime_value(runtime_env, "ANTHROPIC_MODEL", payload.anthropic_model)
    ok, detail = _test_anthropic_connection(anthropic_api_key, anthropic_model)
    return {"ok": ok, "detail": detail, "model": anthropic_model}


_DB_ENV_KEYS = (
    "MEALIE_DB_TYPE",
    "MEALIE_PG_HOST",
    "MEALIE_PG_PORT",
    "MEALIE_PG_DB",
    "MEALIE_PG_USER",
    "MEALIE_PG_PASS",
    "MEALIE_DB_SSH_HOST",
    "MEALIE_DB_SSH_USER",
    "MEALIE_DB_SSH_KEY",
)


_ALLOWED_DB_TYPES = frozenset({"postgres", "sqlite"})


def _test_db_connection(runtime_env: dict[str, str]) -> tuple[bool, str]:
    db_type_val = runtime_env.get("MEALIE_DB_TYPE", "").strip().lower()
    if not db_type_val:
        return False, "MEALIE_DB_TYPE is not configured. Set it to 'postgres' or 'sqlite'."
    if db_type_val not in _ALLOWED_DB_TYPES:
        return False, f"Unsupported MEALIE_DB_TYPE '{db_type_val}'. Use 'postgres' or 'sqlite'."

    saved: dict[str, str | None] = {}
    try:
        for key in _DB_ENV_KEYS:
            saved[key] = os.environ.get(key)
            val = str(runtime_env.get(key, "")).strip()
            if "\x00" in val or "\n" in val:
                continue
            if val:
                os.environ[key] = val
            else:
                os.environ.pop(key, None)

        from cookdex.db_client import MealieDBClient

        with MealieDBClient() as db:
            group_id = db.get_group_id()
        if group_id:
            return True, f"DB connection validated. Group: {group_id[:8]}\u2026"
        return True, "DB connection validated (no household found, but connection succeeded)."
    except Exception as exc:
        return False, f"DB connection failed: {type(exc).__name__}."
    finally:
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


@router.post("/settings/test/db")
async def test_db_settings(
    payload: DbTestRequest,
    _session: dict[str, Any] = Depends(require_owner_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    # Override with draft values from the UI (same pattern as other test endpoints)
    _db_overrides = {
        "MEALIE_DB_TYPE": payload.db_type,
        "MEALIE_PG_HOST": payload.pg_host,
        "MEALIE_PG_PORT": payload.pg_port,
        "MEALIE_PG_DB": payload.pg_db,
        "MEALIE_PG_USER": payload.pg_user,
        "MEALIE_PG_PASS": payload.pg_pass,
        "MEALIE_DB_SSH_HOST": payload.ssh_host,
        "MEALIE_DB_SSH_USER": payload.ssh_user,
        "MEALIE_DB_SSH_KEY": payload.ssh_key,
    }
    for key, value in _db_overrides.items():
        if value is not None:
            runtime_env[key] = value
    ok, detail = _test_db_connection(runtime_env)
    return {"ok": ok, "detail": detail}


# ------------------------------------------------------------------
# DB auto-detect via SSH
# ------------------------------------------------------------------

# Mealie container env vars → CookDex env var names

@router.post("/settings/detect/db")
async def detect_db_settings(
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
        return {"ok": ok, "detail": detail, "detected": detected}
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
async def list_dredger_sites(
    _session: dict[str, Any] = Depends(require_editor_session),
    _services: Services = Depends(require_services),
) -> dict[str, Any]:
    store = _get_dredger_store()
    sites = store.get_all_sites()
    # Auto-seed defaults on first access if table is empty
    if not sites:
        from cookdex.recipe_dredger.sites import DEFAULT_SITES
        store.seed_defaults(DEFAULT_SITES)
        sites = store.get_all_sites()
    return {"sites": sites}


@router.post("/settings/dredger-sites")
async def add_dredger_site(
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
async def update_dredger_site(
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
async def delete_dredger_site(
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
async def seed_dredger_sites(
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
