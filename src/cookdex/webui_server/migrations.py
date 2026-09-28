"""Numbered, one-way migrations for state.db.

SQLite's ``PRAGMA user_version`` records the last migration applied. On start,
every newer migration runs in order, each in its own transaction together
with the version bump, so a failure leaves the database at the last good
version rather than half-changed.

Migration 1 is the schema as it stood before versioning. It only creates what
is missing, so it's safe on a database of any older version, which all report
``user_version`` 0.

To change the schema, append a migration; never edit one that has shipped.
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)

Migration = Callable[[sqlite3.Connection], None]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table});")}


def _add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl};")


def _run(conn: sqlite3.Connection, script: str) -> None:
    """Run each statement in *script*. (executescript would commit the
    migration's transaction first, so it isn't used.)"""
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)


def _baseline(conn: sqlite3.Connection) -> None:
    _run(conn, 
        """
        CREATE TABLE IF NOT EXISTS users (
          username TEXT PRIMARY KEY,
          password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          force_password_reset INTEGER NOT NULL DEFAULT 0,
          role TEXT NOT NULL DEFAULT 'editor'
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY,
          username TEXT NOT NULL,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
          run_id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          status TEXT NOT NULL,
          options_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          started_at TEXT,
          finished_at TEXT,
          exit_code INTEGER,
          error_text TEXT,
          triggered_by TEXT NOT NULL,
          schedule_id TEXT,
          log_path TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS run_logs (
          run_id TEXT PRIMARY KEY,
          log_path TEXT NOT NULL,
          size_bytes INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS schedules (
          schedule_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          task_id TEXT NOT NULL,
          schedule_kind TEXT NOT NULL,
          schedule_data_json TEXT NOT NULL,
          options_json TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          last_enqueued_at TEXT,
          validation_error TEXT
        );
        CREATE TABLE IF NOT EXISTS task_policies (
          task_id TEXT PRIMARY KEY,
          allow_dangerous INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS secrets (
          key TEXT PRIMARY KEY,
          encrypted_value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS run_results (
          run_id TEXT PRIMARY KEY,
          results_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
          key TEXT PRIMARY KEY,
          data_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metric_cache (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          computed_at REAL NOT NULL,
          ttl_seconds INTEGER NOT NULL DEFAULT 300
        );
        """
    )
    # Columns added over time, before migrations were numbered.
    _add_column(conn, "users", "force_password_reset", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "users", "role", "TEXT NOT NULL DEFAULT 'editor'")
    _add_column(conn, "users", "last_sign_in", "TEXT")
    _add_column(conn, "schedules", "validation_error", "TEXT")
    _run(conn, 
        """
        CREATE INDEX IF NOT EXISTS ix_sessions_username ON sessions(username);
        CREATE INDEX IF NOT EXISTS ix_sessions_expires_at ON sessions(expires_at);
        CREATE INDEX IF NOT EXISTS ix_runs_created_at ON runs(created_at DESC);
        """
    )


def _drop_apscheduler_store(conn: sqlite3.Connection) -> None:
    """APScheduler kept a second copy of every schedule here; the schedules
    table is the only one now, rebuilt into memory at start."""
    conn.execute("DROP TABLE IF EXISTS apscheduler_jobs;")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# (version, what it does, function). Append only.
MIGRATIONS: list[tuple[int, str, Migration]] = [
    (1, "schema before numbered migrations", _baseline),
    (2, "drop APScheduler's copy of the schedules", _drop_apscheduler_store),
]


def current_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version;").fetchone()[0])


def migrate(db_path: str, migrations: list[tuple[int, str, Migration]] | None = None) -> list[int]:
    """Bring *db_path* up to the newest migration. Returns the versions applied."""
    steps = MIGRATIONS if migrations is None else migrations
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    applied: list[int] = []
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        version = current_version(conn)
        newest = max((number for number, _, _ in steps), default=0)
        if version > newest:
            logger.warning(
                "state.db is at migration %s, newer than this CookDex knows (%s). "
                "It was used by a newer version; carrying on without changing it.",
                version,
                newest,
            )
            return applied
        for number, name, step in sorted(steps, key=lambda item: item[0]):
            if number <= version:
                continue
            conn.execute("BEGIN IMMEDIATE;")
            try:
                step(conn)
                conn.execute(f"PRAGMA user_version = {int(number)};")
                conn.execute("COMMIT;")
            except BaseException:
                conn.execute("ROLLBACK;")
                raise
            logger.info("state.db migration %s applied: %s", number, name)
            applied.append(number)
    finally:
        conn.close()
    return applied
