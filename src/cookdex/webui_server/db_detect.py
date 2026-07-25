"""Mealie database credential detection over SSH.

Split out of ``routers/settings_api.py``: this is the machinery behind the
single ``POST /settings/detect/db`` endpoint — SSH execution, container
probing, and parsing Mealie's env/compose files — and it has no dependency
on FastAPI routing.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from io import StringIO
from urllib.parse import unquote, urlparse

import yaml
from dotenv import dotenv_values


_MEALIE_ENV_MAP: dict[str, str] = {
    "POSTGRES_USER": "MEALIE_PG_USER",
    "POSTGRES_PASSWORD": "MEALIE_PG_PASS",
    "POSTGRES_DB": "MEALIE_PG_DB",
    "POSTGRES_SERVER": "MEALIE_PG_HOST",
    "POSTGRES_PORT": "MEALIE_PG_PORT",
    "DB_ENGINE": "MEALIE_DB_TYPE",
}
_MEALIE_FILE_ENV_MAP: dict[str, str] = {
    "POSTGRES_USER_FILE": "MEALIE_PG_USER",
    "POSTGRES_PASSWORD_FILE": "MEALIE_PG_PASS",
    "POSTGRES_DB_FILE": "MEALIE_PG_DB",
    "POSTGRES_SERVER_FILE": "MEALIE_PG_HOST",
    "POSTGRES_PORT_FILE": "MEALIE_PG_PORT",
    "DB_ENGINE_FILE": "MEALIE_DB_TYPE",
    "POSTGRES_URL_OVERRIDE_FILE": "POSTGRES_URL_OVERRIDE",
}
_MEALIE_RAW_DB_KEYS = set(_MEALIE_ENV_MAP) | set(_MEALIE_FILE_ENV_MAP) | {"POSTGRES_URL_OVERRIDE"}


def _add_mealie_raw_env(raw: dict[str, str], key: object, value: object) -> None:
    clean_key = str(key or "").strip().strip("'\"").upper()
    if not re.fullmatch(r"[A-Z0-9_]+", clean_key):
        return
    if clean_key not in _MEALIE_RAW_DB_KEYS:
        return
    if value is None:
        return
    clean_value = str(value).strip()
    if re.search(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?::-[^}]*)?\}", clean_value):
        return
    if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", clean_value):
        return
    if clean_value:
        raw[clean_key] = clean_value


def _parse_dotenv_mealie_env(text: str) -> dict[str, str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            line = line[2:].strip()
        if line.startswith("Environment="):
            _prefix, _sep, env_values = line.partition("=")
            try:
                lines.extend(shlex.split(env_values))
            except ValueError:
                lines.append(env_values)
            continue
        lines.append(line)

    raw: dict[str, str] = {}
    try:
        parsed = dotenv_values(stream=StringIO("\n".join(lines)), interpolate=False)
    except Exception:
        return raw

    for key, value in parsed.items():
        _add_mealie_raw_env(raw, key, value)
    return raw


def _collect_yaml_mealie_env(value: object, raw: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _add_mealie_raw_env(raw, key, item)
            if str(key).strip().lower() == "environment" and isinstance(item, str):
                for env_key, env_item in _parse_dotenv_mealie_env(item).items():
                    raw[env_key] = env_item
        for item in value.values():
            _collect_yaml_mealie_env(item, raw)
        return

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                for env_key, env_item in _parse_dotenv_mealie_env(item).items():
                    raw[env_key] = env_item
            else:
                _collect_yaml_mealie_env(item, raw)
        return


def _parse_yaml_mealie_env(text: str) -> dict[str, str]:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}
    raw: dict[str, str] = {}
    _collect_yaml_mealie_env(parsed, raw)
    return raw


def _apply_postgres_url_override(result: dict[str, str], override: str) -> None:
    parsed = urlparse(override if "://" in override else f"postgresql://{override}")
    if parsed.hostname:
        result["MEALIE_PG_HOST"] = parsed.hostname
    if parsed.port:
        result["MEALIE_PG_PORT"] = str(parsed.port)
    if parsed.path and parsed.path.strip("/"):
        result["MEALIE_PG_DB"] = unquote(parsed.path.strip("/"))
    if parsed.username:
        result["MEALIE_PG_USER"] = unquote(parsed.username)
    if parsed.password:
        result["MEALIE_PG_PASS"] = unquote(parsed.password)
    result["MEALIE_DB_TYPE"] = "postgres"


def _normalize_tunneled_pg_host(result: dict[str, str]) -> None:
    pg_host = result.get("MEALIE_PG_HOST", "")
    if pg_host and not re.match(r"^(\d{1,3}\.){3}\d{1,3}$|^localhost$|^\[", pg_host):
        result["MEALIE_PG_HOST"] = "localhost"


def _validated_ssh_host(value: str) -> str:
    """Validate an SSH hostname/IP to prevent argument injection."""
    clean = str(value or "").strip()
    m = re.fullmatch(r"[A-Za-z0-9._:-]+", clean) if clean else None
    if not m:
        raise ValueError("Invalid SSH host.")
    return m.group()


def _validated_ssh_user(value: str) -> str:
    """Validate an SSH username to prevent argument injection."""
    clean = str(value or "").strip()
    m = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", clean) if clean else None
    if not m:
        raise ValueError("Invalid SSH user.")
    return m.group()


def _validated_container_name(value: str) -> str:
    """Validate a Docker container name to prevent command injection."""
    clean = str(value or "").strip()
    m = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", clean) if clean else None
    if not m:
        raise ValueError("Invalid container name.")
    return m.group()


def _validated_ssh_key_path(raw_path: str) -> str:
    """Resolve a user-provided SSH key path safely within allowed directories.

    Accepts a plain filename (e.g. ``cookdex_mealie``) or a path that
    includes a directory (e.g. ``~/.ssh/cookdex_mealie``,
    ``/app/.ssh/cookdex_mealie``).  The resolved file **must** reside
    directly inside one of the allowed directories — paths that escape
    are rejected to prevent path-traversal attacks.

    Allowed directories (checked in order):
      1. ``~/.ssh/``          — standard SSH key location
      2. ``/app/.ssh/``       — documented Docker volume mount path
      3. ``/tmp/.ssh-app/``   — entrypoint copy destination
    """
    candidate = str(raw_path or "").strip()
    if not candidate:
        raise ValueError("Invalid SSH key path.")

    # Extract just the filename; ignore any directory components the
    # caller may have supplied so the result is always inside an allowed dir.
    target_name = os.path.basename(os.path.expanduser(candidate))
    if not target_name or target_name.startswith("."):
        raise ValueError("Invalid SSH key filename.")

    # Search allowed directories for the key file.
    allowed_dirs = [
        os.path.realpath(os.path.expanduser("~/.ssh")),
        "/app/.ssh",
        "/tmp/.ssh-app",
    ]

    for ssh_dir in allowed_dirs:
        try:
            dir_entries = os.listdir(ssh_dir)
        except OSError:
            continue

        # Match against the directory listing (untainted source) and build
        # the return path from the listing entry, breaking the taint chain.
        matched = next((e for e in dir_entries if e == target_name), None)
        if matched is None:
            continue

        safe_path = os.path.realpath(os.path.join(ssh_dir, matched))

        # Ensure the resolved path is under this allowed directory.
        real_dir = os.path.realpath(ssh_dir)
        if not safe_path.startswith(real_dir + os.sep) and safe_path != real_dir:
            continue

        if not os.path.isfile(safe_path):
            continue

        # Must be readable by the current process user — a root-owned 600
        # file in /app/.ssh/ won't work when running as the app user.
        if not os.access(safe_path, os.R_OK):
            continue

        return safe_path

    raise FileNotFoundError("SSH key not found.")


class _HostKeyChangedError(Exception):
    """Raised when a host presents a key that differs from the stored one."""


def _subprocess_ssh(
    host: str, user: str, key_path: str, command: str, timeout: int,
) -> tuple[str, str, int]:
    """Run an SSH command via subprocess using a temporary config file.

    All user-derived values (host, user, key path) are written to a
    temporary SSH config file rather than passed as command-line arguments,
    preventing command-line injection.  The remote command is delivered via
    stdin to a remote ``sh`` process.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ssh_config", delete=False, prefix="cookdex_ssh_",
    ) as cfg:
        cfg.write(f"Host target\n")
        cfg.write(f"  Hostname {host}\n")
        cfg.write(f"  User {user}\n")
        cfg.write(f"  IdentityFile {key_path}\n")
        cfg.write(f"  BatchMode yes\n")
        cfg.write(f"  ConnectTimeout {max(3, timeout)}\n")
        cfg.write(f"  StrictHostKeyChecking accept-new\n")
        cfg.write(f"  PasswordAuthentication no\n")
        config_path = cfg.name

    try:
        completed = subprocess.run(
            ["ssh", "-F", config_path, "target", "sh"],
            input=command,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
        return completed.stdout, completed.stderr, int(completed.returncode)
    finally:
        try:
            os.unlink(config_path)
        except OSError:
            pass


def _ssh_exec(
    host: str,
    user: str,
    key_path: str,
    command: str,
    *,
    timeout: int = 15,
) -> tuple[str, str, int]:
    """Run a single command over SSH and return (stdout, stderr, exit_code)."""
    host = _validated_ssh_host(host)
    user = _validated_ssh_user(user)
    resolved_key = _validated_ssh_key_path(key_path)

    # Prefer paramiko when available; fall back to native ssh binary.
    try:
        import paramiko
    except ModuleNotFoundError:
        paramiko = None  # type: ignore[assignment]

    if paramiko is None:
        return _subprocess_ssh(host, user, resolved_key, command, timeout)

    # Find a writable directory for known_hosts — ~/.ssh/ may not exist
    # when running as the app user (HOME=/nonexistent).
    _kh_dir = os.path.realpath(os.path.expanduser("~/.ssh"))
    if not os.path.isdir(_kh_dir):
        for _alt in ["/tmp/.ssh-app", "/tmp"]:
            if os.path.isdir(_alt) and os.access(_alt, os.W_OK):
                _kh_dir = _alt
                break
    known_hosts = os.path.join(_kh_dir, "known_hosts")

    class _TofuPolicy(paramiko.MissingHostKeyPolicy):
        """Trust-on-first-use: persist new host keys, reject changes."""

        def missing_host_key(
            self,
            client: paramiko.SSHClient,
            hostname: str,
            key: paramiko.PKey,
        ) -> None:
            host_keys = paramiko.HostKeys()
            if os.path.isfile(known_hosts):
                host_keys.load(known_hosts)
            entry = host_keys.lookup(hostname)
            if entry is not None:
                stored = entry.get(key.get_name())
                if stored is not None:
                    if stored == key:
                        return
                    raise _HostKeyChangedError(
                        f"Host key for '{hostname}' has changed."
                    )
            host_keys.add(hostname, key.get_name(), key)
            os.makedirs(os.path.dirname(known_hosts), exist_ok=True)
            host_keys.save(known_hosts)

    client = paramiko.SSHClient()  # type: ignore[union-attr]
    client.set_missing_host_key_policy(_TofuPolicy())  # type: ignore[union-attr]
    try:
        try:
            client.connect(
                hostname=host,
                username=user,
                key_filename=resolved_key,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return (
                stdout.read().decode("utf-8", errors="replace"),
                stderr.read().decode("utf-8", errors="replace"),
                exit_code,
            )
        except _HostKeyChangedError:
            # A changed host key is a security signal, not a transport
            # problem — retrying over the ssh binary would only hide it.
            raise
        except Exception:
            return _subprocess_ssh(host, user, resolved_key, command, timeout)
    finally:
        client.close()


def _parse_mealie_env(text: str) -> dict[str, str]:
    """Parse Mealie DB env assignments and map to CookDex DB keys."""
    raw: dict[str, str] = {}
    raw.update(_parse_dotenv_mealie_env(text))
    raw.update(_parse_yaml_mealie_env(text))

    result: dict[str, str] = {}
    for key, cookdex_key in _MEALIE_ENV_MAP.items():
        value = raw.get(key)
        if value:
            result[cookdex_key] = value

    # If *_FILE variants are set (Mealie docs: Docker secrets), they take precedence.
    for key, cookdex_key in _MEALIE_FILE_ENV_MAP.items():
        value = raw.get(key)
        if not value:
            continue
        # Keep path around for later remote resolution.
        result[f"__FILE__:{cookdex_key}"] = value

    # POSTGRES_URL_OVERRIDE has priority over individual POSTGRES_* values.
    override = raw.get("POSTGRES_URL_OVERRIDE")
    if override:
        _apply_postgres_url_override(result, override)

    # Infer DB type from presence of Postgres vars if DB_ENGINE not set
    if "MEALIE_DB_TYPE" not in result and (
        "MEALIE_PG_USER" in result or
        "MEALIE_PG_HOST" in result or
        "MEALIE_PG_DB" in result
    ):
        result["MEALIE_DB_TYPE"] = "postgres"

    # If POSTGRES_SERVER is a Docker service name, map to localhost (tunnel handles routing)
    _normalize_tunneled_pg_host(result)

    return result


def _parse_env_probe_blocks(text: str) -> list[tuple[str, str]]:
    marker = "__CFG_FILE__:"
    blocks: list[tuple[str, str]] = []
    current_path = ""
    current_lines: list[str] = []
    seen_paths: set[str] = set()

    for raw_line in text.splitlines():
        line = str(raw_line).strip()
        if line.startswith(marker):
            if current_path and current_path not in seen_paths:
                blocks.append((current_path, "\n".join(current_lines)))
                seen_paths.add(current_path)
            current_path = line[len(marker) :].strip()
            current_lines = []
            continue
        if current_path:
            current_lines.append(line)

    if current_path and current_path not in seen_paths:
        blocks.append((current_path, "\n".join(current_lines)))

    return blocks


def _detect_db_credentials_from_env_files(
    ssh_host: str, ssh_user: str, ssh_key: str,
) -> tuple[bool, str, dict[str, str]]:
    probe_cmd = r"""
set +e
emit() {
  p="$1"
  if [ -r "$p" ] && grep -q -E '(DB_ENGINE|POSTGRES_(USER|PASSWORD|DB|SERVER|PORT|URL_OVERRIDE)(_FILE)?|EnvironmentFile=.*mealie)' "$p" 2>/dev/null; then
    echo "__CFG_FILE__:$p"
    sed -n '1,260p' "$p" 2>/dev/null || true
  fi
}
for p in \
  /opt/mealie/mealie.env \
  /opt/mealie/.env \
  /opt/mealie/docker/docker-compose.yml \
  /opt/mealie/docker/docker-compose.yaml \
  /etc/mealie/mealie.env \
  /etc/mealie/.env \
  /etc/systemd/system/mealie.service \
  /srv/mealie/mealie.env \
  /srv/mealie/.env \
  /var/lib/mealie/mealie.env \
  /var/lib/mealie/.env \
  "$HOME/docker/mealie/docker-compose.yml" \
  "$HOME/docker/mealie/docker-compose.yaml" \
  "$HOME/mealie/docker-compose.yml" \
  "$HOME/mealie/docker-compose.yaml"
do
  emit "$p"
done
for p in $(find /opt /etc /srv /var/lib /home -maxdepth 6 -type f \
  \( -name 'mealie.env' -o -name '.env' -o -name '*mealie*.env' -o -name 'docker-compose.yml' -o -name 'docker-compose.yaml' -o -name 'compose.yml' -o -name 'compose.yaml' -o -name 'mealie.service' \) \
  2>/dev/null | head -n 140); do
  emit "$p"
done
"""
    try:
        out, _err, _code = _ssh_exec(ssh_host, ssh_user, ssh_key, probe_cmd, timeout=20)
    except Exception:
        return False, "Could not read Mealie env files over SSH.", {}

    blocks = _parse_env_probe_blocks(out)
    if not blocks:
        return (
            False,
            "No Mealie config with DB credentials found over SSH. "
            "Checked documented paths such as /opt/mealie/mealie.env and docker-compose files under /opt/mealie and ~/docker/mealie.",
            {},
        )

    cache: dict[str, str] = {}

    def _read_remote(path: str, base_path: str) -> str:
        raw_path = str(path or "").strip()
        if not raw_path:
            return ""
        candidates: list[str] = []
        if raw_path.startswith("/"):
            candidates.append(raw_path)
        else:
            candidates.append(os.path.normpath(os.path.join(os.path.dirname(base_path), raw_path)))
            candidates.append(raw_path)

        # Mealie docs use /run/secrets/* inside container; resolve to common host-side files.
        if raw_path.startswith("/run/secrets/"):
            secret_name = os.path.basename(raw_path)
            base_dir = os.path.dirname(base_path)
            candidates.extend(
                [
                    os.path.join(base_dir, "secrets", secret_name),
                    os.path.join(base_dir, "secrets", f"{secret_name}.txt"),
                    os.path.join(base_dir, "secrets", "sensitive", secret_name),
                    os.path.join(base_dir, "secrets", "sensitive", f"{secret_name}.txt"),
                ]
            )

        for candidate in candidates:
            if candidate in cache:
                text = cache[candidate]
            else:
                q_path = shlex.quote(candidate)
                cmd = f"p={q_path}; if [ -r \"$p\" ]; then sed -n '1,4p' \"$p\"; fi"
                out_text, _err_text, code = _ssh_exec(ssh_host, ssh_user, ssh_key, cmd, timeout=12)
                text = out_text if code == 0 else ""
                cache[candidate] = text
            if text.strip():
                return text
        return ""

    best_detected: dict[str, str] = {}
    best_path = ""
    for path, payload in blocks:
        detected = _parse_mealie_env(payload)
        # Resolve *_FILE secret indirections, when present.
        for key in list(detected):
            if not key.startswith("__FILE__:"):
                continue
            target_key = key.split(":", 1)[1]
            secret_path = str(detected.get(key) or "").strip()
            secret_value = _read_remote(secret_path, path).splitlines()[0].strip() if secret_path else ""
            if secret_value:
                if target_key == "POSTGRES_URL_OVERRIDE":
                    _apply_postgres_url_override(detected, secret_value.strip("'\""))
                    _normalize_tunneled_pg_host(detected)
                else:
                    detected[target_key] = secret_value.strip("'\"")
            detected.pop(key, None)

        # systemd unit may point at a separate env file
        for line in payload.splitlines():
            if "EnvironmentFile" not in line:
                continue
            _, _, env_path = line.partition("=")
            env_path = env_path.strip().lstrip("-").strip("'\"")
            if not env_path:
                continue
            env_payload = _read_remote(env_path, path)
            if not env_payload:
                continue
            from_env_file = _parse_mealie_env(env_payload)
            for env_key, env_val in from_env_file.items():
                if env_key not in detected and env_val:
                    detected[env_key] = env_val

        if not detected:
            continue
        if len(detected) > len(best_detected):
            best_detected = detected
            best_path = path

    if best_detected:
        db_type = best_detected.get("MEALIE_DB_TYPE", "postgres")
        return True, f"Detected {db_type} credentials from config '{best_path}'.", best_detected

    return False, "Found candidate config file(s), but no recognized DB credential keys were parsed.", {}


def _detect_db_credentials(
    ssh_host: str, ssh_user: str, ssh_key: str,
) -> tuple[bool, str, dict[str, str]]:
    """SSH into the Mealie host and auto-discover database credentials."""

    docker_hint = ""

    # Strategy 1: find mealie container via docker ps
    try:
        out, _err, code = _ssh_exec(ssh_host, ssh_user, ssh_key, "docker ps --format '{{.Names}}'")
    except (FileNotFoundError, ValueError):
        return (
            False,
            "Auto-detect uses SSH only: key not found or path not allowed. "
            "Set MEALIE_DB_SSH_KEY to a valid key filename/path, or skip auto-detect and use Test DB with manual credentials.",
            {},
        )
    except Exception:
        return False, "SSH connection failed. Check SSH host, user, and key settings.", {}

    if code == 0:
        # Find container with "mealie" in the name
        containers = [name.strip() for name in out.splitlines() if name.strip()]
        mealie_containers = [c for c in containers if "mealie" in c.lower() and "cookdex" not in c.lower()]

        if mealie_containers:
            container = _validated_container_name(mealie_containers[0])

            # Strategy 2: docker inspect
            try:
                inspect_cmd = shlex.join([
                    "docker", "inspect", "--format",
                    "{{range .Config.Env}}{{println .}}{{end}}",
                    container,
                ])
                out, _err, inspect_code = _ssh_exec(
                    ssh_host, ssh_user, ssh_key, inspect_cmd,
                )
                if inspect_code == 0 and out.strip():
                    detected = _parse_mealie_env(out)
                    if detected:
                        db_type = detected.get("MEALIE_DB_TYPE", "postgres")
                        return True, f"Detected {db_type} credentials from container '{container}'.", detected
            except Exception:
                pass

            # Strategy 3: docker exec env
            try:
                exec_cmd = shlex.join(["docker", "exec", container, "env"])
                out, _err, exec_code = _ssh_exec(
                    ssh_host, ssh_user, ssh_key, exec_cmd,
                )
                if exec_code == 0 and out.strip():
                    detected = _parse_mealie_env(out)
                    if detected:
                        db_type = detected.get("MEALIE_DB_TYPE", "postgres")
                        return True, f"Detected {db_type} credentials from container '{container}'.", detected
            except Exception:
                pass

            docker_hint = f"Docker container '{container}' found, but credential extraction failed."
        else:
            docker_hint = "No Mealie Docker container found."
    else:
        docker_hint = "Docker discovery unavailable on remote host."

    # Strategy 4: non-Docker fallback (documented env-file discovery)
    ok, detail, detected = _detect_db_credentials_from_env_files(ssh_host, ssh_user, ssh_key)
    if ok:
        return True, detail, detected

    if docker_hint:
        return False, f"{docker_hint} {detail}", {}
    return False, detail, {}
