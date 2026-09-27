"""Library home: a score and a list of what needs attention.

Everything here is assembled from runs CookDex already has: the latest Health
Check, the latest Clean Recipe Library preview, and the latest tag/category
duplicate preview. ``POST /library/scan`` queues those three read-only runs.
Nothing on this router writes to Mealie.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends

from ..deps import Services, build_runtime_env, require_editor_session, require_services
from ..rate_limit import ActionRateLimiter

router = APIRouter(tags=["library"])
_scan_limiter = ActionRateLimiter(max_per_minute=6)

SCAN_TASKS: dict[str, dict[str, Any]] = {
    "health-check": {},
    "clean-recipes": {"dry_run": True},
    "cleanup-duplicates": {"dry_run": True, "target": "taxonomy"},
}
ACTIVE = {"queued", "running"}

# Coverage dimensions that feed the score: things CookDex can help fix.
SCORE_DIMENSIONS = ("category", "tags", "ingredients", "yield")


def _is_preview(run: dict[str, Any]) -> bool:
    options = run.get("options") or {}
    return options.get("dry_run", True) is not False and not options.get("apply_cleanups")


def _latest(runs: list[dict[str, Any]], task_id: str, *, preview: bool | None = None) -> dict[str, Any] | None:
    for run in runs:  # newest first
        if run.get("task_id") != task_id or run.get("status") != "succeeded":
            continue
        if preview is not None and _is_preview(run) != preview:
            continue
        return run
    return None


def _summary(results: list[dict[str, Any]] | None, title: str) -> dict[str, Any]:
    for entry in results or []:
        summary = entry.get("summary")
        if isinstance(summary, dict) and summary.get("__title__") == title:
            return summary
    return {}


def _cleanup_items(results: list[dict[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
    """Planned cleanup items from a preview, by kind. Later entries win."""
    deletes: dict[str, dict[str, Any]] = {}
    renames: dict[str, dict[str, Any]] = {}
    for entry in results or []:
        for item in entry.get("items") or []:
            if not isinstance(item, dict) or item.get("status") != "planned" or not item.get("slug"):
                continue
            if entry.get("kind") == "recipe_delete":
                deletes[item["slug"]] = item
            elif entry.get("kind") == "recipe_rename":
                renames[item["slug"]] = item
    grouped: dict[str, list[dict[str, Any]]] = {"junk": [], "review": [], "duplicate": [], "rename": list(renames.values())}
    for item in deletes.values():
        grouped[item.get("group") if item.get("group") in grouped else "junk"].append(item)
    return grouped


def _quality_report(services: Services) -> dict[str, Any]:
    path = services.settings.config_root / "reports" / "quality_audit_report.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _score(coverage: dict[str, Any]) -> dict[str, Any] | None:
    parts = []
    for key in SCORE_DIMENSIONS:
        dim = coverage.get(key)
        if isinstance(dim, dict) and "pct_have" in dim:
            parts.append({"key": key, "percent": round(float(dim["pct_have"]))})
    if not parts:
        return None
    value = round(sum(p["percent"] for p in parts) / len(parts))
    if value >= 80:
        label = "In great shape"
    elif value >= 60:
        label = "In good shape"
    elif value >= 40:
        label = "In fair shape"
    else:
        label = "Needs attention"
    return {"value": value, "label": label, "parts": parts}


def _examples(items: list[dict[str, Any]], key: str = "name", limit: int = 3) -> list[str]:
    return [str(item.get(key) or item.get("slug")) for item in items[:limit]]


def build_library(services: Services) -> dict[str, Any]:
    runtime_env = build_runtime_env(services.state, services.cipher)
    connected = bool(runtime_env.get("MEALIE_URL", "").strip() and runtime_env.get("MEALIE_API_KEY", "").strip())
    runs = services.state.list_runs(limit=300)
    scanning = any(run.get("task_id") in SCAN_TASKS and run.get("status") in ACTIVE for run in runs)

    health = _latest(runs, "health-check")
    health_results = services.state.get_run_results(health["run_id"]) if health else None
    quality_summary = _summary(health_results, "Quality Audit")
    report = _quality_report(services)
    coverage = report.get("dimension_coverage") if isinstance(report.get("dimension_coverage"), dict) else {}

    findings: list[dict[str, Any]] = []

    # Cleanup findings come from the latest preview, unless a live cleanup ran
    # after it: then those items may already be gone, so ask for a new scan.
    preview = _latest(runs, "clean-recipes", preview=True)
    live = _latest(runs, "clean-recipes", preview=False)
    # ">=": runs started in the same clock tick (Windows timers are coarse)
    # count as stale, since showing findings a cleanup already acted on is worse.
    cleanup_stale = bool(preview and live and str(live.get("created_at")) >= str(preview.get("created_at")))
    if preview and not cleanup_stale:
        grouped = _cleanup_items(services.state.get_run_results(preview["run_id"]))
        review = {"type": "review", "run_id": preview["run_id"]}
        if grouped["junk"]:
            findings.append({
                "id": "not-recipes", "severity": "high", "count": len(grouped["junk"]),
                "title": "{n} entries aren't recipes", "title_one": "1 entry isn't a recipe",
                "detail": "No ingredients and no usable steps.",
                "examples": _examples(grouped["junk"]),
                "action": {**review, "groups": ["junk"], "label": "Review"},
            })
        if grouped["duplicate"]:
            findings.append({
                "id": "duplicates", "severity": "high", "count": len(grouped["duplicate"]),
                "title": "{n} duplicate recipes", "title_one": "1 duplicate recipe",
                "detail": "Same source as another recipe. The most complete copy is kept.",
                "examples": _examples(grouped["duplicate"]),
                "action": {**review, "groups": ["duplicate"], "label": "Review"},
            })
        if grouped["review"]:
            findings.append({
                "id": "your-call", "severity": "medium", "count": len(grouped["review"]),
                "title": "{n} entries might not be recipes", "title_one": "1 entry might not be a recipe",
                "detail": "They have some recipe content, so nothing is removed unless you choose to.",
                "examples": _examples(grouped["review"]),
                "action": {**review, "groups": ["review"], "label": "Decide"},
            })
        if grouped["rename"]:
            findings.append({
                "id": "names", "severity": "medium", "count": len(grouped["rename"]),
                "title": "{n} names look like web addresses", "title_one": "1 name looks like a web address",
                "detail": "Cleaned-up names are suggested. You can edit them first.",
                "examples": [f"{i.get('old_name')} → {i.get('new_name')}" for i in grouped["rename"][:2]],
                "action": {**review, "groups": ["rename"], "label": "Review"},
            })

    taxonomy = _latest(runs, "cleanup-duplicates", preview=True)
    if taxonomy:
        summary = _summary(services.state.get_run_results(taxonomy["run_id"]), "Tag & Category Duplicates")
        count = int(summary.get("Tags Merge Candidates") or 0) + int(summary.get("Categories Merge Candidates") or 0)
        if count:
            findings.append({
                "id": "taxonomy-duplicates", "severity": "medium", "count": count,
                "title": "{n} near-duplicate tags and categories", "title_one": "1 near-duplicate tag or category",
                "detail": "Like \"salads\" and \"Salad\". Merging moves their recipes to one spelling.",
                "examples": [],
                "action": {"type": "task", "task_id": "cleanup-duplicates", "options": {"target": "taxonomy"}, "label": "Merge"},
            })

    for key, task_id, title, title_one, detail, label in (
        ("category", "tag-categorize", "{n} recipes have no category", "1 recipe has no category",
         "Categories make recipes easy to browse in Mealie. Rules can suggest them from your tag names.", "Suggest"),
        ("ingredients", "ingredient-parse", "{n} recipes have ingredients that aren't linked to foods",
         "1 recipe has ingredients that aren't linked to foods",
         "Linked ingredients power Mealie's shopping lists and ingredient search.", "Parse"),
        ("yield", "yield-normalize", "{n} recipes are missing servings", "1 recipe is missing servings",
         "Servings let Mealie scale a recipe.", "Fill in"),
    ):
        dim = coverage.get(key) if isinstance(coverage, dict) else None
        missing = int((dim or {}).get("missing") or 0)
        if missing:
            findings.append({
                "id": f"missing-{key}", "severity": "low", "count": missing,
                "title": title, "title_one": title_one, "detail": detail, "examples": [],
                "action": {"type": "task", "task_id": task_id, "label": label},
            })

    total = int(quality_summary.get("Total Recipes") or (report.get("summary") or {}).get("total") or 0)
    return {
        "connected": connected,
        "scanning": scanning,
        "last_scanned_at": health.get("finished_at") if health else None,
        "needs_scan": health is None or preview is None or cleanup_stale,
        "recipes": total,
        "score": _score(coverage),
        "findings": findings,
    }


@router.get("/library")
def get_library(
    _session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    return build_library(services)


@router.post("/library/scan", status_code=202)
def scan_library(
    session: dict[str, Any] = Depends(require_editor_session),
    services: Services = Depends(require_services),
) -> dict[str, Any]:
    """Queue the read-only runs the Library is built from."""
    _scan_limiter.check(session["username"])
    runs = services.state.list_runs(limit=100)
    active = {run["task_id"]: run["run_id"] for run in runs if run.get("status") in ACTIVE}
    queued: dict[str, str] = {}
    for task_id, options in SCAN_TASKS.items():
        if task_id in active:
            queued[task_id] = active[task_id]
            continue
        run = services.runner.enqueue(task_id=task_id, options=dict(options), triggered_by=str(session["username"]))
        queued[task_id] = run["run_id"]
    return {"runs": queued}
