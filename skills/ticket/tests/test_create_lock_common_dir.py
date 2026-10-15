"""建票鎖共用位置：檔案系統解析 common dir、降級可見（0.5.0-W1-152.1）。"""
import subprocess
from pathlib import Path

from ticket_system.lib import file_lock as fl
from ticket_system.lib import paths


def _make_repo_with_worktree(tmp_path: Path):
    main = tmp_path / "main"
    (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
    (main / ".git" / "worktrees" / "wt" / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {main}/.git/worktrees/wt\n")
    return main, wt


def test_main_and_linked_worktree_same_common_dir(tmp_path):
    main, wt = _make_repo_with_worktree(tmp_path)
    expected = (main / ".git").resolve()
    assert paths._resolve_git_common_dir_from_fs(main) == expected
    assert paths._resolve_git_common_dir_from_fs(wt) == expected


def test_relative_gitdir_pointer(tmp_path):
    main, wt = _make_repo_with_worktree(tmp_path)
    (wt / ".git").write_text("gitdir: ../main/.git/worktrees/wt\n")
    assert paths._resolve_git_common_dir_from_fs(wt) == (main / ".git").resolve()


def test_lock_in_common_dir_when_subprocess_times_out(tmp_path, monkeypatch):
    main, _ = _make_repo_with_worktree(tmp_path)
    tickets = main / "docs" / "work-logs" / "v1" / "tickets"
    tickets.mkdir(parents=True)

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("git", 5)

    monkeypatch.setattr(paths.subprocess, "run", boom)
    monkeypatch.setattr(fl, "get_project_root", lambda: main)
    lock = fl._resolve_shared_lock_path(tickets)
    assert (main / ".git").resolve() in lock.parents


def test_degraded_warns_and_ignore_rule_present(tmp_path, monkeypatch, capsys):
    tickets = tmp_path / "docs" / "work-logs" / "v1" / "tickets"
    tickets.mkdir(parents=True)
    monkeypatch.setattr(fl, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(fl, "get_git_common_dir", lambda *_: None)
    lock = fl._resolve_shared_lock_path(tickets)
    assert lock == tickets / fl.CREATE_LOCK_FILENAME
    assert "[WARNING]" in capsys.readouterr().err
    root = Path(__file__).resolve().parents[4]
    assert "docs/**/.ticket-create.lock" in (root / ".gitignore").read_text()
