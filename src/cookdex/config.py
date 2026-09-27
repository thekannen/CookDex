import os
from pathlib import Path

from dotenv import dotenv_values


def _looks_like_repo_root(path: Path) -> bool:
    return (path / "configs" / "taxonomy").exists()


def _discover_repo_root() -> Path:
    env_root = os.environ.get("COOKDEX_ROOT", "").strip()
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if candidate.exists():
            return candidate

    source_root = Path(__file__).resolve().parents[2]
    for candidate in (Path.cwd(), Path("/app"), source_root):
        if _looks_like_repo_root(candidate):
            return candidate
    return source_root


REPO_ROOT = _discover_repo_root()
ENV_FILE = REPO_ROOT / ".env"
MEALIE_URL_PLACEHOLDER = "http://your.server.ip.address:9000/api"


def load_env_file(path):
    if not path.exists():
        return

    for key, value in dotenv_values(path).items():
        key = str(key or "").strip()
        if not key or value is None:
            continue
        os.environ.setdefault(key, str(value))


load_env_file(ENV_FILE)


def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    raise ValueError(f"Invalid boolean value: {value}")


def normalize_mealie_url(value):
    """Return the Mealie API base URL for a user-entered address.

    People usually paste the address they open Mealie at. Every Mealie API
    route lives under ``/api``, so append it when missing and drop trailing
    slashes. Blank input stays blank.
    """
    url = str(value or "").strip().rstrip("/")
    if not url:
        return ""
    if not url.lower().endswith("/api"):
        url = f"{url}/api"
    return url


def require_mealie_url(value):
    if not isinstance(value, str):
        raise RuntimeError(f"MEALIE_URL must be a string, got {type(value).__name__}.")

    url = value.strip()
    if not url or url.lower() == MEALIE_URL_PLACEHOLDER.lower() or "your.server.ip.address" in url.lower():
        raise RuntimeError(
            "MEALIE_URL is not configured. Set MEALIE_URL in .env or the environment."
        )

    return normalize_mealie_url(url)


def env_or_config(env_key, config_path=None, default=None, cast=None):
    """Resolve a setting from env var, falling back to *default*.

    The *config_path* parameter is accepted for backward compatibility but
    is **ignored** — all runtime configuration comes from the UI / env vars,
    never from config files.
    """
    raw_env = os.environ.get(env_key)
    if raw_env is not None and raw_env != "":
        raw = raw_env
        source = f"env '{env_key}'"
    else:
        raw = default
        source = "default"

    if raw is None:
        return None

    if cast is None:
        return raw

    try:
        return cast(raw)
    except Exception as exc:
        raise ValueError(f"Invalid value from {source}: {raw}") from exc


def secret(env_key, required=False, default=""):
    value = os.environ.get(env_key, default)
    if required and not value:
        raise RuntimeError(
            f"{env_key} is not set. Add it in CookDex Settings, or set it in the container environment."
        )
    return value


# Settings each AI provider needs before it can be used. Ollama's URL has a
# default, so the model is what shows the user actually set it up.
AI_PROVIDER_REQUIREMENTS = {
    "chatgpt": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    "ollama": ("OLLAMA_URL", "OLLAMA_MODEL"),
}


def ai_provider_ready(provider, env=None):
    """Return True when *provider* is known and all its settings are filled in."""
    source = os.environ if env is None else env
    required = AI_PROVIDER_REQUIREMENTS.get(str(provider or "").strip().lower())
    if not required:
        return False
    return all(str(source.get(key, "") or "").strip() for key in required)


def configured_ai_providers(env=None):
    """Return the providers that are ready to use, in display order."""
    return [name for name in AI_PROVIDER_REQUIREMENTS if ai_provider_ready(name, env)]


def resolve_repo_path(path_value):
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def resolve_mealie_url():
    primary = os.environ.get("MEALIE_URL")
    legacy = os.environ.get("MEALIE_BASE_URL")
    if primary and primary.strip():
        return require_mealie_url(primary)
    if legacy and legacy.strip():
        print("[warn] MEALIE_BASE_URL is deprecated; prefer MEALIE_URL.", flush=True)
        return require_mealie_url(legacy)
    return require_mealie_url(MEALIE_URL_PLACEHOLDER)


def resolve_mealie_api_key(required=True):
    primary = os.environ.get("MEALIE_API_KEY", "").strip()
    if primary:
        return primary
    legacy = os.environ.get("MEALIE_API_TOKEN", "").strip()
    if legacy:
        print("[warn] MEALIE_API_TOKEN is deprecated; prefer MEALIE_API_KEY.", flush=True)
        return legacy
    if required:
        raise RuntimeError("MEALIE_API_KEY is empty. Set MEALIE_API_KEY (or legacy MEALIE_API_TOKEN).")
    return ""
