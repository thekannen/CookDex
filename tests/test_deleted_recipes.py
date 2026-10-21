"""Recently deleted: copies of junk-filter deletions, restore, expiry."""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import requests

from cookdex import recipe_restore
from cookdex.deleted_recipes import CopyError, RecipeArchive, keep_days
from cookdex.recipe_junk_filter import RecipeJunkFilter
from tests.fixtures.mealie_placeholders import PLACEHOLDER_INGREDIENT, PLACEHOLDER_STEP

IMAGE = b"RIFF\x00\x00\x00\x00WEBPVP8 fake image"


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response._content = b'{"detail": "boom"}'
    return requests.HTTPError(f"failed ({status})", response=response)


class FakeMealie:
    """Enough of Mealie's recipe API for saving and restoring copies."""

    def __init__(self, *, zip_export: bool = True, zip_import: bool = True) -> None:
        self.recipes: dict[str, dict] = {}
        self.images: dict[str, bytes] = {}
        self.zip_export = zip_export
        self.zip_import = zip_import
        self.organizers = {"tags": [], "categories": [], "tools": [], "foods": [], "units": []}
        self.created: list[tuple[str, str]] = []
        self.calls: list[str] = []
        self._next = 0

    def _id(self) -> str:
        self._next += 1
        return f"00000000-0000-0000-0000-{self._next:012d}"

    def add(self, recipe: dict, image: bytes | None = None) -> dict:
        recipe = {"id": self._id(), "image": "x" if image else None, **recipe}
        self.recipes[recipe["slug"]] = recipe
        if image:
            self.images[recipe["id"]] = image
        return recipe

    # reading
    def get_recipes(self):
        return [{"slug": r["slug"], "name": r["name"], "orgURL": r.get("orgURL")} for r in self.recipes.values()]

    def get_recipe(self, slug):
        if slug not in self.recipes:
            raise _http_error(404)
        return json.loads(json.dumps(self.recipes[slug]))

    def recipe_export_formats(self):
        return {"json": ["raw"], "zip": ["zip"]} if self.zip_export else {"json": ["raw"]}

    def export_recipe_zip(self, slug):
        recipe = self.recipes[slug]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr(f"{slug}.json", json.dumps(recipe))
            if recipe["id"] in self.images:
                zf.writestr("original.webp", self.images[recipe["id"]])
        return buffer.getvalue()

    def get_recipe_image(self, recipe_id):
        return self.images.get(recipe_id)

    # writing
    def delete_recipe(self, slug):
        self.calls.append(f"delete {slug}")
        recipe = self.recipes.pop(slug)
        self.images.pop(recipe["id"], None)

    def _free_slug(self, slug):
        candidate, n = slug, 1
        while candidate in self.recipes:
            candidate = f"{slug}-{n}"
            n += 1
        return candidate

    def import_recipe_zip(self, archive):
        self.calls.append("import zip")
        if not self.zip_import:
            raise _http_error(500)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            recipe = json.loads(zf.read([n for n in zf.namelist() if n.endswith(".json")][0]))
            image = zf.read("original.webp") if "original.webp" in zf.namelist() else None
        # Like Mealie: a recipe without ingredients gets a placeholder one.
        if not recipe.get("recipeIngredient"):
            recipe["recipeIngredient"] = [dict(PLACEHOLDER_INGREDIENT)]
        recipe["slug"] = self._free_slug(recipe["slug"])
        self.recipes[recipe["slug"]] = recipe
        if image:
            self.images[recipe["id"]] = image
        return recipe["slug"]

    def create_recipe(self, name):
        self.calls.append("create")
        slug = self._free_slug(name.lower().replace(" ", "-"))
        self.recipes[slug] = {"id": self._id(), "slug": slug, "name": name, "image": None,
                              "recipeIngredient": [dict(PLACEHOLDER_INGREDIENT)], "recipeInstructions": [dict(PLACEHOLDER_STEP)]}
        return slug

    def patch_recipe(self, slug, payload):
        self.calls.append("patch")
        self.recipes[slug].update(payload)
        return self.recipes[slug]

    def upload_recipe_image(self, slug, image, extension="webp"):
        self.calls.append("image")
        self.images[self.recipes[slug]["id"]] = image
        self.recipes[slug]["image"] = "x"

    def _list(self, kind):
        return list(self.organizers[kind])

    def _create(self, kind, name):
        item = {"id": self._id(), "name": name, "slug": name.lower()}
        self.organizers[kind].append(item)
        self.created.append((kind, name))
        return item

    def get_organizer_items(self, endpoint):
        return self._list(endpoint)

    def create_organizer_item(self, endpoint, payload):
        return self._create(endpoint, payload["name"])

    def list_tools(self):
        return self._list("tools")

    def create_tool(self, name):
        return self._create("tools", name)

    def list_foods(self):
        return self._list("foods")

    def create_food(self, name):
        return self._create("foods", name)

    def list_units(self):
        return self._list("units")

    def create_unit(self, name, abbreviation=""):
        return self._create("units", name)


def _chili(mealie: FakeMealie, *, image: bytes | None = IMAGE) -> dict:
    tag = mealie._create("tags", "Weeknight")
    category = mealie._create("categories", "Dinner")
    tool = mealie._create("tools", "Dutch Oven")
    beans = mealie._create("foods", "beans")
    cup = mealie._create("units", "cup")
    mealie.created.clear()
    return mealie.add({
        "slug": "chili", "name": "Chili", "description": "Warming.",
        "recipeIngredient": [{"note": "", "quantity": 2, "unit": cup, "food": beans, "referenceId": "r1"}],
        "recipeInstructions": [{"text": "Simmer."}, {"text": "Serve."}],
        "tags": [tag], "recipeCategory": [category], "tools": [tool],
        "recipeYield": "4 servings", "userId": "u1", "groupId": "g1",
    }, image)


def test_save_keeps_zip_and_details(tmp_path):
    mealie = FakeMealie()
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("chili", reason="No ingredients", reason_code="no_ingredients", run_id="run-1", triggered_by="alex")
    folder = tmp_path / meta["id"]
    assert {p.name for p in folder.iterdir()} == {"meta.json", "recipe.json", "export.zip"}
    assert meta["name"] == "Chili" and meta["run_id"] == "run-1" and meta["triggered_by"] == "alex"
    assert meta["has_export"] and meta["has_image"]
    assert meta["ingredients"] == 1 and meta["steps"] == 2
    assert meta["size_bytes"] > 0
    assert archive.list()[0]["id"] == meta["id"]


def test_save_takes_run_from_the_runner_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("COOKDEX_RUN_ID", "run-9")
    monkeypatch.setenv("COOKDEX_TRIGGERED_BY", "scheduler")
    mealie = FakeMealie()
    _chili(mealie)
    meta = RecipeArchive(tmp_path, mealie).save("chili", reason="r", reason_code="c")
    assert (meta["run_id"], meta["triggered_by"]) == ("run-9", "scheduler")


def test_save_without_zip_export_keeps_json_and_image(tmp_path):
    mealie = FakeMealie(zip_export=False)
    _chili(mealie)
    meta = RecipeArchive(tmp_path, mealie).save("chili", reason="r", reason_code="c")
    folder = tmp_path / meta["id"]
    assert (folder / "image.webp").read_bytes() == IMAGE
    assert not (folder / "export.zip").exists()
    assert meta["has_image"] and not meta["has_export"]


def test_save_failure_leaves_nothing(tmp_path):
    mealie = FakeMealie()
    with pytest.raises(CopyError):
        RecipeArchive(tmp_path, mealie).save("missing", reason="r", reason_code="c")
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


def test_save_failure_on_disk_cleans_up(tmp_path, monkeypatch):
    mealie = FakeMealie()
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    monkeypatch.setattr("cookdex.deleted_recipes._write_json", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(CopyError, match="disk full"):
        archive.save("chili", reason="r", reason_code="c")
    assert archive.list() == []
    assert not any(tmp_path.iterdir())


def _junk_mealie() -> FakeMealie:
    mealie = FakeMealie()
    mealie.add({"slug": "about-us", "name": "About Us", "recipeIngredient": [], "recipeInstructions": []})
    mealie.add({"slug": "soup", "name": "Soup", "recipeIngredient": [{"note": "1 leek"}], "recipeInstructions": [{"text": "Cook."}]})
    return mealie


def test_junk_filter_keeps_a_copy_before_deleting(tmp_path):
    mealie = _junk_mealie()
    archive = RecipeArchive(tmp_path / "copies", mealie)
    report = RecipeJunkFilter(mealie, apply=True, dry_run=False, report_file=tmp_path / "r.json", archive=archive).run()
    assert report["summary"]["deleted"] == 1
    assert "about-us" not in mealie.recipes and "soup" in mealie.recipes
    [copy] = archive.list()
    assert copy["slug"] == "about-us" and copy["reason_code"] == "utility"
    assert report["actions"][0]["copy_id"] == copy["id"]


def test_junk_filter_does_not_delete_without_a_copy(tmp_path, monkeypatch):
    mealie = _junk_mealie()
    archive = RecipeArchive(tmp_path / "copies", mealie)
    monkeypatch.setattr(archive, "save", lambda *a, **k: (_ for _ in ()).throw(CopyError("disk full")))
    report = RecipeJunkFilter(mealie, apply=True, dry_run=False, report_file=tmp_path / "r.json", archive=archive).run()
    assert "about-us" in mealie.recipes
    assert report["summary"]["deleted"] == 0 and report["summary"]["failed"] == 1
    assert "Not deleted: disk full" in report["actions"][0]["error"]


def test_junk_filter_drops_the_copy_when_the_delete_fails(tmp_path):
    mealie = _junk_mealie()
    mealie.delete_recipe = lambda slug: (_ for _ in ()).throw(_http_error(500))
    archive = RecipeArchive(tmp_path / "copies", mealie)
    report = RecipeJunkFilter(mealie, apply=True, dry_run=False, report_file=tmp_path / "r.json", archive=archive).run()
    assert report["summary"]["failed"] == 1
    assert archive.list() == []


def test_preview_saves_nothing(tmp_path):
    mealie = _junk_mealie()
    archive = RecipeArchive(tmp_path / "copies", mealie)
    RecipeJunkFilter(mealie, dry_run=True, report_file=tmp_path / "r.json", archive=archive).run()
    assert archive.list() == [] and "about-us" in mealie.recipes


def test_restore_uses_zip_import(tmp_path):
    mealie = FakeMealie()
    original = _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("chili", reason="r", reason_code="c")
    mealie.delete_recipe("chili")
    result = archive.restore(meta["id"])
    assert result == {"slug": "chili", "name": "Chili", "method": "zip"}
    assert mealie.recipes["chili"]["recipeIngredient"] == original["recipeIngredient"]
    assert mealie.images[mealie.recipes["chili"]["id"]] == IMAGE
    assert archive.list() == []


def test_restore_falls_back_when_zip_import_fails(tmp_path):
    mealie = FakeMealie(zip_import=False)
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("chili", reason="r", reason_code="c")
    mealie.delete_recipe("chili")
    result = archive.restore(meta["id"])
    assert result["method"] == "rebuild"
    restored = mealie.recipes[result["slug"]]
    assert [s["text"] for s in restored["recipeInstructions"]] == ["Simmer.", "Serve."]
    assert restored["recipeYield"] == "4 servings" and restored["description"] == "Warming."
    assert [t["name"] for t in restored["tags"]] == ["Weeknight"]
    assert [c["name"] for c in restored["recipeCategory"]] == ["Dinner"]
    assert [t["name"] for t in restored["tools"]] == ["Dutch Oven"]
    assert restored["recipeIngredient"][0]["food"]["name"] == "beans"
    assert mealie.images[restored["id"]] == IMAGE
    # Mealie's own fields aren't copied over.
    assert restored.get("userId") != "u1"
    assert mealie.created == []  # everything still existed, so it was linked, not made again


def test_rebuild_makes_missing_tags_and_foods_again(tmp_path):
    mealie = FakeMealie(zip_export=False)
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("chili", reason="r", reason_code="c")
    mealie.delete_recipe("chili")
    mealie.organizers = {kind: [] for kind in mealie.organizers}  # all removed in the meantime
    result = archive.restore(meta["id"])
    assert result["method"] == "rebuild"
    assert sorted(mealie.created) == sorted([
        ("tags", "Weeknight"), ("categories", "Dinner"), ("tools", "Dutch Oven"), ("foods", "beans"), ("units", "cup"),
    ])
    restored = mealie.recipes[result["slug"]]
    assert restored["tags"][0]["id"] == mealie.organizers["tags"][0]["id"]


@pytest.mark.parametrize("zip_import", [True, False])
def test_restore_takes_off_mealies_placeholders(tmp_path, zip_import):
    mealie = FakeMealie(zip_import=zip_import)
    mealie.add({"slug": "about", "name": "About", "recipeIngredient": [], "recipeInstructions": [{"text": "Hi, I'm Sam."}]})
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("about", reason="r", reason_code="c")
    mealie.delete_recipe("about")
    result = archive.restore(meta["id"])
    restored = mealie.recipes[result["slug"]]
    assert restored["recipeIngredient"] == []
    assert [s["text"] for s in restored["recipeInstructions"]] == ["Hi, I'm Sam."]


def test_restore_gets_a_new_address_when_the_old_one_is_taken(tmp_path):
    mealie = FakeMealie()
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("chili", reason="r", reason_code="c")
    mealie.delete_recipe("chili")
    mealie.add({"slug": "chili", "name": "Chili", "recipeIngredient": [], "recipeInstructions": []})
    assert archive.restore(meta["id"])["slug"] == "chili-1"


def test_restore_refuses_a_recipe_still_in_mealie(tmp_path):
    mealie = FakeMealie()
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("chili", reason="r", reason_code="c")
    with pytest.raises(CopyError, match="still in Mealie"):
        archive.restore(meta["id"])
    assert archive.get(meta["id"]) is not None
    assert "import zip" not in mealie.calls


def test_restore_keeps_the_copy_when_the_result_is_incomplete(tmp_path):
    mealie = FakeMealie()
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("chili", reason="r", reason_code="c")
    mealie.delete_recipe("chili")
    real_import = mealie.import_recipe_zip

    def lossy(archive_bytes):
        slug = real_import(archive_bytes)
        mealie.recipes[slug]["recipeInstructions"] = []
        return slug

    mealie.import_recipe_zip = lossy
    with pytest.raises(CopyError, match="without its steps"):
        archive.restore(meta["id"])
    assert archive.get(meta["id"]) is not None


def test_restore_job_reports_each_recipe(tmp_path, capsys):
    mealie = FakeMealie()
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("chili", reason="r", reason_code="c")
    mealie.delete_recipe("chili")
    assert recipe_restore.run(archive, [meta["id"], "20260101T000000Z-gone-00000000"]) == 1
    out = capsys.readouterr().out
    assert "Chili is back at chili" in out
    assert "This copy is gone" in out


def test_ids_cannot_leave_the_folder(tmp_path):
    archive = RecipeArchive(tmp_path)
    for bad in ("../state.db", "a/b", "", ".hidden"):
        with pytest.raises(CopyError):
            archive.forget(bad)


def test_a_copy_folder_that_points_elsewhere_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("not a copy")
    root = tmp_path / "copies"
    root.mkdir()
    (root / "20261021T000000Z-chili-abcd1234").symlink_to(outside, target_is_directory=True)
    archive = RecipeArchive(root)
    with pytest.raises(CopyError):
        archive.forget("20261021T000000Z-chili-abcd1234")
    assert (outside / "keep.txt").exists()
    with pytest.raises(CopyError):
        archive.get("20261021T000000Z-chili-abcd1234")


def test_prune_removes_old_copies_and_stale_leftovers(tmp_path):
    mealie = FakeMealie()
    _chili(mealie)
    archive = RecipeArchive(tmp_path, mealie)
    fresh = archive.save("chili", reason="r", reason_code="c")
    old = archive.save("chili", reason="r", reason_code="c")
    meta_path = tmp_path / old["id"] / "meta.json"
    data = json.loads(meta_path.read_text())
    data["deleted_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    meta_path.write_text(json.dumps(data))
    half = tmp_path / "20200101T000000Z-half-done-12345678"
    half.mkdir()
    (half / "recipe.json").write_text("{}")
    os.utime(half, (0, 0))
    recent_half = tmp_path / "20990101T000000Z-being-written-12345678"
    recent_half.mkdir()

    assert archive.prune(30) == 2
    assert {item["id"] for item in archive.list()} == {fresh["id"]}
    assert recent_half.exists()
    assert archive.total_size() > 0


def test_keep_days_setting():
    assert keep_days({}) == 30
    assert keep_days({"DELETED_RECIPES_KEEP_DAYS": "7"}) == 7
    assert keep_days({"DELETED_RECIPES_KEEP_DAYS": "0"}) == 1
    assert keep_days({"DELETED_RECIPES_KEEP_DAYS": "soon"}) == 30
    assert keep_days({"DELETED_RECIPES_KEEP_DAYS": "99999"}) == 3650


# ── Web UI: Recently deleted ──────────────────────────────────────────


def _saved_copy(root, entry_id="20261020T120000Z-about-us-1234abcd", **extra):
    folder = root / entry_id
    folder.mkdir(parents=True)
    (folder / "recipe.json").write_text(json.dumps({"slug": "about-us", "name": "About Us"}))
    (folder / "meta.json").write_text(json.dumps({
        "id": entry_id, "slug": "about-us", "name": "About Us", "reason": "Utility page slug: 'about'",
        "reason_code": "utility", "deleted_at": "2026-10-20T12:00:00Z", "run_id": "r1", "triggered_by": "admin",
        **extra,
    }))
    return entry_id


def test_recently_deleted_api_lists_restores_and_clears(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from tests.test_webui_app import _CSRF, _login, _login_as
    from tests.test_webui_library import _make_app

    app, _ = _make_app(tmp_path, monkeypatch)
    root = tmp_path / "deleted-recipes"
    first = _saved_copy(root)
    second = _saved_copy(root, "20261019T120000Z-contact-5678abcd", deleted_at="2026-10-19T12:00:00Z")
    queued: list[dict] = []
    with TestClient(app) as client:
        services = app.state.services
        monkeypatch.setattr(services.runner, "enqueue", lambda **kw: queued.append(kw) or {"run_id": "run-r", **kw})
        _login(client)
        services.state.create_run("r1", "clean-recipes", {}, "admin", None, str(tmp_path / "r1.log"))
        _saved_copy(root, "20261018T120000Z-gone-run-0000abcd", deleted_at="2026-10-18T12:00:00Z", run_id="pruned")
        listing = client.get("/cookdex/api/v1/deleted-recipes").json()
        assert [item["id"] for item in listing["items"]][:2] == [first, second]
        assert [item["run_in_history"] for item in listing["items"]] == [True, True, False]
        client.delete("/cookdex/api/v1/deleted-recipes/20261018T120000Z-gone-run-0000abcd", headers=_CSRF)
        assert listing["keep_days"] == 30 and listing["total_bytes"] > 0

        restore = client.post("/cookdex/api/v1/deleted-recipes/restore", json={"ids": [first]}, headers=_CSRF)
        assert restore.status_code == 202
        assert queued == [{"task_id": "recipe-restore", "options": {"ids": [first]}, "triggered_by": "admin"}]

        gone = client.post("/cookdex/api/v1/deleted-recipes/restore", json={"ids": ["20200101T000000Z-x-00000000"]}, headers=_CSRF)
        assert gone.status_code == 404
        bad = client.delete("/cookdex/api/v1/deleted-recipes/..state.db", headers=_CSRF)
        assert bad.status_code == 422

        assert client.delete(f"/cookdex/api/v1/deleted-recipes/{second}", headers=_CSRF).status_code == 200
        assert not (root / second).exists()
        assert client.delete(f"/cookdex/api/v1/deleted-recipes/{second}", headers=_CSRF).status_code == 404

        # Editors need live cleanups approved first.
        client.post("/cookdex/api/v1/users", json={"username": "editor", "password": "Editor-pass01", "role": "editor"}, headers=_CSRF)
        _login_as(client, "editor", "Editor-pass01")
        assert client.get("/cookdex/api/v1/deleted-recipes").status_code == 200
        assert client.delete(f"/cookdex/api/v1/deleted-recipes/{first}", headers=_CSRF).status_code == 403
        services.state.set_task_policy("clean-recipes", True)
        assert client.delete(f"/cookdex/api/v1/deleted-recipes/{first}", headers=_CSRF).status_code == 200


def test_restore_task_runs_in_the_light_lane():
    from cookdex.webui_server.tasks import TaskRegistry

    registry = TaskRegistry()
    plan = registry.lane_for("recipe-restore", {"ids": ["a"]})
    assert plan.lane == "light" and plan.writes == frozenset({"recipes"})
    execution = registry.build_execution("recipe-restore", {"ids": ["a", "b"]})
    assert execution.command[-4:] == ["--id", "a", "--id", "b"]
    assert not execution.pre_commands  # no Mealie backup for putting a recipe back
    with pytest.raises(ValueError):
        registry.build_execution("recipe-restore", {"ids": []})


def test_housekeeping_removes_expired_copies(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from tests.test_webui_library import _make_app

    app, _ = _make_app(tmp_path, monkeypatch)
    root = tmp_path / "deleted-recipes"
    old = _saved_copy(root, deleted_at="2026-01-01T00:00:00Z")
    with TestClient(app):
        services = app.state.services
        services.state.set_settings({"DELETED_RECIPES_KEEP_DAYS": "7"})
        services.scheduler._run_housekeeping()
    assert not (root / old).exists()


# ── The duplicate finder keeps copies too ─────────────────────────────


def _dupe_mealie() -> FakeMealie:
    mealie = FakeMealie()
    for slug, name in (("chili", "Chili"), ("chili-2", "Chili (2)")):
        mealie.add({"slug": slug, "name": name, "orgURL": "https://example.com/chili",
                    "recipeIngredient": [{"note": "1 can beans"}], "recipeInstructions": [{"text": "Simmer."}]})
    return mealie


def _dedup(mealie, tmp_path, **kwargs):
    from cookdex.recipe_deduplicator import RecipeDeduplicator

    archive = RecipeArchive(tmp_path / "copies", mealie)
    dedup = RecipeDeduplicator(mealie, dry_run=False, apply=True, report_file=tmp_path / "d.json", archive=archive, **kwargs)
    return dedup, archive


def test_dedup_keeps_a_copy_of_each_removed_duplicate(tmp_path):
    mealie = _dupe_mealie()
    dedup, archive = _dedup(mealie, tmp_path)
    report = dedup.run()
    assert set(mealie.recipes) == {"chili"}
    [copy] = archive.list()
    assert copy["slug"] == "chili-2" and copy["reason_code"] == "duplicate"
    assert copy["reason"] == "Duplicate of 'Chili', which was kept"
    assert report["actions"][0]["copy_id"] == copy["id"]
    # And it comes back like any other.
    assert archive.restore(copy["id"])["slug"] == "chili-2"


def test_dedup_does_not_delete_without_a_copy(tmp_path, monkeypatch):
    mealie = _dupe_mealie()
    dedup, archive = _dedup(mealie, tmp_path, use_db=True)
    monkeypatch.setattr(archive, "save", lambda *a, **k: (_ for _ in ()).throw(CopyError("disk full")))
    db_calls = []
    monkeypatch.setattr(dedup, "_try_db_delete", lambda slug: db_calls.append(slug) or True)
    report = dedup.run()
    assert set(mealie.recipes) == {"chili", "chili-2"}
    assert db_calls == []  # no copy means no database delete either
    assert report["summary"]["failed"] == 1
    assert "Not deleted: disk full" in report["actions"][0]["error"]


def test_dedup_database_delete_keeps_its_copy(tmp_path, monkeypatch):
    mealie = _dupe_mealie()
    real_delete = mealie.delete_recipe
    mealie.delete_recipe = lambda slug: (_ for _ in ()).throw(_http_error(500))
    dedup, archive = _dedup(mealie, tmp_path, use_db=True)
    monkeypatch.setattr(dedup, "_try_db_delete", lambda slug: real_delete(slug) or True)
    report = dedup.run()
    assert report["actions"][0]["method"] == "db"
    assert [c["slug"] for c in archive.list()] == ["chili-2"]


def test_dedup_drops_the_copy_when_nothing_deleted_it(tmp_path):
    mealie = _dupe_mealie()
    mealie.delete_recipe = lambda slug: (_ for _ in ()).throw(_http_error(500))
    dedup, archive = _dedup(mealie, tmp_path)
    report = dedup.run()
    assert report["summary"]["failed"] == 1
    assert archive.list() == []


def test_restore_keeps_a_real_lone_ingredient(tmp_path):
    """Only Mealie's exact placeholder is taken off, never a recipe's own line."""
    mealie = FakeMealie()
    mealie.add({"slug": "roux", "name": "Roux", "recipeIngredient": [{"note": "1 cup flour", "quantity": 1}],
                "recipeInstructions": [{"text": "Whisk the flour into melted butter."}]})
    archive = RecipeArchive(tmp_path, mealie)
    meta = archive.save("roux", reason="r", reason_code="c")
    mealie.delete_recipe("roux")
    restored = mealie.recipes[archive.restore(meta["id"])["slug"]]
    assert restored["recipeIngredient"] == [{"note": "1 cup flour", "quantity": 1}]
