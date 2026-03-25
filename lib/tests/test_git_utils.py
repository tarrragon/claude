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
    get_current_branch,
    get_project_root,
    get_uncommitted_files,
    _get_uncommitted_status_lines,
    get_worktree_list,
    is_allowed_branch,
    is_protected_branch,
    run_git_command,
    FileStatus,
    BRANCH_PREFIX_LEN,
    WORKTREE_PREFIX_LEN,
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


class TestFileStatus(unittest.TestCase):
    """測試 FileStatus dataclass"""

    def test_file_status_creation(self):
        """測試 FileStatus 建立"""
        file = FileStatus(status=" M", file_path="file.txt")
        self.assertEqual(file.status, " M")
        self.assertEqual(file.file_path, "file.txt")

    def test_is_modified(self):
        """測試是否為修改狀態"""
        file = FileStatus(status=" M", file_path="file.txt")
        self.assertTrue(file.is_modified)
        self.assertFalse(file.is_added)
        self.assertFalse(file.is_untracked)

    def test_is_added(self):
        """測試是否為新增狀態"""
        file = FileStatus(status="A ", file_path="new.py")
        self.assertFalse(file.is_modified)
        self.assertTrue(file.is_added)
        self.assertFalse(file.is_untracked)

    def test_is_untracked(self):
        """測試是否為未追蹤"""
        file = FileStatus(status="??", file_path="untracked.txt")
        self.assertFalse(file.is_modified)
        self.assertFalse(file.is_added)
        self.assertTrue(file.is_untracked)

    def test_is_staged(self):
        """測試是否有 staged 變更"""
        staged = FileStatus(status="M ", file_path="file.txt")
        unstaged = FileStatus(status=" M", file_path="file.txt")
        untracked = FileStatus(status="??", file_path="file.txt")
        
        self.assertTrue(staged.is_staged)
        self.assertFalse(unstaged.is_staged)
        self.assertFalse(untracked.is_staged)

    def test_file_status_str(self):
        """測試 FileStatus 字串表示"""
        file = FileStatus(status=" M", file_path="file.txt")
        self.assertEqual(str(file), " M file.txt")


class TestUncommittedStatusLines(unittest.TestCase):
    """測試 get_uncommitted_status_lines 和相關函式"""

    @patch('git_utils.run_git_command')
    def test_has_uncommitted_changes(self, mock_run):
        """測試有未提交變更時回傳非空列表"""
        mock_run.return_value = (True, """ M file1.txt
?? file2.txt
A  file3.py
""")
        status_lines = _get_uncommitted_status_lines()
        self.assertEqual(len(status_lines), 3)
        self.assertIn(" M file1.txt", status_lines)
        self.assertIn("?? file2.txt", status_lines)
        self.assertIn("A  file3.py", status_lines)

    @patch('git_utils.run_git_command')
    def test_no_uncommitted_changes(self, mock_run):
        """測試無未提交變更時回傳空列表"""
        mock_run.return_value = (True, "")
        status_lines = _get_uncommitted_status_lines()
        self.assertEqual(status_lines, [])

    @patch('git_utils.run_git_command')
    def test_git_command_failure(self, mock_run):
        """測試 git 命令失敗時回傳空列表"""
        mock_run.return_value = (False, "fatal: not a git repository")
        status_lines = _get_uncommitted_status_lines()
        self.assertEqual(status_lines, [])

    @patch('git_utils.run_git_command')
    def test_porcelain_format_preserved(self, mock_run):
        """測試 porcelain 格式狀態行被保留"""
        mock_run.return_value = (True, """ M modified.txt
?? untracked.txt
 D deleted.txt
""")
        status_lines = _get_uncommitted_status_lines()
        # 驗證格式完整性（含狀態和空格）
        self.assertTrue(any(line.startswith(" M") for line in status_lines))
        self.assertTrue(any(line.startswith("??") for line in status_lines))
        self.assertTrue(any(line.startswith(" D") for line in status_lines))


class TestUncommittedFiles(unittest.TestCase):
    """測試 get_uncommitted_files 高階 API"""

    @patch('git_utils.run_git_command')
    def test_get_uncommitted_files_with_changes(self, mock_run):
        """測試有未提交變更時回傳 FileStatus 列表"""
        mock_run.return_value = (True, """ M file1.txt
?? file2.txt
A  file3.py
""")
        files = get_uncommitted_files()
        
        self.assertEqual(len(files), 3)
        
        # 驗證第一個檔案（修改）
        self.assertEqual(files[0].status, " M")
        self.assertEqual(files[0].file_path, "file1.txt")
        self.assertTrue(files[0].is_modified)
        self.assertFalse(files[0].is_untracked)
        
        # 驗證第二個檔案（未追蹤）
        self.assertEqual(files[1].status, "??")
        self.assertEqual(files[1].file_path, "file2.txt")
        self.assertTrue(files[1].is_untracked)
        
        # 驗證第三個檔案（新增）
        self.assertEqual(files[2].status, "A ")
        self.assertEqual(files[2].file_path, "file3.py")
        self.assertTrue(files[2].is_added)

    @patch('git_utils.run_git_command')
    def test_get_uncommitted_files_empty(self, mock_run):
        """測試無未提交變更時回傳空列表"""
        mock_run.return_value = (True, "")
        files = get_uncommitted_files()
        self.assertEqual(files, [])

    @patch('git_utils.run_git_command')
    def test_get_uncommitted_files_failure(self, mock_run):
        """測試 git 命令失敗時回傳空列表"""
        mock_run.return_value = (False, "fatal: not a git repository")
        files = get_uncommitted_files()
        self.assertEqual(files, [])

    @patch('git_utils.run_git_command')
    def test_get_uncommitted_files_parse_multiple_files(self, mock_run):
        """測試正確解析多個變更檔案"""
        mock_run.return_value = (True, """M  modified_staged.txt
 M unstaged_modified.txt
?? new_untracked.txt
A  added_staged.py
 D deleted_unstaged.py
""")
        files = get_uncommitted_files()
        
        self.assertEqual(len(files), 5)
        
        # 驗證每個檔案的狀態
        statuses = [f.status for f in files]
        file_paths = [f.file_path for f in files]
        
        self.assertIn("M ", statuses)
        self.assertIn(" M", statuses)
        self.assertIn("??", statuses)
        self.assertIn("A ", statuses)
        self.assertIn(" D", statuses)
        
        self.assertIn("modified_staged.txt", file_paths)
        self.assertIn("unstaged_modified.txt", file_paths)
        self.assertIn("new_untracked.txt", file_paths)
        self.assertIn("added_staged.py", file_paths)
        self.assertIn("deleted_unstaged.py", file_paths)


if __name__ == "__main__":
    unittest.main()
