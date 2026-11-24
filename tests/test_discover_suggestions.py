"""Discover's suggested-source updates and its responsible-use acceptance."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cookdex.recipe_dredger import sites as suggested
from cookdex.recipe_dredger.storage import DredgerStore

from tests.test_webui_app import _CSRF
from tests.test_webui_library import _login, _make_app

API = "/cookdex/api/v1"


def _app(tmp_path: Path, monkeypatch):
    from cookdex.webui_server.routers import discover

    store = DredgerStore(tmp_path / "dredger.db")
    monkeypatch.setattr(discover, "_get_dredger_store", lambda: store)
    app, _ = _make_app(tmp_path, monkeypatch)
    return app, store


def test_fresh_install_gets_every_suggestion_and_no_update(tmp_path, monkeypatch):
    app, store = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        body = client.get(f"{API}/discover").json()
    assert body["total"] == len(suggested.load_default_sites())
    assert body["suggestions_update"] is None


def test_older_install_is_offered_new_and_retired_sources_without_changes(tmp_path, monkeypatch):
    app, store = _app(tmp_path, monkeypatch)
    retired = suggested.load_retired_sites()[0]
    kept = next(entry for entry in suggested.load_default_sites() if not entry.get("added"))
    store.seed_defaults([{"url": retired["url"], "group": "General"}, kept], enabled=True)
    with TestClient(app) as client:
        _login(client)
        update = client.get(f"{API}/discover").json()["suggestions_update"]
        assert [item["url"] for item in update["retired"]] == [retired["url"].rstrip("/")]
        assert update["retired"][0]["reason_text"]
        new_urls = {item["url"] for item in update["new"]}
        assert kept["url"] not in new_urls
        assert new_urls == {entry["url"] for entry in suggested.load_default_sites() if entry.get("added")}
        # Showing the update changes nothing.
        assert store.sites_count() == 2

        choice = sorted(new_urls)[:2]
        result = client.post(
            f"{API}/discover/suggestions", headers=_CSRF,
            json={"add": choice, "remove_ids": [update["retired"][0]["id"]]},
        ).json()
        assert result == {"added": 2, "removed": 1}
        sites = {site["url"]: site for site in store.get_all_sites()}
        assert set(choice) <= set(sites)
        assert not any(sites[url]["enabled"] for url in choice)  # added switched off
        assert retired["url"].rstrip("/") not in sites
        assert client.get(f"{API}/discover").json()["suggestions_update"] is None


def test_dismissing_keeps_retired_sources(tmp_path, monkeypatch):
    app, store = _app(tmp_path, monkeypatch)
    retired = suggested.load_retired_sites()[0]
    store.seed_defaults([{"url": retired["url"], "group": "General"}], enabled=True)
    with TestClient(app) as client:
        _login(client)
        assert client.post(f"{API}/discover/suggestions", headers=_CSRF, json={}).json() == {"added": 0, "removed": 0}
        assert client.get(f"{API}/discover").json()["suggestions_update"] is None
    assert store.sites_count() == 1


def test_suggestions_route_only_removes_retired_sources(tmp_path, monkeypatch):
    app, store = _app(tmp_path, monkeypatch)
    site_id = store.add_site("https://my-own-blog.example")
    with TestClient(app) as client:
        _login(client)
        client.post(f"{API}/discover/suggestions", headers=_CSRF, json={"remove_ids": [site_id]})
    assert store.sites_count() == 1


def test_discover_runs_wait_for_owner_acceptance(tmp_path, monkeypatch):
    app, _store = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        body = client.get(f"{API}/discover").json()["responsible_use"]
        assert body["accepted"] is False and body["can_accept"] is True

        refused = client.post(f"{API}/runs", headers=_CSRF, json={"task_id": "recipe-dredger", "options": {"dry_run": True}})
        assert refused.status_code == 409
        assert "responsible-use" in refused.json()["detail"]

        workflow = {"workflow": {"name": "Weekly", "steps": [{"task_id": "recipe-dredger", "options": {}}]}}
        refused = client.post(f"{API}/runs", headers=_CSRF, json={"task_id": "workflow", "options": workflow})
        assert refused.status_code == 409

        accepted = client.post(f"{API}/discover/responsible-use", headers=_CSRF).json()
        assert accepted["accepted"] is True and accepted["accepted_by"] == "admin"
        body = client.get(f"{API}/discover").json()["responsible_use"]
        assert body["accepted"] is True and body["accepted_at"]
        tasks = {t["task_id"]: t for t in client.get(f"{API}/tasks").json()["items"]}
        assert tasks["recipe-dredger"]["available"] is True


def test_scheduled_discover_run_is_skipped_until_accepted(tmp_path, monkeypatch):
    from cookdex.webui_server import responsible_use

    class _State:
        def get_document(self, key):
            return None

    assert responsible_use.blocked_reason(_State(), "recipe-dredger") == responsible_use.NOT_ACCEPTED
    assert responsible_use.blocked_reason(_State(), "tag-categorize") == ""
