"""A clean exit is a complete success only when nothing needs attention."""
from __future__ import annotations

from pathlib import Path

from cookdex.webui_server.run_grading import grade_run


def _log(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "run.log"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_clean_run_has_nothing_to_report(tmp_path):
    log = _log(tmp_path, "[start] go\n[ok] done\n[retry] Retry 1/3 failed: timeout\n[skip] left unticked\n")
    assert grade_run(log, [{"items": [{"status": "applied"}, {"status": "skipped"}]}]) == {
        "errors": 0, "error_text": "", "warning_text": "",
    }


def test_logged_errors_fail_the_run(tmp_path):
    log = _log(tmp_path, "[error] couldn't save 'soup': 500\n[error] couldn't save 'stew': 500\n")
    outcome = grade_run(log, [])
    assert outcome["errors"] == 2
    assert outcome["error_text"] == "Finished, but reported 2 errors. First: couldn't save 'soup': 500"


def test_warnings_skips_with_a_reason_and_declared_warnings_need_attention(tmp_path):
    log = _log(tmp_path, "[warn] No classification returned for beans after fallback attempts.\n")
    results = [
        {"summary": {"__title__": "AI Categorizer", "__warning__": "1 recipe couldn't be classified."}},
        {"items": [{"status": "skipped", "error": "Another recipe is already called 'Plum Jam'."}, {"status": "error", "error": "500"}]},
    ]
    outcome = grade_run(log, results)
    assert outcome["errors"] == 0
    assert outcome["warning_text"] == (
        "1 recipe couldn't be classified. 2 changes were skipped or didn't go through. "
        "1 warning in the log. First: No classification returned for beans after fallback attempts."
    )


def test_a_missing_log_is_not_an_error(tmp_path):
    assert grade_run(tmp_path / "gone.log", None)["warning_text"] == ""


def test_runner_marks_runs_by_what_they_reported(tmp_path):
    from cookdex.webui_server.runner import RunQueueManager
    from cookdex.webui_server.state import StateStore

    state = StateStore(tmp_path / "state.db")
    state.initialize([])
    runner = RunQueueManager.__new__(RunQueueManager)
    runner.state = state
    for run_id, text in (("ok", "[ok] done\n"), ("warn", "[warn] Couldn't save the scan cache.\n"), ("err", "[error] boom\n")):
        log = _log(tmp_path / run_id, text) if (tmp_path / run_id).mkdir() is None else None
        state.create_run(run_id, "tag-categorize", {}, "admin", None, str(log))
        state.update_run_status(run_id, status="succeeded", finished_at="2026-11-26T10:00:00Z", exit_code=0)
        runner._grade_finished_run(run_id, [])
    assert state.get_run("ok")["status"] == "succeeded" and state.get_run("ok")["warning"] is None
    assert state.get_run("warn")["status"] == "succeeded"
    assert state.get_run("warn")["warning"] == "1 warning in the log. First: Couldn't save the scan cache."
    failed = state.get_run("err")
    assert failed["status"] == "failed" and failed["error"].startswith("Finished, but reported 1 error.")
