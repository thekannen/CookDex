from __future__ import annotations

import pytest

from cookdex.organize_apply import _rule_names_to_ids
from cookdex.providers import Capability, Collection, Label, ProviderError, ProviderInfo, Term, Unit
from cookdex.webui_server import taxonomy_io


class MemoryProvider:
    """Just the reads taxonomy_io and cookbook compiling use."""

    kind = "memory"
    display_name = "Mealie"

    def __init__(self) -> None:
        self.terms = {
            "tags": [Term(id="T1", name="Salad", kind="tags"), Term(id="T2", name="Italian", kind="tags")],
            "categories": [Term(id="C1", name="Dinner", kind="categories")],
            "tools": [],
        }
        self.labels = [Label(id="L1", name="Produce", color="#43a047")]
        self.units = [Unit(id="U1", name="tablespoon", abbreviation="tbsp", aliases=["Tbs"])]
        self.collections = [
            Collection(id="K1", name="Salads", rule='tags.id IN ["t1"]', description="Greens", public=False, position=1),
        ]

    def capabilities(self):
        return {Capability.TAGS, Capability.CATEGORIES, Capability.TOOLS, Capability.LABELS, Capability.UNITS,
                Capability.RULE_COLLECTIONS}

    def term_kinds(self):
        return ["tags", "categories", "tools"]

    def health(self):
        return ProviderInfo(kind="mealie", name="Mealie", version="v3.28.0")

    def list_terms(self, kind):
        return list(self.terms[kind])

    def list_labels(self):
        return list(self.labels)

    def list_units(self):
        return list(self.units)

    def list_collections(self):
        return list(self.collections)


def test_export_uses_managed_file_shapes_and_names_in_filters():
    document = taxonomy_io.export_taxonomy(MemoryProvider())
    assert document["format"] == "cookdex-taxonomy" and document["source"] == "Mealie v3.28.0"
    assert document["tags"] == [{"name": "Italian"}, {"name": "Salad"}]
    assert document["labels"] == [{"name": "Produce", "color": "#43a047"}]
    assert document["units_aliases"] == [{"name": "tablespoon", "abbreviation": "tbsp", "aliases": ["Tbs"]}]
    assert document["cookbooks"][0]["queryFilterString"] == 'tags.name IN ["Salad"]'


def test_importing_an_export_changes_nothing():
    provider = MemoryProvider()
    document = taxonomy_io.export_taxonomy(provider)
    plan = taxonomy_io.plan_import(provider, taxonomy_io.read_document(document))
    assert plan["changes"] == []
    assert plan["summary"]["tags"] == {"new": 0, "updated": 0, "unchanged": 2}


def test_import_adds_and_fills_gaps_without_deleting():
    provider = MemoryProvider()
    sections = taxonomy_io.read_document({
        "tags": [{"name": "Salads"}, {"name": "Thai"}],  # "Salads" is the existing "Salad"
        "labels": [{"name": "produce", "color": "#00ff00"}, {"name": "Bakery", "color": "#a1887f"}],
        "units_aliases": [{"name": "Tablespoon", "pluralName": "tablespoons", "aliases": ["T", "tbsp"]}],
        "cookbooks": [{"name": "Thai Night", "queryFilterString": 'tags.name IN ["Thai"]'}],
    })
    plan = taxonomy_io.plan_import(provider, sections)
    by_key = {(c["kind"], c["op"], c["name"]): c for c in plan["changes"]}

    assert set(by_key) == {
        ("tags", "create", "Thai"),
        ("labels", "update", "Produce"),
        ("labels", "create", "Bakery"),
        ("units", "update", "tablespoon"),
        ("cookbooks", "create", "Thai Night"),
    }
    assert by_key[("labels", "update", "Produce")]["to"] == {"name": "Produce", "color": "#00ff00"}
    unit = by_key[("units", "update", "tablespoon")]["to"]
    assert unit == {"name": "tablespoon", "abbreviation": "tbsp", "plural_name": "tablespoons", "aliases": ["Tbs", "T"]}
    assert by_key[("cookbooks", "create", "Thai Night")]["to"]["rule"] == 'tags.name IN ["Thai"]'


def test_single_files_are_read_by_name():
    sections = taxonomy_io.read_document([{"name": "Brunch"}, "Brunch"], "configs/taxonomy/categories.json")
    assert sections == {"categories": [{"name": "Brunch"}]}
    with pytest.raises(ValueError, match="Name it after a section"):
        taxonomy_io.read_document([{"name": "x"}], "stuff.json")
    with pytest.raises(ValueError):
        taxonomy_io.read_document({"recipes": []})


def test_cookbook_names_resolve_to_ids_at_apply_time():
    provider = MemoryProvider()
    assert _rule_names_to_ids(provider, 'tags.name IN ["salad", "Italian"]') == 'tags.id IN ["T1","T2"]'
    assert _rule_names_to_ids(provider, 'tags.id IN ["T1"]') == 'tags.id IN ["T1"]'
    with pytest.raises(ProviderError, match="Thai"):
        _rule_names_to_ids(provider, 'tags.name IN ["Thai"]')


def test_export_warns_about_filters_pointing_at_missing_items():
    provider = MemoryProvider()
    provider.collections.append(Collection(id="K2", name="Ghosts", rule='tags.id IN ["gone"]', position=2))
    document = taxonomy_io.export_taxonomy(provider)
    assert "Ghosts" in document["warnings"][0] and "Salads" not in document["warnings"][0]
