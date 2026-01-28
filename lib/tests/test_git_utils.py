#!/usr/bin/env python3
"""
git_utils 模組單元測試
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from git_utils import (
    run_git_command,
    get_current_branch,
    get_project_root,
    get_worktree_list,
    is_protected_branch,
    is_allowed_branch,
    WORKTREE_PREFIX_LEN,
    BRANCH_PREFIX_LEN,
)


class TestRunGitCommand(unittest.TestCase):
    """測試 run_git_command 函式"""

    @patch('subprocess.run')
    def test_successful_command(self, mock_run):
        """測試成功執行 git 命令"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="main\n",
            stderr=""
        )
        success, output = run_git_command(["branch", "--show-current"])
        self.assertTrue(success)
        self.assertEqual(output, "main")

    @patch('subprocess.run')
    def test_failed_command(self, mock_run):
        """測試失敗的 git 命令"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="fatal: not a git repository"
        )
        success, output = run_git_command(["status"])
        self.assertFalse(success)
        self.assertIn("not a git repository", output)

    @patch('subprocess.run')
    def test_timeout(self, mock_run):
        """測試命令超時"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
        success, output = run_git_command(["status"])
        self.assertFalse(success)
        self.assertIn("timed out", output)


class TestBranchFunctions(unittest.TestCase):
    """測試分支相關函式"""

    @patch('git_utils.run_git_command')
    def test_get_current_branch_success(self, mock_run):
        """測試成功獲取當前分支"""
        mock_run.return_value = (True, "feat/new-feature")
        branch = get_current_branch()
        self.assertEqual(branch, "feat/new-feature")

    @patch('git_utils.run_git_command')
    def test_get_current_branch_failure(self, mock_run):
        """測試獲取分支失敗"""
        mock_run.return_value = (False, "error")
        branch = get_current_branch()
        self.assertIsNone(branch)

    def test_is_protected_branch(self):
        """測試保護分支檢測"""
        self.assertTrue(is_protected_branch("main"))
        self.assertTrue(is_protected_branch("master"))
        self.assertTrue(is_protected_branch("develop"))
        self.assertTrue(is_protected_branch("release/v1.0"))
        self.assertFalse(is_protected_branch("feat/new-feature"))
        self.assertFalse(is_protected_branch("fix/bug-fix"))

    def test_is_allowed_branch(self):
        """測試允許編輯的分支檢測"""
        self.assertTrue(is_allowed_branch("feat/new-feature"))
        self.assertTrue(is_allowed_branch("fix/bug-fix"))
        self.assertTrue(is_allowed_branch("chore/update-deps"))
        self.assertTrue(is_allowed_branch("refactor/cleanup"))
        self.assertFalse(is_allowed_branch("main"))
        self.assertFalse(is_allowed_branch("random-branch"))


class TestWorktreeFunctions(unittest.TestCase):
    """測試 worktree 相關函式"""

    @patch('git_utils.run_git_command')
    def test_get_worktree_list(self, mock_run):
        """測試獲取 worktree 列表"""
        mock_run.return_value = (True, """worktree /path/to/repo
branch refs/heads/main

worktree /path/to/feature
branch refs/heads/feat/new-feature
""")
        worktrees = get_worktree_list()
        self.assertEqual(len(worktrees), 2)
        self.assertEqual(worktrees[0]["path"], "/path/to/repo")
        self.assertEqual(worktrees[0]["branch"], "main")
        self.assertEqual(worktrees[1]["path"], "/path/to/feature")
        self.assertEqual(worktrees[1]["branch"], "feat/new-feature")

    @patch('git_utils.run_git_command')
    def test_get_worktree_list_failure(self, mock_run):
        """測試獲取 worktree 列表失敗"""
        mock_run.return_value = (False, "error")
        worktrees = get_worktree_list()
        self.assertEqual(worktrees, [])


class TestConstants(unittest.TestCase):
    """測試常數定義"""

    def test_worktree_prefix_length(self):
        """測試 worktree 前綴長度"""
        self.assertEqual(WORKTREE_PREFIX_LEN, len("worktree "))

    def test_branch_prefix_length(self):
        """測試 branch 前綴長度"""
        self.assertEqual(BRANCH_PREFIX_LEN, len("branch "))


if __name__ == "__main__":
    unittest.main()
