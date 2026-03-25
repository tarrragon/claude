"""
測試 W16-002 新拆分的助手函式

涵蓋 7 個新拆分函式的單元測試：
1. _get_feature_branch_metrics
2. _determine_ticket_label_and_metrics
3. _build_worktree_display_info
4. _merge_build_warnings_list
5. _merge_collect_warnings_for_branch
6. _merge_validate_preconditions
7. _cleanup_verify_all_gates
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# 加入模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from worktree_manager import (
    _get_feature_branch_metrics,
    _determine_ticket_label_and_metrics,
    _build_worktree_display_info,
    _merge_build_warnings_list,
    _merge_collect_warnings_for_branch,
    _merge_validate_preconditions,
    _cleanup_verify_all_gates,
)
from messages import MergeMessages, CleanupMessages


class TestGetFeatureBranchMetrics:
    """測試 _get_feature_branch_metrics"""

    @patch('worktree_manager.get_worktree_ahead_behind')
    @patch('worktree_manager.extract_ticket_id_from_branch')
    def test_feature_branch_with_valid_ticket_id(self, mock_extract, mock_ahead_behind):
        """場景 1.1：正常 feature 分支，能提取 Ticket ID"""
        mock_extract.return_value = "0.1.1-W9-002"
        mock_ahead_behind.return_value = (3, 1)

        label, ahead, behind = _get_feature_branch_metrics("feat/0.1.1-W9-002")

        assert label == "0.1.1-W9-002"
        assert ahead == 3
        assert behind == 1

    @patch('worktree_manager.get_worktree_ahead_behind')
    @patch('worktree_manager.extract_ticket_id_from_branch')
    def test_feature_branch_with_invalid_ticket_id(self, mock_extract, mock_ahead_behind):
        """場景 1.2：feature 分支但無法提取 Ticket ID"""
        mock_extract.return_value = None
        mock_ahead_behind.return_value = (0, 0)

        label, ahead, behind = _get_feature_branch_metrics("feat/my-feature")

        assert label == "無法辨識"
        assert ahead == 0
        assert behind == 0


class TestDetermineTicketLabelAndMetrics:
    """測試 _determine_ticket_label_and_metrics"""

    @patch('worktree_manager._get_feature_branch_metrics')
    def test_detached_head(self, mock_feature_metrics):
        """場景 2.1：detached HEAD"""
        label, ahead, behind = _determine_ticket_label_and_metrics(
            branch="abc1234",
            is_detached=True,
            is_main=False
        )

        assert label == "detached"
        assert ahead == 0
        assert behind == 0
        mock_feature_metrics.assert_not_called()

    @patch('worktree_manager._get_feature_branch_metrics')
    def test_main_branch(self, mock_feature_metrics):
        """場景 2.2：主倉庫分支"""
        label, ahead, behind = _determine_ticket_label_and_metrics(
            branch="main",
            is_detached=False,
            is_main=True
        )

        assert label == "主倉庫"
        assert ahead == 0
        assert behind == 0
        mock_feature_metrics.assert_not_called()

    @patch('worktree_manager._get_feature_branch_metrics')
    def test_feature_branch(self, mock_feature_metrics):
        """場景 2.3：feature 分支"""
        mock_feature_metrics.return_value = ("0.1.1-W9-002", 2, 0)

        label, ahead, behind = _determine_ticket_label_and_metrics(
            branch="feat/0.1.1-W9-002",
            is_detached=False,
            is_main=False
        )

        assert label == "0.1.1-W9-002"
        assert ahead == 2
        assert behind == 0
        mock_feature_metrics.assert_called_once_with("feat/0.1.1-W9-002")


class TestBuildWorktreeDisplayInfo:
    """測試 _build_worktree_display_info"""

    @patch('worktree_manager.is_protected_branch')
    @patch('worktree_manager._determine_ticket_label_and_metrics')
    @patch('worktree_manager.get_worktree_uncommitted_count')
    def test_build_feature_worktree(self, mock_uncommitted, mock_metrics, mock_protected):
        """場景 3.1：feature worktree"""
        mock_uncommitted.return_value = 2
        mock_protected.return_value = False
        mock_metrics.return_value = ("0.1.1-W9-002", 3, 0)

        wt = {
            "path": "/path/ccsession-0.1.1-W9-002",
            "branch": "feat/0.1.1-W9-002",
            "detached": False
        }

        result = _build_worktree_display_info(wt)

        assert result["label"] == "0.1.1-W9-002"
        assert result["path"] == "/path/ccsession-0.1.1-W9-002"
        assert result["branch"] == "feat/0.1.1-W9-002"
        assert result["ahead"] == 3
        assert result["behind"] == 0
        assert result["uncommitted"] == 2
        assert result["is_main"] is False
        assert result["is_detached"] is False

    @patch('worktree_manager.is_protected_branch')
    @patch('worktree_manager._determine_ticket_label_and_metrics')
    @patch('worktree_manager.get_worktree_uncommitted_count')
    def test_build_main_worktree(self, mock_uncommitted, mock_metrics, mock_protected):
        """場景 3.2：主倉庫 worktree"""
        mock_uncommitted.return_value = 0
        mock_protected.return_value = True
        mock_metrics.return_value = ("主倉庫", 0, 0)

        wt = {
            "path": "/path/ccsession",
            "branch": "main",
            "detached": False
        }

        result = _build_worktree_display_info(wt)

        assert result["label"] == "主倉庫"
        assert result["is_main"] is True


class TestMergeBuildWarningsList:
    """測試 _merge_build_warnings_list"""

    def test_no_warnings(self):
        """場景 4.1：無警告（ahead > 0, behind == 0）"""
        warnings = _merge_build_warnings_list(ahead=3, behind=0, status_msg="")

        assert len(warnings) == 0

    def test_no_new_commits_warning(self):
        """場景 4.2：ahead == 0 警告"""
        warnings = _merge_build_warnings_list(ahead=0, behind=0, status_msg="")

        assert len(warnings) == 1
        assert MergeMessages.NO_NEW_COMMITS.format(base="main") in warnings[0]

    def test_behind_warning(self):
        """場景 4.3：behind > 0 警告"""
        warnings = _merge_build_warnings_list(ahead=2, behind=1, status_msg="")

        assert len(warnings) == 1
        assert "main" in warnings[0]
        assert "1" in warnings[0]

    def test_status_msg_warning(self):
        """場景 4.4：包含狀態訊息警告"""
        status = "[警告] Ticket 狀態不確定"
        warnings = _merge_build_warnings_list(ahead=3, behind=0, status_msg=status)

        assert len(warnings) == 1
        assert status in warnings[0]

    def test_multiple_warnings(self):
        """場景 4.5：多個警告"""
        status = "[警告] Ticket 狀態"
        warnings = _merge_build_warnings_list(ahead=0, behind=2, status_msg=status)

        assert len(warnings) >= 2


class TestMergeCollectWarningsForBranch:
    """測試 _merge_collect_warnings_for_branch"""

    @patch('worktree_manager._merge_build_warnings_list')
    @patch('worktree_manager._merge_validate_ticket_status')
    @patch('worktree_manager.get_worktree_ahead_behind')
    def test_collect_warnings_success(self, mock_ahead_behind, mock_validate, mock_build_warnings):
        """場景 5.1：正常收集警告"""
        mock_ahead_behind.return_value = (3, 0)
        mock_validate.return_value = (True, "")
        mock_build_warnings.return_value = []

        ahead, behind, warnings = _merge_collect_warnings_for_branch(
            "feat/0.1.1-W9-002",
            "0.1.1-W9-002"
        )

        assert ahead == 3
        assert behind == 0
        assert warnings == []

    @patch('worktree_manager._merge_build_warnings_list')
    @patch('worktree_manager._merge_validate_ticket_status')
    @patch('worktree_manager.get_worktree_ahead_behind')
    def test_collect_warnings_with_status_warning(self, mock_ahead_behind, mock_validate, mock_build_warnings):
        """場景 5.2：包含狀態警告"""
        mock_ahead_behind.return_value = (2, 1)
        mock_validate.return_value = (True, "[警告] Ticket 狀態不確定")
        mock_build_warnings.return_value = ["[警告] Ticket 狀態不確定", "behind warning"]

        ahead, behind, warnings = _merge_collect_warnings_for_branch(
            "feat/0.1.1-W9-002",
            "0.1.1-W9-002"
        )

        assert ahead == 2
        assert behind == 1
        assert len(warnings) == 2


class TestMergeValidatePreconditions:
    """測試 _merge_validate_preconditions"""

    @patch('worktree_manager._check_working_tree_clean')
    @patch('worktree_manager._merge_validate_ticket_status')
    def test_preconditions_pass(self, mock_validate_ticket, mock_check_tree, capsys):
        """場景 6.1：前置條件通過"""
        mock_validate_ticket.return_value = (True, "")
        mock_check_tree.return_value = (True, 0)

        result = _merge_validate_preconditions(
            "0.1.1-W9-002",
            "/path/ccsession-0.1.1-W9-002"
        )

        assert result is True

    @patch('worktree_manager._check_working_tree_clean')
    @patch('worktree_manager._merge_validate_ticket_status')
    def test_ticket_status_failed(self, mock_validate_ticket, mock_check_tree, capsys):
        """場景 6.2：Ticket 狀態檢查失敗"""
        mock_validate_ticket.return_value = (False, "[阻擋] Ticket 未完成")
        mock_check_tree.return_value = (True, 0)

        result = _merge_validate_preconditions(
            "0.1.1-W9-002",
            "/path/ccsession-0.1.1-W9-002"
        )

        assert result is False
        captured = capsys.readouterr()
        assert "阻擋" in captured.out

    @patch('worktree_manager._check_working_tree_clean')
    @patch('worktree_manager._merge_validate_ticket_status')
    def test_dirty_working_tree(self, mock_validate_ticket, mock_check_tree, capsys):
        """場景 6.3：working tree 有未 commit 變更"""
        mock_validate_ticket.return_value = (True, "")
        mock_check_tree.return_value = (False, 3)

        result = _merge_validate_preconditions(
            "0.1.1-W9-002",
            "/path/ccsession-0.1.1-W9-002"
        )

        assert result is False
        captured = capsys.readouterr()
        assert "3" in captured.out


class TestCleanupVerifyAllGates:
    """測試 _cleanup_verify_all_gates"""

    @patch('worktree_manager._cleanup_check_level2_and_3')
    @patch('worktree_manager._cleanup_check_level1')
    def test_all_gates_pass(self, mock_level1, mock_level2_3, capsys):
        """場景 7.1：全部閘門通過"""
        mock_level1.return_value = (True, 0)
        mock_level2_3.return_value = (True, 0)

        result = _cleanup_verify_all_gates(
            "/path/ccsession-0.1.1-W9-002",
            "feat/0.1.1-W9-002",
            force=False
        )

        assert result == 0

    @patch('worktree_manager._cleanup_check_level2_and_3')
    @patch('worktree_manager._cleanup_check_level1')
    def test_level1_fails(self, mock_level1, mock_level2_3, capsys):
        """場景 7.2：Level 1 檢查失敗（永不可繞過）"""
        mock_level1.return_value = (False, 2)
        mock_level2_3.return_value = (True, 0)

        result = _cleanup_verify_all_gates(
            "/path/ccsession-0.1.1-W9-002",
            "feat/0.1.1-W9-002",
            force=False
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "拒絕" in captured.out or "2" in captured.out

    @patch('worktree_manager._cleanup_check_level2_and_3')
    @patch('worktree_manager._cleanup_check_level1')
    def test_level2_3_fails(self, mock_level1, mock_level2_3, capsys):
        """場景 7.3：Level 2/3 檢查失敗"""
        mock_level1.return_value = (True, 0)
        mock_level2_3.return_value = (False, 1)

        result = _cleanup_verify_all_gates(
            "/path/ccsession-0.1.1-W9-002",
            "feat/0.1.1-W9-002",
            force=False
        )

        assert result == 1
