"""Suggested starting sets for a new or sparse library.

Organize offers these when a library has few tags, categories, tools or
labels. Picking a pack stages ``create`` changes for the items the library
doesn't already have; nothing is written until the batch is applied.

Keep packs short, neutral and useful to most home cooks. Names use the
spelling and case Mealie shows, and labels carry a color.
"""
from __future__ import annotations

from typing import Any

PACKS: list[dict[str, Any]] = [
    {
        "id": "meal-types",
        "kind": "categories",
        "title": "Meal types",
        "description": "When or how a dish is served.",
        "items": [
            "Breakfast", "Brunch", "Lunch", "Dinner", "Appetizer", "Side Dish", "Soup", "Salad",
            "Dessert", "Snack", "Drink", "Sauce", "Bread", "Baking",
        ],
    },
    {
        "id": "cuisines",
        "kind": "tags",
        "title": "Cuisines",
        "description": "Where a dish comes from.",
        "items": [
            "American", "Chinese", "French", "Greek", "Indian", "Italian", "Japanese", "Korean",
            "Mediterranean", "Mexican", "Middle Eastern", "Spanish", "Thai", "Vietnamese",
        ],
    },
    {
        "id": "diets",
        "kind": "tags",
        "title": "Diets",
        "description": "Filters for dietary needs.",
        "items": [
            "Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Nut-Free", "Low-Carb", "Keto",
            "High-Protein",
        ],
    },
    {
        "id": "main-ingredients",
        "kind": "tags",
        "title": "Main ingredients",
        "description": "What the dish is built around.",
        "items": [
            "Chicken", "Beef", "Pork", "Lamb", "Fish", "Seafood", "Tofu", "Beans", "Eggs", "Pasta",
            "Rice", "Vegetables",
        ],
    },
    {
        "id": "occasions",
        "kind": "tags",
        "title": "Occasions and effort",
        "description": "How much time it takes and when you'd make it.",
        "items": [
            "Quick", "Weeknight", "Make Ahead", "Freezer-Friendly", "One-Pot", "Meal Prep",
            "Kid-Friendly", "Party", "Holiday", "Comfort Food",
        ],
    },
    {
        "id": "kitchen-tools",
        "kind": "tools",
        "title": "Kitchen tools",
        "description": "Equipment a recipe needs.",
        "items": [
            "Air Fryer", "Blender", "Cast-Iron Skillet", "Dutch Oven", "Food Processor", "Grill",
            "Immersion Blender", "Pressure Cooker", "Sheet Pan", "Slow Cooker", "Stand Mixer",
            "Stockpot", "Wok",
        ],
    },
    {
        "id": "grocery-aisles",
        "kind": "labels",
        "title": "Grocery aisles",
        "description": "Groups foods on shopping lists by where you find them.",
        "items": [
            {"name": "Produce", "color": "#43a047"},
            {"name": "Meat & Seafood", "color": "#e53935"},
            {"name": "Dairy & Eggs", "color": "#90caf9"},
            {"name": "Bakery", "color": "#a1887f"},
            {"name": "Deli", "color": "#f06292"},
            {"name": "Pantry", "color": "#ffb300"},
            {"name": "Canned & Jarred", "color": "#8d6e63"},
            {"name": "Spices & Seasonings", "color": "#fb8c00"},
            {"name": "Condiments & Sauces", "color": "#ef6c00"},
            {"name": "Baking Supplies", "color": "#fdd835"},
            {"name": "Frozen", "color": "#4fc3f7"},
            {"name": "Snacks", "color": "#ab47bc"},
            {"name": "Beverages", "color": "#26a69a"},
            {"name": "Household", "color": "#78909c"},
        ],
    },
]


def packs_for(kinds: set[str]) -> list[dict[str, Any]]:
    """Packs whose kind the backend supports, with items as ``{"name", ...}`` dicts."""
    return [
        {**pack, "items": [item if isinstance(item, dict) else {"name": item} for item in pack["items"]]}
        for pack in PACKS
        if pack["kind"] in kinds
    ]
