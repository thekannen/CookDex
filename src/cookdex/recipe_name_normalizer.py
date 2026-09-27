"""Recipe Name Normalizer.

Cleans up recipe names that were auto-generated from URL slugs during import,
turning strings like "how-to-make-chicken-pasta-recipe" into "Chicken Pasta".

Transformations applied (in order):
  1. Replace hyphens and underscores with spaces.
  2. Collapse repeated whitespace.
  3. Strip common URL-artifact prefixes: "recipe for", "how to make",
     "how to cook", "how to", "make", "cook".
  4. Strip trailing word "recipe".
  5. Smart title-case (preserves small words, apostrophes, and acronyms).

A recipe is a candidate for renaming when its name is entirely lowercase
(i.e. it was never given proper casing by a human).  You can also force all
recipes through the normalizer with --all.

Writes PATCH calls to Mealie via the HTTP API.  Use DRY_RUN=true (the default)
to preview changes without writing anything.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from slugify import slugify
from titlecase import titlecase

from .api_client import MealieApiClient
from .config import env_or_config, resolve_mealie_api_key, resolve_mealie_url, resolve_repo_path, to_bool
from .reporting import emit_items, emit_summary, load_apply_plan

DEFAULT_REPORT = "reports/recipe_name_normalize_report.json"
DEFAULT_WORKERS = 8


def _make_slug(name: str) -> str:
    """Generate a slug matching Mealie's create_recipe_slug()."""
    s = slugify(name)
    if len(s) > 250:
        s = s[:250]
    return s


# Ordered from most-specific to least-specific.
_PREFIX_PATTERNS: list[re.Pattern] = [
    re.compile(r"^recipe\s+for\s+", re.IGNORECASE),
    re.compile(r"^how\s+to\s+(?:make|cook)\s+", re.IGNORECASE),
    re.compile(r"^how\s+to\s+", re.IGNORECASE),
    re.compile(r"^(?:make|cook)\s+", re.IGNORECASE),
]
_SUFFIX_PATTERN = re.compile(r"\s+recipe$", re.IGNORECASE)
_HAS_UPPERCASE_RE = re.compile(r"[A-Z]")

# SEO decoration scraped along with the title.
_SITE_TAIL_RE = re.compile(r"\s*[|•]\s*.*$")  # "Chicken Stir Fry | The Best Recipe!"
_EXCLAIM_PAREN_RE = re.compile(r"\s*\([^)]*!\s*\)\s*$")  # "Cookies (Seriously!)"
_RECIPE_TAIL_RE = re.compile(
    r"\s+recipe(?:\s+(?:video|easy|ideas?|with\s+video))*\s*$", re.IGNORECASE
)  # "tikka masala recipe video", "lentil soup recipe easy"
_VIDEO_TAIL_RE = re.compile(r"\s+(?:with\s+)?video\s*$", re.IGNORECASE)
_SHOUTED_HYPE_RE = re.compile(r"^(?:THE\s+BEST|BEST\s+EVER|THE\s+ULTIMATE|THE\s+EASIEST)\b\s*")
_SLUG_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
_SLUG_COPY_SUFFIX_RE = re.compile(r"\s+\d{1,2}$")  # "banana-bread-2" from a slug collision
_SHOUTED_WORDS_RE = re.compile(r"\b[A-Z]{2,}\s+[A-Z]{2,}\b")

# Common food/cooking abbreviations that should stay uppercase.
_ACRONYMS: dict[str, str] = {
    "bbq": "BBQ", "blt": "BLT", "gf": "GF", "diy": "DIY",
    "pb": "PB", "pbj": "PBJ", "xo": "XO", "hk": "HK",
    "thc": "THC", "vgf": "VGF", "ac": "AC",
}
_ACRONYM_WORD_RE = re.compile(r"^([^A-Za-z0-9]*)([A-Za-z0-9]+)((?:'[A-Za-z]+)?[^A-Za-z0-9]*)$")


def _titlecase_acronym_callback(word: str, **_kwargs: Any) -> str | None:
    match = _ACRONYM_WORD_RE.match(word)
    if not match:
        return None
    leading, core, trailing = match.groups()
    replacement = _ACRONYMS.get(core.lower())
    if replacement is None:
        return None
    return f"{leading}{replacement}{trailing.lower()}"


def _smart_title_case(text: str) -> str:
    """Title-case *text* with project acronym preservation."""
    if not text.strip():
        return text
    return titlecase(text.lower(), callback=_titlecase_acronym_callback)


def normalize_recipe_name(raw: str) -> str:
    """Return a cleaned version of *raw*, or the original if no change needed."""
    from_slug = bool(_SLUG_NAME_RE.match(raw.strip()))
    name = _SITE_TAIL_RE.sub("", raw)
    name = _EXCLAIM_PAREN_RE.sub("", name)
    name = _SHOUTED_HYPE_RE.sub("", name.strip())
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()
    for pat in _PREFIX_PATTERNS:
        name = pat.sub("", name).strip()
    name = _RECIPE_TAIL_RE.sub("", name).strip()
    name = _VIDEO_TAIL_RE.sub("", name).strip()
    name = _SUFFIX_PATTERN.sub("", name).strip()
    if from_slug:
        name = _SLUG_COPY_SUFFIX_RE.sub("", name).strip()
    return _smart_title_case(name) if name else raw


def _looks_unformatted(name: str) -> bool:
    """True when the name has no uppercase letters, indicating it was
    auto-generated from a URL slug or import and never human-edited."""
    return not _HAS_UPPERCASE_RE.search(name)


def _has_seo_noise(name: str) -> bool:
    """True when a human-cased title still carries scraped SEO decoration."""
    return bool(
        _SITE_TAIL_RE.search(name)
        or _EXCLAIM_PAREN_RE.search(name)
        or _SHOUTED_WORDS_RE.search(name)
    )


def _should_normalize(recipe: dict[str, Any], *, force_all: bool) -> bool:
    name = str(recipe.get("name") or "").strip()
    slug = str(recipe.get("slug") or "").strip()
    if not name or not slug:
        return False
    if force_all:
        return normalize_recipe_name(name) != name
    return (_looks_unformatted(name) or _has_seo_noise(name)) and normalize_recipe_name(name) != name


@dataclass
class NameAction:
    slug: str
    old_name: str
    new_name: str


def _analyze_recipe(recipe: dict[str, Any], *, force_all: bool) -> NameAction | None:
    if not _should_normalize(recipe, force_all=force_all):
        return None
    old_name = str(recipe.get("name") or "").strip()
    new_name = normalize_recipe_name(old_name)
    if new_name == old_name:
        return None
    return NameAction(slug=str(recipe.get("slug") or ""), old_name=old_name, new_name=new_name)


class RecipeNameNormalizer:
    def __init__(
        self,
        client: MealieApiClient,
        *,
        dry_run: bool = True,
        apply: bool = False,
        force_all: bool = False,
        report_file: Path | str = DEFAULT_REPORT,
        workers: int = DEFAULT_WORKERS,
    ) -> None:
        self.client = client
        self.dry_run = dry_run
        self.apply = apply
        self.force_all = force_all
        self.report_file = Path(report_file)
        self.workers = workers

    def _apply_concurrent(self, actions: list[NameAction]) -> tuple[list[dict], int, int]:
        action_log: list[dict] = []
        applied = 0
        failed = 0

        def _patch(action: NameAction) -> tuple[NameAction, bool, str]:
            try:
                self.client.patch_recipe(action.slug, {
                    "name": action.new_name,
                    "slug": _make_slug(action.new_name),
                })
                return action, True, ""
            except Exception as exc:
                return action, False, str(exc)

        total = len(actions)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(_patch, a): a for a in actions}
            for idx, fut in enumerate(concurrent.futures.as_completed(futures), 1):
                action, ok, err = fut.result()
                if ok:
                    applied += 1
                    action_log.append({"status": "ok", "slug": action.slug, "old_name": action.old_name, "new_name": action.new_name})
                    print(f"[ok] {idx}/{total} {action.slug}: '{action.old_name}' -> '{action.new_name}'", flush=True)
                else:
                    failed += 1
                    action_log.append({"status": "error", "slug": action.slug, "old_name": action.old_name, "new_name": action.new_name, "error": err})
                    print(f"[error] {action.slug}: {err}", flush=True)

        return action_log, applied, failed

    def run(self) -> dict[str, Any]:
        executable = self.apply and not self.dry_run

        print("[start] Fetching all recipes from API ...", flush=True)
        recipes = self.client.get_recipes()
        total = len(recipes)

        actions: list[NameAction] = []
        for r in recipes:
            action = _analyze_recipe(r, force_all=self.force_all)
            if action:
                actions.append(action)

        # With a reviewed plan, apply exactly the approved renames, using the
        # name the user approved (which they may have edited). A rename is
        # skipped if the recipe's name changed since the preview.
        plan = load_apply_plan("names")
        skipped: list[dict[str, Any]] = []
        if plan is not None:
            approved = plan.get("rename") or {}
            current = {str(r.get("slug") or ""): str(r.get("name") or "").strip() for r in recipes}
            planned: list[NameAction] = []
            for slug, change in approved.items():
                if not isinstance(change, dict):
                    continue
                old_name = str(change.get("from") or "").strip()
                new_name = str(change.get("to") or "").strip()
                if slug not in current or not new_name or new_name == old_name:
                    continue
                if current[slug] != old_name:
                    skipped.append({"status": "skipped", "slug": slug, "old_name": current[slug],
                                    "new_name": new_name, "error": "Name changed since the preview."})
                    continue
                planned.append(NameAction(slug=slug, old_name=old_name, new_name=new_name))
            planned_slugs = {a.slug for a in planned}
            skipped.extend(
                {"status": "skipped", "slug": a.slug, "old_name": a.old_name, "new_name": a.new_name}
                for a in actions
                if a.slug not in planned_slugs and a.slug not in approved
            )
            actions = planned

        mode_label = "all recipes" if self.force_all else "lowercase names only"
        print(
            f"[start] {total} recipes scanned ({mode_label}) -> {len(actions)} names to normalize",
            flush=True,
        )

        action_log: list[dict] = []
        applied = 0
        failed = 0

        if executable:
            print(f"[start] Applying {len(actions)} name patches (workers={self.workers}) ...", flush=True)
            action_log, applied, failed = self._apply_concurrent(actions)
        else:
            for action in actions:
                action_log.append({
                    "status": "planned",
                    "slug": action.slug,
                    "old_name": action.old_name,
                    "new_name": action.new_name,
                })
                print(f"[plan] {action.slug}: '{action.old_name}' -> '{action.new_name}'", flush=True)

        action_log.extend(skipped)
        emit_items("recipe_rename", [
            {
                "slug": entry["slug"],
                "old_name": entry["old_name"],
                "new_name": entry["new_name"],
                "status": {"ok": "applied", "patched": "applied", "renamed": "applied"}.get(entry["status"], entry["status"]),
                **({"error": entry["error"]} if entry.get("error") else {}),
            }
            for entry in action_log
        ])

        report: dict[str, Any] = {
            "summary": {
                "total_recipes": total,
                "candidates": len(actions),
                "applied": applied,
                "failed": failed,
                "mode": "apply" if executable else "audit",
                "scope": "all" if self.force_all else "lowercase-only",
            },
            "actions": action_log,
        }

        self.report_file.parent.mkdir(parents=True, exist_ok=True)
        self.report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        mode = "apply" if executable else "audit"
        scope = "all" if self.force_all else "lowercase-only"
        print(
            f"[done] {len(actions)} name(s) to normalize ({scope}) — "
            f"{applied} applied ({mode} mode)",
            flush=True,
        )
        emit_summary({
            "__title__": "Name Normalizer",
            "Total Recipes": total,
            "Candidates": len(actions),
            "Applied": applied,
            "Failed": failed,
            "Scope": scope,
            "Mode": mode,
        })
        return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize recipe names that appear unformatted (lowercase-only by default)."
    )
    parser.add_argument("--apply", action="store_true", help="Write name changes to Mealie.")
    parser.add_argument(
        "--all",
        dest="force_all",
        action="store_true",
        help="Normalize all recipes, not just lowercase/unformatted names.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Concurrent API workers when applying.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dry_run = bool(env_or_config("DRY_RUN", "runtime.dry_run", False, to_bool))
    if dry_run:
        print("[start] runtime.dry_run=true (writes disabled; planning only).", flush=True)
    normalizer = RecipeNameNormalizer(
        MealieApiClient(
            base_url=resolve_mealie_url(),
            api_key=resolve_mealie_api_key(required=True),
            timeout_seconds=60,
            retries=3,
            backoff_seconds=0.4,
        ),
        dry_run=dry_run,
        apply=bool(args.apply),
        force_all=bool(args.force_all),
        report_file=resolve_repo_path(DEFAULT_REPORT),
        workers=args.workers,
    )
    report = normalizer.run()
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
