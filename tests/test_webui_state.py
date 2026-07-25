import sqlite3
from pathlib import Path

import pytest

from cookdex.webui_server.state import StateStore


def test_state_initializes_task_policies(tmp_path: Path):
    store = StateStore(tmp_path / "state.db")
    store.initialize(["ingredient-parse", "cleanup-duplicates"])
    policies = store.list_task_policies()
    assert sorted(policies.keys()) == ["cleanup-duplicates", "ingredient-parse"]
    assert policies["ingredient-parse"]["allow_dangerous"] is False


def test_state_user_and_session_roundtrip(tmp_path: Path):
    store = StateStore(tmp_path / "state.db")
    store.initialize([])
    store.upsert_user("admin", "hash-value")
    assert store.get_password_hash("admin") == "hash-value"
    assert store.get_user("admin")["role"] == "owner"

    token = "token-1"
    expires_at = "2099-01-01T00:00:00Z"
    store.create_session(token=token, username="admin", expires_at=expires_at)
    session = store.get_session(token)
    assert session is not None
    assert session["username"] == "admin"
    assert session["expires_at"] == expires_at


def test_delete_sessions_for_user_can_preserve_current_session(tmp_path: Path):
    store = StateStore(tmp_path / "state.db")
    store.initialize([])
    store.upsert_user("admin", "hash-value")
    store.create_session(token="keep", username="admin", expires_at="2099-01-01T00:00:00Z")
    store.create_session(token="drop", username="admin", expires_at="2099-01-01T00:00:00Z")

    deleted = store.delete_sessions_for_user("admin", except_token="keep")

    assert deleted == 1
    assert store.get_session("keep") is not None
    assert store.get_session("drop") is None


def test_state_migrates_existing_users_to_owner_and_editor(tmp_path: Path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE users (
              username TEXT PRIMARY KEY,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              force_password_reset INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute(
            "INSERT INTO users(username, password_hash, created_at, force_password_reset) VALUES(?, ?, ?, ?);",
            ("admin", "hash-1", "2026-01-01T00:00:00Z", 0),
        )
        conn.execute(
            "INSERT INTO users(username, password_hash, created_at, force_password_reset) VALUES(?, ?, ?, ?);",
            ("editor", "hash-2", "2026-01-02T00:00:00Z", 0),
        )
        conn.commit()
    finally:
        conn.close()

    store = StateStore(db_path)
    store.initialize([])

    users = {item["username"]: item for item in store.list_users()}
    assert users["admin"]["role"] == "owner"
    assert users["editor"]["role"] == "editor"


def test_update_user_role_guarded_blocks_demoting_last_owner(tmp_path: Path):
    store = StateStore(tmp_path / "state.db")
    store.initialize([])
    store.upsert_user("admin", "hash-admin")

    with pytest.raises(ValueError, match="At least one owner account must remain."):
        store.update_user_role_guarded("admin", "editor")

    assert store.get_user("admin")["role"] == "owner"


def test_delete_user_guarded_blocks_removing_last_owner(tmp_path: Path):
    store = StateStore(tmp_path / "state.db")
    store.initialize([])
    store.upsert_user("admin", "hash-admin")
    store.create_user("editor", "hash-editor", role="editor")

    with pytest.raises(ValueError, match="At least one owner account must remain."):
        store.delete_user_guarded("admin")

    assert store.get_user("admin")["role"] == "owner"
    assert store.get_user("editor")["role"] == "editor"


def test_guarded_owner_mutations_allow_safe_changes(tmp_path: Path):
    store = StateStore(tmp_path / "state.db")
    store.initialize([])
    store.upsert_user("admin", "hash-admin")
    store.create_user("editor", "hash-editor", role="editor")

    promoted = store.update_user_role_guarded("editor", "owner")
    assert promoted is not None
    assert promoted["role"] == "owner"

    deleted = store.delete_user_guarded("admin")
    assert deleted is True
    assert store.get_user("admin") is None
    assert store.get_user("editor")["role"] == "owner"


def test_prune_runs_keeps_newest_and_drops_orphan_logs(tmp_path):
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    state.initialize(["mealie-backup"])

    for i in range(10):
        state.create_run(
            run_id=f"run-{i:02d}",
            task_id="mealie-backup",
            options={},
            triggered_by="test",
            schedule_id=None,
            log_path=f"/tmp/run-{i:02d}.log",
        )
        state.update_run_log_size(f"run-{i:02d}", 128)

    assert state.prune_runs(keep=3) == 7

    remaining = [row["run_id"] for row in state.list_runs(limit=100)]
    assert sorted(remaining) == ["run-07", "run-08", "run-09"]

    # run_logs rows for pruned runs go too.
    assert state.get_run("run-00") is None
    with state._connect(readonly=True) as conn:
        log_ids = [row[0] for row in conn.execute("SELECT run_id FROM run_logs;").fetchall()]
    assert sorted(log_ids) == ["run-07", "run-08", "run-09"]


def test_prune_runs_no_op_when_under_limit(tmp_path):
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    state.initialize(["mealie-backup"])
    state.create_run(
        run_id="only",
        task_id="mealie-backup",
        options={},
        triggered_by="test",
        schedule_id=None,
        log_path="/tmp/only.log",
    )
    assert state.prune_runs(keep=10) == 0
    assert state.get_run("only") is not None


def test_connection_is_reused_within_a_thread(tmp_path):
    """Connecting per operation dominated request time; the connection is pooled per thread."""
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    state.initialize(["mealie-backup"])

    first = state._thread_connection()
    for _ in range(10):
        state.count_runs()
    assert state._thread_connection() is first

    state.close()
    assert state._thread_connection() is not first


def test_nested_connect_defers_commit_to_outermost(tmp_path):
    """A nested block must not commit work its caller has not finished."""
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    state.initialize(["mealie-backup"])

    class Boom(Exception):
        pass

    try:
        with state._connect() as conn:
            conn.execute(
                "INSERT INTO app_settings(key, value_json, updated_at) VALUES('OUTER','1','now');"
            )
            with state._connect(readonly=True) as inner:
                inner.execute("SELECT 1;").fetchone()
            raise Boom()
    except Boom:
        pass

    # The inner readonly block must not have committed the outer's insert.
    assert "OUTER" not in state.list_settings()


def test_taxonomy_non_empty_collections(tmp_path):
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    state.initialize(["mealie-backup"])
    assert state.taxonomy_non_empty_collections() == set()

    state.taxonomy_set("categories", [{"name": "Dinner"}])
    assert state.taxonomy_non_empty_collections() == {"categories"}
    assert state.taxonomy_is_empty("categories") is False
    assert state.taxonomy_is_empty("tags") is True
