"""Which recipe manager CookDex is connected to, and what it can do.

The UI uses this to word things for the backend (Mealie's "cookbooks",
Tandoor's "books") and to hide features the backend doesn't have. Only /provider/status
contacts the backend, and it caches the answer briefly.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...providers import BACKENDS, ProviderError, describe_backend, get_provider
from ..deps import Services, build_runtime_env, require_session, require_services

router = APIRouter(tags=["provider"])


@router.get("/provider")
def get_provider_info(
    _session: dict[str, Any] = Depends(require_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    env = build_runtime_env(services.state, services.cipher)
    try:
        provider = describe_backend(env)
    except ProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "kind": provider.kind,
        "name": provider.display_name,
        "capabilities": sorted(c.value for c in provider.capabilities()),
        "term_kinds": provider.term_kinds(),
        "vocabulary": provider.vocabulary(),
        "backends": sorted(BACKENDS),
    }


_STATUS_TTL = 30.0
_status_lock = threading.Lock()
_status_cache: dict[str, Any] = {"key": None, "at": 0.0, "value": None}


@router.get("/provider/status")
def get_provider_status(
    _session: dict[str, Any] = Depends(require_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    """Whether CookDex can reach the recipe manager right now, for an app-wide notice."""
    env = build_runtime_env(services.state, services.cipher)
    key = (env.get("MEALIE_URL", ""), env.get("MEALIE_API_KEY", ""))
    with _status_lock:
        cached = _status_cache
        if cached["key"] == key and time.monotonic() - cached["at"] < _STATUS_TTL and cached["value"] is not None:
            return cached["value"]
    try:
        provider = get_provider(env)
    except ProviderError as exc:
        value = {"configured": False, "ok": False, "detail": str(exc)}
    else:
        try:
            info = provider.health()
            value = {"configured": True, "ok": True, "detail": "", "version": info.version}
        except ProviderError as exc:
            value = {"configured": True, "ok": False, "detail": str(exc)}
    with _status_lock:
        _status_cache.update({"key": key, "at": time.monotonic(), "value": value})
    return value
