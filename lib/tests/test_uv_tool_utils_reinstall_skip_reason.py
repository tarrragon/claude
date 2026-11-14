"""reinstall_skip_reason：只有主 checkout 可作為全域 uv tool 的重裝來源。

以真實 git repo 與 `git worktree add` 建出的 linked worktree 驗證判定，
並以非 git 目錄與模擬 git 失敗驗證判定失敗時落在「不重裝」側。
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib import uv_tool_utils
from lib.uv_tool_utils import reinstall_skip_reason


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def main_and_linked(tmp_path):
    """建立主 checkout 與一個 linked worktree，回傳 (main, linked)。"""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "init")
    linked = tmp_path / "linked"
    _git(main, "worktree", "add", "-q", str(linked))
    return main, linked


def test_main_checkout_allows_reinstall(main_and_linked):
    main, _ = main_and_linked
    assert reinstall_skip_reason(main) is None


def test_main_checkout_subdirectory_allows_reinstall(main_and_linked):
    # git 對子目錄可能回相對與絕對混合的路徑，resolve 後須判為主 checkout
    main, _ = main_and_linked
    sub = main / "a" / "b"
    sub.mkdir(parents=True)
    assert reinstall_skip_reason(sub) is None


def test_linked_worktree_skips_reinstall(main_and_linked):
    main, linked = main_and_linked
    logger = MagicMock()
    reason = reinstall_skip_reason(linked, logger)
    assert reason is not None
    assert "linked worktree" in reason
    assert str(main.resolve()) in reason
    logger.warning.assert_called_once()


def test_non_git_directory_skips_reinstall(tmp_path):
    reason = reinstall_skip_reason(tmp_path / "not_a_repo_dir")
    assert reason is not None
    assert "無法判定" in reason


def test_git_timeout_skips_reinstall(tmp_path):
    with patch.object(
        uv_tool_utils.subprocess, "run",
        side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
    ):
        reason = reinstall_skip_reason(tmp_path)
    assert reason is not None
    assert "無法判定" in reason


def test_git_missing_skips_reinstall(tmp_path):
    with patch.object(
        uv_tool_utils.subprocess, "run", side_effect=FileNotFoundError("git")
    ):
        reason = reinstall_skip_reason(tmp_path)
    assert reason is not None
    assert "無法判定" in reason


def test_incomplete_output_skips_reinstall(tmp_path):
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="/x/.git\n", stderr="")
    with patch.object(uv_tool_utils.subprocess, "run", return_value=fake):
        reason = reinstall_skip_reason(tmp_path)
    assert reason is not None
    assert "輸出不完整" in reason
