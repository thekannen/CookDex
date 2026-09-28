#!/usr/bin/env bash
set -euo pipefail

# Runs as root first to make the mounted folders writable, then drops to the
# app user and starts the web UI. Everything else (tasks, schedules,
# automations) is run by the web UI itself.
WRITABLE_DIRS=(/app/configs /app/configs/taxonomy /app/cache /app/logs /app/reports)

if [ "$(id -u)" = "0" ]; then
  for dir in "${WRITABLE_DIRS[@]}"; do
    mkdir -p "$dir"
    # Bind mounts often arrive owned by root. Only walk a folder when it is
    # not already the app user's, so a large cache doesn't slow every start.
    if [ "$(stat -c %U "$dir")" != "app" ]; then
      chown -R app:app "$dir" 2>/dev/null || true
    fi
    if ! gosu app sh -c "touch '$dir/.write_test' && rm -f '$dir/.write_test'" 2>/dev/null; then
      echo "[warn] CookDex cannot write to $dir. Check the ownership of that folder on the host."
    fi
  done

  # SSH keys for Direct DB are usually mounted read-only; copy them somewhere
  # the app user owns, with the permissions ssh insists on.
  if [ -d /app/.ssh ]; then
    SSH_DIR="/tmp/.ssh-app"
    mkdir -p "$SSH_DIR"
    cp -a /app/.ssh/. "$SSH_DIR/" 2>/dev/null || true
    chown -R app:app "$SSH_DIR" 2>/dev/null || true
    find "$SSH_DIR" -type f -exec chmod 600 {} \; 2>/dev/null || true
    find "$SSH_DIR" -type d -exec chmod 700 {} \; 2>/dev/null || true
    export HOME="/tmp/app-home"
    mkdir -p "$HOME"
    chown app:app "$HOME"
    ln -sfn "$SSH_DIR" "$HOME/.ssh"
  fi

  exec gosu app "$0" "$@"
fi

if [ -n "${TASK:-}" ] && [ "${TASK}" != "webui-server" ]; then
  echo "[warn] TASK=${TASK} is no longer supported and was ignored; starting the web UI." \
       "Run tasks from Tools or Automations instead."
fi

exec python -m cookdex.webui_server.main "$@"
