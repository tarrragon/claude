"""migrate 結束時列出票檔以外的舊號殘留（只列出、不改寫）。

以真實 git repo（tmp_path）驗證 git grep 掃描：票檔與 migration-backups 排除、
子票號不誤命中、無殘留時不輸出（E1 對照）。
"""
import subprocess
from pathlib import Path

import pytest

from ticket_system.commands import migrate
from ticket_system.lib import paths

OLD = "0.3.1-W1-007"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    monkeypatch.setattr(paths, "get_project_root", lambda: tmp_path)
    return tmp_path


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(root, "add", rel)


def test_lists_residue_outside_ticket_files(repo, capsys):
    _write(repo, "docs/spec/a.md", f"承接票 {OLD}\n無關行\n")
    _write(repo, "lib/b.py", f"# see {OLD}\n")
    _write(repo, "docs/work-logs/v0/v0.3/v0.3.1/tickets/x.md", f"blockedBy: [{OLD}]\n")
    _write(repo, ".claude/migration-backups/20260101/x.md", f"{OLD}\n")

    migrate._report_residual_references([OLD])

    out = capsys.readouterr().out
    assert "票檔以外仍引用舊號" in out
    assert f"{OLD}：2 處" in out
    assert "docs/spec/a.md:1:" in out
    assert "lib/b.py:1:" in out
    assert "tickets/x.md" not in out
    assert "migration-backups" not in out


def test_child_ticket_ids_not_matched(repo):
    _write(repo, "docs/spec/a.md", f"{OLD}.1 與 {OLD}0 都不是同一張票\n")

    assert migrate._scan_residual_references([OLD]) == {}


def test_no_residue_prints_nothing_e1(repo, capsys):
    _write(repo, "docs/spec/a.md", "沒有引用\n")

    migrate._report_residual_references([OLD])

    assert capsys.readouterr().out == ""


def test_old_ids_for_report_skips_unchanged_ids():
    same = migrate._MigrationRecord(old_id=OLD, new_id=OLD, target_path=Path("t"), source_path=Path("s"))
    moved = migrate._MigrationRecord(old_id="0.3.1-W1-008", new_id="1.0.0-W1-001",
                                     target_path=Path("t"), source_path=Path("s"))

    assert migrate._old_ids_for_report([same, moved], ["0.3.1-W1-009"]) == [
        "0.3.1-W1-008", "0.3.1-W1-009",
    ]
