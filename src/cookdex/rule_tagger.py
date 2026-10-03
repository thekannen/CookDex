"""Rule-based recipe tagger — no LLM required.

Assigns tags, categories, and tools to Mealie recipes using configurable
regex rules. Every rule type (text, ingredient, tool) works in both modes:

API mode (default)
    Matches rules in memory and saves each changed recipe once. Ingredient
    and tool rules read each recipe's foods and steps, cached between runs
    (see recipe_text_cache), so only changed recipes are opened again.

DB mode (whenever the database is connected, or ``--use-db``)
    Runs every rule as a SQL query and links in one transaction. Much faster
    on large libraries.

In both modes dry-run is the default; use ``--apply`` to write changes.

Usage
-----
    # Preview text-tag/category matches via API (no DB required)
    python -m cookdex.rule_tagger

    # Apply text tags and categories via API
    python -m cookdex.rule_tagger --apply

    # Apply all rules via DB (ingredient + text + tool, tags + categories)
    python -m cookdex.rule_tagger --apply --use-db

    # Custom rules file
    python -m cookdex.rule_tagger --apply --use-db --config /path/to/rules.json

    # Derive rules from the tags, categories and tools in Mealie (no rules file needed)
    python -m cookdex.rule_tagger --apply --from-taxonomy

Config file schema (JSON)
--------------------------
    {
      "ingredient_tags":      [{"tag": "...",      "pattern": "...", ...}],
      "text_tags":            [{"tag": "...",      "pattern": "...", ...}],
      "text_categories":      [{"category": "...", "pattern": "...", ...}],
      "ingredient_categories":[{"category": "...", "pattern": "...", ...}],
      "tool_tags":            [{"tool": "...",     "pattern": "..."}]
    }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import requests as _requests

from .api_client import MealieApiClient
from .config import REPO_ROOT, resolve_mealie_api_key, resolve_mealie_url
from .db_client import MealieDBClient, is_db_enabled, wants_db
from .tag_rules_generation import build_default_tag_rules
from .providers import MealieProvider, ProviderError, RecipeProvider
from .recipe_text_cache import load_recipe_texts, remember_recipe_texts
from .reporting import Progress, emit_summary

DEFAULT_RULES_FILE = str(REPO_ROOT / "configs" / "taxonomy" / "tag_rules.json")
_MISSING_TARGET_CHOICES = {"skip", "create"}


# ---------------------------------------------------------------------------
# Organizer type descriptors — eliminate tag/category code duplication
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _OrgSpec:
    """Describes one kind of organizer (tag, category, or tool)."""
    label: str          # for log messages: "tag", "category", "tool"
    rule_key: str       # key in rule dict: "tag", "category", "tool"
    api_path: str       # Mealie organizer endpoint name (organizers/<api_path>)
    recipe_field: str   # field on recipe JSON object


_TAG = _OrgSpec("tag", "tag", "tags", "tags")
_CAT = _OrgSpec("category", "category", "categories", "recipeCategory")
_TOOL = _OrgSpec("tool", "tool", "tools", "tools")
_RULE_KINDS = ("ingredient_tags", "text_tags", "text_categories", "ingredient_categories", "tool_tags")
_SAVE_WORKERS = 8


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_rules(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Tag rules config not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tagger
# ---------------------------------------------------------------------------

class RecipeRuleTagger:
    """Apply rule-based tags, categories, and tool assignments to Mealie recipes."""

    def __init__(
        self,
        rules_file: str = DEFAULT_RULES_FILE,
        *,
        dry_run: bool = True,
        use_db: bool = False,
        missing_targets: str = "skip",
        _rules: dict[str, Any] | None = None,
    ) -> None:
        self.rules_file = rules_file
        self.dry_run = dry_run
        self.use_db = use_db
        self._preloaded_rules = _rules
        mode = str(missing_targets or "skip").strip().lower()
        if mode not in _MISSING_TARGET_CHOICES:
            raise ValueError(
                f"missing_targets must be one of {sorted(_MISSING_TARGET_CHOICES)}"
            )
        self.missing_targets = mode
        self.create_missing_targets = mode == "create"
        self._missing_target_skips = 0
        self._loaded_kinds: set[str] = set()
        self._new_links = 0
        self._touched: set[str] = set()

    def _count_new(self, recipe_id: str) -> None:
        self._new_links += 1
        self._touched.add(str(recipe_id))

    @classmethod
    def from_taxonomy(
        cls,
        *,
        dry_run: bool = True,
        use_db: bool = False,
        missing_targets: str = "skip",
        provider: RecipeProvider | None = None,
    ) -> "RecipeRuleTagger":
        """Create a tagger with rules derived from the backend's current tags, categories and tools."""
        if provider is None:
            provider = MealieProvider(MealieApiClient(base_url=resolve_mealie_url(), api_key=resolve_mealie_api_key()))
        names: dict[str, list[dict[str, str]]] = {}
        for kind in ("tags", "categories", "tools"):
            if kind not in provider.term_kinds():
                names[kind] = []
                continue
            try:
                names[kind] = [{"name": term.name} for term in provider.list_terms(kind)]
            except ProviderError as exc:
                raise SystemExit(f"[error] Couldn't read {kind}: {exc}") from exc
        tags, categories, tools = names["tags"], names["categories"], names["tools"]

        if not tags and not categories and not tools:
            print(
                "[warn] Mealie has no tags, categories or tools yet, so there are no rules to run.\n"
                "  Add some in Organize (a starter set is a quick way), or provide a --config file.",
                flush=True,
            )

        rules = build_default_tag_rules(tags=tags, categories=categories, tools=tools)
        return cls(dry_run=dry_run, use_db=use_db, missing_targets=missing_targets, _rules=rules)

    # ------------------------------------------------------------------
    # Rule helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_enabled(rule: dict[str, Any]) -> bool:
        raw = rule.get("enabled", True)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().casefold() not in {"0", "false", "no", "off"}
        return bool(raw)

    @staticmethod
    def _rule_match_on(rule: dict[str, Any]) -> str:
        raw = str(rule.get("match_on") or "").strip().casefold()
        if raw in {"name", "description", "both"}:
            return raw
        return "both"

    @staticmethod
    def _recipe_matches_text(
        recipe: dict[str, Any],
        compiled: re.Pattern[str],
        *,
        match_on: str,
    ) -> bool:
        name = recipe.get("name") or ""
        description = recipe.get("description") or ""
        if match_on == "name":
            return bool(compiled.search(name))
        if match_on == "description":
            return bool(compiled.search(description))
        return bool(compiled.search(name)) or bool(compiled.search(description))

    @staticmethod
    def _compile_pattern(pattern: str) -> re.Pattern[str]:
        return re.compile(pattern.replace(r"\y", r"\b"), re.IGNORECASE)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Run all configured rules and return a stats dict."""
        if self._preloaded_rules is not None:
            rules = self._preloaded_rules
        else:
            rules = _load_rules(self.rules_file)

        if self.use_db:
            return self._run_db(rules)
        return self._run_api(rules)

    # ------------------------------------------------------------------
    # API mode
    # ------------------------------------------------------------------

    def _run_api(self, rules: dict[str, Any]) -> dict[str, Any]:
        """Match every rule in memory, then save each changed recipe once.

        Ingredient and tool rules need each recipe's foods and steps, which the
        recipe list leaves out; those come from recipe_text_cache, so only
        recipes that changed since the last run are opened.
        """
        stats: dict[str, Any] = {key: {} for key in _RULE_KINDS}
        stats["missing_target_skips"] = 0
        self._missing_target_skips = 0

        client = MealieApiClient(base_url=resolve_mealie_url(), api_key=resolve_mealie_api_key())
        print(
            f"[start] Rule tagger (API mode) — dry_run={self.dry_run}  missing_targets={self.missing_targets}",
            flush=True,
        )

        active = {kind: [r for r in rules.get(kind, []) if self._rule_enabled(r)] for kind in _RULE_KINDS}
        if not any(active.values()):
            print("[done] No rules to run.", flush=True)
            return stats
        recipes = client.get_recipes(per_page=1000)
        texts: dict[str, dict[str, Any]] = {}
        read_failed = 0
        if active["ingredient_tags"] or active["ingredient_categories"] or active["tool_tags"]:
            texts = load_recipe_texts(client, recipes)
            read_failed = sum(1 for recipe in recipes if recipe.get("slug") and recipe["slug"] not in texts)

        caches: dict[str, dict[str, Optional[dict]]] = {spec.api_path: {} for spec in (_TAG, _CAT, _TOOL)}
        # slug -> recipe field -> organizers to add
        additions: dict[str, dict[str, list[dict]]] = {}
        by_slug = {str(r.get("slug") or ""): r for r in recipes}

        for kind, spec in (
            ("text_tags", _TAG),
            ("text_categories", _CAT),
            ("ingredient_tags", _TAG),
            ("ingredient_categories", _CAT),
            ("tool_tags", _TOOL),
        ):
            for rule in active[kind]:
                target = str(rule.get(spec.rule_key) or "")
                matched = self._api_match(kind, rule, recipes, texts)
                stats[kind][target] = len(matched)
                if not matched:
                    continue
                org = self._api_get_or_create(target, spec, client, caches[spec.api_path])
                if org is None:
                    self._missing_target_skips += 1
                    print(
                        f"[skip] {spec.label} '{target}' is not in current Mealie taxonomy "
                        f"(missing_targets={self.missing_targets}).",
                        flush=True,
                    )
                    continue
                new = 0
                for slug in matched:
                    have = {item.get("id") for item in by_slug[slug].get(spec.recipe_field) or []}
                    planned = additions.setdefault(slug, {}).setdefault(spec.recipe_field, [])
                    if org["id"] in have or any(item["id"] == org["id"] for item in planned):
                        continue
                    planned.append(org)
                    new += 1
                print(
                    f"[info] {spec.label} '{target}': {len(matched)} recipe(s) matched, {new} not tagged yet"
                    f"{' (dry-run)' if self.dry_run else ''}",
                    flush=True,
                )

        additions = {slug: fields for slug, fields in additions.items() if any(fields.values())}
        new_links = sum(len(items) for fields in additions.values() for items in fields.values())
        written = failed = 0
        if not self.dry_run and additions:
            written, failed = self._api_save(client, by_slug, additions)

        matched_total = sum(sum(stats[kind].values()) for kind in _RULE_KINDS)
        print(
            f"[done] {new_links} new assignment(s) across {len(additions)} recipe(s)"
            f" ({matched_total} matches in all, the rest were already there)",
            flush=True,
        )
        summary: dict[str, Any] = {
            "__title__": "Rule Tagger",
            "Total Assignments": new_links,
            **({"Recipes to Update": len(additions)} if self.dry_run else {"Recipes Updated": written}),
            "Tag Rules": len(stats["text_tags"]) + len(stats["ingredient_tags"]),
            "Category Rules": len(stats["text_categories"]) + len(stats["ingredient_categories"]),
            "Tool Rules": len(stats["tool_tags"]),
            "Missing Target Rules Skipped": self._missing_target_skips,
            "Dry Run": self.dry_run,
        }
        if read_failed:
            summary["Recipes Unreadable"] = read_failed
        if failed or read_failed:
            summary["Failed"] = failed + read_failed
        emit_summary(summary)
        stats["missing_target_skips"] = self._missing_target_skips
        stats["failed"] = failed + read_failed
        if self.dry_run:
            print("[dry-run] No changes written.", flush=True)
        return stats

    def _api_match(
        self,
        kind: str,
        rule: dict[str, Any],
        recipes: list[dict[str, Any]],
        texts: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Slugs of the recipes *rule* matches."""
        compiled = self._compile_pattern(rule["pattern"])
        if kind in {"text_tags", "text_categories"}:
            match_on = self._rule_match_on(rule)
            return [
                str(r["slug"]) for r in recipes
                if self._recipe_matches_text(r, compiled, match_on=match_on)
            ]
        if kind == "tool_tags":
            return [slug for slug, text in texts.items() if compiled.search(text.get("instructions") or "")]
        exclude = self._compile_pattern(rule["exclude_pattern"]) if rule.get("exclude_pattern") else None
        needed = max(1, int(rule.get("min_matches", 1)))
        matched: list[str] = []
        for slug, text in texts.items():
            foods = [
                food for food in text.get("foods") or []
                if compiled.search(food) and not (exclude and exclude.search(food))
            ]
            if len({food.casefold() for food in foods}) >= needed:
                matched.append(slug)
        return matched

    def _api_save(
        self,
        client: MealieApiClient,
        by_slug: dict[str, dict[str, Any]],
        additions: dict[str, dict[str, list[dict]]],
    ) -> tuple[int, int]:
        """One small PATCH per recipe with just the lists that grew. Returns (saved, failed)."""

        def ref(item: dict[str, Any]) -> dict[str, Any]:
            return {"id": item.get("id"), "name": item.get("name"), "slug": item.get("slug", "")}

        def save(slug: str, recipe: dict[str, Any] | None = None) -> tuple[str, str, dict[str, Any] | None]:
            recipe = recipe or by_slug[slug]
            have = {field: {item.get("id") for item in recipe.get(field) or []} for field in additions[slug]}
            body = {
                field: [ref(item) for item in recipe.get(field) or []]
                + [ref(item) for item in items if item.get("id") not in have[field]]
                for field, items in additions[slug].items()
                if items
            }
            try:
                updated = client.patch_recipe(slug, body)
            except _requests.HTTPError as exc:
                return slug, str(getattr(exc.response, "status_code", None) or exc), None
            except _requests.RequestException as exc:
                return slug, str(exc), None
            return slug, "", updated if isinstance(updated, dict) else None

        progress = Progress("Saving tags, categories and tools", len(additions))
        saved = failed = 0
        fulls: list[dict[str, Any]] = []
        retry: list[str] = []
        with ThreadPoolExecutor(max_workers=_SAVE_WORKERS) as pool:
            for slug, error, updated in pool.map(save, list(additions)):
                progress.advance()
                if error:
                    retry.append(slug)
                else:
                    saved += 1
                    if updated:
                        fulls.append(updated)
        # Mealie occasionally rejects one of many parallel saves (a duplicate-key
        # error on a link that isn't there yet). Try those again one at a time,
        # from a fresh copy of the recipe.
        for slug in retry:
            try:
                fresh = client.get_recipe(slug)
            except _requests.RequestException as exc:
                fresh, error, updated = None, str(exc), None
            else:
                _slug, error, updated = save(slug, fresh)
            if error:
                failed += 1
                print(f"[warn] Couldn't save '{slug}': {error}", flush=True)
            else:
                saved += 1
                if updated:
                    fulls.append(updated)
        # Saving moved each recipe's updatedAt; keep the text cache in step.
        remember_recipe_texts(fulls)
        return saved, failed

    def _api_get_or_create(
        self,
        name: str,
        spec: _OrgSpec,
        client: MealieApiClient,
        cache: dict[str, Optional[dict]],
    ) -> Optional[dict]:
        """Return existing organizer (tag/category/tool) by name, or create it; cached."""
        key = name.lower()
        if key in cache:
            return cache[key]

        if spec.api_path not in self._loaded_kinds:
            for item in client.get_organizer_items(spec.api_path):
                cache[item["name"].lower()] = item
            self._loaded_kinds.add(spec.api_path)
            if key in cache:
                return cache[key]

        if not self.create_missing_targets:
            cache[key] = None
            return None

        if self.dry_run:
            placeholder = {"id": f"dry-run-{spec.api_path}-{key}", "name": name, "slug": "dry-run"}
            cache[key] = placeholder
            return placeholder

        created = client.create_organizer_item(spec.api_path, {"name": name})
        cache[str(created.get("name") or name).lower()] = created
        cache[key] = created
        return created

    # ------------------------------------------------------------------
    # DB mode
    # ------------------------------------------------------------------

    def _run_db(self, rules: dict[str, Any]) -> dict[str, Any]:
        if not is_db_enabled():
            print("[warn] The database isn't connected; running through Mealie's API instead.", flush=True)
            return self._run_api(rules)
        try:
            db = MealieDBClient()
        except Exception as exc:  # noqa: BLE001 - fall back rather than fail the run
            print(f"[warn] Couldn't reach the database ({type(exc).__name__}); running through Mealie's API instead.", flush=True)
            return self._run_api(rules)

        stats: dict[str, Any] = {
            "ingredient_tags": {},
            "text_tags": {},
            "text_categories": {},
            "ingredient_categories": {},
            "tool_tags": {},
            "missing_target_skips": 0,
        }
        self._missing_target_skips = 0

        with db:
            group_id = db.get_group_id()
            if not group_id:
                print("[error] Could not determine group_id from database.", flush=True)
                sys.exit(1)

            print(
                f"[start] Rule tagger (DB mode) — dry_run={self.dry_run}  "
                f"group_id={group_id}  missing_targets={self.missing_targets}",
                flush=True,
            )

            for rule in rules.get("ingredient_tags", []):
                name = rule.get("tag", "")
                stats["ingredient_tags"][name] = self._db_apply_ingredient_rule(
                    db, group_id, rule, _TAG,
                )
            for rule in rules.get("text_tags", []):
                name = rule.get("tag", "")
                stats["text_tags"][name] = self._db_apply_text_rule(db, group_id, rule, _TAG)
            for rule in rules.get("text_categories", []):
                name = rule.get("category", "")
                stats["text_categories"][name] = self._db_apply_text_rule(db, group_id, rule, _CAT)
            for rule in rules.get("ingredient_categories", []):
                name = rule.get("category", "")
                stats["ingredient_categories"][name] = self._db_apply_ingredient_rule(
                    db, group_id, rule, _CAT,
                )
            for rule in rules.get("tool_tags", []):
                name = rule.get("tool", "")
                stats["tool_tags"][name] = self._db_apply_tool_rule(db, group_id, rule)

        total = sum(
            sum(stats[key].values())
            for key in ("ingredient_tags", "text_tags", "text_categories", "ingredient_categories", "tool_tags")
        )
        print(
            f"[done] {self._new_links} new assignment(s) across {len(self._touched)} recipe(s)"
            f" ({total} matches in all, the rest were already there)",
            flush=True,
        )
        emit_summary({
            "__title__": "Rule Tagger",
            "Total Assignments": self._new_links,
            **({"Recipes to Update": len(self._touched)} if self.dry_run else {"Recipes Updated": len(self._touched)}),
            "Matches": total,
            "Ingredient Tag Rules": len(stats["ingredient_tags"]),
            "Text Tag Rules": len(stats["text_tags"]),
            "Text Category Rules": len(stats["text_categories"]),
            "Ingredient Category Rules": len(stats["ingredient_categories"]),
            "Tool Rules": len(stats["tool_tags"]),
            "Missing Target Rules Skipped": self._missing_target_skips,
            "Dry Run": self.dry_run,
        })
        stats["missing_target_skips"] = self._missing_target_skips
        if self.dry_run:
            print("[dry-run] No changes written.", flush=True)
        return stats

    # --- DB resolvers (tag / category / tool) ---

    def _db_resolve_id(
        self,
        db: MealieDBClient,
        group_id: str,
        name: str,
        lookup: Callable[[str, str], Optional[str]],
        ensure: Callable[..., Optional[str]],
        label: str,
    ) -> Optional[str]:
        if self.create_missing_targets:
            return ensure(name, group_id, dry_run=self.dry_run)
        found = lookup(name, group_id)
        if found:
            return found
        self._missing_target_skips += 1
        print(
            f"[skip] {label} '{name}' is not in current taxonomy (missing_targets={self.missing_targets}).",
            flush=True,
        )
        return None

    def _db_resolve_tag_id(self, db: MealieDBClient, group_id: str, name: str) -> Optional[str]:
        return self._db_resolve_id(db, group_id, name, db.lookup_tag_id, db.ensure_tag, "tag")

    def _db_resolve_category_id(self, db: MealieDBClient, group_id: str, name: str) -> Optional[str]:
        return self._db_resolve_id(db, group_id, name, db.lookup_category_id, db.ensure_category, "category")

    def _db_resolve_tool_id(self, db: MealieDBClient, group_id: str, name: str) -> Optional[str]:
        return self._db_resolve_id(db, group_id, name, db.lookup_tool_id, db.ensure_tool, "tool")

    # --- DB rule application ---

    def _db_apply_text_rule(
        self,
        db: MealieDBClient,
        group_id: str,
        rule: dict[str, Any],
        spec: _OrgSpec,
    ) -> int:
        if not self._rule_enabled(rule):
            return 0
        name: str = rule[spec.rule_key]
        match_on = self._rule_match_on(rule)
        resolve = self._db_resolve_tag_id if spec is _TAG else self._db_resolve_category_id
        link = db.link_tag if spec is _TAG else db.link_category

        org_id = resolve(db, group_id, name)
        if not org_id:
            return 0

        recipe_ids = db.find_recipe_ids_by_text(group_id, rule["pattern"], match_on=match_on)
        if recipe_ids:
            print(
                f"[text] '{name}': {len(recipe_ids)} recipe(s) matched"
                f"{' (dry-run)' if self.dry_run else ''}",
                flush=True,
            )
        for recipe_id in recipe_ids:
            if link(recipe_id, org_id, dry_run=self.dry_run):
                self._count_new(recipe_id)
        return len(recipe_ids)

    def _db_apply_ingredient_rule(
        self,
        db: MealieDBClient,
        group_id: str,
        rule: dict[str, Any],
        spec: _OrgSpec,
    ) -> int:
        name: str = rule[spec.rule_key]
        pattern: str = rule["pattern"]
        exclude: str = rule.get("exclude_pattern", "")
        min_matches: int = int(rule.get("min_matches", 1))
        resolve = self._db_resolve_tag_id if spec is _TAG else self._db_resolve_category_id
        link = db.link_tag if spec is _TAG else db.link_category

        org_id = resolve(db, group_id, name)
        if not org_id:
            return 0

        recipe_ids = db.find_recipe_ids_by_ingredient(
            group_id, pattern, exclude_pattern=exclude, min_matches=min_matches,
        )
        if recipe_ids:
            label = "ingredient" if spec is _TAG else "ingredient-category"
            print(
                f"[{label}] '{name}': {len(recipe_ids)} recipe(s) matched"
                f"{' (dry-run)' if self.dry_run else ''}",
                flush=True,
            )
        for recipe_id in recipe_ids:
            if link(recipe_id, org_id, dry_run=self.dry_run):
                self._count_new(recipe_id)
        return len(recipe_ids)

    def _db_apply_tool_rule(
        self,
        db: MealieDBClient,
        group_id: str,
        rule: dict[str, Any],
    ) -> int:
        tool_name: str = rule["tool"]
        tool_id = self._db_resolve_tool_id(db, group_id, tool_name)
        if not tool_id:
            return 0

        recipe_ids = db.find_recipe_ids_by_instruction(group_id, rule["pattern"])
        if recipe_ids:
            print(
                f"[tool] '{tool_name}': {len(recipe_ids)} recipe(s) matched"
                f"{' (dry-run)' if self.dry_run else ''}",
                flush=True,
            )
        for recipe_id in recipe_ids:
            if db.link_tool(recipe_id, tool_id, dry_run=self.dry_run):
                self._count_new(recipe_id)
        return len(recipe_ids)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rule-based recipe tagger — assigns tags/tools via regex rules, no LLM required.\n"
            "Runs through Mealie's database when it's connected, otherwise through the API.\n"
            "--from-taxonomy: derive rules from the tags, categories and tools in Mealie."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write changes (default: dry-run preview only).",
    )
    parser.add_argument(
        "--use-db",
        action="store_true",
        default=False,
        help=(
            "Use Mealie's database (the default whenever MEALIE_DB_URL is set)."
        ),
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_RULES_FILE,
        metavar="FILE",
        help=f"Tag rules JSON config file (default: {DEFAULT_RULES_FILE}).",
    )
    parser.add_argument(
        "--from-taxonomy",
        action="store_true",
        default=False,
        help=(
            "Derive rules from the tags, categories and tools currently in Mealie "
            "instead of loading tag_rules.json."
        ),
    )
    parser.add_argument(
        "--missing-targets",
        choices=sorted(_MISSING_TARGET_CHOICES),
        default="skip",
        help=(
            "How to handle rules whose target tag/category/tool is missing from current taxonomy: "
            "'skip' (default) or 'create'."
        ),
    )
    args = parser.parse_args()

    if args.from_taxonomy:
        tagger = RecipeRuleTagger.from_taxonomy(
            dry_run=not args.apply,
            use_db=wants_db(args.use_db),
            missing_targets=args.missing_targets,
        )
    else:
        tagger = RecipeRuleTagger(
            rules_file=args.config,
            dry_run=not args.apply,
            use_db=wants_db(args.use_db),
            missing_targets=args.missing_targets,
        )
    stats = tagger.run()
    return 1 if stats.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
