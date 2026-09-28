"""Mealie Backup Manager.

Create and prune Mealie backups via the admin API.

Usage:
    python -m cookdex.mealie_backup                    # create a backup
    python -m cookdex.mealie_backup --prune 5          # create + keep only the newest 5 CookDex made
    python -m cookdex.mealie_backup --prune-only 5     # prune without creating
    python -m cookdex.mealie_backup --kind pre-change  # the restore point taken before a change

Pruning only ever deletes backups CookDex created, which it records in a
small ledger file (``backup_ledger.json`` in the checkpoint directory).
Backups made in Mealie, uploaded to it, or made before CookDex kept the
ledger are never deleted. Backups taken before a change (``--kind
pre-change``) are counted separately and trimmed to the newest
``PRE_CHANGE_KEEP``, so they never push out the regular ones.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .api_client import MealieApiClient
from .config import env_or_config, resolve_mealie_api_key, resolve_mealie_url, resolve_repo_path
from .reporting import emit_summary

KINDS = ("cookdex", "pre-change")
PRE_CHANGE_KEEP = 10
LEDGER_NAME = "backup_ledger.json"


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return value


# ── Ledger of backups CookDex created ────────────────────────────────


def default_ledger_path() -> Path:
    base = env_or_config("CHECKPOINT_DIR", "maintenance.checkpoint_dir", "cache/maintenance")
    return resolve_repo_path(str(base)) / LEDGER_NAME


def read_ledger(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = data.get("backups") if isinstance(data, dict) else None
    return [e for e in entries or [] if isinstance(e, dict) and e.get("name") and e.get("kind") in KINDS]


def write_ledger(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"backups": entries}, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# ── Mealie calls ─────────────────────────────────────────────────────


def _backup_time(backup: dict[str, Any]) -> str:
    # Mealie's ISO date sorts correctly; names start with the Mealie version,
    # so they don't sort by time across upgrades.
    return str(backup.get("date") or "")


def list_backups(client: MealieApiClient) -> list[dict[str, Any]]:
    """List all existing backups, newest first."""
    data = client.request_json("GET", "/admin/backups", timeout=30)
    imports = data.get("imports", []) if isinstance(data, dict) else []
    imports.sort(key=lambda b: (_backup_time(b), str(b.get("name") or "")), reverse=True)
    return imports


def create_backup(client: MealieApiClient, *, kind: str = "cookdex", ledger: Path | None = None) -> bool:
    """Create a new Mealie backup and record it in the ledger. Returns True on success."""
    ledger = ledger or default_ledger_path()
    print("[start] Creating Mealie backup...", flush=True)
    try:
        before = {str(b.get("name")) for b in list_backups(client)}
        data = client.request_json("POST", "/admin/backups", timeout=900)
        msg = data.get("message", "") if isinstance(data, dict) else str(data)
        print(f"[ok] Backup created: {msg}", flush=True)
    except Exception as exc:
        print(f"[error] Backup failed: {exc}", flush=True)
        return False

    # Mealie doesn't return the new name, so find it by comparing listings.
    try:
        created = [b for b in list_backups(client) if str(b.get("name")) not in before]
    except Exception as exc:
        print(f"[warn] Couldn't list backups to record the new one ({exc}); it won't be pruned later.", flush=True)
        return True
    if not created:
        print("[warn] Couldn't tell which backup is new; it won't be pruned later.", flush=True)
        return True
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    entries = read_ledger(ledger)
    known = {e["name"] for e in entries}
    for backup in created:
        if str(backup["name"]) not in known:
            entries.append({"name": str(backup["name"]), "kind": kind, "created_at": _backup_time(backup) or now})
            print(f"[info] Recorded {backup['name']} as a {kind} backup.", flush=True)
    try:
        write_ledger(ledger, entries)
    except OSError as exc:
        # The backup exists either way; only the bookkeeping for pruning is lost.
        print(f"[warn] Couldn't record the new backup ({exc}); it won't be pruned later.", flush=True)
    return True


def prune_backups(
    client: MealieApiClient, keep: int, *, kind: str = "cookdex", ledger: Path | None = None
) -> tuple[int, int]:
    """Delete the oldest backups CookDex made of *kind*, keeping the newest *keep*.

    Backups that aren't in the ledger (made in Mealie, uploaded, or older than
    the ledger) are never touched. Returns (deleted, failed to delete).
    Listing the backups or writing the ledger can still raise.
    """
    if keep < 1:
        raise ValueError("keep must be at least 1.")
    ledger = ledger or default_ledger_path()
    backups = list_backups(client)
    existing = {str(b.get("name")) for b in backups}
    entries = [e for e in read_ledger(ledger) if e["name"] in existing]  # forget ones deleted elsewhere
    ours = {e["name"] for e in entries if e["kind"] == kind}
    candidates = [b for b in backups if str(b.get("name")) in ours]
    untouched = len(backups) - len({e["name"] for e in entries})
    label = "nightly/task" if kind == "cookdex" else kind

    deleted: set[str] = set()
    failed = 0
    for backup in candidates[keep:]:
        name = str(backup.get("name"))
        try:
            client.request_json("DELETE", f"/admin/backups/{name}", timeout=30)
            print(f"[ok] Deleted backup: {name}", flush=True)
            deleted.add(name)
        except Exception as exc:
            print(f"[warn] Failed to delete {name}: {exc}", flush=True)
            failed += 1

    write_ledger(ledger, [e for e in entries if e["name"] not in deleted])
    kept = len(candidates) - len(deleted)
    failed_note = f" {failed} couldn't be deleted, so more than {keep} are left." if failed else ""
    print(
        f"[{'warn' if failed else 'done'}] Pruned {len(deleted)} {label} backup(s); kept {kept}.{failed_note} "
        f"{untouched} backup(s) CookDex didn't make were left alone.",
        flush=True,
    )
    return len(deleted), failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and prune Mealie backups via the admin API.")
    parser.add_argument(
        "--prune",
        type=_positive_int,
        metavar="N",
        help="After creating a backup, delete the oldest backups CookDex made, keeping the newest N.",
    )
    parser.add_argument(
        "--prune-only",
        type=_positive_int,
        metavar="N",
        help="Skip backup creation and only prune, keeping the newest N that CookDex made.",
    )
    parser.add_argument(
        "--kind",
        choices=KINDS,
        default="cookdex",
        help="'pre-change' for the restore point taken before a change; these are trimmed to the newest "
        f"{PRE_CHANGE_KEEP} and never count against --prune.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing backups and exit.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    client = MealieApiClient(
        base_url=resolve_mealie_url(),
        api_key=resolve_mealie_api_key(required=True),
        timeout_seconds=60,
        retries=0,
        backoff_seconds=0,
    )
    ledger = default_ledger_path()

    if args.list:
        backups = list_backups(client)
        kinds = {e["name"]: e["kind"] for e in read_ledger(ledger)}
        if not backups:
            print("[info] No backups found.", flush=True)
        else:
            print(f"[info] {len(backups)} backup(s):", flush=True)
            for b in backups:
                made_by = kinds.get(str(b.get("name")), "not made by CookDex")
                print(f"  {b.get('name', '?')}  ({b.get('size', '?')}, {made_by})", flush=True)
        return 0

    if args.prune_only is not None:
        summary: dict[str, Any] = {"__title__": "Mealie Backup", "Created": 0}
        ok = _prune_into(summary, client, args.prune_only, kind="cookdex", ledger=ledger)
        summary["Kept"] = args.prune_only
        emit_summary(summary)
        return 0 if ok else 1

    if not create_backup(client, kind=args.kind, ledger=ledger):
        return 1

    summary = {"__title__": "Mealie Backup", "Created": 1}
    if args.kind == "pre-change":
        # This backup runs before a change and the restore point exists, so
        # failing to trim old ones is reported but doesn't block the change.
        _prune_into(summary, client, PRE_CHANGE_KEEP, kind="pre-change", ledger=ledger)
        emit_summary(summary)
        return 0
    ok = True
    if args.prune is not None:
        ok = _prune_into(summary, client, args.prune, kind="cookdex", ledger=ledger)
        summary["Kept"] = args.prune
    emit_summary(summary)
    return 0 if ok else 1


def _prune_into(summary: dict[str, Any], client: MealieApiClient, keep: int, *, kind: str, ledger: Path) -> bool:
    """Prune and add the counts to *summary*; returns False when any part of the prune failed."""
    try:
        deleted, failed = prune_backups(client, keep, kind=kind, ledger=ledger)
    except Exception as exc:
        print(f"[error] Couldn't prune old backups: {exc}", flush=True)
        summary["Pruned"] = 0
        summary["Prune Failed"] = str(exc)
        return False
    summary["Pruned"] = deleted
    if failed:
        summary["Failed"] = failed
    return not failed


if __name__ == "__main__":
    sys.exit(main())
