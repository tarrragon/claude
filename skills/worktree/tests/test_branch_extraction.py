"""
Test 反推邏輯和 ahead/behind 計算

涵蓋 extract_ticket_id_from_branch, get_worktree_ahead_behind 等
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# 動態新增 scripts 目錄到 Python 路徑
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from worktree_manager import (
    extract_ticket_id_from_branch,
    get_worktree_ahead_behind,
    get_worktree_uncommitted_count,
)


class TestExtractTicketIdFromBranch:
    """extract_ticket_id_from_branch 測試"""

    def test_extract_valid_feat_branch(self):
        """場景 8.1：合法 feat 分支"""
        result = extract_ticket_id_from_branch("feat/0.1.1-W9-002.1")
        assert result == "0.1.1-W9-002.1"

    def test_extract_root_ticket_branch(self):
        """場景 8.2：根任務分支"""
        result = extract_ticket_id_from_branch("feat/0.1.1-W9-002")
        assert result == "0.1.1-W9-002"

    def test_extract_protected_branch(self):
        """場景 8.3：保護分支（main）"""
        result = extract_ticket_id_from_branch("main")
        assert result is None

    def test_extract_non_ticket_feat_branch(self):
        """場景 8.4：非 ticket 格式的 feat 分支"""
        result = extract_ticket_id_from_branch("feat/my-custom-feature")
        assert result is None

    def test_extract_detached_head(self):
        """場景 8.5：detached HEAD"""
        result = extract_ticket_id_from_branch("")
        assert result is None


class TestGetWorktreeAheadBehind:
    """get_worktree_ahead_behind 測試"""

    @patch('worktree_manager.run_git_command')
    def test_ahead_behind_normal(self, mock_run_git):
        """場景 9.1：正常計算"""
        # 模擬 branch 領先 3，落後 0
        mock_run_git.side_effect = [
            (True, "3"),   # ahead
            (True, "0"),   # behind
        ]

        ahead, behind = get_worktree_ahead_behind("feat/0.1.1-W9-002.1", "main")
        assert ahead == 3
        assert behind == 0

    @patch('worktree_manager.run_git_command')
    def test_ahead_behind_diverged(self, mock_run_git):
        """場景 9.2：分支落後 base"""
        # 模擬 branch 領先 1，落後 1
        mock_run_git.side_effect = [
            (True, "1"),   # ahead
            (True, "1"),   # behind
        ]

        ahead, behind = get_worktree_ahead_behind("feat/0.1.1-W9-002.2", "main")
        assert ahead == 1
        assert behind == 1

    @patch('worktree_manager.run_git_command')
    def test_ahead_behind_error_handling(self, mock_run_git):
        """場景 9.3：base 分支不存在（錯誤處理）"""
        # 模擬 git 命令失敗
        mock_run_git.side_effect = [
            (False, "error"),  # ahead 失敗
        ]

        ahead, behind = get_worktree_ahead_behind("feat/0.1.1-W9-002.1", "nonexistent")
        # 應該返回安全的預設值
        assert ahead == 0
        assert behind == 0


class TestGetWorktreeUncommittedCount:
    """get_worktree_uncommitted_count 測試"""

    @patch('worktree_manager.run_git_command')
    def test_uncommitted_with_changes(self, mock_run_git):
        """場景 10.1：有未 commit 變更"""
        # 模擬 2 行未 commit
        mock_run_git.return_value = (True, "M  ui/lib/main.dart\n?? test.txt")

        count = get_worktree_uncommitted_count("/path/to/worktree")
        assert count == 2

    @patch('worktree_manager.run_git_command')
    def test_uncommitted_no_changes(self, mock_run_git):
        """場景 10.2：無未 commit 變更"""
        # 模擬無變更
        mock_run_git.return_value = (True, "")

        count = get_worktree_uncommitted_count("/path/to/worktree")
        assert count == 0
