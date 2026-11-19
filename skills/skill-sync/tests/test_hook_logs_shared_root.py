"""hook-logs 在 linked worktree 內落到主倉庫（3.4.0-W1-169.1）。

worktree 的 .claude/hook-logs 被 gitignore 忽略、隨 worktree 清理刪除，force-log
寫在那裡等於遺失。以真實 git repo 與 worktree 驗證，不 mock git。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import skill_sync.cli as cli_module  # noqa: E402
from skill_sync.cli import _resolve_hook_logs_dir, get_skills_dir  # noqa: E402


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
    )


def _repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", cwd=main)
    (main / "README.md").write_text("x")
    _git("add", "README.md", cwd=main)
    _git("commit", "-q", "-m", "init", cwd=main)
    linked = tmp_path / "linked"
    _git("worktree", "add", "-q", "-b", "feat", str(linked), cwd=main)
    return main.resolve(), linked.resolve()


def test_hook_logs_in_linked_worktree_land_in_main_repo(tmp_path, monkeypatch):
    main, linked = _repo_with_worktree(tmp_path)
    monkeypatch.delenv("HOOK_LOGS_DIR", raising=False)
    monkeypatch.chdir(linked)

    assert _resolve_hook_logs_dir() == main / ".claude" / "hook-logs"


def test_hook_logs_in_main_repo_stay_in_main_repo_contrast(tmp_path, monkeypatch):
    main, _ = _repo_with_worktree(tmp_path)
    monkeypatch.delenv("HOOK_LOGS_DIR", raising=False)
    monkeypatch.chdir(main)

    assert _resolve_hook_logs_dir() == main / ".claude" / "hook-logs"


def test_skills_dir_in_linked_worktree_stays_in_worktree(tmp_path, monkeypatch):
    _, linked = _repo_with_worktree(tmp_path)
    monkeypatch.chdir(linked)

    assert get_skills_dir().resolve() == linked / ".claude" / "skills"


def test_common_dir_failure_falls_back_to_toplevel_with_warning(tmp_path, monkeypatch, capsys):
    toplevel = tmp_path / "not-a-repo"
    toplevel.mkdir()
    monkeypatch.delenv("HOOK_LOGS_DIR", raising=False)
    monkeypatch.setattr(cli_module, "_resolve_project_root", lambda purpose="": toplevel)

    assert _resolve_hook_logs_dir() == toplevel / ".claude" / "hook-logs"
    assert "git-common-dir" in capsys.readouterr().err
