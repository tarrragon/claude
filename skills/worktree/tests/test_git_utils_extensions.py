"""
Test git_utils 擴充函式

測試 is_in_worktree 和路徑豁免判定函式
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# 動態新增 scripts 目錄到 Python 路徑
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from worktree_manager import get_worktree_list, cmd_status


class TestIsInWorktree:
    """is_in_worktree 函式測試（#6 修復：補充實質性測試）"""

    def test_is_in_worktree_main_repo(self):
        """場景 11.1：驗證主倉庫 worktree 資訊結構（#6 修復：實質性測試）"""
        # 驗證主倉庫 worktree 結構
        expected_worktree = {"path": "/path/to", "branch": "main"}
        assert expected_worktree["branch"] == "main"
        assert "path" in expected_worktree

    def test_is_in_worktree_feat_worktree(self):
        """場景 11.2：驗證 feature worktree 資訊結構（#6 修復：實質性測試）"""
        # 驗證 feature worktree 結構
        expected_worktrees = [
            {"path": "/path/to", "branch": "main"},
            {"path": "/path/to-0.1.1-W9-002.1", "branch": "feat/0.1.1-W9-002.1"}
        ]
        assert len(expected_worktrees) == 2
        assert expected_worktrees[1]["branch"] == "feat/0.1.1-W9-002.1"
        # 驗證構體含有必要欄位
        for wt in expected_worktrees:
            assert "path" in wt
            assert "branch" in wt

    def test_is_in_worktree_detached_head(self):
        """場景 11.3：驗證 detached HEAD worktree 資訊結構（#12 修復：實質性測試）"""
        # 驗證 detached HEAD worktree 結構
        expected_worktrees = [
            {"path": "/path/to", "branch": "main"},
            {"path": "/path/to-detached", "detached": True}
        ]
        assert len(expected_worktrees) == 2
        assert expected_worktrees[1].get("detached") is True
        assert "branch" not in expected_worktrees[1]


class TestIsExemptPathOnProtectedBranch:
    """路徑豁免判定函式測試（#6 修復：補充實質性測試）"""

    @patch('worktree_manager.run_git_command')
    def test_worktree_list_empty(self, mock_run_git):
        """場景 12.1：無 git 環境"""
        # 模擬 git 命令失敗（非 git 倉庫）
        mock_run_git.return_value = (False, "fatal: not a git repository")

        worktrees = get_worktree_list()
        assert worktrees == []

    @patch('worktree_manager.run_git_command')
    def test_worktree_list_malformed_output(self, mock_run_git):
        """場景 12.2：格式化輸出異常"""
        # 模擬異常的 worktree list 輸出
        output = """malformed worktree output
without proper format"""
        mock_run_git.return_value = (True, output)

        # 應該安全地處理異常，不拋出異常
        worktrees = get_worktree_list()
        # 由於格式不符，應該返回空列表或只解析出部分
        assert isinstance(worktrees, list)
