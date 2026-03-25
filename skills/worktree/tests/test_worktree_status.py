"""
Test status 子命令

涵蓋查看全部 worktree、查詢特定 Ticket、無 worktree 等情況
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# 動態新增 scripts 目錄到 Python 路徑
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from worktree_manager import cmd_status


class TestStatusCommand:
    """status 子命令測試"""

    @patch('worktree_manager.get_worktree_list')
    def test_status_no_worktree(self, mock_get_worktree, capsys):
        """場景 6.2 / 9：只有主倉庫（無其他 worktree）"""
        # 模擬只有主倉庫
        mock_get_worktree.return_value = [
            {"path": "/Users/mac-eric/project/ccsession", "branch": "main"}
        ]

        result = cmd_status()
        assert result == 0

        captured = capsys.readouterr()
        assert "目前沒有任何 worktree" in captured.out
        assert "/worktree create" in captured.out

    @patch('worktree_manager.get_worktree_uncommitted_count')
    @patch('worktree_manager.get_worktree_ahead_behind')
    @patch('worktree_manager.get_worktree_list')
    def test_status_show_all_worktrees(self, mock_get_worktree, mock_ahead_behind,
                                       mock_uncommitted, capsys):
        """場景 6.1：顯示多個 worktree（無參數）"""
        # 模擬 3 個 worktree
        mock_get_worktree.return_value = [
            {"path": "/Users/mac-eric/project/ccsession", "branch": "main"},
            {"path": "/Users/mac-eric/project/ccsession-0.1.1-W9-002.1",
             "branch": "feat/0.1.1-W9-002.1"},
            {"path": "/Users/mac-eric/project/ccsession-0.1.1-W9-002.2",
             "branch": "feat/0.1.1-W9-002.2"},
        ]
        mock_ahead_behind.side_effect = [(3, 0), (1, 1)]
        mock_uncommitted.side_effect = [0, 2, 0]

        result = cmd_status()
        assert result == 0

        captured = capsys.readouterr()
        assert "Worktree 狀態（共 3 個）" in captured.out
        assert "[主倉庫]" in captured.out
        assert "[0.1.1-W9-002.1]" in captured.out
        assert "[0.1.1-W9-002.2]" in captured.out
        assert "feat/0.1.1-W9-002.1" in captured.out

    @patch('worktree_manager.get_worktree_uncommitted_count')
    @patch('worktree_manager.get_worktree_ahead_behind')
    @patch('worktree_manager.get_worktree_list')
    def test_status_specific_ticket(self, mock_get_worktree, mock_ahead_behind,
                                    mock_uncommitted, capsys):
        """場景 7.1：查詢存在的 Ticket"""
        mock_get_worktree.return_value = [
            {"path": "/Users/mac-eric/project/ccsession", "branch": "main"},
            {"path": "/Users/mac-eric/project/ccsession-0.1.1-W9-002.1",
             "branch": "feat/0.1.1-W9-002.1"},
        ]
        # 為了正確應用 mock，需要設定相同次數的返回值
        mock_ahead_behind.return_value = (3, 0)
        mock_uncommitted.side_effect = [0, 2]  # main worktree 和 feat worktree

        result = cmd_status("0.1.1-W9-002.1")
        assert result == 0

        captured = capsys.readouterr()
        # 當指定 ticket_id 時，只應顯示該 ticket
        assert "0.1.1-W9-002.1" in captured.out

    @patch('worktree_manager.get_worktree_list')
    def test_status_ticket_not_found(self, mock_get_worktree, capsys):
        """場景 7.2 / 10：查詢不存在的 Ticket"""
        mock_get_worktree.return_value = [
            {"path": "/Users/mac-eric/project/ccsession", "branch": "main"},
            {"path": "/Users/mac-eric/project/ccsession-0.1.1-W9-002.2",
             "branch": "feat/0.1.1-W9-002.2"},
        ]

        result = cmd_status("0.1.1-W9-002.1")
        assert result == 1

        captured = capsys.readouterr()
        assert "找不到 Ticket" in captured.out
        assert "0.1.1-W9-002.1" in captured.out
        assert "0.1.1-W9-002.2" in captured.out
        assert "/worktree create 0.1.1-W9-002.1" in captured.out
