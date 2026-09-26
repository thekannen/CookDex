"""Upgrade cookbook filters seeded from CookDex's old default cookbook config.

Releases up to 2026.7.2 shipped ``configs/taxonomy/cookbooks.json`` with
filters written as tag and category IDs from one particular Mealie instance.
Everywhere else those IDs match nothing, so every seeded cookbook came out
empty.  Entries still holding one of those exact filters are rewritten to the
name-based form, which cookbook sync resolves against the connected Mealie.
Filters a user has edited never match and are left alone.
"""
from __future__ import annotations

from typing import Any

LEGACY_FILTERS: dict[str, str] = {
    "tags.id IN [\"ec112baa-2db8-448f-9b86-a286c77cba22\",\"78a91213-3fdb-494f-9d01-736cdbe5f445\",\"2280ee0f-4fcf-4d5e-b1b7-8049eb698caf\",\"94aca502-6412-49e1-8b8c-4abb8dc4104c\"]":
        "tags.name IN [\"Chicken\", \"Beef\", \"Pork\", \"Seafood\"]",
    "tags.id IN [\"85382c56-65a7-4ebb-8aa3-4814431e262b\",\"ed1a15af-d6e8-40f7-963a-00940a7f4877\",\"1a947d47-973c-4034-a601-10e3533cfb72\",\"4b04e046-d4ed-4967-a4a5-198368b7edcb\",\"c36f731a-e052-44b0-af2d-f2c739a6f4cc\",\"09a4d899-b83d-4a80-8e60-6c2e83abef01\"]":
        "tags.name IN [\"Noodles\", \"Chinese\", \"Japanese\", \"Korean\", \"Thai\", \"Vietnamese\"]",
    "tags.id IN [\"6b2fafc4-5f92-4c13-83f9-22f17ec99fe9\"]":
        "tags.name IN [\"Casserole\"]",
    "recipe_category.id IN [\"bef4a72f-4fe3-4e33-83b9-408476b8a20c\"] AND tags.id IN [\"c67939f5-5cd9-46f3-86d6-b7aca2c1f00e\",\"c9b551a9-5149-49ed-a3ab-c9e2c349e288\",\"569abee2-808a-4183-a58f-b93ac2c612ba\"]":
        "recipeCategory.name IN [\"Dinner\"] AND tags.name IN [\"Weeknight\", \"30-Minute\", \"One-Pot\"]",
    "tags.id IN [\"1aa0780f-d720-4e3d-bf58-015d83c48c10\",\"c03c4425-55cb-4750-9111-c5592a081c69\",\"e68b7d50-d2af-4ff9-99d2-61fa4add39fe\"]":
        "tags.name IN [\"Vegetarian\", \"Vegan\", \"Tofu\"]",
    "recipe_category.id IN [\"73355115-61eb-4c39-9f95-ffeb8075d9b7\"]":
        "recipeCategory.name IN [\"Originals\"]",
    "recipe_category.id IN [\"95263898-eaf4-4009-8801-bc4fbce8717b\"] AND tags.id IN [\"31eb932a-ffc5-453e-b702-0d770b8aaf0c\"]":
        "recipeCategory.name IN [\"Drink\"] AND tags.name IN [\"Non-Alcoholic\"]",
    "tags.id IN [\"f2e1e339-094c-4a97-a6e4-b4f6119ab279\",\"9bd070a7-7279-4cc0-8df6-4597a2aaea2c\",\"9f1e63db-69d6-4950-a7ab-4cf61e2da3cc\"]":
        "tags.name IN [\"Meal Prep\", \"Make-Ahead\", \"Freezer-Friendly\"]",
    "tags.id IN [\"827da27d-ec71-485f-8fdd-b507bfd224d2\",\"ec112baa-2db8-448f-9b86-a286c77cba22\",\"94aca502-6412-49e1-8b8c-4abb8dc4104c\",\"e68b7d50-d2af-4ff9-99d2-61fa4add39fe\"]":
        "tags.name IN [\"High-Protein\", \"Chicken\", \"Seafood\", \"Tofu\"]",
    "tags.id IN [\"af06e9d4-55d5-49fe-8b86-f40b40d9a5aa\",\"ad9acae1-bdb6-447b-926f-92836f4cf19a\",\"f497fcce-ca65-4b8c-8ab2-d274c66141d6\",\"276338f6-9511-4329-80e0-8359f2b57de3\",\"9eeffed7-ce2d-46a7-8e3a-aed1b564195e\"]":
        "tags.name IN [\"Fresh\", \"Citrus\", \"No-Cook\", \"Low-Carb\", \"Mediterranean\"]",
    "recipe_category.id IN [\"d71f824b-bcc6-445d-b522-069c34f565df\"]":
        "recipeCategory.name IN [\"Dessert\"]",
    "tags.id IN [\"329f6f03-6af1-472b-b491-8bdbfd490d8e\",\"120f6e9c-0f27-4ba5-8c2f-056d67ce40ba\",\"e6ff9392-c457-4513-bb3c-1dd5537a6e7d\"]":
        "tags.name IN [\"Crowd-Pleaser\", \"Party\", \"Holiday\"]",
    "tags.id IN [\"5d7c0fa4-a564-43df-941a-821ec5a62f57\"]":
        "tags.name IN [\"Comfort Food\"]",
    "tags.id IN [\"bd8b0fe6-fb20-4545-9c95-587f2b40f2c7\",\"ebfa2352-7c70-42ef-80e4-7c2941156a0c\",\"1a4ee717-6630-469a-8c3a-1c15138c0e8e\"]":
        "tags.name IN [\"Gluten-Free\", \"Dairy-Free\", \"Nut-Free\"]",
    "recipe_category.id IN [\"95263898-eaf4-4009-8801-bc4fbce8717b\"] AND tags.id IN [\"4adc0ced-67fe-454b-b5cb-e8fe1bdad8c1\"]":
        "recipeCategory.name IN [\"Drink\"] AND tags.name IN [\"Cocktail\"]",
}


def upgrade_cookbook_filters(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Return ``entries`` with legacy filters replaced, and how many changed."""
    changed = 0
    upgraded: list[dict[str, Any]] = []
    for entry in entries:
        replacement = LEGACY_FILTERS.get(str(entry.get("queryFilterString") or ""))
        if replacement is None:
            upgraded.append(entry)
            continue
        upgraded.append({**entry, "queryFilterString": replacement})
        changed += 1
    return upgraded, changed
