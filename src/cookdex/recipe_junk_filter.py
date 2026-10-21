"""Recipe Junk Filter.

Detects and removes non-recipe content that slipped in during bulk import:
listicles, how-to articles, digest posts, utility pages, and recipes with
placeholder or missing instructions.

Names and slugs provide review hints. The content is read too: about,
contact and policy pages, trip write-ups and other stories have no measured
ingredients, no cooking steps, no servings or times, and read like prose.

How much evidence deletes a page on its own depends on the strength
(``--strength``):

- ``cautious`` (default): only records missing both meaningful ingredients and
  usable instructions. Everything else that looks off goes to review.
- ``balanced``: also about/contact/policy pages, trip or story posts and other
  articles with no recipe structure at all.
- ``strong``: also those with a little recipe-like content, and title or slug
  matches (how-to, listicle, digest, keyword, utility) with almost none.

At every strength a page with measured ingredients and cooking steps is a
recipe and is never deleted on its own. Deleted recipes are kept in Recently
deleted (see cookdex.deleted_recipes), so each can be restored.

In dry-run mode (default) the tool reports what would be deleted without touching
anything.  Pass --apply to actually delete.

Use --reason to filter by a specific junk category only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .api_client import MealieApiClient
from .config import env_or_config, resolve_mealie_api_key, resolve_mealie_url, resolve_repo_path, to_bool
from .deleted_recipes import CopyError, RecipeArchive
from .mealie_placeholders import without_placeholders
from .reporting import Progress, emit_items, emit_summary, load_apply_plan

DEFAULT_REPORT = "reports/recipe_junk_filter_report.json"
DEFAULT_WORKERS = 8
# Bump when what _inspect records or how it decides changes, so old cached
# checks are thrown away.
CACHE_VERSION = 3
STRENGTHS = ("cautious", "balanced", "strong")
DEFAULT_STRENGTH = "cautious"
CACHE_NAME = "junk_scan_cache.json"

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_HOW_TO_RE = re.compile(r"^how\s+to\s+(?:make|cook)\b", re.IGNORECASE)

_LISTICLE_RE = re.compile(
    # "top/best" + number + food-plural → "Top 10 Desserts", "Best 25 Wines"
    r"\b(top|best)\b\s+\d+\b.*\b(recipes?|meals?|dishes?|desserts?|breakfasts?|lunches?|dinners?"
    r"|snacks?|drinks?|wines?|cocktails?|foods?|appetizers?|sides?|soups?|salads?)\b"
    # Starts with 2-3 digit number + food-plural or "ways to" → "32 Wines...", "21 Ways to..."
    r"|^\s*\d{2,3}\b.*\b(recipes?|meals?|dishes?|wines?|cocktails?|foods?|appetizers?"
    r"|ways\s+to|entrees?|dips?)\b",
    re.IGNORECASE,
)

_DIGEST_RE = re.compile(
    r"\b(friday\s*finds?|sunday\s*stuff|weekly\s*round\s*up|monthly\s*report"
    r"|weekend\s*reads?|favorites?\s*of\s*the\s*week|what\s*i\s*ate"
    r"|meal\s*plan|menu\s*plan|weekly\s*menu|holiday\s*guide)\b",
    re.IGNORECASE,
)

_HIGH_RISK_KEYWORDS = frozenset({
    "cleaning", "storing", "freezing", "pantry", "kitchen tools",
    "review", "giveaway", "shop", "store", "product", "gift", "unboxing",
    "news", "travel", "podcast", "interview",
    "night cream", "face mask", "skin care", "beauty", "diy",
    "detox water", "lose weight", "taste test", "clear winner",
    "foods to try", "things to eat", "we tried",
    "we tasted", "we tested", "we ranked", "we compared",
    "just launched", "just released",
    "is sabotaging", "start with these",
})

_UTILITY_SLUGS = frozenset({
    "privacy-policy", "contact", "about-us", "about", "login",
    "cart", "checkout", "terms", "terms-of-service", "disclaimer",
    "sitemap", "404", "page-not-found",
})

_BAD_INSTRUCTIONS = frozenset({
    "could not detect instructions",
    "instruction unavailable",
    "no instructions found",
    "instructions not available",
    "unable to extract instructions",
})

_FAILED_SCRAPE_NAMES = frozenset({
    "no recipe name found",
    "untitled recipe",
    "untitled",
    "recipe",
})

# Matches UUIDs / GUIDs used as recipe names (e.g. "a1b2c3d4-e5f6-...")
_GUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _classify_name(name: str, slug: str) -> tuple[str | None, str]:
    """Fast name/slug-based classification (no API calls needed)."""
    name_lower = name.lower().strip()
    slug_lower = slug.lower()

    # 0. Failed scrapes — placeholder names or GUIDs
    if not name_lower:
        return "failed_scrape", "Empty recipe name"
    if name_lower in _FAILED_SCRAPE_NAMES:
        return "failed_scrape", f"Placeholder name: '{name}'"
    if _GUID_RE.match(name_lower):
        return "failed_scrape", f"GUID as recipe name: '{name}'"

    # 1. How-to — match on name only; slug may retain the prefix after name
    #    normalization (e.g. slug "how-to-make-lemon-tea" for recipe "Lemon Tea"),
    #    which causes false positives on legitimate recipes.
    if _HOW_TO_RE.search(name_lower):
        return "how_to", "How-to article (not a recipe)"

    # 2. Listicle
    if _LISTICLE_RE.search(name_lower):
        return "listicle", "Listicle / roundup post"

    # 3. Digest
    if _DIGEST_RE.search(name_lower) or _DIGEST_RE.search(slug_lower.replace("-", " ")):
        return "digest", "Digest / weekly post"

    # 4. High-risk keywords
    for kw in _HIGH_RISK_KEYWORDS:
        if kw in name_lower:
            return "keyword", f"High-risk keyword: '{kw}'"

    # 5. Utility pages
    for util in _UTILITY_SLUGS:
        if util in slug_lower:
            return "utility", f"Utility page slug: '{util}'"

    return None, ""


def _classify_instructions(instructions_text: str) -> tuple[str | None, str]:
    """Check instruction content for placeholder/broken text."""
    if not instructions_text:
        return None, ""
    inst_lower = instructions_text.lower().strip()
    for bad in _BAD_INSTRUCTIONS:
        if bad in inst_lower:
            return "bad_instructions", f"Placeholder instruction text: '{bad}'"
    return None, ""


def _extract_instructions_text(recipe: dict[str, Any]) -> str:
    """Flatten recipeInstructions to a plain string for matching."""
    raw = recipe.get("recipeInstructions")
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("name") or ""))
        return " ".join(parts)
    return str(raw)


def _classify_bad_scrape(recipe: dict[str, Any]) -> tuple[str | None, str]:
    """Detect recipes where the scraper produced garbled data.

    Known patterns (discovered during Mealie→Tandoor migration):
      - Char-by-char HTML steps: scraper iterated an HTML string character by
        character instead of parsing it, producing hundreds of single-char steps
        like ``<``, ``p``, ``>``, ``r``, ``e`` …
      - All ingredients in one note: structured ingredient list collapsed into a
        single ingredient whose ``note`` field contains the entire ingredient
        block as unparsed text (often >200 chars).
    """
    steps = recipe.get("recipeInstructions") or []
    ingredients = recipe.get("recipeIngredient") or []

    if not isinstance(steps, list):
        return None, ""

    # --- char-by-char steps ---
    # Real recipes rarely exceed ~80 steps; >100 with majority single-char is
    # a dead giveaway of an iterated HTML string.
    if len(steps) > 50:
        single_char = sum(
            1 for s in steps
            if len(str(s.get("text", "") if isinstance(s, dict) else s).strip()) <= 1
        )
        ratio = single_char / len(steps)
        if ratio >= 0.8:
            return "bad_scrape", (
                f"Char-by-char steps ({len(steps)} steps, "
                f"{single_char} single-char = {ratio:.0%})"
            )

    # --- all ingredients in one note ---
    # Legit recipes with 1 ingredient have a short note; collapsed scrapes
    # stuff the entire ingredient list into a single note field.
    if len(ingredients) == 1:
        ing = ingredients[0]
        if isinstance(ing, dict):
            note = ing.get("note") or ""
            # A single ingredient note >200 chars almost certainly contains
            # the full unparsed ingredient list.
            if len(note) > 200:
                return "bad_scrape", (
                    f"All ingredients collapsed into one note "
                    f"({len(note)} chars)"
                )

    return None, ""


# ---------------------------------------------------------------------------
# Content: does this read like a recipe, or like a page about something else?
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z][a-z']*")

_FRACTIONS = "½¼¾⅓⅔⅛⅜⅝⅞"
_UNITS = (
    r"cups?|c\.|tbsps?|tbsp\.?|tablespoons?|tsps?|tsp\.?|teaspoons?|g|grams?|kg|kilograms?|oz|ounces?|lbs?|pounds?"
    r"|ml|millilit(?:er|re)s?|l|lit(?:er|re)s?|cloves?|cans?|tins?|pinch(?:es)?|dash(?:es)?|sticks?|slices?|sprigs?"
    r"|bunch(?:es)?|handfuls?|pints?|quarts?|packages?|pkgs?|jars?|heads?|stalks?|knobs?|inch(?:es)?|cm"
)
_QUANTITY_RE = re.compile(
    rf"^\s*(?:\d|[{_FRACTIONS}]|(?:a|an|one|two|three|four|five|six|half|a few|several)\s+(?:{_UNITS}|large|medium|small|whole)\b)"
    rf"|\b\d+(?:[./]\d+)?\s*(?:{_UNITS})\b",
    re.IGNORECASE,
)

# Words that only turn up when someone explains how to cook something.
_COOKING_TERMS = frozenset({
    "add", "bake", "baked", "baking", "beat", "blend", "blanch", "boil", "braise", "broil", "brown", "browned",
    "chill", "chop", "chopped", "combine", "cool", "cover", "crush", "dice", "diced", "drain", "drizzle",
    "fold", "fry", "fried", "garnish", "grate", "grease", "grill", "heat", "knead", "marinate", "mash",
    "melt", "mince", "minced", "mix", "oven", "pan", "peel", "pour", "preheat", "preheated", "puree",
    "reduce", "refrigerate", "rinse", "roast", "saute", "sauté", "season", "sear", "serve", "shred",
    "sift", "simmer", "skillet", "slice", "sliced", "soak", "spoon", "spread", "sprinkle", "steam", "stir",
    "strain", "toast", "toss", "transfer", "whisk", "bowl", "saucepan", "minutes", "tender", "golden",
    "batter", "dough", "degrees", "°f", "°c", "stirring", "roll", "cut", "squeeze", "layer",
    "pot", "stove", "added", "stirred", "simmered", "whisked", "kneaded", "lid", "boiling", "griddle", "wok",
    "steep", "shake", "muddle", "freeze", "microwave", "scoop", "brush", "wrap", "assemble", "press", "pipe",
    "overnight", "fridge", "refrigerator", "freezer", "blender", "shaker", "chilled",
})
# A step that starts with one of these is an instruction ("Stir in the rice").
_STEP_VERBS = frozenset(t for t in _COOKING_TERMS if not t.endswith(("ed", "ing")) and t not in {
    "oven", "pan", "skillet", "bowl", "saucepan", "minutes", "tender", "golden", "batter", "dough", "degrees", "°f", "°c",
    "pot", "stove", "lid", "griddle", "wok", "overnight", "fridge", "refrigerator", "freezer", "blender", "shaker",
}) | {"place", "put", "let", "bring", "remove", "make", "line", "set", "keep", "store", "arrange", "fill", "repeat", "using", "in", "on"}

# Common foods, so a list of them reads as ingredients and a list of headings
# or places ("Before", "Day 1: Florence") doesn't.
_FOOD_WORDS = frozenset("""
chicken beef pork lamb turkey duck fish salmon tuna cod shrimp prawn crab lobster clam mussel bacon sausage ham
salami chorizo prosciutto steak mince egg yolk white milk cream buttermilk butter ghee cheese cheddar parmesan
mozzarella ricotta feta brie provolone cotija gruyere yogurt flour cornmeal cornstarch sugar salt pepper oil vinegar
garlic onion shallot scallion leek ginger lemon lime orange apple pear peach plum cherry grape banana berry
strawberry blueberry raspberry cranberry mango pineapple coconut avocado tomato potato carrot celery spinach lettuce
romaine arugula kale cabbage broccoli cauliflower zucchini squash pumpkin corn pea bean lentil chickpea rice pasta
noodle spaghetti macaroni bread baguette tortilla bun roll crouton cracker oat granola honey maple syrup molasses
chocolate cocoa vanilla cinnamon nutmeg clove cumin paprika turmeric curry oregano basil thyme rosemary parsley
cilantro dill mint sage chili chile jalapeno chipotle mushroom bell cucumber olive caper nut almond walnut pecan
peanut cashew pistachio raisin date fig water stock broth wine beer rum vodka gin tequila whiskey bourbon brandy
vermouth soda juice tea coffee espresso ice mayonnaise mayo mustard ketchup soy tahini miso sauce salsa pesto yeast
powder gelatin marshmallow jam jelly pretzel candy sprinkle tofu tempeh quinoa couscous barley bulgur farro seed
sesame beet radish fennel artichoke asparagus eggplant okra herb spice zest seasoning dressing vinaigrette
""".split())

_FIRST_PERSON = frozenset({"i", "i'm", "i've", "i'd", "i'll", "me", "my", "mine", "we", "we're", "we've", "we'd", "us", "our", "ours"})

# Trips and travel. Counted in the text, not the title, so "Tuscan Chicken"
# or "Paris-Brest" mean nothing by themselves.
_TRAVEL_TERMS = frozenset({
    "trip", "travel", "traveled", "travelled", "traveling", "travelling", "vacation", "itinerary", "flight", "flew",
    "airport", "hotel", "hostel", "airbnb", "resort", "sightseeing", "visited", "visiting", "explore", "explored",
    "exploring", "tour", "toured", "tourist", "tourists", "museum", "museums", "beach", "beaches", "cathedral",
    "journey", "passport", "luggage", "train", "drove", "road", "honeymoon", "getaway", "destination", "landed",
    "countryside", "village", "piazza", "market", "markets", "stayed", "checked", "guide", "days", "week",
})
_TRAVEL_STRONG = frozenset({
    "trip", "travel", "traveled", "travelled", "traveling", "travelling", "vacation", "itinerary", "flight", "flew",
    "airport", "hotel", "hostel", "airbnb", "resort", "sightseeing", "visited", "tourist", "tourists", "passport",
    "luggage", "honeymoon", "getaway", "destination", "museum", "museums", "cathedral",
})

# About, contact and policy pages: what they say about themselves.
_PAGE_TITLE_RE = re.compile(
    r"^\s*(?:about(?:\s+(?:me|us|the\s+\w+|this\s+(?:blog|site)))?|meet\s+(?:the\s+)?\w+|my\s+story|our\s+story|who\s+(?:i|we)\s+am|"
    r"contact(?:\s+(?:me|us))?|get\s+in\s+touch|work\s+with\s+(?:me|us)|advertise(?:\s+with\s+(?:me|us))?|press|media\s+kit|"
    r"faqs?|frequently\s+asked\s+questions|privacy(?:\s+policy)?|cookie\s+policy|terms(?:\s+(?:of\s+(?:use|service)|and\s+conditions))?|"
    r"disclaimer|disclosure(?:\s+policy)?|affiliate\s+disclosure|accessibility(?:\s+statement)?|subscribe|newsletter|shop|"
    r"start\s+here|welcome)\s*[!.]*\s*$",
    re.IGNORECASE,
)
_PAGE_PHRASES = (
    "about me", "about us", "my name is", "welcome to my", "welcome to our", "i started this blog", "started this blog",
    "this blog", "contact me", "contact us", "get in touch", "email me", "send me an email", "drop me a line",
    "fill out the form", "work with me", "brand partnerships", "sponsored", "advertising", "media kit",
    "privacy policy", "personal information", "cookies", "third parties", "third-party", "terms of service",
    "affiliate links", "earn a commission", "amazon associate", "subscribe", "newsletter", "follow me", "instagram",
    "pinterest", "facebook", "all rights reserved", "copyright", "the information we collect",
)


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower().replace("’", "'"))


def _is_food(word: str) -> bool:
    if word in _FOOD_WORDS:
        return True
    for ending in ("ies", "es", "s"):
        if word.endswith(ending):
            stem = word[: -len(ending)] + ("y" if ending == "ies" else "")
            if stem in _FOOD_WORDS:
                return True
    return False


def _ingredient_text(ingredient: Any) -> str:
    if isinstance(ingredient, str):
        return ingredient
    if not isinstance(ingredient, dict):
        return ""
    parts = [str(ingredient.get(k) or "") for k in ("originalText", "display", "note")]
    food = ingredient.get("food")
    if isinstance(food, dict) and food.get("name"):
        parts.append(str(food["name"]))
    return " ".join(p for p in parts if p).strip()


def _measured(ingredient: Any) -> bool:
    """Whether an ingredient line has an amount or unit: "2 cups flour", parsed or not."""
    if isinstance(ingredient, dict):
        try:
            if float(ingredient.get("quantity") or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
        unit = ingredient.get("unit")
        if isinstance(unit, dict) and unit.get("name"):
            return True
    return bool(_QUANTITY_RE.search(_ingredient_text(ingredient)))


def _step_texts(recipe: dict[str, Any]) -> list[str]:
    raw = recipe.get("recipeInstructions")
    if isinstance(raw, str):
        return [line for line in raw.splitlines() if line.strip()]
    out = []
    for item in raw or []:
        text = item if isinstance(item, str) else str((item or {}).get("text") or "") if isinstance(item, dict) else ""
        if text.strip():
            out.append(text.strip())
    return out


def _has_time_or_yield(recipe: dict[str, Any]) -> bool:
    for key in ("recipeYield", "totalTime", "prepTime", "cookTime", "performTime"):
        value = recipe.get(key)
        if value not in (None, "", 0, "0"):
            return True
    for key in ("recipeServings", "recipeYieldQuantity"):
        try:
            if float(recipe.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _content_facts(recipe: dict[str, Any]) -> dict[str, Any]:
    """Numbers about the content that tell a recipe from an about page or a trip post."""
    ingredients = [i for i in recipe.get("recipeIngredient") or [] if _ingredient_text(i)]
    steps = _step_texts(recipe)
    step_words = _words(" ".join(steps))
    body_words = _words(" ".join([str(recipe.get("description") or ""), *steps, *(_ingredient_text(i) for i in ingredients)]))
    short_lines = sum(1 for i in ingredients if len(_words(_ingredient_text(i))) <= 8)
    food_lines = sum(1 for i in ingredients if any(_is_food(w) for w in _words(_ingredient_text(i))))
    leading = sum(1 for step in steps if (_words(step)[:1] or [""])[0] in _STEP_VERBS)
    body = " ".join(body_words)
    return {
        "measured": sum(1 for i in ingredients if _measured(i)),
        # "Steep 1 cup grounds in 4 cups water": amounts written into the steps.
        "measured_steps": sum(1 for step in steps if _QUANTITY_RE.search(step)),
        "ingredient_lines": len(ingredients),
        "short_lines": short_lines,
        "food_lines": food_lines,
        "steps": len(steps),
        "step_words": len(step_words),
        "cooking_terms": len({w for w in step_words if w in _COOKING_TERMS}),
        "leading_verbs": leading,
        "time_or_yield": _has_time_or_yield(recipe),
        "first_person": sum(1 for w in body_words if w in _FIRST_PERSON),
        "body_words": len(body_words),
        "travel_terms": sorted({w for w in body_words if w in _TRAVEL_TERMS}),
        "page_phrases": sorted({p for p in _PAGE_PHRASES if p in body}),
    }


def _structure(facts: dict[str, Any]) -> int:
    """How much reads like a recipe: 0 is none, 4 or more is plainly a recipe."""
    score = 0
    if facts["measured"] >= 2 or (facts["measured"] and facts["measured"] >= facts["ingredient_lines"] / 2):
        score += 2
    if facts["cooking_terms"] >= 3:
        score += 2
    elif facts["cooking_terms"]:
        score += 1
    if facts["steps"] and facts["leading_verbs"] / facts["steps"] >= 0.3:
        score += 1
    if facts["time_or_yield"]:
        score += 1
    if _ingredient_list(facts):
        score += 1
    return score


def _ingredient_list(facts: dict[str, Any]) -> bool:
    """Three or more short lines, most naming a food: a list of ingredients, not headings or paragraphs."""
    return (
        facts["short_lines"] >= 3
        and facts["short_lines"] >= 0.6 * facts["ingredient_lines"]
        and facts.get("food_lines", 0) >= max(2, 0.5 * facts["short_lines"])
    )


def _protected(facts: dict[str, Any]) -> bool:
    """Ingredients and cooking steps: a recipe, whatever else it says."""
    if _structure(facts) >= 4:
        return True
    return (facts["measured"] > 0 and facts["cooking_terms"] >= 2) or (_ingredient_list(facts) and facts["cooking_terms"] >= 2)


def _no_recipe(facts: dict[str, Any]) -> bool:
    """Prose with no amounts, no cooking steps and no servings or times: an article, not a recipe."""
    all_food = facts.get("food_lines", 0) >= 2 and facts["food_lines"] == facts["ingredient_lines"]
    return (
        not facts["measured"]
        and not facts.get("measured_steps")
        and not all_food
        and not facts["time_or_yield"]
        and not facts["leading_verbs"]
        and facts["cooking_terms"] <= 2
        and facts["body_words"] >= 20
        and facts["steps"] > 0
        and facts["step_words"] / facts["steps"] >= 10
    )


def _classify_content(facts: dict[str, Any] | None, name: str, slug: str) -> tuple[str | None, str]:
    """About/contact/policy pages and trip or story posts, from what they say."""
    if not facts or _protected(facts):
        return None, ""
    title = name.strip()
    slug_words = slug.lower().replace("-", " ").strip()
    per_100 = 100 / max(facts["body_words"], 1)
    first_person = facts["first_person"] * per_100
    travel = set(facts["travel_terms"])
    strong_travel = travel & _TRAVEL_STRONG

    if _PAGE_TITLE_RE.match(title) or _PAGE_TITLE_RE.match(slug_words):
        return "about_page", f"Looks like a site page ('{title or slug}'), not a recipe"
    if len(facts["page_phrases"]) >= 2:
        shown = ", ".join(f"'{p}'" for p in facts["page_phrases"][:3])
        return "about_page", f"Reads like an about, contact or policy page ({shown})"
    if len(strong_travel) >= 2 or (strong_travel and len(travel) >= 3 and first_person >= 2):
        shown = ", ".join(f"'{w}'" for w in sorted(strong_travel or travel)[:3])
        return "travel_post", f"Reads like a trip write-up ({shown}), with no recipe steps"
    if facts["body_words"] >= 40 and first_person >= 3 and facts["cooking_terms"] <= 2 and not facts["measured"]:
        return "story_post", "Reads like a story, with no measured ingredients or cooking steps"
    if _no_recipe(facts):
        return "no_recipe", "No amounts, cooking steps, servings or times; reads like an article"
    return None, ""


# Title and slug matches that Strong deletes when the page has almost no recipe in it.
_NAME_CODES_STRONG = {"how_to", "listicle", "digest", "keyword", "utility", "failed_scrape"}


def _auto_delete(strength: str, *, content_code: str | None, name_code: str | None,
                 instruction_code: str | None, facts: dict[str, Any] | None) -> bool:
    """Whether *strength* deletes a page with some content on its own (it's reviewed otherwise)."""
    if strength == "cautious" or not facts or _protected(facts):
        return False
    structure = _structure(facts)
    if content_code == "no_recipe":
        # Only the prose itself to go on, so Balanced wants no cooking words at
        # all, and a list of foods (a lazy recipe, perhaps) is always reviewed.
        if _ingredient_list(facts):
            return False
        return facts["cooking_terms"] == 0 or strength == "strong"
    if content_code:
        if strength == "balanced":
            return structure == 0 or (content_code == "about_page" and structure <= 1 and not facts["measured"])
        return structure <= 2 and not facts["measured"]
    if strength == "strong" and (name_code in _NAME_CODES_STRONG or instruction_code):
        return structure <= 1 and not facts["measured"]
    return False


def _inspect(full: dict[str, Any]) -> dict[str, Any]:
    """The facts about one full recipe that junk detection needs (cacheable)."""
    # Mealie's "1 Cup Flour" and markdown step stand in for nothing.
    full = without_placeholders(full)
    instructions = _extract_instructions_text(full).strip()
    ingredients = full.get("recipeIngredient") or []
    instruction_code, instruction_reason = _classify_instructions(instructions)
    scrape_code, scrape_reason = _classify_bad_scrape(full)
    return {
        "name": str(full.get("name") or "").strip(),
        "has_ingredients": any(
            isinstance(ing, dict) and any(ing.get(k) for k in ("note", "originalText", "food", "referencedRecipe"))
            or isinstance(ing, str) and ing.strip()
            for ing in ingredients
        ),
        "has_instructions": bool(instructions),
        "instruction_code": instruction_code or "",
        "instruction_reason": instruction_reason,
        "scrape_code": scrape_code or "",
        "scrape_reason": scrape_reason,
        "content": _content_facts(full),
    }


def _stamp(recipe: dict[str, Any]) -> str:
    return str(recipe.get("updatedAt") or recipe.get("dateUpdated") or "")


def default_cache_path() -> Path:
    base = env_or_config("CHECKPOINT_DIR", "maintenance.checkpoint_dir", "cache/maintenance")
    return resolve_repo_path(str(base)) / CACHE_NAME


def _read_cache(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {}
    recipes = data.get("recipes")
    return recipes if isinstance(recipes, dict) else {}


def _write_cache(path: Path, recipes: dict[str, dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": CACHE_VERSION, "recipes": recipes}), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        print(f"[warn] Couldn't save the scan cache ({exc}); the next scan checks every recipe again.", flush=True)


@dataclass
class JunkAction:
    slug: str
    name: str
    reason_code: str
    reason: str


class RecipeJunkFilter:
    def __init__(
        self,
        client: MealieApiClient,
        *,
        dry_run: bool = True,
        apply: bool = False,
        filter_reason: str | None = None,
        report_file: Path | str = DEFAULT_REPORT,
        workers: int = DEFAULT_WORKERS,
        cache_path: Path | str | None = None,
        archive: RecipeArchive | None = None,
        strength: str = DEFAULT_STRENGTH,
    ) -> None:
        if strength not in STRENGTHS:
            raise ValueError(f"Unknown strength '{strength}'. Use one of: {', '.join(STRENGTHS)}.")
        self.strength = strength
        self.client = client
        self.dry_run = dry_run
        self.apply = apply
        self.filter_reason = filter_reason
        self.report_file = Path(report_file)
        self.workers = max(1, int(workers))
        self.cache_path = Path(cache_path) if cache_path else None
        # Where a copy of each deleted recipe goes, so it can be restored.
        self.archive = archive if archive is not None else RecipeArchive(client=client)

    def _inspect_all(self, recipes: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], int]:
        """Facts per slug, reusing cached checks for recipes that haven't changed.

        Opening every recipe is the slow part (one request each), so unchanged
        recipes come from the cache and the rest are fetched in parallel.
        Returns (facts by slug, number of recipes that couldn't be read).
        """
        cache = _read_cache(self.cache_path) if self.cache_path else {}
        facts: dict[str, dict[str, Any]] = {}
        todo: list[str] = []
        for recipe in recipes:
            slug = str(recipe.get("slug") or "")
            cached = cache.get(slug)
            if cached and _stamp(recipe) and cached.get("updated") == _stamp(recipe):
                facts[slug] = cached
            else:
                todo.append(slug)
        if facts:
            print(f"[info] {len(facts)} recipe(s) unchanged since the last scan; opening {len(todo)}.", flush=True)

        progress = Progress("Checking recipes for pages that aren't recipes", len(recipes))
        progress.advance(len(facts))
        failed = 0
        stamps = {str(r.get("slug") or ""): _stamp(r) for r in recipes}

        def fetch(slug: str) -> tuple[str, dict[str, Any] | None, str]:
            try:
                return slug, _inspect(self.client.get_recipe(slug)), ""
            except Exception as exc:
                return slug, None, str(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            for slug, result, error in pool.map(fetch, todo):
                progress.advance()
                if result is None:
                    failed += 1
                    print(f"[error] Could not inspect {slug}: {error}", flush=True)
                    continue
                facts[slug] = {**result, "updated": stamps.get(slug, "")}

        if self.cache_path:
            _write_cache(self.cache_path, {slug: f for slug, f in facts.items() if f.get("updated")})
        return facts, failed

    def run(self) -> dict[str, Any]:
        executable = self.apply and not self.dry_run

        print("[start] Fetching all recipes from API ...", flush=True)
        recipes = self.client.get_recipes()
        total = len(recipes)

        # Cautious (the default) deletes only pages with no ingredients and no
        # usable steps; stronger levels also delete pages whose content reads
        # like anything but a recipe. The rest that looks off goes to review.
        actions: list[JunkAction] = []
        review_candidates: list[dict[str, str]] = []
        facts, scan_failed = self._inspect_all(recipes)
        print(f"[info] Strength: {self.strength}.", flush=True)
        for recipe in recipes:
            slug = str(recipe.get("slug") or "")
            fact = facts.get(slug)
            if fact is None:
                continue
            name = fact["name"]
            name_code, name_reason = _classify_name(name, slug)
            content = fact.get("content")
            content_code, content_reason = _classify_content(content, name, slug)
            instructions = fact["has_instructions"]
            has_ingredients = fact["has_ingredients"]
            instruction_code, instruction_reason = fact["instruction_code"] or None, fact["instruction_reason"]
            scrape_code, scrape_reason = fact["scrape_code"] or None, fact["scrape_reason"]
            usable_instructions = instructions and not instruction_code
            if not has_ingredients and not usable_instructions:
                # Nothing of a recipe left: deleted at every strength.
                reason_code = name_code or instruction_code or "no_ingredients"
                reason = name_reason or instruction_reason or "No ingredients or usable instructions"
            elif _auto_delete(self.strength, content_code=content_code, name_code=name_code,
                              instruction_code=instruction_code, facts=content):
                reason_code = content_code or name_code or instruction_code or ""
                reason = content_reason or name_reason or instruction_reason
            else:
                if name_code or scrape_code or instruction_code or content_code:
                    review_candidates.append({"slug": slug, "name": name,
                                              "reason": content_reason or name_reason or scrape_reason or instruction_reason})
                continue
            if not self.filter_reason or self.filter_reason == reason_code:
                actions.append(JunkAction(slug, name, reason_code, reason))

        by_reason: dict[str, int] = {}
        for a in actions:
            by_reason[a.reason_code] = by_reason.get(a.reason_code, 0) + 1

        print(
            f"[start] {total} recipes scanned -> {len(actions)} junk recipes detected",
            flush=True,
        )
        for code, count in sorted(by_reason.items()):
            print(f"  {code}: {count}", flush=True)

        # With a reviewed plan, delete exactly the approved slugs, drawn from
        # detected junk and from review candidates the user chose to remove.
        plan = load_apply_plan("junk")
        skipped: list[JunkAction] = []
        if plan is not None:
            approved = {str(slug) for slug in plan.get("delete") or []}
            reviewed = [
                JunkAction(item["slug"], item["name"], "review", item["reason"])
                for item in review_candidates
                if item["slug"] in approved and item["slug"] not in {a.slug for a in actions}
            ]
            skipped = [a for a in actions if a.slug not in approved]
            actions = [a for a in actions if a.slug in approved] + reviewed

        action_log: list[dict] = []
        deleted = 0
        failed = scan_failed

        for idx, action in enumerate(actions, 1):
            entry: dict[str, Any] = {
                "slug": action.slug,
                "name": action.name,
                "reason_code": action.reason_code,
                "reason": action.reason,
            }
            if executable:
                # Keep a copy first; without one, the recipe stays.
                try:
                    copy = self.archive.save(action.slug, reason=action.reason, reason_code=action.reason_code)
                except CopyError as exc:
                    entry["status"] = "error"
                    entry["error"] = f"Not deleted: {exc}"
                    failed += 1
                    print(f"[error] {action.slug}: not deleted, because {exc}", flush=True)
                    action_log.append(entry)
                    continue
                try:
                    self.client.delete_recipe(action.slug)
                    entry["status"] = "deleted"
                    entry["copy_id"] = copy["id"]
                    deleted += 1
                    print(f"[ok] {idx}/{len(actions)} {action.slug} reason={action.reason_code} (copy kept in Recently deleted)", flush=True)
                except Exception as exc:
                    self.archive.forget(copy["id"])
                    entry["status"] = "error"
                    entry["error"] = str(exc)
                    failed += 1
                    print(f"[error] {action.slug}: {exc}", flush=True)
            else:
                entry["status"] = "planned"
                print(f"[plan] {action.slug}: '{action.name}' — {action.reason}", flush=True)
            action_log.append(entry)

        for action in skipped:
            action_log.append({
                "slug": action.slug, "name": action.name, "reason_code": action.reason_code,
                "reason": action.reason, "status": "skipped",
            })
        logged = {entry["slug"] for entry in action_log}
        emit_items("recipe_delete", [
            {
                "slug": entry["slug"],
                "name": entry["name"],
                "group": "review" if entry["reason_code"] == "review" else "junk",
                "reason_code": entry["reason_code"],
                "reason": entry["reason"],
                "status": {"deleted": "applied"}.get(entry["status"], entry["status"]),
                **({"error": entry["error"]} if entry.get("error") else {}),
            }
            for entry in action_log
        ] + [
            # Not deleted without approval: shown so a person can decide.
            {"slug": item["slug"], "name": item["name"], "group": "review", "reason_code": "review",
             "reason": item["reason"], "status": "planned" if not executable else "skipped"}
            for item in review_candidates
            if item["slug"] not in logged
        ])

        report: dict[str, Any] = {
            "summary": {
                "total_recipes": total,
                "junk_found": len(actions),
                "by_reason": by_reason,
                "deleted": deleted,
                "failed": failed,
                "review_candidates": len(review_candidates),
                "mode": "apply" if executable else "audit",
                "strength": self.strength,
            },
            "actions": action_log,
            "review_candidates": review_candidates,
        }

        self.report_file.parent.mkdir(parents=True, exist_ok=True)
        self.report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        mode = "apply" if executable else "audit"
        top_reason = max(by_reason, key=by_reason.get) if by_reason else "none"
        print(
            f"[done] {len(actions)} junk recipe(s) found out of {total} — "
            f"top reason: {top_reason}, {deleted} deleted ({mode} mode)",
            flush=True,
        )
        emit_summary({
            "__title__": "Junk Filter",
            "Total Recipes": total,
            "Junk Found": len(actions),
            "Review Candidates": len(review_candidates),
            "Top Reason": top_reason,
            "Strength": self.strength.capitalize(),
            "Deleted": deleted,
            "Failed": failed,
            "Mode": mode,
        })
        return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect and remove junk recipes from Mealie.")
    parser.add_argument("--apply", action="store_true", help="Delete junk recipes from Mealie.")
    parser.add_argument(
        "--reason",
        choices=["how_to", "listicle", "digest", "keyword", "utility", "bad_instructions", "failed_scrape", "no_ingredients",
                 "bad_scrape", "about_page", "travel_post", "story_post", "no_recipe"],
        default=None,
        help="Only process recipes matching this specific junk category.",
    )
    parser.add_argument(
        "--strength",
        choices=list(STRENGTHS),
        default=DEFAULT_STRENGTH,
        help="How much evidence deletes a page on its own; the rest goes to review.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dry_run = bool(env_or_config("DRY_RUN", "runtime.dry_run", False, to_bool))
    if dry_run:
        print("[start] runtime.dry_run=true (writes disabled; planning only).", flush=True)
    junk_filter = RecipeJunkFilter(
        MealieApiClient(
            base_url=resolve_mealie_url(),
            api_key=resolve_mealie_api_key(required=True),
            timeout_seconds=60,
            retries=3,
            backoff_seconds=0.4,
        ),
        dry_run=dry_run,
        apply=bool(args.apply),
        filter_reason=args.reason,
        report_file=resolve_repo_path(DEFAULT_REPORT),
        cache_path=default_cache_path(),
        strength=args.strength,
    )
    report = junk_filter.run()
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
