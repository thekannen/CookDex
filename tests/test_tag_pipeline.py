from __future__ import annotations

from cookdex.tag_pipeline import build_parser


def test_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.provider is None
    assert args.skip_ai is False
    assert args.skip_rules is False
    assert args.use_db is False
    assert args.missing_targets == "skip"
    assert args.config == ""


def test_parser_skip_ai_flag() -> None:
    args = build_parser().parse_args(["--skip-ai"])
    assert args.skip_ai is True


def test_parser_skip_rules_flag() -> None:
    args = build_parser().parse_args(["--skip-rules"])
    assert args.skip_rules is True


def test_parser_provider_override() -> None:
    args = build_parser().parse_args(["--provider", "anthropic"])
    assert args.provider == "anthropic"


def test_parser_use_db_flag() -> None:
    args = build_parser().parse_args(["--use-db"])
    assert args.use_db is True


def test_parser_missing_targets_create() -> None:
    args = build_parser().parse_args(["--missing-targets", "create"])
    assert args.missing_targets == "create"


def test_ai_layer_is_skipped_without_credentials(monkeypatch, capsys) -> None:
    import subprocess

    from cookdex import tag_pipeline

    calls: list[list[str]] = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(tag_pipeline.subprocess, "run", fake_run)
    monkeypatch.setattr("sys.argv", ["tag_pipeline"])
    monkeypatch.setenv("CATEGORIZER_PROVIDER", "chatgpt")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert tag_pipeline.main() == 0
    assert len(calls) == 1  # rules layer only
    assert "AI step skipped" in capsys.readouterr().out


def test_ai_layer_runs_with_ready_provider(monkeypatch) -> None:
    import subprocess

    from cookdex import tag_pipeline

    calls: list[list[str]] = []
    monkeypatch.setattr(
        tag_pipeline.subprocess, "run", lambda cmd, check=False: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0)
    )
    monkeypatch.setattr("sys.argv", ["tag_pipeline"])
    monkeypatch.setenv("CATEGORIZER_PROVIDER", "chatgpt")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert tag_pipeline.main() == 0
    assert calls[-1][-2:] == ["--provider", "chatgpt"]
