from cookdex.webui_server.tasks import TaskRegistry


def test_registry_defaults_to_dry_run_for_parser():
    registry = TaskRegistry()
    execution = registry.build_execution("ingredient-parse", {})
    assert execution.env["DRY_RUN"] == "true"
    assert execution.dangerous_requested is False


def test_registry_marks_dry_run_false_as_dangerous():
    registry = TaskRegistry()
    execution = registry.build_execution("cleanup-duplicates", {"dry_run": False})
    assert execution.dangerous_requested is True


def test_registry_rejects_unknown_options():
    registry = TaskRegistry()
    try:
        registry.build_execution("tag-categorize", {"unknown": "value"})
    except ValueError as exc:
        assert "Unsupported options" in str(exc)
    else:
        assert False, "Expected ValueError for unsupported options."


def test_live_runs_back_up_first_by_default():
    registry = TaskRegistry()
    execution = registry.build_execution("clean-recipes", {"dry_run": False})
    assert execution.dangerous_requested is True
    assert len(execution.pre_commands) == 1


def test_previews_never_back_up_even_when_requested():
    registry = TaskRegistry()
    execution = registry.build_execution("clean-recipes", {"dry_run": True, "backup_first": True})
    assert execution.pre_commands == []


def test_live_backup_can_be_turned_off():
    registry = TaskRegistry()
    execution = registry.build_execution("clean-recipes", {"dry_run": False, "backup_first": False})
    assert execution.pre_commands == []


def test_backup_first_option_defaults_on():
    registry = TaskRegistry()
    task = next(item for item in registry.describe_tasks() if item["task_id"] == "clean-recipes")
    backup = next(option for option in task["options"] if option["key"] == "backup_first")
    assert backup["default"] is True


def test_clean_recipes_passes_reviewed_plan_to_modules():
    import json

    registry = TaskRegistry()
    plan = {"dedup": {"delete": ["guacamole-1"]}, "names": {"rename": {"banana-bread-2": {"from": "banana-bread-2", "to": "Banana Bread"}}}}
    execution = registry.build_execution("clean-recipes", {"dry_run": False, "plan": plan})
    assert json.loads(execution.env["COOKDEX_APPLY_PLAN"]) == plan


def test_clean_recipes_rejects_malformed_plan():
    registry = TaskRegistry()
    for bad in ({"junk": {"delete": "all"}}, {"everything": {}}, {"names": {"rename": {"a": "b"}}}):
        try:
            registry.build_execution("clean-recipes", {"dry_run": False, "plan": bad})
        except ValueError:
            continue
        assert False, f"Expected ValueError for {bad}"


def test_url_and_servings_repairs_back_up_before_live_changes():
    for task in ('slug-repair', 'yield-normalize'):
        registry = TaskRegistry()
        assert registry.build_execution(task, {'dry_run': False}).pre_commands
        assert not registry.build_execution(task, {'dry_run': True}).pre_commands
        assert not registry.build_execution(task, {'dry_run': False, 'backup_first': False}).pre_commands
