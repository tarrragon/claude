"""
Test create 子命令

涵蓋正常建立、各種錯誤情況、dry-run 模式等
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# 動態新增 scripts 目錄到 Python 路徑
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from worktree_manager import cmd_create


class TestCreateCommand:
    """create 子命令測試"""

    def test_create_invalid_ticket_id(self, capsys):
        """場景 5.1：Ticket ID 格式無效"""
        result = cmd_create("my-feature")
        assert result == 1

        captured = capsys.readouterr()
        assert "無效的 Ticket ID 格式" in captured.out
        assert "my-feature" in captured.out

    def test_create_dry_run_valid_ticket(self, capsys):
        """場景 4.3：dry-run 模式"""
        result = cmd_create("0.1.1-W9-002.1", dry_run=True)
        assert result == 0

        captured = capsys.readouterr()
        assert "Dry Run" in captured.out
        assert "git worktree add" in captured.out
        assert "feat/0.1.1-W9-002.1" in captured.out

    @patch('worktree_manager.check_branch_exists')
    def test_create_branch_already_exists(self, mock_check_branch, capsys):
        """場景 5.2：分支已存在"""
        # 第一次檢查 base 分支（main），第二次檢查 feat 分支
        mock_check_branch.side_effect = [True, True]

        result = cmd_create("0.1.1-W9-002.1")
        assert result == 1

        captured = capsys.readouterr()
        assert "分支已存在" in captured.out

    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_worktree_path_exists(self, mock_path_exists, mock_check_branch, capsys):
        """場景 5.3：worktree 路徑已存在"""
        # 第一次檢查 base 分支（存在），第二次檢查 feat 分支（不存在）
        mock_check_branch.side_effect = [True, False]
        mock_path_exists.return_value = True

        result = cmd_create("0.1.1-W9-002.1")
        assert result == 1

        captured = capsys.readouterr()
        assert "目錄已存在" in captured.out

    @patch('worktree_manager.check_branch_exists')
    def test_create_base_branch_not_exists(self, mock_check_branch, capsys):
        """場景 5.4：base 分支不存在"""
        # 模擬 base 分支不存在
        mock_check_branch.side_effect = lambda b: False if b == "develop" else True

        result = cmd_create("0.1.1-W9-002.1", base="develop")
        assert result == 1

        captured = capsys.readouterr()
        assert "基礎分支不存在" in captured.out
        assert "develop" in captured.out

    @patch('worktree_manager.check_branch_exists')
    def test_create_with_custom_base_dry_run(self, mock_check_branch, capsys):
        """場景 4.2：指定 base 分支 + dry-run"""
        # dry-run 模式下不需要檢查分支，但為了測試完整性，模擬分支存在
        mock_check_branch.return_value = True

        result = cmd_create("0.1.1-W9-002.1", base="develop", dry_run=True)
        assert result == 0

        captured = capsys.readouterr()
        assert "develop" in captured.out

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_success_valid_ticket(self, mock_path_exists, mock_check_branch, mock_run_git, capsys):
        """場景 5.5：成功建立 worktree（#5 修復：補充成功路徑測試）"""
        # 模擬檢查：base 分支存在，feat 分支不存在
        mock_check_branch.side_effect = [True, False]
        # 模擬路徑不存在
        mock_path_exists.return_value = False
        # 模擬 git worktree add 成功
        mock_run_git.return_value = (True, "正在建立 worktree")

        result = cmd_create("0.1.1-W9-002.1")
        assert result == 0

        captured = capsys.readouterr()
        assert "建立成功" in captured.out
        assert "0.1.1-W9-002.1" in captured.out
        assert "feat/0.1.1-W9-002.1" in captured.out

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_success_with_custom_base(self, mock_path_exists, mock_check_branch, mock_run_git, capsys):
        """場景 5.6：成功建立 worktree（自訂 base 分支）"""
        # 模擬檢查：develop 分支存在，feat 分支不存在
        mock_check_branch.side_effect = [True, False]
        # 模擬路徑不存在
        mock_path_exists.return_value = False
        # 模擬 git worktree add 成功
        mock_run_git.return_value = (True, "")

        result = cmd_create("0.1.1-W9-002.1", base="develop")
        assert result == 0

        captured = capsys.readouterr()
        assert "建立成功" in captured.out
        assert "develop" in captured.out
