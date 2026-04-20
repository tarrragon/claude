"""
hook_base.py 的 get_project_root() 單元測試

測試覆蓋：
- 環境變數優先
- git rev-parse 成功（worktree 修復核心）
- git 不可用的 fallback
- CLAUDE.md 搜尋
- cwd fallback
- 相容性驗證
"""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from hook_utils.hook_base import get_project_root


class TestGetProjectRootHookBase:
    """hook_base.py 的 get_project_root() 測試類別"""

    def test_env_var_priority(self):
        """環境變數 CLAUDE_PROJECT_DIR 優先"""
        custom_path = "/custom/project/path"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": custom_path}):
            result = get_project_root()
            assert result == Path(custom_path)

    def test_git_revparse_success(self):
        """git rev-parse 成功時回傳 git repo 根目錄"""
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
        """worktree 環境下 git rev-parse 正確回傳源 repo 根目錄"""
        # 模擬 worktree 結構
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        (repo_root / "CLAUDE.md").write_text("# CLAUDE.md")

        worktree_dir = tmp_path / "worktree"
        worktree_dir.mkdir()

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=worktree_dir):
                with patch("subprocess.run") as mock_run:
                    # git 回傳源 repo 根目錄（不是 worktree 目錄）
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout=str(repo_root) + "\n"
                    )
                    result = get_project_root()
                    # 應該回傳 git 回傳的路徑，不是 cwd
                    assert result == repo_root
                    assert result != worktree_dir

    def test_git_not_found_fallback(self, tmp_path):
        """git 命令不存在時 fallback 到 CLAUDE.md 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# CLAUDE.md")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    # 應該找到 CLAUDE.md
                    assert result == root

    def test_git_timeout_fallback(self, tmp_path):
        """git 命令超時時 fallback 到 CLAUDE.md 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# CLAUDE.md")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = subprocess.TimeoutExpired("git", 5)
                    result = get_project_root()
                    # 應該找到 CLAUDE.md
                    assert result == root

    def test_git_failure_fallback(self, tmp_path):
        """git 失敗（returncode != 0）時 fallback 到 CLAUDE.md 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# CLAUDE.md")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    # git 命令回傳非 0（例如 128 表示非 git repo）
                    mock_run.return_value = MagicMock(returncode=128, stdout="")
                    result = get_project_root()
                    # 應該找到 CLAUDE.md
                    assert result == root

    def test_claudemd_search_success(self, tmp_path):
        """CLAUDE.md 搜尋成功"""
        root = tmp_path / "root"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# CLAUDE.md")

        subdir = root / "subdir1" / "subdir2"
        subdir.mkdir(parents=True)

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=subdir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    # 應該向上搜尋找到 root
                    assert result == root

    def test_claudemd_search_depth_limit(self, tmp_path):
        """CLAUDE.md 搜尋深度限制（5 層）"""
        root = tmp_path / "root"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# CLAUDE.md")

        # 建立超過 5 層的目錄結構
        deep_dir = root / "l1" / "l2" / "l3" / "l4" / "l5" / "l6"
        deep_dir.mkdir(parents=True)

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=deep_dir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    # 搜尋深度超過 5，應該 fallback 到 cwd
                    # 實際上會搜尋 5 層，無法搜尋到根的 CLAUDE.md
                    # 最終會 fallback 到 cwd
                    assert result == deep_dir

    def test_cwd_fallback(self, tmp_path):
        """全部失敗時 fallback 到 cwd"""
        isolated_dir = tmp_path / "isolated"
        isolated_dir.mkdir()

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=isolated_dir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    # 應該回傳 cwd
                    assert result == isolated_dir

    def test_symlink_resolution(self, tmp_path):
        """symlink 目錄正確解析"""
        real_dir = tmp_path / "real_path"
        real_dir.mkdir()
        (real_dir / ".git").mkdir()

        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=link_dir):
                with patch("subprocess.run") as mock_run:
                    # git 會回傳解析後的真實路徑
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout=str(real_dir) + "\n"
                    )
                    result = get_project_root()
                    # 應該回傳 git 回傳的真實路徑
                    assert result == real_dir

    def test_backward_compatibility(self):
        """驗證向後相容性：函式簽名保持不變"""
        # 驗證函式存在且簽名正確
        assert callable(get_project_root)
        # 驗證回傳型別
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": "/test"}):
            result = get_project_root()
            assert isinstance(result, Path)
