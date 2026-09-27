"""Recipe-manager backends. See providers/base.py for the contract.

``get_provider(env)`` picks the backend from ``COOKDEX_BACKEND`` (default
``mealie``). Adding a backend means implementing RecipeProvider and listing
it in BACKENDS; pages built on providers then work with it.
"""
from __future__ import annotations

from typing import Callable

from .base import Capability, ProviderError, ProviderInfo, RecipeProvider, Term, UnsupportedCapability
from .mealie import MealieProvider

BACKENDS: dict[str, Callable[[dict[str, str]], RecipeProvider]] = {
    "mealie": MealieProvider.from_env,
}

# Unconnected instances, for describing a backend (capabilities, wording)
# without credentials or network access.
DESCRIBERS: dict[str, Callable[[], RecipeProvider]] = {
    "mealie": lambda: MealieProvider(None),
}


def describe_backend(env: dict[str, str]) -> RecipeProvider:
    kind = backend_kind(env)
    describer = DESCRIBERS.get(kind)
    if describer is None:
        raise ProviderError(f"CookDex doesn't support the '{kind}' backend yet. Supported: {', '.join(BACKENDS)}.")
    return describer()


def backend_kind(env: dict[str, str]) -> str:
    return str(env.get("COOKDEX_BACKEND") or "mealie").strip().lower() or "mealie"


def get_provider(env: dict[str, str]) -> RecipeProvider:
    kind = backend_kind(env)
    factory = BACKENDS.get(kind)
    if factory is None:
        raise ProviderError(f"CookDex doesn't support the '{kind}' backend yet. Supported: {', '.join(BACKENDS)}.")
    return factory(env)


__all__ = [
    "BACKENDS", "Capability", "MealieProvider", "ProviderError", "ProviderInfo", "RecipeProvider",
    "Term", "UnsupportedCapability", "backend_kind", "describe_backend", "get_provider",
]
