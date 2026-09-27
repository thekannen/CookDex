"""Mealie implementation of RecipeProvider, on top of MealieApiClient."""
from __future__ import annotations

from typing import Any

import requests

from ..api_client import MealieApiClient
from .base import Capability, Collection, ProviderError, ProviderInfo, Term, UnsupportedCapability

TERM_KINDS = ("tags", "categories", "tools")

CAPABILITIES = {
    Capability.TAGS,
    Capability.CATEGORIES,
    Capability.TOOLS,
    Capability.RENAME_TERMS,
    Capability.MERGE_TERMS,
    Capability.DELETE_TERMS,
    Capability.MERGE_FOODS,
    Capability.MERGE_UNITS,
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
    return ProviderError(f"Couldn't reach Mealie while {doing} ({type(exc).__name__}).")


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
            if raw and all(isinstance(item.get("recipeCount"), int) for item in raw):
                usage = {str(item["id"]): int(item["recipeCount"]) for item in raw}
            else:
                # Older Mealie servers don't report counts; tally recipe links.
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

    def require(self, capability: Capability) -> None:
        if capability not in CAPABILITIES:
            raise UnsupportedCapability(capability, self.display_name)
