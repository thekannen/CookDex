import json
from pathlib import Path

from cookdex.legacy_cookbook_filters import LEGACY_FILTERS, upgrade_cookbook_filters

_SHIPPED = Path(__file__).resolve().parents[1] / "configs" / "taxonomy" / "cookbooks.json"


def test_every_legacy_filter_upgrades_to_the_shipped_name_filter():
    shipped = {cb["queryFilterString"] for cb in json.loads(_SHIPPED.read_text(encoding="utf-8"))}
    assert set(LEGACY_FILTERS.values()) == shipped
    assert all(".id " in legacy for legacy in LEGACY_FILTERS)


def test_upgrade_rewrites_only_untouched_legacy_filters():
    legacy, upgraded = next(iter(LEGACY_FILTERS.items()))
    entries = [
        {"name": "Seeded", "queryFilterString": legacy, "position": 1},
        {"name": "Edited", "queryFilterString": 'tags.id IN ["my-own-id"]', "position": 2},
    ]

    result, changed = upgrade_cookbook_filters(entries)

    assert changed == 1
    assert result[0] == {"name": "Seeded", "queryFilterString": upgraded, "position": 1}
    assert result[1] == entries[1]
    assert upgrade_cookbook_filters(result) == (result, 0)
