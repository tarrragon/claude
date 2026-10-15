"""hook_base.get_shared_state_root 單元測試（0.5.0-W1-264.1）。

以真實 git 建立主 repo 與 linked worktree，不 mock git。
"""
import os
import subprocess
from pathlib import Path

import pytest

from lib import hook_base
from lib.hook_base import get_project_root, get_shared_state_root


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo_and_worktree(tmp_path, monkeypatch):
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("x", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    # 解除 conftest 的測試隔離，走真實解析
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    hook_base.clear_project_root_cache()
    yield main, wt
    hook_base.clear_project_root_cache()


def test_linked_worktree_returns_main_repo(repo_and_worktree, monkeypatch):
    main, wt = repo_and_worktree
    monkeypatch.chdir(wt)
    assert get_project_root() == wt  # 對照：get_project_root 語意不變
    assert get_shared_state_root() == main


def test_linked_worktree_ignores_env_var(repo_and_worktree, monkeypatch):
    main, wt = repo_and_worktree
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    monkeypatch.chdir(wt)
    assert get_shared_state_root() == main


def test_main_repo_returns_project_root(repo_and_worktree, monkeypatch):
    main, _ = repo_and_worktree
    monkeypatch.chdir(main)
    assert get_shared_state_root() == get_project_root() == main


def test_default_root_used_when_not_worktree(repo_and_worktree, monkeypatch, tmp_path):
    main, _ = repo_and_worktree
    monkeypatch.chdir(main)
    assert get_shared_state_root(tmp_path) == tmp_path


def test_not_a_repo_falls_back_to_project_root(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(plain))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(plain)
    hook_base.clear_project_root_cache()
    assert get_shared_state_root() == plain


def test_git_unavailable_falls_back_without_error(tmp_path, monkeypatch, capsys):
    plain = tmp_path / "nogit"
    plain.mkdir()
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(plain))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.chdir(plain)
    hook_base.clear_project_root_cache()
    assert get_shared_state_root() == plain
    assert capsys.readouterr().err == ""  # 非 worktree 屬正常情境，不寫 stderr


def test_common_dir_failure_in_worktree_degrades_with_stderr(
    repo_and_worktree, monkeypatch, capsys
):
    main, wt = repo_and_worktree
    monkeypatch.chdir(wt)
    real_run = subprocess.run

    def fake_run(cmd, *a, **kw):
        if "--git-common-dir" in cmd and "--path-format=absolute" in cmd:
            return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="boom")
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(hook_base.subprocess, "run", fake_run)
    hook_base.clear_project_root_cache()
    assert get_shared_state_root() == wt  # 退回 get_project_root 語意
    assert "get_shared_state_root 降級" in capsys.readouterr().err


def test_isolation_flag_returns_project_root(repo_and_worktree, monkeypatch):
    _, wt = repo_and_worktree
    monkeypatch.chdir(wt)
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    hook_base.clear_project_root_cache()
    assert get_shared_state_root() == wt
