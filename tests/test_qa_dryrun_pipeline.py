from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "qa"
    / "run_task_dryrun_pipeline.py"
)
SPEC = importlib.util.spec_from_file_location("run_task_dryrun_pipeline", SCRIPT_PATH)
assert SPEC and SPEC.loader
PIPELINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PIPELINE
SPEC.loader.exec_module(PIPELINE)


def test_data_maintenance_variants_use_current_task_options() -> None:
    variants = [
        variant
        for variant in PIPELINE._build_variants()
        if variant.task_id == "data-maintenance"
    ]

    assert variants
    assert all("skip_ai" not in variant.options for variant in variants)


def test_health_check_variant_does_not_receive_dry_run(monkeypatch) -> None:
    captured_options: list[dict] = []

    class Registry:
        def describe_tasks(self):
            return [
                {
                    "task_id": "health-check",
                    "options": [{"key": "scope_quality"}],
                }
            ]

        def build_execution(self, _task_id: str, options: dict):
            captured_options.append(options)
            return SimpleNamespace(command=["python", "-c", ""], env={})

    monkeypatch.setattr(
        PIPELINE.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
        ),
    )
    variant = PIPELINE.Variant(
        task_id="health-check",
        label="health-check",
        options={"scope_quality": True},
    )

    status, _elapsed, _details = PIPELINE.run_variant(
        variant,
        Registry(),
        timeout=1,
    )

    assert status == "PASS"
    assert captured_options == [{"scope_quality": True}]


def test_unknown_variant_is_reported_as_a_build_failure() -> None:
    class Registry:
        def describe_tasks(self):
            return []

    variant = PIPELINE.Variant(
        task_id="removed-task",
        label="removed-task",
        options={},
    )

    status, _elapsed, details = PIPELINE.run_variant(
        variant,
        Registry(),
        timeout=1,
    )

    assert status == "FAIL"
    assert details.startswith("build error:")
