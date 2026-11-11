"""3.2.0-W1-065：ticket track commit 提交「停止追蹤並補 .gitignore」的刪除。

情境：HEAD 追蹤 local.txt；執行 git rm --cached local.txt 並把它寫進
.gitignore，檔案仍留在磁碟上。修正前隔離 index 對 local.txt 執行 git add，
磁碟上的檔案被重新暫存，提交內容沒有這筆刪除。
"""
import argparse
import subprocess
from unittest.mock import patch

import pytest

from ticket_system.commands import track_commit

_TICKET_ID = "0.2.1-W3-998"
_VERSION = "0.2.1"


def _git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "keep.txt").write_text("keep\n")
    (tmp_path / "local.txt").write_text("local only\n")
    _git(tmp_path, "add", "keep.txt", "local.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "new.txt").write_text("new\n")
    return tmp_path


def _commit(repo, files):
    declared = ["new.txt", ".gitignore", "local.txt"]
    ticket = {"id": _TICKET_ID, "type": "IMP", "where": {"files": declared}}
    args = argparse.Namespace(
        ticket_id=_TICKET_ID, message="untrack local", files=files, worktree=None
    )
    with patch.object(track_commit, "load_ticket", return_value=ticket), \
         patch.object(track_commit, "resolve_project_cwd", return_value=str(repo)):
        return track_commit.execute_commit(args, _VERSION)


def _committed_name_status(repo):
    out = _git(repo, "diff", "--name-status", "--no-renames", "HEAD~1", "HEAD").stdout
    return sorted(line.split("\t") for line in out.strip().splitlines())


def test_ignored_deletion_committed_with_new_files(repo):
    _git(repo, "rm", "-q", "--cached", "local.txt")
    (repo / ".gitignore").write_text("local.txt\n")
    # 預期值：同一組變更經共用 index 精確 add 後的 cached diff
    _git(repo, "add", "new.txt", ".gitignore")
    expected = sorted(
        line.split("\t")
        for line in _git(repo, "diff", "--cached", "--name-status", "--no-renames")
        .stdout.strip().splitlines()
    )
    _git(repo, "restore", "--staged", "new.txt", ".gitignore")

    assert _commit(repo, ["new.txt", ".gitignore", "local.txt"]) == 0
    assert _committed_name_status(repo) == expected
    assert ["D", "local.txt"] in expected
    assert (repo / "local.txt").exists()


def test_without_deletion_behaviour_unchanged(repo):
    """E1 對照：同 fixture 不停止追蹤 local.txt，只提交新檔，local.txt 不受影響。"""
    (repo / ".gitignore").write_text("local.txt\n")
    assert _commit(repo, ["new.txt", ".gitignore"]) == 0
    assert _committed_name_status(repo) == [["A", ".gitignore"], ["A", "new.txt"]]
    assert "local.txt" in _git(repo, "ls-files").stdout


def test_force_tracked_ignored_file_is_not_deleted(repo):
    """仍在共用 index 的 ignore 檔（強制追蹤）照常以修改提交，不被當成刪除。"""
    (repo / ".gitignore").write_text("local.txt\n")
    (repo / "local.txt").write_text("changed\n")
    assert _commit(repo, ["local.txt"]) == 0
    assert _committed_name_status(repo) == [["M", "local.txt"]]
