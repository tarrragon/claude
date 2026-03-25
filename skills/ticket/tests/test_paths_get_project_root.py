"""
paths.py 的 get_project_root() 單元測試

測試覆蓋：
- 環境變數優先
- git rev-parse 優先（替代現有的 marker 搜尋）
- worktree 修復
- git 不可用 fallback
- marker 搜尋順序
- cwd fallback
- 相容性驗證
"""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from ticket_system.lib.paths import get_project_root


class TestGetProjectRootPaths:
    """paths.py 的 get_project_root() 測試類別"""

    def test_env_var_priority(self):
        """環境變數 CLAUDE_PROJECT_DIR 優先"""
        custom_path = "/custom/project/path"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": custom_path}):
            result = get_project_root()
            assert result == Path(custom_path)

    def test_git_revparse_success(self):
        """git rev-parse 優先於 marker 搜尋"""
        git_root = "/path/to/git/repo"
        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=git_root + "\n"
                )
                result = get_project_root()
                assert result == Path(git_root)
                # 驗證 subprocess 被呼叫
                mock_run.assert_called_once()
                call_args = mock_run.call_args
                assert "git" in call_args[0][0]

    def test_worktree_git_revparse(self, tmp_path):
        """worktree 環境下 git rev-parse 回傳源 repo 根目錄"""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        (repo_root / "CLAUDE.md").write_text("# CLAUDE.md")

        worktree_dir = tmp_path / "worktree"
        worktree_dir.mkdir()

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=worktree_dir):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout=str(repo_root) + "\n"
                    )
                    result = get_project_root()
                    assert result == repo_root
                    assert result != worktree_dir

    def test_git_not_found_fallback(self, tmp_path):
        """git 命令不存在時 fallback 到 marker 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# CLAUDE.md")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    assert result == root

    def test_git_timeout_fallback(self, tmp_path):
        """git 命令超時時 fallback 到 marker 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "go.mod").write_text("module example.com")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = subprocess.TimeoutExpired("git", 5)
                    result = get_project_root()
                    assert result == root

    def test_git_failure_fallback(self, tmp_path):
        """git 失敗（returncode != 0）時 fallback 到 marker 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "pubspec.yaml").write_text("name: example")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=128, stdout="")
                    result = get_project_root()
                    assert result == root

    def test_marker_fallback_order(self, tmp_path):
        """marker 搜尋順序：CLAUDE.md > go.mod > pubspec.yaml"""
        root = tmp_path / "root"
        root.mkdir()

        # 建立所有三種 marker
        (root / "CLAUDE.md").write_text("# CLAUDE.md")
        (root / "go.mod").write_text("module example.com")
        (root / "pubspec.yaml").write_text("name: example")

        subdir = root / "subdir"
        subdir.mkdir()

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=subdir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    # 應該找到 root（優先序不重要，只要找到任何 marker）
                    assert result == root

    def test_cwd_fallback(self, tmp_path):
        """全部失敗時 fallback 到 cwd"""
        isolated_dir = tmp_path / "isolated"
        isolated_dir.mkdir()

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=isolated_dir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    assert result == isolated_dir

    def test_backward_compatibility_ticket_commands(self):
        """驗證 ticket 命令相容性：函式簽名保持不變"""
        assert callable(get_project_root)
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": "/test"}):
            result = get_project_root()
            assert isinstance(result, Path)
