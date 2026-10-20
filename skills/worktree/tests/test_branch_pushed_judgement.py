"""
_is_branch_pushed 對真實 git repo 的判定（0.5.0-W1-373）

不 mock run_git_command：缺陷在 ref 狀態。feat／agent 分支從不推送，
合進 main 後只推 main；判定須為「分支 tip 在任一遠端 ref 上」。
E2 正向對照：含遠端沒有的 commit 的分支須判為未推送（一般 / worktree checkout 中 / 不存在）。
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from worktree_manager import _is_branch_pushed  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True,
    )


def _commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    _git(repo, "add", name)
    _git(repo, "commit", "-m", name)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True)
    r = tmp_path / "repo"
    subprocess.run(["git", "clone", str(origin), str(r)], check=True, capture_output=True)
    _git(r, "checkout", "-b", "main")
    _commit(r, "base")
    _git(r, "push", "origin", "main")
    monkeypatch.chdir(r)
    return r


def test_merged_into_pushed_main_is_pushed(repo):
    """分支從未推送，但已合進並推送的 main：tip 在遠端 ref 上，判為已推送。"""
    _git(repo, "checkout", "-b", "feat/x")
    _commit(repo, "x")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", "-m", "m", "feat/x")
    _git(repo, "push", "origin", "main")
    assert _is_branch_pushed("feat/x") is True


def test_branch_with_unpushed_commit_is_not_pushed(repo):
    """E2(a)：含遠端沒有的 commit。"""
    _git(repo, "checkout", "-b", "feat/y")
    _commit(repo, "y")
    _git(repo, "checkout", "main")
    assert _is_branch_pushed("feat/y") is False


def test_checked_out_branch_with_unpushed_commit_is_not_pushed(repo):
    """E2(b)：同 (a)，分支正被 worktree checkout。"""
    _git(repo, "branch", "feat/z")
    wt = repo.parent / "wt_z"
    _git(repo, "worktree", "add", str(wt), "feat/z")
    _commit(wt, "z")
    assert _is_branch_pushed("feat/z") is False


def test_missing_branch_is_not_pushed(repo):
    """E2(c)：分支不存在。"""
    assert _is_branch_pushed("feat/nope") is False
