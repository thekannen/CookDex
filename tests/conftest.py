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
