"""寫入命令 auto-commit 最終失敗的可見性與 exit code（0.4.0-W1-067）。

對照設計（測試規則 E1）：每個失敗情境都有同 fixture 的「無鎖成功」對照，
故殘鎖是唯一差異；只斷言失敗一側的測項在 reporting 退化為空操作時仍會綠。
"""
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ticket_system.commands.lifecycle import _auto_commit_completion_files
from ticket_system.commands.track_acceptance import execute_check_acceptance
from ticket_system.lib import git_ops, git_utils

_TID = "0.0.0-W0-001"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    md = tmp_path / f"{_TID}.md"
    md.write_text("v1\n")
    _git(tmp_path, "add", md.name)
    _git(tmp_path, "commit", "-q", "-m", "init")
    md.write_text("v2\n")  # working tree 有待提交變更
    # 不真的等待：重試預算歸零、sleep 不睡
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 0.0)
    monkeypatch.setattr(git_ops.time, "sleep", lambda _s: None)
    return tmp_path


def _plant_ref_lock(repo: Path) -> Path:
    lock = repo / ".git" / "refs" / "heads" / "main.lock"
    lock.write_text("residue\n")
    return lock


def test_reporting_control_success_without_lock(repo, capsys):
    failed = git_utils.commit_ticket_md_reporting(
        "append-log", str(repo / f"{_TID}.md"), _TID, "Solution"
    )
    assert failed is False
    assert "[WARNING]" not in capsys.readouterr().err


def test_reporting_final_failure_with_residual_lock(repo, capsys):
    lock = _plant_ref_lock(repo)
    failed = git_utils.commit_ticket_md_reporting(
        "append-log", str(repo / f"{_TID}.md"), _TID, "Solution"
    )
    err = capsys.readouterr().err
    assert failed is True
    assert "[WARNING] [append-log]" in err
    assert "exit code 75" in err
    assert str(lock) in err
    assert "補救指令" in err and "git add" in err


def test_complete_metadata_commit_control_success_without_lock(repo, capsys):
    assert _auto_commit_completion_files(_TID, [str(repo / f"{_TID}.md")]) is False
    assert "[WARNING]" not in capsys.readouterr().err


def test_complete_metadata_commit_fails_visibly_with_residual_lock(repo, capsys):
    md = repo / f"{_TID}.md"
    _plant_ref_lock(repo)
    assert _auto_commit_completion_files(_TID, [str(md)]) is True
    err = capsys.readouterr().err
    assert "[WARNING] [complete]" in err
    assert "exit code 75" in err
    assert f"git add {md}" in err


def _check_args():
    args = Mock()
    args.ticket_id = _TID
    args.version = "0.0.0"
    args.index = "1"
    args.uncheck = False
    args.all = False
    return args


@pytest.mark.parametrize(
    "commit_status, expected_rc",
    [("committed", 0), ("no_change", 0), ("not_git_repo", 0), ("git_failed", 75)],
)
def test_check_acceptance_exit_code_by_commit_status(commit_status, expected_rc, capsys, tmp_path):
    """check-acceptance：僅 git_failed 改 exit 75，其餘狀態維持 0（E1 對照）。"""
    ticket = {"id": _TID, "title": "t", "_path": str(tmp_path / "t.md"), "acceptance": ["[ ] a"]}
    with patch(
        "ticket_system.commands.track_acceptance.load_and_validate_ticket",
        return_value=(ticket, None),
    ), patch("ticket_system.commands.track_acceptance.save_ticket"), patch(
        "ticket_system.commands.track_acceptance.get_ticket_path",
        return_value=tmp_path / "t.md",
    ), patch(
        "ticket_system.lib.git_utils._auto_commit_ticket_md", return_value=commit_status
    ):
        rc = execute_check_acceptance(_check_args(), "0.0.0")
    assert rc == expected_rc
    warned = "[WARNING] [check-acceptance]" in capsys.readouterr().err
    assert warned is (commit_status == "git_failed")
