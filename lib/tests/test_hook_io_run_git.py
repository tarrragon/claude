"""hook_io.run_git 的失敗/逾時訊號與唯讀不改寫 index 測試（3.3.0-W1-204.8）"""
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.hook_io import run_git


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def stale_repo(tmp_path):
    """提交一個檔案後只改 mtime，使 index stat 資訊過期"""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    f = tmp_path / "a.txt"
    f.write_text("hello\n")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    st = f.stat()
    os.utime(f, (st.st_atime, st.st_mtime + 100))
    return tmp_path


def _index_bytes(repo):
    return (repo / ".git" / "index").read_bytes()


def test_failure_logs_warning_without_logger(caplog):
    with caplog.at_level(logging.WARNING):
        assert run_git(["git", "no-such-subcommand-xyz"]) is None
    assert any("git 命令失敗" in r.message for r in caplog.records)


def test_timeout_logs_warning_without_logger(caplog):
    exc = subprocess.TimeoutExpired(cmd="git", timeout=1)
    with patch("lib.hook_io.subprocess.run", side_effect=exc):
        with caplog.at_level(logging.WARNING):
            assert run_git(["git", "status"], timeout=1) is None
    assert any("超時" in r.message for r in caplog.records)


def test_not_found_logs_warning_without_logger(caplog):
    with patch("lib.hook_io.subprocess.run", side_effect=FileNotFoundError()):
        with caplog.at_level(logging.WARNING):
            assert run_git(["git", "status"]) is None
    assert any("未找到" in r.message for r in caplog.records)


def test_passed_logger_receives_record(caplog):
    custom = logging.getLogger("custom.run_git.test")
    with caplog.at_level(logging.WARNING, logger="custom.run_git.test"):
        run_git(["git", "no-such-subcommand-xyz"], logger=custom)
    assert any(r.name == "custom.run_git.test" for r in caplog.records)


def test_bare_git_status_rewrites_index(stale_repo):
    """正向對照：fixture 確實能讓裸 git status 改寫 index"""
    before = _index_bytes(stale_repo)
    subprocess.run(["git", "status"], cwd=stale_repo, capture_output=True, check=True)
    assert _index_bytes(stale_repo) != before


@pytest.mark.parametrize("cmd", [["git", "status", "--porcelain"], ["git", "diff"]])
def test_run_git_does_not_rewrite_index(stale_repo, cmd):
    before = _index_bytes(stale_repo)
    run_git(cmd, cwd=str(stale_repo))
    assert _index_bytes(stale_repo) == before
