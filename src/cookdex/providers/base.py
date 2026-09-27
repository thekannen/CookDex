"""What CookDex needs from a recipe manager.

Mealie is the only backend today. This module describes the operations the
web UI's newer pages (Library, Organize, Discover) rely on in terms that
don't assume Mealie, so another manager such as Tandoor can be added as a
second implementation without touching those pages.

Rules for adapters:
- Report only capabilities you implement. The UI and task list hide what a
  backend can't do, based on ``capabilities()``.
- Speak in these types. Backend-specific fields (Mealie's slugs, Tandoor's
  keyword tree) stay inside the adapter.
- Raise ``ProviderError`` with a message a person can act on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class Capability(str, Enum):
    TAGS = "tags"                      # flat tags on recipes
    CATEGORIES = "categories"          # flat categories on recipes
    TOOLS = "tools"                    # tools/equipment on recipes
    TERM_HIERARCHY = "term_hierarchy"  # terms can have parents (Tandoor keywords)
    RENAME_TERMS = "rename_terms"
    MERGE_TERMS = "merge_terms"        # move recipes from one term to another
    DELETE_TERMS = "delete_terms"
    MERGE_FOODS = "merge_foods"
    MERGE_UNITS = "merge_units"
    SERVER_PARSER = "server_parser"    # backend parses ingredient lines
    IMPORT_URL = "import_url"          # backend scrapes and saves a recipe URL
    BACKUP = "backup"                  # backend can create backups via its API
    RULE_COLLECTIONS = "rule_collections"  # saved-filter collections (Mealie cookbooks)
    LABELS = "labels"
    DIRECT_DB = "direct_db"            # CookDex can read/write the backend's database
    SLUGS = "slugs"                    # recipes are addressed by slug (Mealie)


class ProviderError(RuntimeError):
    """A backend call failed. The message is meant for people."""


class UnsupportedCapability(ProviderError):
    def __init__(self, capability: Capability, backend: str) -> None:
        super().__init__(f"{backend} doesn't support {capability.value.replace('_', ' ')}.")
        self.capability = capability


@dataclass(frozen=True)
class ProviderInfo:
    kind: str           # "mealie", later "tandoor"
    name: str           # display name, e.g. "Mealie"
    version: str = ""
    user: str = ""


@dataclass
class Term:
    """A tag, category, tool or keyword, with how many recipes use it."""

    id: str
    name: str
    kind: str
    count: int = 0
    parent_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # adapter-private details


@dataclass
class Collection:
    """A saved-filter collection of recipes (Mealie cookbooks, Tandoor books).

    ``rule`` is the backend's filter expression. Adapters without rule-based
    collections don't advertise ``rule_collections``.
    """

    id: str
    name: str
    rule: str = ""
    description: str = ""
    public: bool = False
    position: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Label:
    """A colored label for foods (groups shopping lists by aisle)."""

    id: str
    name: str
    color: str = "#959595"
    count: int = 0  # foods using it


@runtime_checkable
class RecipeProvider(Protocol):
    kind: str
    display_name: str

    def capabilities(self) -> set[Capability]: ...

    def vocabulary(self) -> dict[str, Any]:
        """Words the UI should use for this backend (term kinds, collections)."""
        ...

    def health(self) -> ProviderInfo:
        """Check the connection and credentials; raise ProviderError if not usable."""
        ...

    def term_kinds(self) -> list[str]: ...

    def list_terms(self, kind: str) -> list[Term]: ...

    def rename_term(self, kind: str, term_id: str, name: str) -> None: ...

    def merge_terms(self, kind: str, source_id: str, target_id: str) -> None: ...

    def delete_term(self, kind: str, term_id: str) -> None: ...

    def count_recipes(self) -> int: ...

    def import_url(self, url: str) -> str:
        """Import a recipe from a URL; return the backend's id or slug for it."""
        ...

    def create_backup(self) -> None: ...

    # Rule-based collections (only when Capability.RULE_COLLECTIONS is advertised)

    def list_collections(self) -> list[Collection]: ...

    def count_rule_matches(self, rule: str, *, sample: int = 0) -> tuple[int, list[str]]:
        """How many recipes a rule matches, plus up to ``sample`` recipe names."""
        ...

    def create_collection(self, collection: Collection) -> Collection: ...

    def update_collection(self, collection: Collection) -> Collection: ...

    def delete_collection(self, collection_id: str) -> None: ...

    # Food labels (only when Capability.LABELS is advertised)

    def list_labels(self) -> list[Label]: ...

    def create_label(self, name: str, color: str) -> Label: ...

    def update_label(self, label_id: str, name: str, color: str) -> Label: ...

    def delete_label(self, label_id: str) -> None: ...

    def merge_labels(self, source_id: str, target_id: str) -> int:
        """Move every food from one label to another, then delete the source. Returns foods moved."""
        ...
