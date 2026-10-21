"""Parse ingredient lines inside CookDex instead of asking Mealie for each recipe.

Mealie's "nlp" parser runs the ``ingredient-parser-nlp`` library and then
matches the parsed food and unit against every food and unit in its database.
Each parse request builds a fresh parser, so Mealie reloads its whole food and
unit tables for every recipe. On a large library that reload, not the parsing,
is what makes a request take seconds.

This module does the same work locally: the same library (pinned to the
version Mealie ships), the same mapping from the library's result to Mealie's
quantity/unit/food/note, and the same food and unit matching, against foods
and units loaded from Mealie once per run.  ``parse`` returns the same shape
as Mealie's ``POST /parser/ingredients`` so the rest of the ingredient parser
handles both alike.

Ported from Mealie v3.29 (``mealie/services/parser_services``), AGPL-3.0.
Mealie 3.28 runs ingredient-parser-nlp 2.7.0 and made a second measurement
("1 (14 oz) can") a substitution note; results otherwise match 3.28 too.
"""

from __future__ import annotations

import re
import string
import uuid
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import zip_longest
from typing import Any, Iterable

from rapidfuzz import fuzz, process
from text_unidecode import unidecode

# Mealie's thresholds (ABCIngredientParser.food/unit_fuzzy_match_threshold).
FOOD_FUZZY_MATCH_THRESHOLD = 85
UNIT_FUZZY_MATCH_THRESHOLD = 70
# RecipeIngredient rounds float quantities to this many places.
INGREDIENT_QTY_PRECISION = 3
MAX_INGREDIENT_DENOMINATOR = 32

# Mealie's SqlAlchemyBase.normalize: punctuation other than quotes becomes spaces.
_NORMALIZE_PUNCTUATION = string.punctuation.replace("'", "").replace('"', "")
_NORMALIZE_TABLE = str.maketrans(_NORMALIZE_PUNCTUATION, " " * len(_NORMALIZE_PUNCTUATION))

_SUPERSCRIPT = dict(zip("1234567890", "¹²³⁴⁵⁶⁷⁸⁹⁰"))
_SUBSCRIPT = dict(zip("1234567890", "₁₂₃₄₅₆₇₈₉₀"))

_VULGAR_FRACTIONS = {
    "¼": "1/4", "½": "1/2", "¾": "3/4", "⅐": "1/7", "⅑": "1/9", "⅒": "1/10", "⅓": "1/3", "⅔": "2/3",
    "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5", "⅙": "1/6", "⅚": "5/6", "⅛": "1/8", "⅜": "3/8",
    "⅝": "5/8", "⅞": "7/8",
}
_MIXED_FRACTION_RE = re.compile(r"(\d+)\s+(\d+)/(\d+)")
_FRACTION_RE = re.compile(r"(\d+)/(\d+)")
_NUMBER_RE = re.compile(r"\d+(\.\d+)?")


class LocalParserUnavailable(RuntimeError):
    """The ingredient-parser-nlp library isn't installed."""


def normalize(value: str) -> str:
    return unidecode(value).translate(_NORMALIZE_TABLE).lower().strip()[:255]


def extract_quantity_from_string(source: str) -> float:
    """Mealie's parser_utils.extract_quantity_from_string, quantity only."""
    source = source.strip()
    if not source:
        return 0
    for vulgar, regular in _VULGAR_FRACTIONS.items():
        source = source.replace(vulgar, f" {regular}").strip()
    try:
        if match := _MIXED_FRACTION_RE.search(source):
            return int(match.group(1)) + float(Fraction(int(match.group(2)), int(match.group(3))))
        if match := _FRACTION_RE.search(source):
            return float(Fraction(int(match.group(1)), int(match.group(2))))
        if match := _NUMBER_RE.search(source):
            return float(match.group())
    except ZeroDivisionError:
        pass
    return 0


def _find_match(value: str, store: dict[str, dict[str, Any]], threshold: int) -> dict[str, Any] | None:
    """Mealie's services.matching.find_match: exact key, then the closest fuzzy key."""
    if value in store:
        return store[value]
    result = process.extractOne(value, store.keys(), scorer=fuzz.ratio, score_cutoff=threshold)
    if result is None:
        return None
    return store[result[0]]


def _names(entity: dict[str, Any], *keys: str) -> list[str]:
    names = [str(entity.get(key) or "") for key in keys]
    names += [str(alias.get("name") or "") for alias in entity.get("aliases") or [] if isinstance(alias, dict)]
    return [name for name in names if name]


class FoodUnitMatcher:
    """Mealie's DataMatcher over foods and units fetched once from the API."""

    def __init__(self, foods: Iterable[dict[str, Any]], units: Iterable[dict[str, Any]]) -> None:
        self.foods_by_alias: dict[str, dict[str, Any]] = {}
        self.units_by_alias: dict[str, dict[str, Any]] = {}
        self.units: list[dict[str, Any]] = [unit for unit in units if isinstance(unit, dict) and unit.get("id")]
        for food in foods:
            self.add_food(food)
        for unit in self.units:
            for name in _names(unit, "name", "pluralName", "abbreviation", "pluralAbbreviation"):
                self.units_by_alias[normalize(name)] = unit

    def add_food(self, food: dict[str, Any]) -> None:
        if not isinstance(food, dict) or not food.get("id"):
            return
        for name in _names(food, "name", "pluralName"):
            self.foods_by_alias[normalize(name)] = food

    def find_food(self, name: str) -> dict[str, Any] | None:
        return _find_match(normalize(name), self.foods_by_alias, FOOD_FUZZY_MATCH_THRESHOLD)

    def find_unit(self, name: str) -> dict[str, Any] | None:
        return _find_match(normalize(name), self.units_by_alias, UNIT_FUZZY_MATCH_THRESHOLD)

    def custom_units(self) -> dict[str, str]:
        """The ``custom_units`` Mealie hands the library: plural (or name) -> name."""
        units: dict[str, str] = {}
        for unit in self.units:
            name = str(unit.get("name") or "")
            if name:
                units[str(unit.get("pluralName") or name)] = name
            abbreviation = str(unit.get("abbreviation") or "")
            if abbreviation:
                units[str(unit.get("pluralAbbreviation") or abbreviation)] = abbreviation
        return units


@dataclass
class _Part:
    qty: float = 0
    unit: str = ""
    food: str = ""
    extra_amounts: list[Any] = field(default_factory=list)
    qty_conf: float = 0
    unit_conf: float = 0
    food_conf: float = 0

    @property
    def avg_conf(self) -> float:
        return (self.qty_conf + self.unit_conf + self.food_conf) / 3


def _round_qty(value: float) -> float:
    return round(float(value), INGREDIENT_QTY_PRECISION)


def _display_fraction(value: Fraction) -> str:
    return (
        "".join(_SUPERSCRIPT[c] for c in str(value.numerator))
        + "/"
        + "".join(_SUBSCRIPT[c] for c in str(value.denominator))
    )


def _display_quantity(quantity: float) -> str:
    qty = Fraction(quantity).limit_denominator(MAX_INGREDIENT_DENOMINATOR)
    if qty.denominator == 1:
        return str(qty.numerator)
    if qty.numerator <= qty.denominator:
        return _display_fraction(qty)
    whole = qty.numerator // qty.denominator
    return f"{whole} {_display_fraction(qty - whole)}"


def _display(quantity: float, unit: str, food: str, note: str | None) -> str:
    """Mealie's display text for an unmatched ingredient (new units show fractions)."""
    parts: list[str] = []
    if quantity:
        parts.append(_display_quantity(quantity))
        if unit:
            parts.append(unit)
    if food:
        parts.append(food)
    if note:
        parts.append(note)
    return " ".join(parts).strip()


class LocalIngredientParser:
    """Parses lines the way Mealie's "nlp" parser does, without calling Mealie."""

    def __init__(self, matcher: FoodUnitMatcher) -> None:
        try:
            from ingredient_parser import parse_ingredient
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise LocalParserUnavailable(
                "the ingredient-parser-nlp package isn't installed, so CookDex can't parse locally"
            ) from exc
        self._parse_ingredient = parse_ingredient
        self.matcher = matcher
        self._custom_units = matcher.custom_units()

    @classmethod
    def from_client(cls, client: Any) -> "LocalIngredientParser":
        return cls(FoodUnitMatcher(client.list_foods(), client.list_units()))

    def parse(self, lines: list[str]) -> list[dict[str, Any]]:
        return [self.parse_one(line) for line in lines]

    def parse_one(self, line: str) -> dict[str, Any]:
        return self._convert(self._parse_ingredient(line, custom_units=self._custom_units))

    # -- NLPParser._convert_ingredient --------------------------------------

    @staticmethod
    def _quantity(amount: Any) -> tuple[float, float]:
        confidence = amount.confidence
        if isinstance(amount.quantity, str):
            return extract_quantity_from_string(amount.quantity), confidence
        try:
            return float(amount.quantity), confidence
        except (TypeError, ValueError):
            return 0, 0

    @staticmethod
    def _note(parsed: Any, extra_amounts: list[Any]) -> tuple[str, float]:
        texts: list[str] = []
        confidences: list[float] = []
        for part in (parsed.size, parsed.preparation, parsed.comment, parsed.purpose):
            if part:
                texts.append(part.text)
                confidences.append(part.confidence)
        confidence = sum(confidences) / len(confidences) if confidences else 0
        note = ", ".join(texts).replace("(", "").replace(")", "")
        if extra_amounts:
            amounts = "(" + ", ".join(amount.text for amount in extra_amounts) + ")"
            note = " ".join(filter(None, [amounts, note]))
        return note, confidence

    def _convert(self, parsed: Any) -> dict[str, Any]:
        from ingredient_parser.dataclasses import CompositeIngredientAmount

        parts: list[_Part] = []
        for amount, name in zip_longest(parsed.amount, parsed.name, fillvalue=None):
            if amount and not name and parts:
                # Mealie 3.29+: an amount with no name is another measurement of the
                # main ingredient (the "(42g)" in "3 tablespoons (42g) water"), not
                # an alternative. Mealie 3.28 made it a substitution note instead.
                if isinstance(amount, CompositeIngredientAmount):
                    parts[0].extra_amounts.extend(amount.amounts)
                else:
                    parts[0].extra_amounts.append(amount)
                continue
            part = _Part()
            if amount:
                if isinstance(amount, CompositeIngredientAmount):
                    part.extra_amounts = list(amount.amounts[1:])
                    amount = amount.amounts[0]
                part.qty, part.qty_conf = self._quantity(amount)
                part.unit = str(amount.unit) if amount.unit else ""
                part.unit_conf = amount.confidence
            if name:
                part.food = name.text
                part.food_conf = name.confidence
            parts.append(part)

        note, note_conf = self._note(parsed, parts[0].extra_amounts if parts else [])
        if not parts:
            parts.append(_Part())

        primary = parts[0]
        confidences: list[float] = []
        if primary.qty:
            confidences.append(primary.qty_conf)
        if primary.unit:
            confidences.append(primary.unit_conf)
        if primary.food:
            confidences.append(primary.food_conf)
        if note:
            confidences.append(note_conf)
        confidences.extend(part.avg_conf for part in parts[1:])

        ingredient: dict[str, Any] = {
            "quantity": _round_qty(primary.qty),
            "unit": {"name": primary.unit} if primary.unit else None,
            "food": {"name": primary.food} if primary.food else None,
            "note": note,
            "originalText": parsed.sentence,
            "referenceId": str(uuid.uuid4()),
        }
        substitutions = self._substitutions(parts[1:])
        if substitutions:
            ingredient["substitutions"] = substitutions
        self._match(ingredient)

        return {
            "input": parsed.sentence,
            "confidence": {
                "average": (sum(confidences) / len(confidences)) if confidences else 0,
                "quantity": _round_qty(primary.qty_conf),
                "unit": primary.unit_conf,
                "food": primary.food_conf,
                "comment": note_conf,
            },
            "ingredient": ingredient,
        }

    def _substitutions(self, extras: list[_Part]) -> list[dict[str, Any]]:
        """NLPParser._convert_extra_ingredients: "stock or broth" alternatives."""
        substitutions: list[dict[str, Any]] = []
        for part in extras:
            note = ", ".join(f"and {amount.text}" for amount in part.extra_amounts) or None
            qty = _round_qty(part.qty)
            if part.food and not qty and not part.unit and not note:
                food = self.matcher.find_food(part.food)
                if food is not None:
                    substitutions.append({"substituteFoodId": str(food["id"]), "note": None})
                    continue
            display = _display(qty, part.unit, part.food, note)
            if display:
                substitutions.append({"substituteFoodId": None, "note": display})
        return substitutions

    def _match(self, ingredient: dict[str, Any]) -> None:
        """ABCIngredientParser.find_ingredient_match."""
        food, unit = ingredient["food"], ingredient["unit"]
        if food and (match := self.matcher.find_food(food["name"])):
            ingredient["food"] = food = match
        if unit and (match := self.matcher.find_unit(unit["name"])):
            ingredient["unit"] = unit = match

        # The library may have split a food into a unit and a food.
        if food and unit and not food.get("id") and not unit.get("id"):
            if match := self.matcher.find_food(f"{unit['name']} {food['name']}"):
                ingredient["food"] = match
                ingredient["unit"] = None
