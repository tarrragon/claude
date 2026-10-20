"""
_is_branch_merged_to_base 對真實 git repo 的判定（0.5.0-W1-363）

不 mock run_git_command：缺陷在 git branch --merged 對 worktree 已 checkout
分支加「+ 」前綴的實際輸出格式，mock 會遮住它。
E2 正向對照：未合併分支（一般 / worktree checkout 中 / 不存在）須判為未合併。
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from worktree_manager import _is_branch_merged_to_base  # noqa: E402


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
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _commit(r, "base")
    monkeypatch.chdir(r)
    return r


def _add_branch(repo: Path, branch: str, merged: bool, checked_out: bool) -> None:
    """建分支；merged=False 時在該分支上多一個 main 沒有的 commit。"""
    _git(repo, "branch", branch)
    if checked_out:
        wt = repo.parent / branch.replace("/", "_")
        _git(repo, "worktree", "add", str(wt), branch)
        if not merged:
            _commit(wt, "extra")
    elif not merged:
        _git(repo, "checkout", branch)
        _commit(repo, "extra")
        _git(repo, "checkout", "main")


def test_merged_branch_checked_out_in_worktree_is_merged(repo):
    _add_branch(repo, "feat/x", merged=True, checked_out=True)
    assert _is_branch_merged_to_base("feat/x", "main") is True


def test_merged_plain_branch_is_merged(repo):
    _add_branch(repo, "feat/y", merged=True, checked_out=False)
    assert _is_branch_merged_to_base("feat/y", "main") is True


def test_unmerged_plain_branch_is_not_merged(repo):
    _add_branch(repo, "feat/u", merged=False, checked_out=False)
    assert _is_branch_merged_to_base("feat/u", "main") is False


def test_unmerged_worktree_checked_out_branch_is_not_merged(repo):
    _add_branch(repo, "feat/uw", merged=False, checked_out=True)
    assert _is_branch_merged_to_base("feat/uw", "main") is False


def test_missing_branch_is_not_merged(repo):
    assert _is_branch_merged_to_base("feat/nope", "main") is False
