from __future__ import annotations

from pathlib import Path

from cookdex import mealie_backup


class FakeMealie:
    """/admin/backups with a clock, so each new backup is newer than the last."""

    def __init__(self, backups: list[tuple[str, str]]) -> None:
        self.backups = [{"name": name, "date": date, "size": "1 MB"} for name, date in backups]
        self.deleted: list[str] = []
        self.clock = 0

    def request_json(self, method, path, **kwargs):
        if (method, path) == ("GET", "/admin/backups"):
            return {"imports": [dict(b) for b in self.backups], "templates": []}
        if (method, path) == ("POST", "/admin/backups"):
            self.clock += 1
            name = f"mealie_v3.29.0_2026.10.0{self.clock}.03.00.00.zip"
            self.backups.append({"name": name, "date": f"2026-10-0{self.clock}T03:00:00Z", "size": "1 MB"})
            return {"message": "Backup created successfully"}
        if method == "DELETE" and path.startswith("/admin/backups/"):
            name = path.rsplit("/", 1)[1]
            self.deleted.append(name)
            self.backups = [b for b in self.backups if b["name"] != name]
            return {}
        raise AssertionError((method, path))


def _ledger(tmp_path: Path, entries: list[tuple[str, str]]) -> Path:
    path = tmp_path / "backup_ledger.json"
    mealie_backup.write_ledger(path, [{"name": n, "kind": k, "created_at": ""} for n, k in entries])
    return path


def test_prune_only_touches_backups_cookdex_made(tmp_path):
    nightly = [
        # Across a Mealie upgrade: sorting by name would call the v3.28 ones newest.
        ("mealie_v3.28.0_2026.09.28.03.00.00.zip", "2026-09-28T03:00:00Z"),
        ("mealie_v3.28.0_2026.09.29.03.00.00.zip", "2026-09-29T03:00:00Z"),
        ("mealie_v3.29.0_2026.09.30.03.00.00.zip", "2026-09-30T03:00:00Z"),
    ]
    mine = [
        ("mealie_v3.28.0_2026.09.01.12.00.00.zip", "2026-09-01T12:00:00Z"),  # made in Mealie by hand
        ("before-upgrade.zip", "2026-08-01T00:00:00Z"),  # uploaded; sorts first by name
    ]
    pre_change = [("mealie_v3.28.0_2026.09.27.10.00.00.zip", "2026-09-27T10:00:00Z")]
    client = FakeMealie(nightly + mine + pre_change)
    ledger = _ledger(tmp_path, [(n, "cookdex") for n, _ in nightly] + [(n, "pre-change") for n, _ in pre_change])

    deleted = mealie_backup.prune_backups(client, 2, ledger=ledger)

    assert deleted == 1
    assert client.deleted == ["mealie_v3.28.0_2026.09.28.03.00.00.zip"]  # the oldest nightly by date
    remaining = {b["name"] for b in client.backups}
    assert {n for n, _ in mine + pre_change} <= remaining
    assert "mealie_v3.28.0_2026.09.28.03.00.00.zip" not in {e["name"] for e in mealie_backup.read_ledger(ledger)}


def test_new_backups_are_recorded_and_pre_change_ones_trimmed_separately(tmp_path, monkeypatch):
    client = FakeMealie([("mealie_v3.28.0_2026.09.01.12.00.00.zip", "2026-09-01T12:00:00Z")])
    ledger = tmp_path / "backup_ledger.json"
    monkeypatch.setattr(mealie_backup, "PRE_CHANGE_KEEP", 2)

    assert mealie_backup.create_backup(client, kind="cookdex", ledger=ledger)
    for _ in range(3):
        mealie_backup.create_backup(client, kind="pre-change", ledger=ledger)
        mealie_backup.prune_backups(client, mealie_backup.PRE_CHANGE_KEEP, kind="pre-change", ledger=ledger)

    kinds = {e["name"]: e["kind"] for e in mealie_backup.read_ledger(ledger)}
    assert sorted(kinds.values()) == ["cookdex", "pre-change", "pre-change"]
    assert client.deleted == ["mealie_v3.29.0_2026.10.02.03.00.00.zip"]  # oldest pre-change only
    assert "mealie_v3.28.0_2026.09.01.12.00.00.zip" in {b["name"] for b in client.backups}


def test_existing_installs_start_with_no_ledger_and_prune_nothing(tmp_path):
    client = FakeMealie([(f"mealie_v3.28.0_2026.09.0{i}.03.00.00.zip", f"2026-09-0{i}T03:00:00Z") for i in range(1, 10)])
    assert mealie_backup.prune_backups(client, 7, ledger=tmp_path / "missing.json") == 0
    assert client.deleted == []


def test_the_task_builder_marks_the_before_change_backup():
    from cookdex.webui_server.tasks import TaskRegistry

    execution = TaskRegistry().build_execution("clean-recipes", {"dry_run": False, "backup_first": True})
    assert execution.pre_commands and execution.pre_commands[0][-2:] == ["--kind", "pre-change"]
