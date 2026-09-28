from __future__ import annotations

import importlib
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tests.test_webui_app import _CSRF, _login, _seed_config_root, _write_json


def _make_app(tmp_path: Path, monkeypatch):
    config_root = tmp_path / "repo"
    _seed_config_root(config_root)
    for key, value in {
        "MO_WEBUI_MASTER_KEY": Fernet.generate_key().decode("utf-8"),
        "WEB_BOOTSTRAP_PASSWORD": "Secret-pass1",
        "WEB_BOOTSTRAP_USER": "admin",
        "WEB_STATE_DB_PATH": str(tmp_path / "state.db"),
        "WEB_BASE_PATH": "/cookdex",
        "WEB_CONFIG_ROOT": str(config_root),
        "WEB_COOKIE_SECURE": "false",
        "MEALIE_URL": "http://127.0.0.1:9000/api",
        "MEALIE_API_KEY": "placeholder",
    }.items():
        monkeypatch.setenv(key, value)
    app_module = importlib.import_module("cookdex.webui_server.app")
    importlib.reload(app_module)
    return app_module.create_app(), config_root


def _finished_run(state, run_id, task_id, options, results, tmp_path):
    state.create_run(run_id, task_id, options, "admin", None, str(tmp_path / f"{run_id}.log"))
    state.update_run_status(run_id, status="succeeded", finished_at="2026-09-26T10:00:00Z")
    state.set_run_results(run_id, results)


def test_library_builds_findings_from_latest_scan(tmp_path: Path, monkeypatch):
    app, config_root = _make_app(tmp_path, monkeypatch)
    _write_json(config_root / "reports" / "quality_audit_report.json", {
        "summary": {"total": 10},
        "dimension_coverage": {
            "category": {"have": 6, "missing": 4, "pct_have": 60.0},
            "tags": {"have": 8, "missing": 2, "pct_have": 80.0},
            "ingredients": {"have": 0, "missing": 10, "pct_have": 0.0},
            "yield": {"have": 10, "missing": 0, "pct_have": 100.0},
        },
    })
    with TestClient(app) as client:
        state = app.state.services.state
        _finished_run(state, "h1", "health-check", {}, [
            {"source": "q", "summary": {"__title__": "Quality Audit", "Total Recipes": 10}},
        ], tmp_path)
        _finished_run(state, "c1", "clean-recipes", {"dry_run": True}, [
            {"source": "j", "kind": "recipe_delete", "items": [
                {"slug": "privacy", "name": "Privacy Policy", "group": "junk", "status": "planned"},
                {"slug": "gift", "name": "Gift Guide", "group": "review", "status": "planned"},
            ]},
            {"source": "n", "kind": "recipe_rename", "items": [
                {"slug": "a-b", "old_name": "a-b", "new_name": "A B", "status": "planned"},
            ]},
        ], tmp_path)
        _finished_run(state, "t1", "cleanup-duplicates", {"dry_run": True, "target": "taxonomy"}, [
            {"source": "t", "summary": {"__title__": "Tag & Category Duplicates",
                                        "Tags Merge Candidates": 1, "Categories Merge Candidates": 5}},
        ], tmp_path)
        _login(client)

        library = client.get("/cookdex/api/v1/library").json()

    assert library["connected"] is True
    assert library["recipes"] == 10
    assert library["needs_scan"] is False
    assert library["score"]["value"] == 60  # (60 + 80 + 0 + 100) / 4
    by_id = {f["id"]: f for f in library["findings"]}
    assert by_id["not-recipes"]["count"] == 1
    assert by_id["not-recipes"]["action"] == {"type": "review", "run_id": "c1", "groups": ["junk"], "label": "Review"}
    assert by_id["your-call"]["examples"] == ["Gift Guide"]
    assert by_id["names"]["examples"] == ["a-b → A B"]
    assert by_id["taxonomy-duplicates"]["count"] == 6
    assert by_id["missing-category"]["count"] == 4
    assert by_id["missing-ingredients"]["action"]["task_id"] == "ingredient-parse"
    assert "missing-yield" not in by_id


def test_library_drops_cleanup_findings_after_a_live_cleanup(tmp_path: Path, monkeypatch):
    app, _ = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        state = app.state.services.state
        _finished_run(state, "c1", "clean-recipes", {"dry_run": True}, [
            {"source": "j", "kind": "recipe_delete", "items": [
                {"slug": "privacy", "name": "Privacy Policy", "group": "junk", "status": "planned"},
            ]},
        ], tmp_path)
        _finished_run(state, "c2", "clean-recipes", {"dry_run": False}, [], tmp_path)
        _login(client)
        library = client.get("/cookdex/api/v1/library").json()

    assert library["needs_scan"] is True
    assert all(f["id"] != "not-recipes" for f in library["findings"])


def test_library_scan_queues_read_only_runs(tmp_path: Path, monkeypatch):
    app, _ = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        response = client.post("/cookdex/api/v1/library/scan", headers=_CSRF)
        assert response.status_code == 202
        runs = response.json()["runs"]
        assert set(runs) == {"health-check", "clean-recipes", "cleanup-duplicates"}
        for run_id in runs.values():
            run = client.get(f"/cookdex/api/v1/runs/{run_id}").json()
            assert run["options"].get("dry_run", True) is not False


def test_invalid_task_options_are_a_422_not_a_500(tmp_path: Path, monkeypatch):
    app, _ = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/cookdex/api/v1/runs", json={"task_id": "organize-apply", "options": {}}, headers=_CSRF
        )
    assert response.status_code == 422
    assert "plan" in response.json()["detail"]


def test_discover_lists_sources_off_by_default_with_history(tmp_path: Path, monkeypatch):
    from cookdex.recipe_dredger.storage import DredgerStore
    from cookdex.webui_server.routers import discover

    store = DredgerStore(tmp_path / "dredger.db")
    monkeypatch.setattr(discover, "_get_dredger_store", lambda: store)
    app, _ = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        first = client.get("/cookdex/api/v1/discover").json()
        assert first["total"] > 0
        assert first["enabled_count"] == 0  # suggested sources start switched off

        site = first["sources"][0]
        store.add_imported(site["url"].rstrip("/") + "/some-recipe")
        state = app.state.services.state
        state.create_run("d1", "recipe-dredger", {"dry_run": True}, "admin", None, str(tmp_path / "d1.log"))
        state.update_run_status("d1", status="succeeded", finished_at="2026-09-26T10:00:00Z")
        state.set_run_results("d1", [{"source": "x", "kind": "recipe_import", "items": [
            {"url": "https://example.com/r", "site": "example.com", "status": "planned"},
        ]}])

        again = client.get("/cookdex/api/v1/discover").json()
    by_id = {s["id"]: s for s in again["sources"]}
    assert by_id[site["id"]]["imported"] == 1
    assert again["last_run"]["preview"] is True
    assert again["last_run"]["count"] == 1


def test_provider_endpoint_and_unsupported_tasks(tmp_path: Path, monkeypatch):
    from cookdex import providers
    from cookdex.providers import Capability, MealieProvider

    app, _ = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _login(client)
        info = client.get("/cookdex/api/v1/provider").json()
        assert info["kind"] == "mealie"
        assert info["term_kinds"] == ["tags", "categories", "tools"]
        assert "merge_terms" in info["capabilities"]
        tasks = {t["task_id"]: t for t in client.get("/cookdex/api/v1/tasks").json()["items"]}
        assert all(t["available"] for t in tasks.values())

        # A backend without a backup API or a server-side parser.
        class LimitedProvider(MealieProvider):
            kind = "limited"
            display_name = "Limited"

            def capabilities(self):
                return super().capabilities() - {Capability.BACKUP, Capability.SERVER_PARSER}

        monkeypatch.setitem(providers.DESCRIBERS, "limited", lambda: LimitedProvider(None))
        monkeypatch.setenv("COOKDEX_BACKEND", "limited")
        tasks = {t["task_id"]: t for t in client.get("/cookdex/api/v1/tasks").json()["items"]}
        assert tasks["mealie-backup"]["available"] is False
        assert "backup" in tasks["mealie-backup"]["unavailable_reason"]
        assert tasks["health-check"]["available"] is True
        blocked = client.post("/cookdex/api/v1/runs", json={"task_id": "ingredient-parse", "options": {}}, headers=_CSRF)
        assert blocked.status_code == 409
