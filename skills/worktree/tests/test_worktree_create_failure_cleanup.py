"""
create 的 git worktree add 逾時或失敗時的清理契約（0.5.0-W1-368）

用真實 git：tmp 內 init repo，注入「add 實際建出 worktree 與分支後回報逾時」
的失敗，驗證不殘留 worktree 與本次新建的分支。
"""

import subprocess
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

import worktree_manager
from worktree_manager import cmd_create, derive_branch_name, derive_worktree_path

TICKET = "0.1.1-W9-002.1"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "a.txt").write_text("a")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-m", "init")
    monkeypatch.chdir(root)
    return root


def _inject_add_timeout(monkeypatch, seen: list):
    """add 真實執行（建出 worktree 與分支）後回報逾時，模擬被殺後的殘留狀態。"""
    real = worktree_manager.run_git_command

    def fake(args, cwd=None, timeout=10):
        if args[:2] == ["worktree", "add"]:
            seen.append(timeout)
            real(args, cwd=cwd, timeout=60)
            # 實際殘留狀態是 locked initializing，需雙 --force 才能移除
            real(["worktree", "lock", "--reason", "initializing", args[-2]], cwd=cwd, timeout=60)
            return False, f"Command timed out after {timeout}s"
        return real(args, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(worktree_manager, "run_git_command", fake)


def test_add_timeout_leaves_no_worktree_or_branch(repo, monkeypatch, capsys):
    seen: list = []
    _inject_add_timeout(monkeypatch, seen)

    assert cmd_create(TICKET) == 1

    branch = derive_branch_name(TICKET)
    wt_path = derive_worktree_path(TICKET)
    assert _git(repo, "rev-parse", "--verify", branch).returncode != 0
    assert branch not in _git(repo, "branch", "--list").stdout
    assert wt_path not in _git(repo, "worktree", "list", "--porcelain").stdout
    assert not Path(wt_path).exists()
    assert "逾時" in capsys.readouterr().out


def _cleanup_log(repo: Path) -> str:
    log = repo / ".claude" / "logs" / "worktree-merge.log"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def test_cleanup_steps_written_to_log(repo, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    _inject_add_timeout(monkeypatch, [])

    cmd_create(TICKET)

    lines = [l for l in _cleanup_log(repo).splitlines() if "[建立清理]" in l]
    assert any("worktree remove" in l and "結果 成功" in l for l in lines)
    assert any("worktree prune" in l and "結果 成功" in l for l in lines)
    assert any("branch -D" in l and derive_branch_name(TICKET) in l and "結果 成功" in l
               for l in lines)


def test_branch_delete_failure_logged(repo, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    _inject_add_timeout(monkeypatch, [])
    wrapped = worktree_manager.run_git_command

    def fail_branch_delete(args, cwd=None, timeout=10):
        if args[:2] == ["branch", "-D"]:
            return False, "error: cannot delete branch\nbusy"
        return wrapped(args, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(worktree_manager, "run_git_command", fail_branch_delete)

    cmd_create(TICKET)

    lines = [l for l in _cleanup_log(repo).splitlines() if "[建立清理]" in l]
    assert any("branch -D" in l and "結果 失敗" in l and "cannot delete branch" in l
               for l in lines)
    assert "清理分支" in capsys.readouterr().err


def test_add_gets_generous_timeout(repo, monkeypatch):
    seen: list = []
    _inject_add_timeout(monkeypatch, seen)
    cmd_create(TICKET)
    assert seen and seen[0] >= 60


def test_preexisting_branch_not_deleted_on_failure(repo, monkeypatch):
    branch = derive_branch_name(TICKET)
    _git(repo, "branch", branch)
    seen: list = []
    _inject_add_timeout(monkeypatch, seen)

    assert cmd_create(TICKET) == 1

    # 分支已存在時，前置驗證在 add 之前就返回：此路徑不經過 add 與清理程式碼
    assert seen == []
    assert _git(repo, "rev-parse", "--verify", branch).returncode == 0
