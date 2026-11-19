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


def test_command_does_not_require_path_format_option(tmp_path):
    # --path-format=absolute 需 git 2.31；舊版會把它原樣印成第一行且 rc=0
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=".git\n.git\n", stderr="")
    with patch.object(uv_tool_utils.subprocess, "run", return_value=fake) as run:
        reinstall_skip_reason(tmp_path)
    assert not any(a.startswith("--path-format") for a in run.call_args.args[0])


def test_relative_output_resolves_against_project_root(tmp_path, monkeypatch):
    # 不帶 --path-format 時 git 回相對於 -C 目錄的路徑（子目錄的 common dir 為 ../.git）
    root = tmp_path / "repo"
    sub = root / "sub"
    sub.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=f"{root / '.git'}\n../.git\n", stderr=""
    )
    with patch.object(uv_tool_utils.subprocess, "run", return_value=fake):
        assert reinstall_skip_reason(sub) is None


def test_linked_worktree_reason_names_main_checkout_from_relative_output(tmp_path, monkeypatch):
    main = tmp_path / "main"
    linked = tmp_path / "linked"
    linked.mkdir()
    monkeypatch.chdir(tmp_path)
    fake = subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout=f"{main / '.git' / 'worktrees' / 'linked'}\n{main / '.git'}\n", stderr="",
    )
    with patch.object(uv_tool_utils.subprocess, "run", return_value=fake):
        reason = reinstall_skip_reason(linked)
    assert reason is not None
    assert f"主 checkout 為 {main.resolve()}" in reason


def test_incomplete_output_skips_reinstall(tmp_path):
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="/x/.git\n", stderr="")
    with patch.object(uv_tool_utils.subprocess, "run", return_value=fake):
        reason = reinstall_skip_reason(tmp_path)
    assert reason is not None
    assert "輸出不完整" in reason
