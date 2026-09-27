from __future__ import annotations

from dataclasses import dataclass


DEFAULT_MAX_RUN_DURATION_SECONDS = 4 * 60 * 60
MAX_RUN_DURATION_SECONDS_CAP = 12 * 60 * 60


@dataclass(frozen=True)
class EnvVarSpec:
    key: str
    label: str
    group: str
    default: str
    secret: bool
    description: str
    choices: tuple[str, ...] = ()
    # Hidden settings still work but aren't shown in Settings: deployment
    # values that belong in the container environment, and older keys that a
    # newer setting replaced.
    hidden: bool = False


ENV_VAR_SPECS: tuple[EnvVarSpec, ...] = (
    EnvVarSpec(
        key="UPDATE_CHECK_ENABLED", label="Check for updates", group="Updates",
        default="true", secret=False, choices=("true", "false"),
        description="Once a day, asks GitHub whether there's a newer CookDex. Sends only the version number.",
    ),
    EnvVarSpec(
        key="MEALIE_URL",
        label="Mealie address",
        group="Connection",
        default="",
        secret=False,
        description="The address you open Mealie at, like http://mealie:9000. CookDex adds /api for you.",
    ),
    EnvVarSpec(
        key="MEALIE_API_KEY",
        label="Mealie API token",
        group="Connection",
        default="",
        secret=True,
        description="Create one in Mealie: your profile, then API Tokens. Mealie shows it only once.",
    ),
    EnvVarSpec(
        key="CATEGORIZER_PROVIDER",
        label="AI provider",
        group="AI",
        default="chatgpt",
        secret=False,
        description="Which AI suggests what the tagging rules miss. Off uses rules only.",
    ),
    EnvVarSpec(
        key="OPENAI_MODEL",
        label="OpenAI model",
        group="AI",
        default="gpt-4o-mini",
        secret=False,
        description="Load models lists the ones your key can use. gpt-4o-mini is cheap and good enough for tagging.",
    ),
    EnvVarSpec(
        key="OPENAI_API_KEY",
        label="OpenAI API key",
        group="AI",
        default="",
        secret=True,
        description="From platform.openai.com, under API keys. Stored encrypted.",
    ),
    EnvVarSpec(
        key="ANTHROPIC_API_KEY",
        label="Anthropic API key",
        group="AI",
        default="",
        secret=True,
        description="From console.anthropic.com, under API Keys. Stored encrypted.",
    ),
    EnvVarSpec(
        key="ANTHROPIC_MODEL",
        label="Anthropic model",
        group="AI",
        default="",
        secret=False,
        description="Load models lists the ones your key can use.",
    ),
    EnvVarSpec(
        key="OLLAMA_URL",
        label="Ollama address",
        group="AI",
        default="http://host.docker.internal:11434/api",
        secret=False,
        description="Where your Ollama server answers, like http://host.docker.internal:11434.",
    ),
    EnvVarSpec(
        key="OLLAMA_MODEL",
        label="Ollama model",
        group="AI",
        default="",
        secret=False,
        description="Load models lists what your Ollama server has pulled.",
    ),
    EnvVarSpec(
        key="OLLAMA_NUM_CTX",
        label="Context window",
        group="AI",
        default="2048",
        secret=False,
        description="Token context window for Ollama inference. Lower defaults keep CPU-only local models responsive.",
    ),
    EnvVarSpec(
        key="OLLAMA_NUM_PREDICT",
        label="Longest answer (tokens)",
        group="AI",
        default="512",
        secret=False,
        description="Maximum tokens the model can generate per request. Lower defaults reduce local model stalls.",
    ),
    EnvVarSpec(
        key="OLLAMA_BATCH_SIZE",
        label="Recipes per request",
        group="AI",
        default="1",
        secret=False,
        description="Recipes per Ollama categorizer request. Default 1 keeps local CPU models visibly moving.",
    ),
    EnvVarSpec(
        key="OLLAMA_NUM_THREAD",
        label="CPU threads",
        group="AI",
        default="4",
        secret=False,
        description="CPU threads used by Ollama generation. Default 4 matches modest self-hosted containers.",
    ),
    EnvVarSpec(
        key="OLLAMA_REQUEST_TIMEOUT",
        label="Wait per request (seconds)",
        group="AI",
        default="300",
        secret=False,
        description="Seconds to wait for each Ollama request before retrying.",
    ),
    EnvVarSpec(
        key="AI_BATCH_HEARTBEAT_SECONDS",
        label="Progress message every (seconds)",
        group="AI",
        default="30",
        secret=False,
        description="While the AI works on a batch, the log says so this often. 0 turns it off.",
    ),
    EnvVarSpec(
        key="COOKDEX_BACKEND",
        label="Recipe manager",
        group="Behavior",
        default="mealie",
        secret=False,
        description="Which recipe manager CookDex works with. Only mealie is available today.",
        hidden=True,
    ),
    # ------------------------------------------------------------------
    # Dredger
    # ------------------------------------------------------------------
    EnvVarSpec(
        key="DREDGER_TARGET_LANGUAGE",
        label="Recipe language",
        group="Dredger",
        default="en",
        secret=False,
        description="Recipes in other languages are skipped.",
        choices=(
            "en", "es", "fr", "de", "it", "pt", "nl", "pl", "sv", "da",
            "no", "fi", "ru", "uk", "ja", "ko", "zh", "th", "vi", "id",
            "tr", "ar", "he", "hi", "el", "cs", "ro", "hu", "hr", "bg",
        ),
    ),
    EnvVarSpec(
        key="DREDGER_CRAWL_DELAY",
        label="Pause between pages (seconds)",
        group="Dredger",
        default="2.0",
        secret=False,
        description="How long to wait between pages on the same site. A site's own robots.txt wins when it asks for longer.",
    ),
    EnvVarSpec(
        key="DREDGER_CACHE_EXPIRY_DAYS",
        label="Re-read site maps after (days)",
        group="Dredger",
        default="7",
        secret=False,
        description="How long a site's list of recipe pages is reused before it's read again.",
    ),
    EnvVarSpec(
        key="WEB_BIND_PORT",
        label="Web UI Port",
        group="Web UI",
        default="4820",
        secret=False,
        description="Web UI bind port inside container runtime.",
        hidden=True,
    ),
    EnvVarSpec(
        key="WEB_BASE_PATH",
        label="Web UI Path",
        group="Web UI",
        default="/cookdex",
        secret=False,
        description="Web UI route prefix.",
        hidden=True,
    ),
    EnvVarSpec(
        key="WEB_SESSION_TTL_SECONDS",
        label="Session Timeout (seconds)",
        group="Web UI",
        default="43200",
        secret=False,
        description="Session TTL in seconds for Web UI login cookies.",
        hidden=True,
    ),
    # ------------------------------------------------------------------
    # Direct DB access (optional). Tasks use it on their own once it's set.
    # MEALIE_DB_URL replaced MEALIE_DB_TYPE and the MEALIE_PG_* keys, which
    # still work and are folded into it on startup.
    # ------------------------------------------------------------------
    EnvVarSpec(
        key="MEALIE_DB_URL",
        label="Database connection",
        group="Direct DB",
        default="",
        secret=True,
        description=(
            "Mealie's POSTGRES_ user, password, server, port and database as one line, like "
            "postgresql://mealie:password@postgres:5432/mealie."
        ),
    ),
    EnvVarSpec(
        key="MEALIE_DB_TYPE",
        label="DB Type",
        group="Direct DB",
        default="",
        secret=False,
        description="Set to 'postgres' or 'sqlite' to enable direct DB access. Leave blank to use API-only mode.",
        choices=("", "postgres", "sqlite"),
        hidden=True,
    ),
    EnvVarSpec(
        key="MEALIE_PG_HOST",
        label="Postgres Host",
        group="Direct DB",
        default="localhost",
        secret=False,
        description="Postgres server hostname or IP. Used when MEALIE_DB_TYPE=postgres.",
        hidden=True,
    ),
    EnvVarSpec(
        key="MEALIE_PG_PORT",
        label="Postgres Port",
        group="Direct DB",
        default="5432",
        secret=False,
        description="Postgres server port.",
        hidden=True,
    ),
    EnvVarSpec(
        key="MEALIE_PG_DB",
        label="Postgres Database",
        group="Direct DB",
        default="mealie_db",
        secret=False,
        description="Postgres database name.",
        hidden=True,
    ),
    EnvVarSpec(
        key="MEALIE_PG_USER",
        label="Postgres User",
        group="Direct DB",
        default="mealie__user",
        secret=False,
        description="Postgres user name.",
        hidden=True,
    ),
    EnvVarSpec(
        key="MEALIE_PG_PASS",
        label="Postgres Password",
        group="Direct DB",
        default="",
        secret=True,
        description="Postgres password (stored encrypted).",
        hidden=True,
    ),
    EnvVarSpec(
        key="MEALIE_DB_SSH_HOST",
        label="SSH host",
        group="Direct DB",
        default="",
        secret=False,
        description="Only if CookDex can't reach the database directly. CookDex connects to this machine over SSH first, then to the database from there.",
    ),
    EnvVarSpec(
        key="MEALIE_DB_SSH_USER",
        label="SSH user",
        group="Direct DB",
        default="root",
        secret=False,
        description="The user CookDex signs in to the SSH host as.",
    ),
    EnvVarSpec(
        key="MEALIE_DB_SSH_KEY",
        label="SSH key file",
        group="Direct DB",
        default="/app/.ssh/cookdex_mealie",
        secret=False,
        description="Where the private key is inside the CookDex container, like /app/.ssh/cookdex_mealie.",
    ),
    EnvVarSpec(
        key="MAX_RUN_DURATION_SECONDS",
        label="Stop a run after",
        group="Runner",
        default=str(DEFAULT_MAX_RUN_DURATION_SECONDS),
        secret=False,
        description="A job still running after this long is stopped. Up to 12 hours.",
    ),
)

ENV_SPEC_BY_KEY: dict[str, EnvVarSpec] = {item.key: item for item in ENV_VAR_SPECS}
