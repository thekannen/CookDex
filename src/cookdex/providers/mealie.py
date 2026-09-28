"""Mealie implementation of RecipeProvider, on top of MealieApiClient."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

from ..api_client import MealieApiClient
from .base import Capability, Collection, Food, Label, ProviderError, ProviderInfo, Term, Unit, UnsupportedCapability

TERM_KINDS = ("tags", "categories", "tools")

CAPABILITIES = {
    Capability.TAGS,
    Capability.CATEGORIES,
    Capability.TOOLS,
    Capability.RENAME_TERMS,
    Capability.MERGE_TERMS,
    Capability.DELETE_TERMS,
    Capability.FOODS,
    Capability.UNITS,
    Capability.MERGE_FOODS,
    Capability.MERGE_UNITS,
    Capability.STANDARD_LISTS,
    Capability.SERVER_PARSER,
    Capability.IMPORT_URL,
    Capability.BACKUP,
    Capability.RULE_COLLECTIONS,
    Capability.LABELS,
    Capability.DIRECT_DB,
    Capability.SLUGS,
}


def _problem(exc: requests.RequestException, doing: str) -> ProviderError:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return ProviderError(f"Mealie rejected the API token while {doing}.")
    if status is not None:
        return ProviderError(f"Mealie answered with HTTP {status} while {doing}.")
    cause = exc.__cause__ if isinstance(exc.__cause__, requests.RequestException) else exc
    if isinstance(cause, (requests.exceptions.ReadTimeout,)) or (
        isinstance(cause, requests.exceptions.Timeout) and not isinstance(cause, requests.exceptions.ConnectTimeout)
    ):
        return ProviderError(f"Mealie didn't answer in time while {doing}. It may be busy or stopped.")
    return ProviderError(f"Couldn't reach Mealie while {doing}. It may be stopped, or its address changed.")


class MealieProvider:
    kind = "mealie"
    display_name = "Mealie"

    def __init__(self, client: MealieApiClient | None) -> None:
        # client may be None when only describing the backend (capabilities,
        # wording); every call that talks to Mealie needs one.
        self.client = client

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "MealieProvider":
        from ..config import normalize_mealie_url

        url = normalize_mealie_url(env.get("MEALIE_URL", ""))
        key = str(env.get("MEALIE_API_KEY", "")).strip()
        if not url or not key:
            raise ProviderError("Connect Mealie in Settings first.")
        return cls(MealieApiClient(base_url=url, api_key=key))

    def capabilities(self) -> set[Capability]:
        return set(CAPABILITIES)

    def vocabulary(self) -> dict[str, Any]:
        return {
            "backend": "Mealie",
            "terms": {"tags": "Tags", "categories": "Categories", "tools": "Tools"},
            "term_singular": {"tags": "tag", "categories": "category", "tools": "tool"},
            "collections": "Cookbooks",
            "address_label": "Mealie address",
            "token_label": "Mealie API token",
        }

    def health(self) -> ProviderInfo:
        try:
            user = self.client.request_json("GET", "/users/self", timeout=12)
        except requests.RequestException as exc:
            raise _problem(exc, "checking the connection") from exc
        except ValueError as exc:  # an HTML page, e.g. the address is missing /api
            raise ProviderError("That address answered, but it isn't the Mealie API.") from exc
        if not isinstance(user, dict) or not (user.get("id") or user.get("username")):
            raise ProviderError("That address answered, but it isn't the Mealie API.")
        version = ""
        try:
            about = self.client.get_about()
            version = str(about.get("version") or "")
        except requests.RequestException:
            pass
        return ProviderInfo(kind=self.kind, name=self.display_name, version=version,
                            user=str(user.get("username") or user.get("email") or ""))

    def term_kinds(self) -> list[str]:
        return list(TERM_KINDS)

    def _check_kind(self, kind: str) -> None:
        if kind not in TERM_KINDS:
            raise ProviderError(f"Mealie has no '{kind}'. Use one of: {', '.join(TERM_KINDS)}.")

    def _raw_terms(self, kind: str) -> list[dict[str, Any]]:
        return self.client.list_tools() if kind == "tools" else self.client.get_organizer_items(kind)

    def list_terms(self, kind: str) -> list[Term]:
        self._check_kind(kind)
        try:
            raw = self._raw_terms(kind)
            # Mealie reports recipeCount for tools too, but it's always 0 (seen on
            # v3.28 with 10k recipes using tools), so tools are counted with a filter.
            usage = self._tool_usage(raw) if kind == "tools" else None
            if usage is None and kind != "tools" and raw and all(isinstance(item.get("recipeCount"), int) for item in raw):
                usage = {str(item["id"]): int(item["recipeCount"]) for item in raw}
            if usage is None:
                # Older Mealie servers don't report counts, and tool counts can't
                # be trusted; tally recipe links.
                field = {"tags": "tags", "categories": "recipeCategory", "tools": "tools"}[kind]
                usage = {}
                for recipe in self.client.get_recipes(per_page=1000):
                    for entry in recipe.get(field) or []:
                        if isinstance(entry, dict) and entry.get("id"):
                            usage[str(entry["id"])] = usage.get(str(entry["id"]), 0) + 1
        except requests.RequestException as exc:
            raise _problem(exc, f"reading {kind}") from exc
        return [
            Term(
                id=str(item["id"]),
                name=str(item.get("name") or ""),
                kind=kind,
                count=usage.get(str(item["id"]), 0),
                extra={"slug": item.get("slug"), "groupId": item.get("groupId")},
            )
            for item in raw
            if item.get("id")
        ]

    def _tool_usage(self, raw: list[dict[str, Any]]) -> dict[str, int] | None:
        """Recipes per tool from Mealie's recipe filter, or None when that fails."""
        ids = [str(item["id"]) for item in raw if item.get("id") and re.fullmatch(r"[A-Za-z0-9-]+", str(item["id"]))]

        def count(tool_id: str) -> int:
            data = self.client.request_json(
                "GET", "/recipes", params={"perPage": 1, "page": 1, "queryFilter": f'tools.id IN ["{tool_id}"]'}, timeout=30
            )
            return int(data.get("total") or 0) if isinstance(data, dict) else 0

        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                return dict(zip(ids, pool.map(count, ids)))
        except (requests.RequestException, ValueError):
            return None

    def create_term(self, kind: str, name: str) -> Term:
        self._check_kind(kind)
        try:
            data = self.client.create_organizer_item(kind, {"name": name})
        except requests.RequestException as exc:
            raise _problem(exc, f"creating a {kind[:-1]}") from exc
        return Term(id=str(data.get("id") or ""), name=str(data.get("name") or name), kind=kind,
                    extra={"slug": data.get("slug"), "groupId": data.get("groupId")})

    def rename_term(self, kind: str, term_id: str, name: str) -> None:
        self._check_kind(kind)
        try:
            self.client.rename_organizer_item(kind, term_id, name)
        except requests.RequestException as exc:
            raise _problem(exc, f"renaming a {kind[:-1]}") from exc

    def merge_terms(self, kind: str, source_id: str, target_id: str) -> None:
        self._check_kind(kind)
        try:
            if kind == "tools":
                self.client.merge_tool(source_id, target_id)
            else:
                self.client.merge_organizer_item(kind, source_id, target_id)
        except requests.RequestException as exc:
            raise _problem(exc, f"merging {kind}") from exc

    def delete_term(self, kind: str, term_id: str) -> None:
        self._check_kind(kind)
        try:
            self.client.delete_organizer_item(kind, term_id)
        except requests.RequestException as exc:
            raise _problem(exc, f"deleting a {kind[:-1]}") from exc

    def count_recipes(self) -> int:
        try:
            return self.client.count_paginated("/recipes")
        except requests.RequestException as exc:
            raise _problem(exc, "counting recipes") from exc

    def import_url(self, url: str) -> str:
        try:
            return self.client.scrape_recipe_url(url)
        except requests.RequestException as exc:
            raise _problem(exc, "importing a recipe") from exc

    def create_backup(self) -> None:
        from ..mealie_backup import create_backup

        if not create_backup(self.client):
            raise ProviderError("Mealie didn't create the backup. Check that the API token belongs to an admin.")

    # Cookbooks -----------------------------------------------------------

    @staticmethod
    def _to_collection(raw: dict[str, Any]) -> Collection:
        return Collection(
            id=str(raw.get("id") or ""),
            name=str(raw.get("name") or ""),
            rule=str(raw.get("queryFilterString") or ""),
            description=str(raw.get("description") or ""),
            public=bool(raw.get("public")),
            position=int(raw.get("position") or 0),
            extra={"slug": raw.get("slug"), "householdId": raw.get("householdId"), "groupId": raw.get("groupId")},
        )

    @staticmethod
    def _cookbook_payload(collection: Collection) -> dict[str, Any]:
        return {
            "name": collection.name,
            "description": collection.description,
            "queryFilterString": collection.rule,
            "public": collection.public,
            "position": collection.position,
        }

    def list_collections(self) -> list[Collection]:
        try:
            raw = self.client.list_cookbooks()
        except requests.RequestException as exc:
            raise _problem(exc, "reading cookbooks") from exc
        return sorted((self._to_collection(item) for item in raw), key=lambda c: (c.position, c.name.lower()))

    def count_rule_matches(self, rule: str, *, sample: int = 0) -> tuple[int, list[str]]:
        try:
            data = self.client.request_json(
                "GET", "/recipes", params={"perPage": max(1, sample), "page": 1, "queryFilter": rule}, timeout=30
            )
        except requests.HTTPError as exc:
            if getattr(exc.response, "status_code", None) in (400, 422):
                raise ProviderError("Mealie couldn't read this filter. Check the fields and values.") from exc
            raise _problem(exc, "counting matching recipes") from exc
        except requests.RequestException as exc:
            raise _problem(exc, "counting matching recipes") from exc
        if not isinstance(data, dict):
            return 0, []
        names = [str(item.get("name") or "") for item in (data.get("items") or [])][:sample] if sample else []
        return int(data.get("total") or 0), names

    def create_collection(self, collection: Collection) -> Collection:
        try:
            data = self.client.request_json("POST", "/households/cookbooks", json=self._cookbook_payload(collection), timeout=60)
        except requests.RequestException as exc:
            raise _problem(exc, "creating a cookbook") from exc
        return self._to_collection(data if isinstance(data, dict) else {})

    def update_collection(self, collection: Collection) -> Collection:
        try:
            data = self.client.request_json(
                "PUT", f"/households/cookbooks/{collection.id}",
                json={**self._cookbook_payload(collection), "id": collection.id}, timeout=60,
            )
        except requests.RequestException as exc:
            raise _problem(exc, "updating a cookbook") from exc
        return self._to_collection(data if isinstance(data, dict) else {})

    def delete_collection(self, collection_id: str) -> None:
        try:
            self.client._request_raw("DELETE", f"/households/cookbooks/{collection_id}", timeout=60)
        except requests.RequestException as exc:
            raise _problem(exc, "deleting a cookbook") from exc

    # Food labels ---------------------------------------------------------

    def list_labels(self) -> list[Label]:
        try:
            raw = self.client.list_labels()
            foods = self.client.list_foods()
        except requests.RequestException as exc:
            raise _problem(exc, "reading labels") from exc
        counts: dict[str, int] = {}
        for food in foods:
            label_id = food.get("labelId") or (food.get("label") or {}).get("id")
            if label_id:
                counts[str(label_id)] = counts.get(str(label_id), 0) + 1
        return sorted(
            (Label(id=str(item["id"]), name=str(item.get("name") or ""), color=str(item.get("color") or "#959595"),
                   count=counts.get(str(item["id"]), 0)) for item in raw if item.get("id")),
            key=lambda label: label.name.lower(),
        )

    def create_label(self, name: str, color: str) -> Label:
        try:
            data = self.client.create_label(name, color=color)
        except requests.RequestException as exc:
            raise _problem(exc, "creating a label") from exc
        return Label(id=str(data.get("id") or ""), name=str(data.get("name") or name), color=str(data.get("color") or color))

    def update_label(self, label_id: str, name: str, color: str) -> Label:
        try:
            current = next((item for item in self.client.list_labels() if str(item.get("id")) == label_id), None)
            if current is None:
                raise ProviderError("That label no longer exists in Mealie.")
            data = self.client.update_label({**current, "name": name, "color": color})
        except requests.RequestException as exc:
            raise _problem(exc, "updating a label") from exc
        return Label(id=label_id, name=str(data.get("name") or name), color=str(data.get("color") or color))

    def delete_label(self, label_id: str) -> None:
        try:
            self.client.delete_label(label_id)
        except requests.RequestException as exc:
            raise _problem(exc, "deleting a label") from exc

    def merge_labels(self, source_id: str, target_id: str) -> int:
        # Mealie has no label merge endpoint: move each food, then delete.
        moved = 0
        try:
            for food in self.client.list_foods():
                label_id = food.get("labelId") or (food.get("label") or {}).get("id")
                if str(label_id or "") != source_id:
                    continue
                self.client.update_food({**food, "labelId": target_id, "label": None})
                moved += 1
            self.client.delete_label(source_id)
        except requests.RequestException as exc:
            raise _problem(exc, "merging labels") from exc
        return moved

    # Ingredient foods and units ------------------------------------------

    @staticmethod
    def _aliases(raw: Any) -> list[str]:
        names = [str(a.get("name") if isinstance(a, dict) else a or "").strip() for a in (raw or [])]
        return [name for name in names if name]

    def _to_food(self, data: dict[str, Any]) -> Food:
        return Food(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or ""),
            plural_name=str(data.get("pluralName") or ""),
            label_id=str(data.get("labelId") or (data.get("label") or {}).get("id") or ""),
            aliases=self._aliases(data.get("aliases")),
        )

    def _to_unit(self, data: dict[str, Any]) -> Unit:
        return Unit(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or ""),
            plural_name=str(data.get("pluralName") or ""),
            abbreviation=str(data.get("abbreviation") or ""),
            aliases=self._aliases(data.get("aliases")),
        )

    def list_foods(self) -> list[Food]:
        try:
            raw = self.client.list_foods()
        except requests.RequestException as exc:
            raise _problem(exc, "reading foods") from exc
        return sorted((self._to_food(item) for item in raw if item.get("id")), key=lambda f: f.name.lower())

    def update_food(self, food: Food) -> Food:
        try:
            current = self.client.request_json("GET", f"/foods/{food.id}", timeout=60)
            payload = {
                **(current if isinstance(current, dict) else {}),
                "id": food.id,
                "name": food.name,
                "pluralName": food.plural_name or None,
                "labelId": food.label_id or None,
                "label": None,
                "aliases": [{"name": alias} for alias in food.aliases],
            }
            return self._to_food(self.client.update_food(payload) or payload)
        except requests.RequestException as exc:
            raise _problem(exc, "updating a food") from exc

    def merge_foods(self, source_id: str, target_id: str) -> None:
        try:
            self.client.merge_food(source_id, target_id)
        except requests.RequestException as exc:
            raise _problem(exc, "merging foods") from exc

    def delete_food(self, food_id: str) -> None:
        try:
            self.client.delete_food(food_id)
        except requests.RequestException as exc:
            raise _problem(exc, "deleting a food") from exc

    def list_units(self) -> list[Unit]:
        try:
            raw = self.client.list_units()
        except requests.RequestException as exc:
            raise _problem(exc, "reading units") from exc
        return sorted((self._to_unit(item) for item in raw if item.get("id")), key=lambda u: u.name.lower())

    def create_unit(self, unit: Unit) -> Unit:
        payload = {
            "name": unit.name,
            "pluralName": unit.plural_name or None,
            "abbreviation": unit.abbreviation,
            "aliases": [{"name": alias} for alias in unit.aliases],
            "fraction": True,
            "useAbbreviation": False,
        }
        try:
            data = self.client.request_json("POST", "/units", json=payload, timeout=60)
        except requests.RequestException as exc:
            raise _problem(exc, "creating a unit") from exc
        return self._to_unit(data if isinstance(data, dict) else payload)

    def update_unit(self, unit: Unit) -> Unit:
        try:
            current = self.client.request_json("GET", f"/units/{unit.id}", timeout=60)
            payload = {
                **(current if isinstance(current, dict) else {}),
                "id": unit.id,
                "name": unit.name,
                "pluralName": unit.plural_name or None,
                "abbreviation": unit.abbreviation,
                "aliases": [{"name": alias} for alias in unit.aliases],
            }
            return self._to_unit(self.client.update_unit(payload) or payload)
        except requests.RequestException as exc:
            raise _problem(exc, "updating a unit") from exc

    def merge_units(self, source_id: str, target_id: str) -> None:
        try:
            self.client.merge_unit(source_id, target_id)
        except requests.RequestException as exc:
            raise _problem(exc, "merging units") from exc

    def add_standard(self, kind: str, locale: str) -> None:
        if kind not in {"foods", "units"}:
            raise ProviderError(f"Mealie has no standard list of {kind}.")
        try:
            self.client.request_json("POST", f"/groups/seeders/{kind}", json={"locale": locale}, timeout=300)
        except requests.RequestException as exc:
            raise _problem(exc, f"adding Mealie's standard {kind}") from exc

    def delete_unit(self, unit_id: str) -> None:
        try:
            self.client.delete_unit(unit_id)
        except requests.RequestException as exc:
            raise _problem(exc, "deleting a unit") from exc

    def count_ingredient_uses(self, kind: str, item_id: str) -> int:
        field_name = {"foods": "food", "units": "unit"}.get(kind)
        if field_name is None:
            raise ProviderError(f"Unknown ingredient kind '{kind}'.")
        if not re.fullmatch(r"[A-Za-z0-9-]+", item_id or ""):
            raise ProviderError("That isn't a Mealie id.")
        rule = f'recipe_ingredient.{field_name}.id IN ["{item_id}"]'
        try:
            data = self.client.request_json("GET", "/recipes", params={"perPage": 1, "page": 1, "queryFilter": rule}, timeout=30)
        except requests.RequestException as exc:
            raise _problem(exc, f"counting recipes that use a {field_name}") from exc
        return int(data.get("total") or 0) if isinstance(data, dict) else 0

    def require(self, capability: Capability) -> None:
        if capability not in CAPABILITIES:
            raise UnsupportedCapability(capability, self.display_name)
