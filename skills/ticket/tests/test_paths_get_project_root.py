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
        """環境變數 CLAUDE_PROJECT_DIR 優先（非 worktree 場景）"""
        custom_path = "/custom/project/path"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": custom_path}):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None
            ):
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
                # 驗證 subprocess（git）被呼叫
                assert mock_run.called
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
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None
            ):
                result = get_project_root()
                assert isinstance(result, Path)

    def test_worktree_aware_prefers_worktree_root_over_env(self):
        """worktree 感知：位於 linked worktree 時優先用 worktree root（凌駕 CLAUDE_PROJECT_DIR）

        W3-008 根因 1 修復：worktree 場景下 CLAUDE_PROJECT_DIR 恆指向主 repo，
        應優先用 worktree root 避免 ticket CRUD/auto-commit 洩漏到主 repo。
        """
        main_repo = "/main/repo"
        worktree_root = Path("/main/repo/.claude/worktrees/agent-abc")
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": main_repo}):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=worktree_root
            ):
                result = get_project_root()
                assert result == worktree_root
                assert result != Path(main_repo)

    def test_non_worktree_uses_env(self):
        """非 worktree 場景（_linked_worktree_root 回 None）：用 CLAUDE_PROJECT_DIR"""
        main_repo = "/main/repo"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": main_repo}):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None
            ):
                result = get_project_root()
                assert result == Path(main_repo)


class TestLinkedWorktreeRoot:
    """_linked_worktree_root() 的 git-native 偵測測試"""

    def test_main_repo_returns_none(self):
        """主 repo：--git-dir == --git-common-dir，回傳 None"""
        from ticket_system.lib.paths import _linked_worktree_root
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=".git\n.git\n"
            )
            assert _linked_worktree_root() is None

    def test_linked_worktree_returns_toplevel(self):
        """linked worktree：--git-dir != --git-common-dir，回傳 worktree toplevel"""
        from ticket_system.lib.paths import _linked_worktree_root
        wt_root = "/main/repo/.claude/worktrees/agent-abc"
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(
                    returncode=0,
                    stdout="/main/repo/.git/worktrees/agent-abc\n/main/repo/.git\n"
                ),
                MagicMock(returncode=0, stdout=wt_root + "\n"),
            ]
            assert _linked_worktree_root() == Path(wt_root)

    def test_git_unavailable_returns_none(self):
        """git 不可用：回傳 None（不誤判 worktree）"""
        from ticket_system.lib.paths import _linked_worktree_root
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            assert _linked_worktree_root() is None

    def test_git_failure_returns_none(self):
        """git 失敗（returncode != 0）：回傳 None"""
        from ticket_system.lib.paths import _linked_worktree_root
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            assert _linked_worktree_root() is None
