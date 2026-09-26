"""Merge near-duplicate tags and categories with Mealie's native merge routes.

Mealie v3.25 added ``POST /organizers/{tags,categories}/merge``, which repoints
every recipe from the source organizer to the target and deletes the source.
Tools have no such route, so they are not handled here.

Matching is deliberately conservative: two names are merged only when they
differ by case, whitespace, punctuation, accents, ``&`` vs ``and``, or a plural
ending on the last word whose singular form also exists as its own entry.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .api_client import MealieApiClient
from .config import (
    env_or_config,
    resolve_mealie_api_key,
    resolve_mealie_url,
    resolve_repo_path,
    to_bool,
)

# Organizer endpoint -> key holding that organizer's list on a recipe summary.
KINDS: dict[str, str] = {"tags": "tags", "categories": "recipeCategory"}
_SINGULAR = {"tags": "tag", "categories": "category"}

_APOSTROPHES = re.compile(r"['‘’`]")
_NON_WORD = re.compile(r"[\W_]+")


@dataclass
class OrganizerMergeAction:
    kind: str
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    group_id: str
    normalized_name: str
    source_usage: int
    target_usage: int


def normalize_name(name: str) -> str:
    """Fold case, accents, punctuation, and ``&`` so cosmetic variants share a key."""
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = _APOSTROPHES.sub("", text)
    return " ".join(_NON_WORD.sub(" ", text).split())


def singular_candidates(key: str) -> list[str]:
    """Possible singular forms of a normalized key, changing only the last word."""
    head, _, last = key.rpartition(" ")
    if not last.isalpha() or not last.endswith("s") or last.endswith("ss"):
        return []
    stems = [last[:-1]]
    if last.endswith("es"):
        stems.append(last[:-2])
    if last.endswith("ies"):
        stems.append(last[:-3] + "y")
    prefix = f"{head} " if head else ""
    return [prefix + stem for stem in stems if len(stem) >= 3]


def build_duplicate_groups(items: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Group organizers that are clearly the same thing.

    A plural key is folded into its singular only when the singular already
    exists as its own entry in the same Mealie group, so no new spellings are
    invented. The group is labelled with the shortest (singular) key.
    """
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        item_id = str(item.get("id") or "").strip()
        key = normalize_name(str(item.get("name") or ""))
        if not item_id or not key:
            continue
        group_id = str(item.get("groupId") or "").strip()
        by_key.setdefault((group_id, key), []).append(item)

    parent: dict[tuple[str, str], tuple[str, str]] = {k: k for k in by_key}

    def find(node: tuple[str, str]) -> tuple[str, str]:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for group_id, key in sorted(by_key):
        for candidate in singular_candidates(key):
            other = (group_id, candidate)
            if other in by_key:
                a, b = find((group_id, key)), find(other)
                if a != b:
                    # Root on the shorter key so the label is the singular form.
                    keep, drop = sorted((a, b), key=lambda k: (len(k[1]), k[1]))
                    parent[drop] = keep

    merged: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for node in sorted(by_key):
        merged.setdefault(find(node), []).extend(by_key[node])
    return {key: value for key, value in merged.items() if len(value) > 1}


def choose_canonical(candidates: list[dict[str, Any]], usage: dict[str, int]) -> dict[str, Any]:
    """Pick the most-used entry; ties prefer tidy names, then a stable order."""

    def rank(item: dict[str, Any]) -> tuple[Any, ...]:
        name = str(item.get("name") or "")
        untidy = name != " ".join(name.split())
        # "Quick Meal" reads better than "QUICK MEAL" or "quick meal".
        single_case = name == name.upper() or name == name.lower()
        usage_rank = -usage.get(str(item.get("id") or ""), 0)
        return (usage_rank, untidy, single_case, name.casefold(), name, str(item.get("id") or ""))

    return sorted(candidates, key=rank)[0]


class TaxonomyDuplicatesManager:
    def __init__(
        self,
        client: MealieApiClient,
        *,
        kinds: list[str] | None = None,
        dry_run: bool = False,
        apply: bool = False,
        max_actions: int = 250,
        report_file: Path | str = "reports/taxonomy_duplicates_report.json",
    ) -> None:
        self.client = client
        self.kinds = list(kinds or KINDS)
        unknown = [kind for kind in self.kinds if kind not in KINDS]
        if unknown:
            raise ValueError(f"Unsupported organizer kind(s): {', '.join(unknown)}")
        self.dry_run = dry_run
        self.apply = apply
        self.max_actions = max(1, int(max_actions))
        self.report_file = Path(report_file)
        self._recipes: list[dict[str, Any]] | None = None

    def build_usage(self, kind: str, items: list[dict[str, Any]]) -> dict[str, int]:
        # Mealie v3.25+ reports an accurate recipeCount for tags and categories.
        if items and all(isinstance(item.get("recipeCount"), int) for item in items):
            return {str(item.get("id") or ""): int(item["recipeCount"]) for item in items}
        # Older servers: count links from recipe summaries instead.
        if self._recipes is None:
            self._recipes = self.client.get_recipes(per_page=1000)
        usage: dict[str, int] = {}
        for recipe in self._recipes:
            for entry in recipe.get(KINDS[kind]) or []:
                if isinstance(entry, dict) and entry.get("id"):
                    entry_id = str(entry["id"])
                    usage[entry_id] = usage.get(entry_id, 0) + 1
        return usage

    def build_merge_plan(
        self, kind: str, items: list[dict[str, Any]], usage: dict[str, int]
    ) -> list[OrganizerMergeAction]:
        plan: list[OrganizerMergeAction] = []
        for (group_id, normalized_name), candidates in build_duplicate_groups(items).items():
            canonical = choose_canonical(candidates, usage)
            target_id = str(canonical.get("id") or "")
            for item in candidates:
                source_id = str(item.get("id") or "")
                if source_id == target_id:
                    continue
                plan.append(
                    OrganizerMergeAction(
                        kind=kind,
                        source_id=source_id,
                        source_name=str(item.get("name") or ""),
                        target_id=target_id,
                        target_name=str(canonical.get("name") or ""),
                        group_id=group_id,
                        normalized_name=normalized_name,
                        source_usage=usage.get(source_id, 0),
                        target_usage=usage.get(target_id, 0),
                    )
                )
        return sorted(plan, key=lambda action: (action.normalized_name, action.group_id, action.source_name, action.source_id))

    def run(self) -> dict[str, Any]:
        executable = self.apply and not self.dry_run
        applied = 0
        failed = 0
        attempted: list[dict[str, Any]] = []
        per_kind: dict[str, dict[str, Any]] = {}

        for kind in self.kinds:
            items = self.client.get_organizer_items(kind, per_page=1000)
            print(f"[start] Scanning {len(items)} {kind} for duplicates ...", flush=True)
            groups = build_duplicate_groups(items)
            usage = self.build_usage(kind, items) if groups else {}
            plan = self.build_merge_plan(kind, items, usage)
            stats: dict[str, Any] = {
                "total": len(items),
                "duplicate_groups": len(groups),
                "merge_candidates": len(plan),
                "applied": 0,
                "failed": 0,
                "merge_supported": None,
            }
            per_kind[kind] = stats

            for idx, action in enumerate(plan, 1):
                if executable and applied >= self.max_actions:
                    break
                entry = {
                    "kind": kind,
                    "source_id": action.source_id,
                    "source_name": action.source_name,
                    "target_id": action.target_id,
                    "target_name": action.target_name,
                    "group_id": action.group_id,
                    "normalized_name": action.normalized_name,
                    "source_usage": action.source_usage,
                    "target_usage": action.target_usage,
                    "mode": "apply" if executable else "plan",
                }
                label = f"{_SINGULAR[kind]} '{action.source_name}' -> '{action.target_name}'"

                if not executable:
                    entry["status"] = "planned"
                    print(
                        f"[plan] {idx}/{len(plan)} would merge {label}"
                        f" ({action.source_usage} -> {action.target_usage} recipes)",
                        flush=True,
                    )
                elif stats["merge_supported"] is False:
                    entry["status"] = "unsupported"
                else:
                    try:
                        self.client.merge_organizer_item(kind, action.source_id, action.target_id)
                        stats["merge_supported"] = True
                        applied += 1
                        stats["applied"] += 1
                        entry["status"] = "merged"
                        print(f"[ok] {stats['applied']}/{len(plan)} merged {label}", flush=True)
                    except requests.HTTPError as exc:
                        if MealieApiClient.is_missing_route(exc):
                            stats["merge_supported"] = False
                            entry["status"] = "unsupported"
                            print(
                                f"[warn] This Mealie server has no POST /organizers/{kind}/merge route "
                                "(added in Mealie v3.25). Upgrade Mealie to merge duplicate "
                                f"{kind}; skipping the remaining {kind} merges.",
                                flush=True,
                            )
                        else:
                            failed += 1
                            stats["failed"] += 1
                            entry["status"] = "failed"
                            entry["error"] = str(exc)
                            print(f"[error] merge {label}: {exc}", flush=True)
                attempted.append(entry)

        # Mealie's merge leaves cookbook filters pointing at the deleted source.
        merged_ids = {
            entry["source_id"]: entry["target_id"]
            for entry in attempted
            if entry.get("status") in ("merged", "planned")
        }
        cookbooks = self.repoint_cookbooks(merged_ids, executable=executable) if merged_ids else {}

        report = {
            "summary": {
                "kinds": self.kinds,
                "cookbooks_repointed": cookbooks.get("repointed", 0),
                "cookbooks_failed": cookbooks.get("failed", 0),
                "duplicate_groups": sum(s["duplicate_groups"] for s in per_kind.values()),
                "merge_candidates_total": sum(s["merge_candidates"] for s in per_kind.values()),
                "actions_attempted": len(attempted),
                "actions_applied": applied,
                "actions_failed": failed,
                "unsupported_kinds": [k for k, s in per_kind.items() if s["merge_supported"] is False],
                "mode": "apply" if executable else "audit",
            },
            "by_kind": per_kind,
            "attempted_actions": attempted,
        }

        self.report_file.parent.mkdir(parents=True, exist_ok=True)
        self.report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        s = report["summary"]
        print(
            f"[done] {s['merge_candidates_total']} merge candidate(s) across "
            f"{s['duplicate_groups']} group(s) -- {s['actions_applied']} applied ({s['mode']} mode)",
            flush=True,
        )
        summary: dict[str, Any] = {"__title__": "Tag & Category Duplicates"}
        for kind, stats in per_kind.items():
            title = kind.capitalize()
            summary[f"{title} Total"] = stats["total"]
            summary[f"{title} Merge Candidates"] = stats["merge_candidates"]
        summary["Applied"] = s["actions_applied"]
        if s["cookbooks_repointed"] or s["cookbooks_failed"]:
            summary["Cookbooks Repointed"] = s["cookbooks_repointed"]
        summary["Failed"] = s["actions_failed"]
        if s["unsupported_kinds"]:
            summary["Merge Unsupported"] = ", ".join(s["unsupported_kinds"])
        summary["Mode"] = s["mode"]
        print("[summary] " + json.dumps(summary), flush=True)
        return report

    def repoint_cookbooks(self, merged_ids: dict[str, str], *, executable: bool) -> dict[str, int]:
        """Point cookbook filters that name a merged-away organizer at the kept one."""
        result = {"repointed": 0, "failed": 0}
        try:
            cookbooks = self.client.list_cookbooks()
        except requests.RequestException as exc:
            print(f"[warn] Could not list cookbooks to repoint filters: {exc}", flush=True)
            return result
        for cookbook in cookbooks:
            original = str(cookbook.get("queryFilterString") or "")
            updated = original
            for source_id, target_id in merged_ids.items():
                pattern = rf"([\"']){re.escape(source_id)}\1"
                updated = re.sub(pattern, rf"\g<1>{target_id}\g<1>", updated, flags=re.IGNORECASE)
            if updated == original:
                continue
            name = cookbook.get("name")
            if not executable:
                print(f"[plan] would repoint cookbook '{name}' to the kept tags/categories", flush=True)
                result["repointed"] += 1
                continue
            try:
                self.client.update_cookbook({**cookbook, "queryFilterString": updated})
                result["repointed"] += 1
                print(f"[ok] Repointed cookbook '{name}' to the kept tags/categories", flush=True)
            except requests.RequestException as exc:
                result["failed"] += 1
                print(f"[error] repoint cookbook '{name}': {exc}", flush=True)
        return result


def parse_kinds(raw: str) -> list[str]:
    kinds = [item.strip().lower() for item in str(raw or "").split(",") if item.strip()]
    if not kinds:
        raise argparse.ArgumentTypeError("At least one kind is required.")
    unknown = [kind for kind in kinds if kind not in KINDS]
    if unknown:
        raise argparse.ArgumentTypeError(f"Unknown kind(s): {', '.join(unknown)}")
    return list(dict.fromkeys(kinds))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge near-duplicate Mealie tags and categories.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    cleanup = subparsers.add_parser("cleanup", help="Audit/apply tag and category merge actions.")
    cleanup.add_argument("--apply", action="store_true", help="Apply merge actions.")
    cleanup.add_argument(
        "--kinds",
        type=parse_kinds,
        default=list(KINDS),
        help="Comma-separated organizer kinds to deduplicate: tags, categories.",
    )
    cleanup.add_argument(
        "--max-actions",
        type=int,
        default=int(env_or_config("MAX_ACTIONS_PER_STAGE", "maintenance.max_actions_per_stage", 250, int)),
    )
    cleanup.add_argument("--report-file", default="reports/taxonomy_duplicates_report.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command != "cleanup":
        raise RuntimeError(f"Unsupported command: {args.command}")

    dry_run = bool(env_or_config("DRY_RUN", "runtime.dry_run", False, to_bool))
    if dry_run:
        print("[start] runtime.dry_run=true (writes disabled; planning only).", flush=True)

    client = MealieApiClient(
        base_url=resolve_mealie_url(),
        api_key=resolve_mealie_api_key(required=True),
        timeout_seconds=60,
        retries=3,
        backoff_seconds=0.4,
    )
    manager = TaxonomyDuplicatesManager(
        client,
        kinds=args.kinds,
        dry_run=dry_run,
        apply=bool(args.apply),
        max_actions=args.max_actions,
        report_file=resolve_repo_path(args.report_file),
    )
    report = manager.run()
    return 1 if report["summary"]["actions_failed"] or report["summary"]["cookbooks_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
