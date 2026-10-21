"""Copies of recipes CookDex deleted, so each one can be put back.

Mealie has no trash, so before the junk filter or the duplicate finder
deletes a recipe it saves a copy in CookDex's data directory, next to state.db::

    deleted-recipes/<id>/meta.json     name, reason, when, which run
    deleted-recipes/<id>/recipe.json   the recipe as Mealie returned it
    deleted-recipes/<id>/export.zip    Mealie's own zip export, when it has one
    deleted-recipes/<id>/image.webp    the image, when there's no zip to hold it

The copy is written and read back before the delete is sent; if that fails,
the recipe stays in Mealie.

Restoring prefers Mealie's zip import (``POST /recipes/create/zip``), which
keeps the recipe whole. When there's no zip, or Mealie won't take it, the
recipe is created again from the saved JSON: the fields are copied over, tags,
categories, tools, foods and units are linked again by name (and made again if
they're gone), and the image is uploaded. Either way the recipe's web address
(slug) and id can change.

Copies are kept for ``DELETED_RECIPES_KEEP_DAYS`` days (30 by default); the
web UI's housekeeping removes older ones.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import requests

from .api_client import MealieApiClient, mealie_unreachable
from .config import state_db_path
from .mealie_placeholders import is_placeholder_ingredients, is_placeholder_steps

DIR_NAME = "deleted-recipes"
KEEP_DAYS_ENV = "DELETED_RECIPES_KEEP_DAYS"
DEFAULT_KEEP_DAYS = 30
MAX_KEEP_DAYS = 3650
# Set by the web UI's runner, so a copy says which run deleted it.
RUN_ID_ENV = "COOKDEX_RUN_ID"
TRIGGERED_BY_ENV = "COOKDEX_TRIGGERED_BY"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")

# Fields Mealie sets itself; a recipe made again from a copy gets new ones.
_SERVER_FIELDS = {
    "id", "slug", "userId", "groupId", "householdId", "image", "dateAdded", "dateUpdated",
    "createdAt", "updatedAt", "update_at", "lastMade", "comments", "assets",
}


class CopyError(RuntimeError):
    """A copy couldn't be saved (so the recipe isn't deleted) or read back."""


def store_dir() -> Path:
    return state_db_path().parent / DIR_NAME


def keep_days(env: Mapping[str, str] | None = None) -> int:
    raw = str((os.environ if env is None else env).get(KEEP_DAYS_ENV, "") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_KEEP_DAYS
    return min(max(value, 1), MAX_KEEP_DAYS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _entry_dir(root: Path, entry_id: str) -> Path:
    if not _ID_RE.match(str(entry_id or "")):
        raise CopyError("That isn't a saved recipe.")
    return root / entry_id


def _write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _write_json(path: Path, value: Any) -> None:
    _write_bytes(path, json.dumps(value, ensure_ascii=False, indent=1).encode("utf-8"))


def _dir_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _counts(recipe: dict[str, Any]) -> dict[str, int]:
    return {
        "ingredients": len(recipe.get("recipeIngredient") or []),
        "steps": len(recipe.get("recipeInstructions") or []),
    }


def _zip_recipe(archive: bytes) -> dict[str, Any] | None:
    """The recipe JSON inside a Mealie zip export, or None if it isn't one."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            if zf.testzip() is not None:
                return None
            names = [n for n in zf.namelist() if n.endswith(".json")]
            if not names:
                return None
            data = json.loads(zf.read(names[0]).decode("utf-8"))
    except (zipfile.BadZipFile, ValueError, OSError, KeyError):
        return None
    return data if isinstance(data, dict) else None


def _zip_image(archive: bytes) -> bytes | None:
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            names = [n for n in zf.namelist() if not n.endswith(".json")]
            return zf.read(names[0]) if names else None
    except (zipfile.BadZipFile, OSError, KeyError):
        return None


class RecipeArchive:
    """Saves, lists, restores and expires copies of deleted recipes."""

    def __init__(self, root: Path | str | None = None, client: MealieApiClient | None = None) -> None:
        self.root = Path(root) if root else store_dir()
        self.client = client
        self._zip_export: bool | None = None

    # ── Saving ────────────────────────────────────────────────────────

    def _can_export_zip(self) -> bool:
        if self._zip_export is None:
            try:
                self._zip_export = "zip" in self.client.recipe_export_formats()
            except requests.HTTPError:
                self._zip_export = False
        return self._zip_export

    def save(
        self,
        slug: str,
        *,
        reason: str,
        reason_code: str,
        run_id: str | None = None,
        triggered_by: str | None = None,
    ) -> dict[str, Any]:
        """Save a copy of the recipe at *slug* and read it back.

        Returns the copy's details. Raises CopyError when the copy can't be
        made, in which case nothing is left behind and the recipe must not be
        deleted.
        """
        if self.client is None:
            raise CopyError("No Mealie connection to read the recipe from.")
        try:
            recipe = self.client.get_recipe(slug)
        except Exception as exc:  # noqa: BLE001 - any failure to read means no copy, so no delete
            raise CopyError(f"Couldn't read the recipe to keep a copy: {exc}") from exc
        archive: bytes | None = None
        if self._can_export_zip():
            try:
                archive = self.client.export_recipe_zip(slug)
            except requests.HTTPError as exc:
                if mealie_unreachable(exc):
                    raise CopyError(f"Mealie didn't answer while saving a copy: {exc}") from exc
                archive = None
            if archive is not None and _zip_recipe(archive) is None:
                archive = None
        image: bytes | None = None
        if archive is None and recipe.get("image") and recipe.get("id"):
            try:
                image = self.client.get_recipe_image(str(recipe["id"]))
            except requests.HTTPError as exc:
                raise CopyError(f"Couldn't read the recipe's image to keep a copy: {exc}") from exc

        moment = _now()
        entry_id = f"{moment.strftime('%Y%m%dT%H%M%SZ')}-{re.sub(r'[^a-z0-9-]+', '-', slug.lower())[:60].strip('-') or 'recipe'}-{uuid.uuid4().hex[:8]}"
        folder = self.root / entry_id
        meta = {
            "id": entry_id,
            "slug": slug,
            "name": str(recipe.get("name") or slug),
            "recipe_id": str(recipe.get("id") or ""),
            "reason": reason,
            "reason_code": reason_code,
            "deleted_at": _iso(moment),
            "run_id": run_id if run_id is not None else os.environ.get(RUN_ID_ENV, ""),
            "triggered_by": triggered_by if triggered_by is not None else os.environ.get(TRIGGERED_BY_ENV, ""),
            "has_export": archive is not None,
            "has_image": archive is not None and _zip_image(archive) is not None or image is not None,
            **_counts(recipe),
        }
        try:
            folder.mkdir(parents=True, exist_ok=False)
            _write_json(folder / "recipe.json", recipe)
            if archive is not None:
                _write_bytes(folder / "export.zip", archive)
            if image is not None:
                _write_bytes(folder / "image.webp", image)
            meta["size_bytes"] = _dir_size(folder)
            _write_json(folder / "meta.json", meta)
            self._verify(folder, recipe, archive, image)
        except (OSError, CopyError, ValueError) as exc:
            shutil.rmtree(folder, ignore_errors=True)
            raise CopyError(f"Couldn't save a copy in {self.root}: {exc}") from exc
        return meta

    @staticmethod
    def _verify(folder: Path, recipe: dict[str, Any], archive: bytes | None, image: bytes | None) -> None:
        saved = json.loads((folder / "recipe.json").read_text(encoding="utf-8"))
        if saved.get("slug") != recipe.get("slug") or saved.get("id") != recipe.get("id"):
            raise CopyError("the saved recipe doesn't match what Mealie sent")
        if archive is not None and (folder / "export.zip").read_bytes() != archive:
            raise CopyError("the saved zip doesn't match what Mealie sent")
        if image is not None and (folder / "image.webp").read_bytes() != image:
            raise CopyError("the saved image doesn't match what Mealie sent")
        json.loads((folder / "meta.json").read_text(encoding="utf-8"))

    def forget(self, entry_id: str) -> bool:
        """Remove a copy. Returns False when there was none."""
        folder = _entry_dir(self.root, entry_id)
        if not folder.is_dir():
            return False
        shutil.rmtree(folder)
        return True

    # ── Listing and expiry ───────────────────────────────────────────

    def get(self, entry_id: str) -> dict[str, Any] | None:
        folder = _entry_dir(self.root, entry_id)
        try:
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return meta if isinstance(meta, dict) and meta.get("id") == entry_id else None

    def list(self) -> list[dict[str, Any]]:
        """Saved copies, newest first."""
        items: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return items
        for folder in self.root.iterdir():
            if not folder.is_dir() or not _ID_RE.match(folder.name):
                continue
            meta = self.get(folder.name)
            if meta is not None:
                items.append(meta)
        items.sort(key=lambda m: str(m.get("deleted_at") or ""), reverse=True)
        return items

    def total_size(self) -> int:
        return _dir_size(self.root) if self.root.is_dir() else 0

    def prune(self, days: int, *, now: datetime | None = None) -> int:
        """Remove copies older than *days*, and leftovers of copies that never finished.

        Returns how many were removed.
        """
        now = now or _now()
        cutoff = now - timedelta(days=days)
        removed = 0
        if not self.root.is_dir():
            return removed
        for folder in self.root.iterdir():
            if not folder.is_dir() or not _ID_RE.match(folder.name):
                continue
            meta = self.get(folder.name)
            moment = _parse_iso(str((meta or {}).get("deleted_at") or ""))
            expired = moment is not None and moment < cutoff
            if meta is None:
                # No readable details: a save that stopped halfway. Leave it a
                # day in case one is being written right now.
                try:
                    expired = datetime.fromtimestamp(folder.stat().st_mtime, timezone.utc) < now - timedelta(days=1)
                except OSError:
                    continue
            if expired:
                shutil.rmtree(folder, ignore_errors=True)
                removed += 1
        return removed

    # ── Restoring ────────────────────────────────────────────────────

    def restore(self, entry_id: str) -> dict[str, Any]:
        """Put a saved recipe back in Mealie and remove the copy.

        Returns {"slug", "name", "method"} where method is "zip" or "rebuild".
        Raises CopyError with a plain reason when it can't.
        """
        if self.client is None:
            raise CopyError("No Mealie connection to restore to.")
        meta = self.get(entry_id)
        if meta is None:
            raise CopyError("This copy is gone. It may have been restored or cleared already.")
        folder = _entry_dir(self.root, entry_id)
        try:
            recipe = json.loads((folder / "recipe.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CopyError(f"The saved copy can't be read: {exc}") from exc
        archive_path = folder / "export.zip"
        archive = archive_path.read_bytes() if archive_path.is_file() else None

        self._check_not_in_mealie(recipe)

        slug = ""
        method = ""
        if archive is not None:
            try:
                slug = self.client.import_recipe_zip(archive)
                method = "zip"
            except requests.HTTPError as exc:
                if mealie_unreachable(exc):
                    raise CopyError(f"Mealie didn't answer: {exc}") from exc
                print(f"[info] Mealie didn't take the zip ({exc}); making the recipe again from the saved copy.", flush=True)
        if not slug:
            image_path = folder / "image.webp"
            image = image_path.read_bytes() if image_path.is_file() else (_zip_image(archive) if archive else None)
            slug = self._rebuild(recipe, image)
            method = "rebuild"

        restored = self._clear_placeholders(slug, recipe)
        missing = [
            what for what, key in (("ingredients", "recipeIngredient"), ("steps", "recipeInstructions"))
            if len(recipe.get(key) or []) and not len(restored.get(key) or [])
        ]
        if missing:
            raise CopyError(
                f"Mealie has the recipe again at {slug}, but without its {' and '.join(missing)}. "
                "The copy was kept so you can try again."
            )
        self.forget(entry_id)
        return {"slug": slug, "name": str(restored.get("name") or meta.get("name") or slug), "method": method}

    def _clear_placeholders(self, slug: str, recipe: dict[str, Any]) -> dict[str, Any]:
        """Mealie gives a new recipe a "1 Cup Flour" ingredient and a first step
        when it has none; take those off again when the saved recipe had none."""
        restored = self.client.get_recipe(slug)
        extra = {
            key: [] for key, placeholder in (("recipeIngredient", is_placeholder_ingredients),
                                             ("recipeInstructions", is_placeholder_steps))
            if not (recipe.get(key) or []) and placeholder(restored.get(key))
        }
        if not extra:
            return restored
        try:
            self.client.patch_recipe(slug, extra)
        except requests.HTTPError as exc:
            print(f"[warn] {slug} came back with Mealie's placeholder {', '.join(extra)}: {exc}", flush=True)
            return restored
        return self.client.get_recipe(slug)

    def _check_not_in_mealie(self, recipe: dict[str, Any]) -> None:
        slug = str(recipe.get("slug") or "")
        if not slug:
            return
        try:
            current = self.client.get_recipe(slug)
        except requests.HTTPError as exc:
            if mealie_unreachable(exc):
                raise CopyError(f"Mealie didn't answer: {exc}") from exc
            return  # not there: good
        if recipe.get("id") and current.get("id") == recipe.get("id"):
            raise CopyError(f"This recipe is still in Mealie at {slug}, so there's nothing to restore.")

    def _rebuild(self, recipe: dict[str, Any], image: bytes | None) -> str:
        """Create the recipe again from its saved JSON (works on any Mealie)."""
        name = str(recipe.get("name") or recipe.get("slug") or "Restored recipe")
        try:
            slug = self.client.create_recipe(name)
            payload = {key: value for key, value in recipe.items() if key not in _SERVER_FIELDS}
            payload["tags"] = self._relink("tags", recipe.get("tags"))
            payload["recipeCategory"] = self._relink("categories", recipe.get("recipeCategory"))
            payload["tools"] = self._relink("tools", recipe.get("tools"))
            payload["recipeIngredient"] = self._relink_ingredients(recipe.get("recipeIngredient") or [])
            self.client.patch_recipe(slug, payload)
            # A PATCH that renames can move the slug; read where it ended up.
            created = self.client.get_recipe(slug)
            slug = str(created.get("slug") or slug)
            if image:
                self.client.upload_recipe_image(slug, image, "webp")
        except requests.HTTPError as exc:
            raise CopyError(f"Mealie didn't accept the recipe: {exc}") from exc
        return slug

    def _existing(self, kind: str) -> dict[str, dict[str, Any]]:
        cache = getattr(self, "_names", None)
        if cache is None:
            cache = self._names = {}
        if kind not in cache:
            if kind == "foods":
                items = self.client.list_foods()
            elif kind == "units":
                items = self.client.list_units()
            elif kind == "tools":
                items = self.client.list_tools()
            else:
                items = self.client.get_organizer_items(kind)
            cache[kind] = {str(i.get("name") or "").strip().lower(): i for i in items if i.get("name")}
        return cache[kind]

    def _by_name(self, kind: str, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            return None
        name = str(item["name"]).strip()
        known = self._existing(kind)
        found = known.get(name.lower())
        if found is None:
            if kind == "foods":
                found = self.client.create_food(name)
            elif kind == "units":
                found = self.client.create_unit(name, str(item.get("abbreviation") or ""))
            elif kind == "tools":
                found = self.client.create_tool(name)
            else:
                found = self.client.create_organizer_item(kind, {"name": name})
            if found:
                known[name.lower()] = found
        return found or None

    def _relink(self, kind: str, items: Any) -> list[dict[str, Any]]:
        out = []
        for item in items or []:
            found = self._by_name(kind, item)
            if found:
                out.append({k: found.get(k) for k in ("id", "name", "slug") if found.get(k) is not None})
        return out

    def _relink_ingredients(self, ingredients: list[Any]) -> list[Any]:
        out = []
        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                out.append(ingredient)
                continue
            line = dict(ingredient)
            for key, kind in (("food", "foods"), ("unit", "units")):
                if line.get(key):
                    line[key] = self._by_name(kind, line[key])
            # A recipe linked as an ingredient may be gone; keep its name as text.
            linked = line.pop("referencedRecipe", None)
            if isinstance(linked, dict) and linked.get("name") and not line.get("note"):
                line["note"] = str(linked["name"])
            out.append(line)
        return out
