"""Run an automation: several jobs, one after another, as one run.

The web UI's runner starts this module with the automation in the
``COOKDEX_WORKFLOW`` environment variable (JSON)::

    {"name": "...", "mode": "preview" | "apply", "backup_first": true,
     "stop_on_error": true, "steps": [{"task_id": "...", "options": {...}}]}

Each step is built exactly as if it were run on its own, then started as a
child process whose output goes straight to this run's log, so its progress
and results show up as usual. When the automation applies changes and backs
up first, one backup is made before the first step instead of one per step.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

from .reporting import emit_summary

WORKFLOW_ENV = "COOKDEX_WORKFLOW"
STEP_PREFIX = "[step] "
_MODE_KEYS = ("dry_run", "backup_first", "apply_cleanups")


def step_options(task, options: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    """A step's options with the automation's preview/apply setting applied."""
    keys = {option.key for option in task.options}
    result = {key: value for key, value in (options or {}).items() if key not in _MODE_KEYS}
    if "dry_run" in keys:
        result["dry_run"] = not apply
    if apply and "apply_cleanups" in keys:
        result["apply_cleanups"] = True
    if "backup_first" in keys:
        result["backup_first"] = False  # the automation backs up once, up front
    return result


def plan(spec: dict[str, Any], registry=None) -> list[dict[str, Any]]:
    """Build every step up front, so a bad step stops the run before anything changes."""
    if registry is None:
        from .webui_server.tasks import TaskRegistry

        registry = TaskRegistry()
    apply = spec.get("mode") == "apply"
    steps = []
    for index, step in enumerate(spec.get("steps") or [], 1):
        task_id = str(step.get("task_id") or "")
        task = registry.get(task_id)
        if task is None or task_id == "workflow":
            raise ValueError(f"Step {index}: unknown job '{task_id}'.")
        options = step_options(task, step.get("options") or {}, apply=apply)
        execution = registry.build_execution(task_id, options)
        steps.append({"index": index, "task_id": task_id, "title": task.title, "execution": execution, "options": options})
    if not steps:
        raise ValueError("This automation has no steps.")
    return steps


def _run(command: list[str], env: dict[str, str]) -> int:
    print(f"$ {' '.join(command)}", flush=True)
    return subprocess.run(command, env=env, check=False).returncode


def main() -> int:
    raw = os.environ.get(WORKFLOW_ENV, "")
    try:
        spec = json.loads(raw)
    except ValueError:
        print("[error] This run has no automation to run.", flush=True)
        return 2
    name = str(spec.get("name") or "Automation")
    apply = spec.get("mode") == "apply"
    stop_on_error = bool(spec.get("stop_on_error", True))
    try:
        steps = plan(spec)
    except (ValueError, KeyError) as exc:
        print(f"[error] {exc}", flush=True)
        return 2

    print(f"[start] {name}: {len(steps)} step(s), {'applying changes' if apply else 'preview only'}", flush=True)
    started = time.monotonic()
    base_env = dict(os.environ)
    base_env.pop(WORKFLOW_ENV, None)

    if apply and spec.get("backup_first", True) and any(step["execution"].dangerous_requested for step in steps):
        print("[info] Backing up Mealie before the first step.", flush=True)
        code = _run([sys.executable, "-m", "cookdex.mealie_backup", "--kind", "pre-change"], {**base_env, "DRY_RUN": "false"})
        if code != 0:
            print("[error] The backup didn't work, so no step ran.", flush=True)
            emit_summary({"__title__": name, "Steps": len(steps), "Finished": 0, "Failed": 0, "Stopped": "backup failed"})
            return code or 1

    finished = failed = 0
    failed_titles: list[str] = []
    for step in steps:
        execution = step["execution"]
        print(STEP_PREFIX + json.dumps({"index": step["index"], "total": len(steps), "task_id": step["task_id"], "title": step["title"]}), flush=True)
        env = {**base_env, **execution.env}
        code = 0
        for command in [*execution.pre_commands, execution.command]:
            code = _run(command, env)
            if code != 0:
                break
        if code == 0:
            finished += 1
            print(f"[done] Step {step['index']}: {step['title']}", flush=True)
            continue
        failed += 1
        failed_titles.append(step["title"])
        print(f"[error] Step {step['index']} ({step['title']}) didn't finish (exit {code}).", flush=True)
        if stop_on_error:
            remaining = len(steps) - step["index"]
            if remaining:
                print(f"[warn] Stopped here; {remaining} later step(s) didn't run.", flush=True)
            break

    summary: dict[str, Any] = {
        "__title__": name,
        "Steps": len(steps),
        "Finished": finished,
        "Failed": failed,
        "Elapsed": f"{time.monotonic() - started:.1f}s",
    }
    if failed_titles:
        summary["Failed Steps"] = ", ".join(failed_titles)
    emit_summary(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
