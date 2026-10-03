from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from ..organize_plan import validate_dependencies


@dataclass(frozen=True)
class OptionSpec:
    key: str
    label: str
    value_type: str
    default: Any = None
    required: bool = False
    dangerous: bool = False
    help_text: str = ""
    hidden_when: dict[str, Any] | list[dict[str, Any]] | None = None
    choices: list[dict[str, Any]] | None = None
    multi: bool = False
    advanced: bool = False
    option_group: str = ""


WORKFLOW_TASK = "workflow"


def policy_key(task_id: str, options: dict[str, Any] | None = None) -> str:
    """Where a run's unattended-change approval is kept.

    Jobs are approved per job. Automations are approved one by one, since
    each combines its own jobs and settings.
    """
    if task_id == WORKFLOW_TASK:
        spec = (options or {}).get("workflow")
        workflow_id = str(spec.get("id") or "") if isinstance(spec, dict) else ""
        return f"workflow:{workflow_id}"
    return task_id


# What each task needs from the recipe manager (see cookdex.providers).
# Tasks whose needs a backend can't meet are shown as unavailable.
TASK_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "clean-recipes": ("slugs",),
    "slug-repair": ("slugs",),
    "ingredient-parse": ("server_parser",),
    "yield-normalize": ("slugs",),
    "cleanup-duplicates": ("merge_terms", "merge_foods", "merge_units"),
    "reimport-recipes": ("import_url", "slugs"),
    "tag-categorize": ("tags", "categories"),
    "mealie-backup": ("backup",),
    "recipe-dredger": ("import_url",),
    "organize-apply": ("rename_terms", "merge_terms", "delete_terms"),
    "data-maintenance": ("slugs",),
}


@dataclass(frozen=True)
class TaskExecution:
    command: list[str]
    env: dict[str, str]
    dangerous_requested: bool
    pre_commands: list[list[str]] = field(default_factory=list)
    max_duration: int | None = None  # seconds; None = no limit


BuildFn = Callable[[dict[str, Any]], TaskExecution]


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    title: str
    description: str
    group: str = ""
    options: list[OptionSpec] = field(default_factory=list)
    build: BuildFn | None = None
    badges: list[str] = field(default_factory=list)  # e.g. ["ai"], ["db"], ["ai", "db"]
    # Hidden tasks run from other pages (such as Organize) and stay out of the
    # Tasks catalog, but still get run history, backups and safety checks.
    hidden: bool = False


def _py_module(module: str, *args: str) -> list[str]:
    return [sys.executable, "-m", module, *args]


def _bool_option(options: dict[str, Any], key: str, default: bool) -> bool:
    raw = options.get(key, default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        text = raw.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Option '{key}' must be boolean.")


def _str_option(options: dict[str, Any], key: str, default: str = "") -> str:
    raw = options.get(key, default)
    if raw is None:
        return default
    text = str(raw).strip()
    return text


def _int_option(options: dict[str, Any], key: str, default: int | None = None) -> int | None:
    if key not in options:
        return default
    raw = options.get(key)
    if raw is None or raw == "":
        return default
    return int(raw)


def _float_option(options: dict[str, Any], key: str, default: float | None = None) -> float | None:
    if key not in options:
        return default
    raw = options.get(key)
    if raw is None or raw == "":
        return default
    return float(raw)


def _common_env(options: dict[str, Any]) -> tuple[dict[str, str], bool]:
    dry_run = _bool_option(options, "dry_run", True)
    return {"DRY_RUN": "true" if dry_run else "false"}, (not dry_run)


def _validate_allowed(options: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(options) - allowed)
    if unknown:
        raise ValueError(f"Unsupported options: {', '.join(unknown)}")


def _submitted_values(spec: OptionSpec, raw: Any) -> list[str]:
    """Normalize a submitted option value to the list of values to check."""
    if spec.multi:
        items = raw if isinstance(raw, list) else str(raw).split(",")
    else:
        items = [raw]
    return [text for text in (str(item).strip() for item in items) if text]


def _validate_choices(definition: TaskDefinition, options: dict[str, Any]) -> None:
    """Reject option values outside the spec's declared choices.

    The choices list is also sent to the UI for rendering, but the UI is not
    the only caller — the API and saved schedules build executions directly,
    so the allowlist has to be enforced here.
    """
    for spec in definition.options:
        if not spec.choices or spec.key not in options:
            continue
        allowed = {str(choice.get("value", "")) for choice in spec.choices}
        for value in _submitted_values(spec, options[spec.key]):
            if value not in allowed:
                raise ValueError(f"Option '{spec.key}' has unsupported value '{value}'.")


# Mirrors the argparse `choices` on cookdex.recipe_categorizer and
# cookdex.data_maintenance so an invalid provider is rejected before a
# subprocess is spawned rather than failing mid-run.
_PROVIDER_CHOICES: list[dict[str, str]] = [
    {"value": "", "label": "Configured default"},
    {"value": "chatgpt", "label": "ChatGPT (OpenAI)"},
    {"value": "anthropic", "label": "Anthropic"},
    {"value": "ollama", "label": "Ollama (local)"},
]


_JUNK_REASON_CHOICES: list[dict[str, str]] = [
    {"value": "", "label": "All categories"},
    {"value": "how_to", "label": "How-to articles"},
    {"value": "listicle", "label": "Listicles / roundups"},
    {"value": "digest", "label": "Digest / weekly posts"},
    {"value": "keyword", "label": "High-risk keywords"},
    {"value": "utility", "label": "Utility pages"},
    {"value": "bad_instructions", "label": "Placeholder instructions"},
    {"value": "failed_scrape", "label": "Failed scrapes (no name / GUID)"},
    {"value": "no_ingredients", "label": "No ingredients"},
    {"value": "bad_scrape", "label": "Bad scrapes (garbled steps / collapsed ingredients)"},
]


# ---------------------------------------------------------------------------
# Build functions
# ---------------------------------------------------------------------------

def _backup_pre_command() -> list[str]:
    """Return the CLI command for the restore point taken before a change."""
    return _py_module("cookdex.mealie_backup", "--kind", "pre-change")


def _maybe_add_backup(execution: TaskExecution, options: dict[str, Any]) -> TaskExecution:
    """Wrap a writing execution with a pre-backup step unless backup_first is off.

    Read-only runs never back up. Writing runs back up by default, so a caller
    that omits the option still gets a restore point.
    """
    if not execution.dangerous_requested or not _bool_option(options, "backup_first", True):
        return execution
    return TaskExecution(
        command=execution.command,
        env=execution.env,
        dangerous_requested=execution.dangerous_requested,
        pre_commands=[_backup_pre_command()] + list(execution.pre_commands),
    )


_BACKUP_FIRST_OPTION = OptionSpec(
    "backup_first",
    "Backup First",
    "boolean",
    default=True,
    help_text="Create a Mealie backup before applying changes, so you can restore if something looks wrong. CookDex keeps the newest 10 of these.",
    hidden_when={"key": "dry_run", "value": True},
)


def _build_mealie_backup(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(options, {"prune", "prune_only", "keep"})
    keep = _int_option(options, "keep")
    prune_only = _bool_option(options, "prune_only", False)
    if keep is not None and keep < 1:
        raise ValueError("Option 'keep' must be at least 1.")
    if prune_only and keep is None:
        raise ValueError("Option 'keep' is required when prune_only is enabled.")

    cmd = _py_module("cookdex.mealie_backup")
    if prune_only and keep is not None:
        cmd.extend(["--prune-only", str(keep)])
    elif keep is not None:
        cmd.extend(["--prune", str(keep)])
    return TaskExecution(cmd, {}, dangerous_requested=(keep is not None))


def _build_tag_categorize(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(options, {"dry_run", "backup_first", "method", "provider", "use_db", "missing_targets", "recat", "max_recipes", "fill"})
    env, dangerous = _common_env(options)
    method = _str_option(options, "method", "both") or "both"

    recat = _bool_option(options, "recat", False)
    max_recipes = _int_option(options, "max_recipes")
    if max_recipes is not None and max_recipes < 1:
        raise ValueError("Option 'max_recipes' must be at least 1.")
    ai_limit = ["--max-recipes", str(max_recipes)] if max_recipes else []
    fill = (_str_option(options, "fill", "any") or "any").strip().lower()
    if fill not in {"any", "categories", "tags", "tools"}:
        raise ValueError("Option 'fill' must be any, categories, tags or tools.")
    if fill != "any":
        ai_limit += [f"--missing-{fill}"]

    if method == "both":
        cmd = _py_module("cookdex.tag_pipeline")
        provider = _str_option(options, "provider", "")
        use_db = _bool_option(options, "use_db", False)
        missing_targets = (_str_option(options, "missing_targets", "skip") or "skip").strip().lower()
        if missing_targets not in {"skip", "create"}:
            raise ValueError("Option 'missing_targets' must be 'skip' or 'create'.")
        if provider:
            cmd.extend(["--provider", provider])
        if use_db:
            cmd.append("--use-db")
        cmd.extend(["--missing-targets", missing_targets])
        if recat:
            cmd.append("--recat")
        cmd.extend(ai_limit)
    elif method == "rules":
        cmd = _py_module("cookdex.rule_tagger", "--from-taxonomy")
        dry_run = _bool_option(options, "dry_run", True)
        use_db = _bool_option(options, "use_db", False)
        missing_targets = (_str_option(options, "missing_targets", "skip") or "skip").strip().lower()
        if missing_targets not in {"skip", "create"}:
            raise ValueError("Option 'missing_targets' must be 'skip' or 'create'.")
        if not dry_run:
            cmd.append("--apply")
        if use_db:
            cmd.append("--use-db")
        cmd.extend(["--missing-targets", missing_targets])
    else:
        provider = _str_option(options, "provider", "")
        cmd = _py_module("cookdex.recipe_categorizer")
        if provider:
            cmd.extend(["--provider", provider])
        if recat:
            cmd.append("--recat")
        cmd.extend(ai_limit)

    return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)


def _build_health_check(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(options, {"scope_quality", "scope_taxonomy", "use_db", "nutrition_sample"})
    env = {"DRY_RUN": "true"}
    dangerous = False
    scope_quality = _bool_option(options, "scope_quality", True)
    scope_taxonomy = _bool_option(options, "scope_taxonomy", True)
    use_db = _bool_option(options, "use_db", False)
    nutrition_sample = _int_option(options, "nutrition_sample")

    if scope_quality and scope_taxonomy:
        cmd = _py_module("cookdex.data_maintenance", "--stages", "quality,audit")
        if use_db:
            cmd.append("--use-db")
        if nutrition_sample is not None:
            cmd.extend(["--nutrition-sample", str(nutrition_sample)])
        return TaskExecution(cmd, env, dangerous_requested=dangerous)

    if scope_quality:
        cmd = _py_module("cookdex.recipe_quality_audit")
        if nutrition_sample is not None:
            cmd.extend(["--nutrition-sample", str(nutrition_sample)])
        if use_db:
            cmd.append("--use-db")
        return TaskExecution(cmd, env, dangerous_requested=dangerous)

    if scope_taxonomy:
        return TaskExecution(_py_module("cookdex.audit_taxonomy"), env, dangerous_requested=dangerous)

    raise ValueError("At least one audit scope must be selected.")


def _build_ingredient_parse(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(
        options,
        {
            "dry_run",
            "confidence_threshold",
            "max_recipes",
            "after_slug",
            "parsers",
            "force_parser",
            "page_size",
            "delay_seconds",
            "timeout_seconds",
            "retries",
            "backoff_seconds",
            "no_cache",
            "backup_first",
        },
    )
    env, dangerous = _common_env(options)
    cmd = _py_module("cookdex.ingredient_parser")
    confidence_pct = _int_option(options, "confidence_threshold")
    max_recipes = _int_option(options, "max_recipes")
    after_slug = _str_option(options, "after_slug", "")
    parsers = _str_option(options, "parsers", "")
    force_parser = _str_option(options, "force_parser", "")
    page_size = _int_option(options, "page_size")
    delay_seconds = _float_option(options, "delay_seconds")
    timeout_seconds = _int_option(options, "timeout_seconds")
    retries = _int_option(options, "retries")
    backoff_seconds = _float_option(options, "backoff_seconds")

    if confidence_pct is not None:
        cmd.extend(["--conf", str(confidence_pct / 100.0)])
    if max_recipes is not None:
        cmd.extend(["--max", str(max_recipes)])
    if after_slug:
        cmd.extend(["--after-slug", after_slug])
    if parsers:
        cmd.extend(["--parsers", parsers])
    if force_parser:
        cmd.extend(["--force-parser", force_parser])
    if page_size is not None:
        cmd.extend(["--page-size", str(page_size)])
    if delay_seconds is not None:
        cmd.extend(["--delay", str(delay_seconds)])
    if timeout_seconds is not None:
        cmd.extend(["--timeout", str(timeout_seconds)])
    if retries is not None:
        cmd.extend(["--retries", str(retries)])
    if backoff_seconds is not None:
        cmd.extend(["--backoff", str(backoff_seconds)])
    if _bool_option(options, "no_cache", False):
        cmd.append("--no-cache")

    return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)


def _build_cleanup_duplicates(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(options, {"dry_run", "backup_first", "target"})
    env, dangerous = _common_env(options)
    dry_run = _bool_option(options, "dry_run", True)
    target = _str_option(options, "target", "both") or "both"

    if target == "both":
        cmd = _py_module("cookdex.data_maintenance", "--stages", "foods,units")
        if not dry_run:
            cmd.append("--apply-cleanups")
        return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)

    if target == "foods":
        cmd = _py_module("cookdex.foods_manager", "cleanup")
    elif target == "units":
        cmd = _py_module("cookdex.units_manager", "cleanup")
    else:
        # Tags and categories use Mealie's native organizer merge (v3.25+).
        kinds = "tags,categories" if target == "taxonomy" else target
        cmd = _py_module("cookdex.taxonomy_duplicates", "cleanup", "--kinds", kinds)
    if not dry_run:
        cmd.append("--apply")

    return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)


def _build_data_maintenance(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(
        options,
        {
            "dry_run",
            "backup_first",
            "stages",
            "continue_on_error",
            "apply_cleanups",
            "provider",
            "use_db",
            "nutrition_sample",
            "reason",
            "force_all",
            "confidence_threshold",
            "max_recipes",
            "after_slug",
            "parsers",
            "force_parser",
            "page_size",
            "delay_seconds",
            "timeout_seconds",
            "retries",
            "backoff_seconds",
            "no_cache",
            "taxonomy_mode",  # for the retired taxonomy stage; accepted so old schedules still run
        },
    )
    env, dangerous = _common_env(options)
    cmd = _py_module("cookdex.data_maintenance")
    stages = options.get("stages")
    continue_on_error = _bool_option(options, "continue_on_error", False)
    apply_cleanups = _bool_option(options, "apply_cleanups", False)
    provider = _str_option(options, "provider", "")
    use_db = _bool_option(options, "use_db", False)
    nutrition_sample = _int_option(options, "nutrition_sample")
    junk_reason = _str_option(options, "reason", "")
    names_force_all = _bool_option(options, "force_all", False)
    confidence_pct = _int_option(options, "confidence_threshold")
    parse_max = _int_option(options, "max_recipes")
    parse_after_slug = _str_option(options, "after_slug", "")
    parse_parsers = _str_option(options, "parsers", "")
    parse_force_parser = _str_option(options, "force_parser", "")
    parse_page_size = _int_option(options, "page_size")
    parse_delay = _float_option(options, "delay_seconds")
    parse_timeout = _int_option(options, "timeout_seconds")
    parse_retries = _int_option(options, "retries")
    parse_backoff = _float_option(options, "backoff_seconds")
    if stages:
        if isinstance(stages, list):
            stage_value = ",".join(str(item).strip() for item in stages if str(item).strip())
        else:
            stage_value = str(stages).strip()
        if stage_value:
            cmd.extend(["--stages", stage_value])
    if continue_on_error:
        cmd.append("--continue-on-error")
    if apply_cleanups:
        cmd.append("--apply-cleanups")
    if provider:
        cmd.extend(["--provider", provider])
    if use_db:
        cmd.append("--use-db")
    if nutrition_sample is not None:
        cmd.extend(["--nutrition-sample", str(nutrition_sample)])
    if junk_reason:
        cmd.extend(["--junk-reason", junk_reason])
    if names_force_all:
        cmd.append("--names-force-all")
    if confidence_pct is not None:
        cmd.extend(["--parse-conf", str(confidence_pct / 100.0)])
    if parse_max is not None:
        cmd.extend(["--parse-max", str(parse_max)])
    if parse_after_slug:
        cmd.extend(["--parse-after-slug", parse_after_slug])
    if parse_parsers:
        cmd.extend(["--parse-parsers", parse_parsers])
    if parse_force_parser:
        cmd.extend(["--parse-force-parser", parse_force_parser])
    if parse_page_size is not None:
        cmd.extend(["--parse-page-size", str(parse_page_size)])
    if parse_delay is not None:
        cmd.extend(["--parse-delay", str(parse_delay)])
    if parse_timeout is not None:
        cmd.extend(["--parse-timeout", str(parse_timeout)])
    if parse_retries is not None:
        cmd.extend(["--parse-retries", str(parse_retries)])
    if parse_backoff is not None:
        cmd.extend(["--parse-backoff", str(parse_backoff)])
    if _bool_option(options, "no_cache", False):
        cmd.append("--parse-no-cache")
    return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=(dangerous or apply_cleanups)), options)


_MAX_PLAN_BYTES = 256_000


def _apply_plan_env(options: dict[str, Any]) -> dict[str, str]:
    """Validate a reviewed-changes plan and pass it to the task modules.

    Shape: {"dedup": {"delete": [slug]}, "junk": {"delete": [slug]},
    "names": {"rename": {slug: {"from": old, "to": new}}}}. See
    cookdex.reporting.load_apply_plan for how modules apply it.
    """
    raw = options.get("plan")
    if raw is None or raw == "":
        return {}
    plan = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(plan, dict):
        raise ValueError("Option 'plan' must be an object.")
    unknown = set(plan) - {"dedup", "junk", "names"}
    if unknown:
        raise ValueError(f"Option 'plan' has unknown sections: {', '.join(sorted(unknown))}")
    for section in ("dedup", "junk"):
        slugs = (plan.get(section) or {}).get("delete", [])
        if not isinstance(slugs, list) or not all(isinstance(slug, str) for slug in slugs):
            raise ValueError(f"Option 'plan.{section}.delete' must be a list of recipe slugs.")
    renames = (plan.get("names") or {}).get("rename", {})
    if not isinstance(renames, dict) or not all(
        isinstance(change, dict) and isinstance(change.get("from"), str) and isinstance(change.get("to"), str)
        for change in renames.values()
    ):
        raise ValueError("Option 'plan.names.rename' must map slugs to {from, to} names.")
    encoded = json.dumps(plan, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > _MAX_PLAN_BYTES:
        raise ValueError("Too many changes in one plan. Apply them in smaller batches.")
    return {"COOKDEX_APPLY_PLAN": encoded}


# Tasks that pushed CookDex's own taxonomy copy to Mealie. Organize edits Mealie
# directly now; schedules that still use these are turned off with this reason.
RETIRED_TASKS: dict[str, str] = {
    "taxonomy-refresh": "Refresh Taxonomy was retired. Edit tags, categories, labels and tools in Organize, or import a taxonomy file there.",
    "cookbook-sync": "Cookbook Sync was retired. Edit cookbooks in Organize, or import a taxonomy file there.",
}

_ORGANIZE_OPS = {"rename", "merge", "delete", "create", "update"}
_ORGANIZE_KINDS = {"tags", "categories", "tools", "cookbooks", "labels", "foods", "units"}
_ORGANIZE_CREATE = {"tags", "categories", "tools", "cookbooks", "labels", "units"}
_ORGANIZE_UPDATE = {"cookbooks", "labels", "foods", "units"}


def _build_organize_apply(options: dict[str, Any]) -> TaskExecution:
    """Apply staged Organize changes (see cookdex.organize_apply)."""
    _validate_allowed(options, {"dry_run", "backup_first", "plan"})
    env, dangerous = _common_env(options)
    raw = options.get("plan")
    plan = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(plan, dict) or set(plan) != {"organize"}:
        raise ValueError("Option 'plan' must be an object with only an 'organize' section.")
    changes = (plan.get("organize") or {}).get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("Option 'plan.organize.changes' must be a non-empty list.")
    for change in changes:
        if not isinstance(change, dict) or change.get("op") not in _ORGANIZE_OPS or change.get("kind") not in _ORGANIZE_KINDS:
            raise ValueError("Each change needs a known op (rename, merge, delete, create, update) and kind.")
        if not change.get("id") or not isinstance(change.get("name"), str):
            raise ValueError("Each change needs the item's id and current name.")
        if change["op"] == "rename" and not str(change.get("to") or "").strip():
            raise ValueError("A rename needs a new name.")
        if change["op"] in {"create", "update"}:
            allowed = _ORGANIZE_CREATE if change["op"] == "create" else _ORGANIZE_UPDATE
            if change["kind"] not in allowed:
                raise ValueError(f"{change['kind'].capitalize()} can't be {change['op']}d here.")
            fields = change.get("to")
            if not isinstance(fields, dict) or not str(fields.get("name") or "").strip():
                raise ValueError(f"A new or edited {change['kind'][:-1]} needs a name.")
        if change["op"] == "merge" and not (change.get("target_id") and change.get("target_name")):
            raise ValueError("A merge needs the item to merge into.")
    validate_dependencies(changes)
    encoded = json.dumps(plan, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > _MAX_PLAN_BYTES:
        raise ValueError("Too many changes in one batch. Apply them in smaller batches.")
    env["COOKDEX_APPLY_PLAN"] = encoded
    return _maybe_add_backup(TaskExecution(_py_module("cookdex.organize_apply"), env, dangerous_requested=dangerous), options)


def _build_clean_recipes(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(options, {"dry_run", "backup_first", "run_dedup", "run_junk", "run_names", "reason", "force_all", "use_db", "plan"})
    env, dangerous = _common_env(options)
    env.update(_apply_plan_env(options))
    dry_run = _bool_option(options, "dry_run", True)
    run_dedup = _bool_option(options, "run_dedup", True)
    run_junk = _bool_option(options, "run_junk", True)
    run_names = _bool_option(options, "run_names", True)
    use_db = _bool_option(options, "use_db", False)

    if not any([run_dedup, run_junk, run_names]):
        raise ValueError("At least one operation must be selected.")

    # Single operation: call the module directly to preserve per-task options
    if run_dedup and not run_junk and not run_names:
        cmd = _py_module("cookdex.recipe_deduplicator")
        if not dry_run:
            cmd.append("--apply")
        if use_db:
            cmd.append("--use-db")
        return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)

    if run_junk and not run_dedup and not run_names:
        reason = _str_option(options, "reason", "")
        cmd = _py_module("cookdex.recipe_junk_filter")
        if not dry_run:
            cmd.append("--apply")
        if reason:
            cmd.extend(["--reason", reason])
        return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)

    if run_names and not run_dedup and not run_junk:
        force_all = _bool_option(options, "force_all", False)
        cmd = _py_module("cookdex.recipe_name_normalizer")
        if not dry_run:
            cmd.append("--apply")
        if force_all:
            cmd.append("--all")
        return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)

    # Multiple operations: route through data_maintenance
    stage_map = [
        (run_dedup, "dedup"),
        (run_junk, "junk"),
        (run_names, "names"),
    ]
    stages = ",".join(s for flag, s in stage_map if flag)
    cmd = _py_module("cookdex.data_maintenance", "--stages", stages)
    if not dry_run:
        cmd.append("--apply-cleanups")
    if use_db:
        cmd.append("--use-db")
    reason = _str_option(options, "reason", "")
    if reason and run_junk:
        cmd.extend(["--junk-reason", reason])
    force_all = _bool_option(options, "force_all", False)
    if force_all and run_names:
        cmd.append("--names-force-all")
    return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)


def _build_reimport_recipes(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(options, {"dry_run", "backup_first", "max_recipes", "slugs", "workers", "delay", "resume"})
    env, dangerous = _common_env(options)
    dry_run = _bool_option(options, "dry_run", True)
    max_recipes = _int_option(options, "max_recipes", 0)
    workers = _int_option(options, "workers", 2)
    delay = options.get("delay")
    resume = _bool_option(options, "resume", False)
    slugs = _str_option(options, "slugs", "")
    cmd = _py_module("cookdex.recipe_reimporter")
    if not dry_run:
        cmd.append("--apply")
    if max_recipes:
        cmd.extend(["--max", str(max_recipes)])
    if workers and workers != 2:
        cmd.extend(["--workers", str(min(workers, 4))])
    if delay is not None:
        cmd.extend(["--delay", str(float(delay))])
    if resume:
        cmd.append("--resume")
    if slugs:
        cmd.extend(["--slugs", slugs])
    return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)


def _build_slug_repair(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(options, {"dry_run", "use_db", "backup_first"})
    env, dangerous = _common_env(options)
    dry_run = _bool_option(options, "dry_run", True)
    use_db = _bool_option(options, "use_db", False)
    cmd = _py_module("cookdex.slug_repair")
    if not dry_run:
        cmd.append("--apply")
    if use_db:
        cmd.append("--use-db")
    return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)


def _build_yield_normalize(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(options, {"dry_run", "use_db", "backup_first"})
    env, dangerous = _common_env(options)
    dry_run = _bool_option(options, "dry_run", True)
    use_db = _bool_option(options, "use_db", False)
    cmd = _py_module("cookdex.yield_normalizer")
    if not dry_run:
        cmd.append("--apply")
    if use_db:
        cmd.append("--use-db")
    return _maybe_add_backup(TaskExecution(cmd, env, dangerous_requested=dangerous), options)


DREDGER_DEFAULT_MAX_TOTAL = 25


def _build_recipe_dredger(options: dict[str, Any]) -> TaskExecution:
    _validate_allowed(
        options,
        {"dry_run", "limit", "max_total", "depth", "no_cache", "import_workers",
         "precheck_duplicates", "language_filter", "max_retry_attempts"},
    )
    env, dangerous = _common_env(options)
    cmd = _py_module("cookdex.recipe_dredger")
    dry_run = _bool_option(options, "dry_run", True)
    if dry_run:
        cmd.append("--dry-run")
    limit = _int_option(options, "limit", 50)
    if limit is not None and limit != 50:
        cmd.extend(["--limit", str(limit)])
    # Missing means the default overall cap; 0 means no overall cap.
    max_total = _int_option(options, "max_total", DREDGER_DEFAULT_MAX_TOTAL)
    if max_total:
        cmd.extend(["--max-total", str(max_total)])
    depth = _int_option(options, "depth", 1000)
    if depth is not None and depth != 1000:
        cmd.extend(["--depth", str(depth)])
    if _bool_option(options, "no_cache", False):
        cmd.append("--no-cache")
    workers = _int_option(options, "import_workers", 2)
    if workers is not None and workers != 2:
        cmd.extend(["--workers", str(min(workers, 4))])
    if not _bool_option(options, "precheck_duplicates", True):
        cmd.append("--no-precheck")
    if not _bool_option(options, "language_filter", True):
        cmd.append("--no-language-filter")
    max_retries = _int_option(options, "max_retry_attempts", 3)
    if max_retries is not None and max_retries != 3:
        cmd.extend(["--max-retries", str(max_retries)])
    return TaskExecution(cmd, env, dangerous_requested=dangerous)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskDefinition] = {}
        self._register_defaults()
        self._register(
            TaskDefinition(
                task_id=WORKFLOW_TASK,
                title="Automation",
                description="Several jobs, one after another. Built on the Automations page.",
                group="Automations",
                options=[OptionSpec("workflow", "Automation", "object", help_text="The automation to run.")],
                build=self._build_workflow,
                hidden=True,
            )
        )

    @property
    def task_ids(self) -> list[str]:
        return sorted(self._tasks.keys())

    def get(self, task_id: str) -> TaskDefinition | None:
        return self._tasks.get(task_id)

    def _build_workflow(self, options: dict[str, Any]) -> TaskExecution:
        """Check every step now, so a broken automation fails when it's saved or started."""
        _validate_allowed(options, {"workflow"})
        spec = options.get("workflow")
        if not isinstance(spec, dict):
            raise ValueError("Option 'workflow' must describe the automation.")
        from ..workflow_runner import plan

        steps = plan(spec, self)
        apply = spec.get("mode") == "apply"
        writes = apply and any(step["execution"].dangerous_requested for step in steps)
        payload = {
            "id": str(spec.get("id") or ""),
            "name": str(spec.get("name") or "Automation"),
            "mode": "apply" if apply else "preview",
            "backup_first": bool(spec.get("backup_first", True)),
            "stop_on_error": bool(spec.get("stop_on_error", True)),
            "steps": [{"task_id": step["task_id"], "options": step["options"]} for step in steps],
        }
        return TaskExecution(
            _py_module("cookdex.workflow_runner"),
            {"COOKDEX_WORKFLOW": json.dumps(payload), "DRY_RUN": "false" if apply else "true"},
            dangerous_requested=writes,
        )

    def _register(self, definition: TaskDefinition) -> None:
        self._tasks[definition.task_id] = definition

    def _register_defaults(self) -> None:
        # ── Data Pipeline ────────────────────────────────────────────────
        self._register(
            TaskDefinition(
                task_id="data-maintenance",
                title="Data Maintenance Pipeline",
                group="Data Pipeline",
                # Replaced by automations, which run the jobs you pick in your
                # own order. Hidden, but schedules and automations that already
                # use it keep running.
                hidden=True,
                description="Run all maintenance stages in order: Dedup > Junk Filter > Name Normalize > Ingredient Parse > Foods Cleanup > Units Cleanup > Categorize > Yield Normalize > Quality Audit > Taxonomy Audit. Select specific stages to run a subset.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Preview changes without writing anything."),
                    _BACKUP_FIRST_OPTION,
                    OptionSpec(
                        "stages",
                        "Stages",
                        "string",
                        help_text="Select stages to run. Leave all unselected to run the full pipeline.",
                        multi=True,
                        choices=[
                            {"value": "dedup", "label": "Recipe Dedup"},
                            {"value": "junk", "label": "Junk Filter"},
                            {"value": "names", "label": "Name Normalize"},
                            {"value": "parse", "label": "Ingredient Parse"},
                            {"value": "foods", "label": "Foods Cleanup"},
                            {"value": "units", "label": "Units Cleanup"},
                            {"value": "categorize", "label": "Categorize (AI)"},
                            {"value": "yield", "label": "Yield Normalize"},
                            {"value": "quality", "label": "Quality Audit"},
                            {"value": "audit", "label": "Taxonomy Audit"},
                        ],
                    ),
                    OptionSpec(
                        "confidence_threshold",
                        "Confidence Threshold",
                        "integer",
                        default=70,
                        help_text="NLP confidence % (0–100). Lower values accept more NLP results and reduce AI fallback costs.",
                        advanced=True,
                        option_group="Ingredient Parse",
                    ),
                    OptionSpec(
                        "max_recipes",
                        "Max Recipes",
                        "integer",
                        help_text="Limit ingredient parsing to at most N recipes.",
                        advanced=True,
                        option_group="Ingredient Parse",
                    ),
                    OptionSpec(
                        "no_cache",
                        "Bypass Parse Cache",
                        "boolean",
                        default=False,
                        help_text="Ignore the scan cache and reprocess all unparsed recipes.",
                        advanced=True,
                        option_group="Ingredient Parse",
                    ),
                    OptionSpec(
                        "reason",
                        "Junk Category",
                        "string",
                        help_text="Limit junk filtering to one category.",
                        choices=_JUNK_REASON_CHOICES,
                        advanced=True,
                        option_group="Junk Filter",
                    ),
                    OptionSpec(
                        "force_all",
                        "Normalize All Names",
                        "boolean",
                        default=False,
                        help_text="Apply to all recipes, not just unformatted names.",
                        advanced=True,
                        option_group="Name Normalize",
                    ),
                    OptionSpec(
                        "provider",
                        "AI Provider",
                        "string",
                        help_text="Override categorizer provider. Leave blank for configured default.",
                        advanced=True,
                        option_group="Categorize",
                        choices=_PROVIDER_CHOICES,
                    ),
                    OptionSpec(
                        "nutrition_sample",
                        "Nutrition Sample",
                        "integer",
                        default=200,
                        help_text="Quality-stage nutrition sample size (skipped when the database is connected).",
                        advanced=True,
                        option_group="Quality & Yield",
                    ),
                    OptionSpec(
                        "continue_on_error",
                        "Continue on Error",
                        "boolean",
                        default=False,
                        help_text="Keep running remaining stages if one fails.",
                    ),
                    OptionSpec(
                        "apply_cleanups",
                        "Apply Cleanup Writes",
                        "boolean",
                        default=False,
                        dangerous=True,
                        help_text="Write deduplication and cleanup results. Only takes effect for cleanup stages.",
                        hidden_when={"key": "dry_run", "value": True},
                    ),
                ],
                build=_build_data_maintenance,
                badges=["ai"],
            )
        )
        self._register(
            TaskDefinition(
                task_id="recipe-dredger",
                title="Recipe Dredger",
                group="Data Pipeline",
                description="Discover and import recipes from the sources you choose on the Discover page. Crawls sitemaps, checks each page is a real recipe, filters by language, and imports to Mealie.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Preview what would be imported without writing anything."),
                    OptionSpec(
                        "max_total",
                        "New recipes per run",
                        "integer",
                        default=DREDGER_DEFAULT_MAX_TOTAL,
                        help_text=(
                            "A run stops after this many new recipes, from all your sources together, so each batch "
                            "stays easy to look over. Enter 0 for no limit."
                        ),
                    ),
                    OptionSpec(
                        "limit",
                        "From one site, at most",
                        "integer",
                        default=50,
                        help_text="Keeps one site from filling a run on its own. Enter 0 for no limit.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "depth",
                        "Scan Depth",
                        "integer",
                        default=1000,
                        help_text="Maximum URLs to scan per site sitemap.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "no_cache",
                        "Force Fresh Crawl",
                        "boolean",
                        default=False,
                        help_text="Ignore cached sitemaps and re-crawl everything.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "import_workers",
                        "Import Workers",
                        "integer",
                        default=2,
                        help_text="Concurrent import threads (1-4). More is faster but heavier on Mealie.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "precheck_duplicates",
                        "Pre-check Duplicates",
                        "boolean",
                        default=True,
                        help_text="Fetch existing Mealie recipes first to skip duplicates before importing.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "language_filter",
                        "Language Filter",
                        "boolean",
                        default=True,
                        help_text="Skip recipes that don't match the configured target language.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "max_retry_attempts",
                        "Max Retries",
                        "integer",
                        default=3,
                        help_text="Retry transient failures up to this many times before permanently rejecting.",
                        advanced=True,
                    ),
                ],
                build=_build_recipe_dredger,
            )
        )

        self._register(
            TaskDefinition(
                task_id="mealie-backup",
                title="Mealie Backup",
                group="Data Pipeline",
                description="Create a Mealie backup via the admin API. Optionally delete older backups this task made, keeping the newest N. Backups you make in Mealie are never deleted.",
                options=[
                    OptionSpec(
                        "keep",
                        "Keep Newest",
                        "integer",
                        help_text="After creating a backup, delete older backups this task made, keeping this many. Backups made in Mealie or before a change are never touched. Leave blank to keep all.",
                    ),
                    OptionSpec(
                        "prune_only",
                        "Prune Only",
                        "boolean",
                        default=False,
                        help_text="Skip backup creation and only delete older backups this task made.",
                    ),
                ],
                build=_build_mealie_backup,
            )
        )

        # ── Actions ──────────────────────────────────────────────────────
        self._register(
            TaskDefinition(
                task_id="clean-recipes",
                title="Clean Recipe Library",
                group="Actions",
                description="Remove duplicates, filter out junk content, and normalize messy import names — select which operations to run.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Preview changes without writing anything."),
                    _BACKUP_FIRST_OPTION,
                    OptionSpec(
                        "run_dedup",
                        "Remove Duplicates",
                        "boolean",
                        default=True,
                        help_text="Find recipes with the same source URL and delete the copies, keeping the best version.",
                    ),
                    OptionSpec(
                        "run_junk",
                        "Filter Junk",
                        "boolean",
                        default=True,
                        help_text="Detect and remove non-recipe content: listicles, how-to articles, digest posts, and placeholder instructions.",
                    ),
                    OptionSpec(
                        "run_names",
                        "Normalize Names",
                        "boolean",
                        default=True,
                        help_text="Clean up recipe names derived from URL slugs — turns 'how-to-make-chicken-pasta-recipe' into 'Chicken Pasta'.",
                    ),
                    OptionSpec(
                        "reason",
                        "Junk Filter Category",
                        "string",
                        help_text="Only scan for a specific junk category. Leave blank to check all.",
                        hidden_when={"key": "run_junk", "value": False},
                        choices=_JUNK_REASON_CHOICES,
                        advanced=True,
                    ),
                    OptionSpec(
                        "force_all",
                        "Normalize All Names",
                        "boolean",
                        default=False,
                        help_text="Apply name normalization to all recipes, not just lowercase/unformatted names.",
                        hidden_when={"key": "run_names", "value": False},
                        advanced=True,
                    ),
                ],
                build=_build_clean_recipes,
            )
        )
        self._register(
            TaskDefinition(
                task_id="slug-repair",
                title="Repair Recipe Slugs",
                group="Actions",
                description="Find recipes whose web address (slug) no longer matches their name, and fix them. Older Mealie versions refuse edits to these recipes.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Only list the recipes that would change."),
                    _BACKUP_FIRST_OPTION,
                ],
                build=_build_slug_repair,
            )
        )
        self._register(
            TaskDefinition(
                task_id="ingredient-parse",
                title="Ingredient Parser",
                group="Actions",
                description="Run NLP parsing on recipe ingredients to extract food, unit, and quantity from raw text. When confidence is below the threshold, parsing falls back to an AI processor.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Preview changes without writing anything."),
                    _BACKUP_FIRST_OPTION,
                    OptionSpec(
                        "max_recipes",
                        "Max Recipes",
                        "integer",
                        help_text="Limit parsing to at most N recipes. Leave blank to parse all candidates.",
                    ),
                    OptionSpec(
                        "no_cache",
                        "Bypass Cache",
                        "boolean",
                        default=False,
                        help_text="Ignore the scan cache and reprocess all unparsed recipes.",
                    ),
                    OptionSpec(
                        "confidence_threshold",
                        "Confidence Threshold",
                        "integer",
                        default=70,
                        help_text="Minimum confidence % (0–100) to accept an NLP parse result. Results below this threshold fall back to AI parsing.",
                        advanced=True,
                    ),
                ],
                build=_build_ingredient_parse,
                badges=["ai"],
            )
        )
        self._register(
            TaskDefinition(
                task_id="yield-normalize",
                title="Yield Normalizer",
                group="Actions",
                description="Fill missing yield text from servings count, or parse yield text to set numeric servings.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Preview changes without writing anything."),
                    _BACKUP_FIRST_OPTION,
                ],
                build=_build_yield_normalize,
            )
        )
        self._register(
            TaskDefinition(
                task_id="cleanup-duplicates",
                title="Clean Up Duplicates",
                group="Actions",
                description="Find and merge duplicate food, unit, tag, or category entries — e.g. 'garlic' and 'Garlic Clove', 'tsp' / 'teaspoon' / 'Teaspoon', or 'Gluten-Free' / 'gluten free'.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Preview changes without writing anything."),
                    _BACKUP_FIRST_OPTION,
                    OptionSpec(
                        "target",
                        "Target",
                        "string",
                        default="both",
                        help_text=(
                            "Which lookup table to deduplicate. Tags and categories are merged with "
                            "Mealie's merge endpoint (Mealie v3.25+), which moves their recipes to the "
                            "most-used spelling and deletes the others."
                        ),
                        choices=[
                            {"value": "both", "label": "Foods & Units"},
                            {"value": "foods", "label": "Foods only"},
                            {"value": "units", "label": "Units only"},
                            {"value": "taxonomy", "label": "Tags & Categories"},
                            {"value": "tags", "label": "Tags only"},
                            {"value": "categories", "label": "Categories only"},
                        ],
                    ),
                ],
                build=_build_cleanup_duplicates,
            )
        )

        self._register(
            TaskDefinition(
                task_id="reimport-recipes",
                title="Re-import Recipes",
                group="Actions",
                description="Re-scrape recipes from their original URLs. Overwrites content but preserves tags, categories, and favorites. Strips parsed ingredient links for re-parsing.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Preview which recipes would be reimported."),
                    _BACKUP_FIRST_OPTION,
                    OptionSpec(
                        "max_recipes",
                        "Max Recipes",
                        "integer",
                        help_text="Limit reimport to at most N recipes. Leave blank for all.",
                    ),
                    OptionSpec(
                        "workers",
                        "Workers",
                        "integer",
                        default=2,
                        help_text="Concurrent scrape workers (1–4). More is faster but heavier on Mealie.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "delay",
                        "Delay (seconds)",
                        "number",
                        default=0.5,
                        help_text="Seconds between requests per worker. Lower is faster but risks overloading Mealie.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "resume",
                        "Resume",
                        "boolean",
                        default=False,
                        help_text="Skip recipes already reimported in the previous run.",
                        advanced=True,
                    ),
                    OptionSpec(
                        "slugs",
                        "Specific Slugs",
                        "string",
                        help_text="Comma-separated list of recipe slugs to reimport. Leave blank for all eligible recipes.",
                        advanced=True,
                    ),
                ],
                build=_build_reimport_recipes,
            )
        )

        # ── Organizers ───────────────────────────────────────────────────
        self._register(
            TaskDefinition(
                task_id="tag-categorize",
                title="Tag & Categorize Recipes",
                group="Organizers",
                description="Assign categories, tags, and tools to recipes. Both runs rules first (free, fast) then AI to fill gaps. Rules Only needs no AI provider. AI Only skips the rules layer.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Preview changes without writing anything."),
                    _BACKUP_FIRST_OPTION,
                    OptionSpec(
                        "method",
                        "Method",
                        "string",
                        default="both",
                        help_text="Both runs rules first then AI. Rules Only works without any AI provider. AI Only skips name-matching rules.",
                        choices=[
                            {"value": "both", "label": "Both (recommended)"},
                            {"value": "rules", "label": "Rules Only"},
                            {"value": "ai", "label": "AI Only"},
                        ],
                    ),
                    OptionSpec(
                        "fill",
                        "What to Fill In",
                        "string",
                        default="any",
                        help_text="Which recipes the AI looks at: any recipe missing something, or only recipes missing categories, tags or tools.",
                        hidden_when={"key": "method", "value": "rules"},
                        choices=[
                            {"value": "any", "label": "Anything missing"},
                            {"value": "categories", "label": "Missing categories"},
                            {"value": "tags", "label": "Missing tags"},
                            {"value": "tools", "label": "Missing tools"},
                        ],
                    ),
                    OptionSpec(
                        "max_recipes",
                        "Try on at Most",
                        "integer",
                        help_text="Only send this many recipes to the AI, to see its suggestions (and what it costs) before a full run. Leave blank for all.",
                        hidden_when={"key": "method", "value": "rules"},
                    ),
                    OptionSpec(
                        "recat",
                        "Re-categorize All",
                        "boolean",
                        default=False,
                        help_text="Re-process every recipe, even those that already have categories/tags/tools assigned.",
                        hidden_when={"key": "method", "value": "rules"},
                    ),
                    OptionSpec(
                        "provider",
                        "AI Provider",
                        "string",
                        help_text="Override the AI provider. Leave blank to use the configured default.",
                        hidden_when={"key": "method", "value": "rules"},
                        choices=_PROVIDER_CHOICES,
                    ),
                    OptionSpec(
                        "missing_targets",
                        "Missing Target Handling",
                        "string",
                        default="skip",
                        help_text="When a rule points to a tag/category/tool that does not exist in current taxonomy, skip it (recommended) or create it automatically.",
                        hidden_when={"key": "method", "value": "ai"},
                        choices=[
                            {"value": "skip", "label": "Skip Missing Targets"},
                            {"value": "create", "label": "Create Missing Targets"},
                        ],
                    ),
                ],
                build=_build_tag_categorize,
                badges=["ai"],
            )
        )
        self._register(
            TaskDefinition(
                task_id="organize-apply",
                title="Apply Organize Changes",
                group="Organizers",
                description="Rename, merge, and delete tags, categories, and tools staged on the Organize page.",
                options=[
                    OptionSpec("dry_run", "Dry Run", "boolean", default=True, help_text="Check the changes without writing anything."),
                    _BACKUP_FIRST_OPTION,
                ],
                build=_build_organize_apply,
                hidden=True,
            )
        )

        # ── Audits ───────────────────────────────────────────────────────
        self._register(
            TaskDefinition(
                task_id="health-check",
                title="Health Check",
                group="Audits",
                description="Run diagnostic audits on your recipe library and taxonomy — surface missing metadata, unused entries, and duplicates.",
                options=[
                    OptionSpec(
                        "scope_quality",
                        "Recipe Quality",
                        "boolean",
                        default=True,
                        help_text="Score all recipes on completeness: categories, tags, tools, ingredients, cook time, yield, and nutrition.",
                    ),
                    OptionSpec(
                        "scope_taxonomy",
                        "Taxonomy",
                        "boolean",
                        default=True,
                        help_text="Scan taxonomy for unused entries, duplicate names, and recipes missing categories or tags.",
                    ),
                    OptionSpec(
                        "nutrition_sample",
                        "Nutrition Sample Size",
                        "integer",
                        default=200,
                        help_text="Number of recipes to sample for nutrition coverage estimate (skipped when the database is connected).",
                        hidden_when={"key": "scope_quality", "value": False},
                        advanced=True,
                    ),
                ],
                build=_build_health_check,
            )
        )

    def build_execution(self, task_id: str, options: dict[str, Any] | None = None) -> TaskExecution:
        definition = self._tasks.get(task_id)
        if definition is None or definition.build is None:
            raise KeyError(f"Unknown task '{task_id}'.")
        payload = options or {}
        if not isinstance(payload, dict):
            raise ValueError("Task options must be a JSON object.")
        _validate_choices(definition, payload)
        return definition.build(payload)

    def describe_tasks(self) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for task_id in sorted(self._tasks):
            task = self._tasks[task_id]
            payload.append(
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "description": task.description,
                    "group": task.group,
                    "options": [
                        {
                            "key": option.key,
                            "label": option.label,
                            "type": option.value_type,
                            "default": option.default,
                            "required": option.required,
                            "dangerous": option.dangerous,
                            "help_text": option.help_text,
                            "hidden_when": option.hidden_when,
                            "choices": option.choices,
                            "multi": option.multi,
                            "advanced": option.advanced,
                            "option_group": option.option_group,
                        }
                        for option in task.options
                    ],
                    "badges": list(task.badges),
                    "hidden": task.hidden,
                    "requires": list(TASK_REQUIREMENTS.get(task.task_id, ())),
                }
            )
        return payload
