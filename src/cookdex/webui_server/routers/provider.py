"""Which recipe manager CookDex is connected to, and what it can do.

The UI uses this to word things for the backend (Mealie's "cookbooks",
Tandoor's "books") and to hide features the backend doesn't have. It never
contacts the backend.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...providers import BACKENDS, ProviderError, describe_backend
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
