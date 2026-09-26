import pytest


@pytest.fixture(autouse=True)
def disable_live_update_requests(monkeypatch):
    """App tests must not contact GitHub; checker tests use explicit mock sessions."""
    monkeypatch.setenv('UPDATE_CHECK_ENABLED', 'false')
