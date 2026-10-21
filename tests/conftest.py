import pytest


@pytest.fixture(autouse=True)
def disable_live_update_requests(monkeypatch):
    """App tests must not contact GitHub; checker tests use explicit mock sessions."""
    monkeypatch.setenv('UPDATE_CHECK_ENABLED', 'false')


@pytest.fixture(autouse=True)
def reset_mealie_slots():
    """Building an app makes this process take Mealie slots as the web UI; undo that per test."""
    from cookdex import mealie_slots

    yield
    mealie_slots.use_for_web_ui(None)


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    """Jobs keep files next to state.db (deleted-recipe copies, dredger.db); keep them out of the repo."""
    if not __import__("os").environ.get("WEB_STATE_DB_PATH"):
        monkeypatch.setenv("WEB_STATE_DB_PATH", str(tmp_path / "state-dir" / "state.db"))
