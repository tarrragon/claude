"""
Test Ticket ID 解析和推導函式

涵蓋 parse_ticket_id, derive_branch_name, derive_worktree_path 等
"""

import pytest
import sys
import os
from pathlib import Path

# 動態新增 scripts 目錄到 Python 路徑
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from worktree_manager import (
    is_valid_ticket_id,
    derive_branch_name,
    derive_worktree_path,
)


class TestParseTicketId:
    """is_valid_ticket_id 測試"""

    def test_valid_root_ticket(self, sample_ticket_ids):
        """場景 1.1：正常格式 - 根任務"""
        assert is_valid_ticket_id(sample_ticket_ids["valid_root"]) is True

    def test_valid_subtask_ticket(self, sample_ticket_ids):
        """場景 1.2：子任務格式"""
        assert is_valid_ticket_id(sample_ticket_ids["valid_subtask"]) is True

    def test_valid_nested_ticket(self, sample_ticket_ids):
        """場景 1.2：多層子任務格式"""
        assert is_valid_ticket_id(sample_ticket_ids["valid_nested"]) is True

    def test_invalid_format_free_text(self, sample_ticket_ids):
        """場景 1.4：無效格式 - 自由文字"""
        assert is_valid_ticket_id(sample_ticket_ids["invalid_format"]) is False

    def test_invalid_format_no_w(self, sample_ticket_ids):
        """場景 1.3：無效格式 - 缺少 W"""
        assert is_valid_ticket_id(sample_ticket_ids["invalid_no_w"]) is False

    def test_invalid_format_with_v_prefix(self):
        """場景 1.5：無效格式 - v 前綴"""
        assert is_valid_ticket_id("v0.1.1-W9-002") is False

    def test_invalid_format_single_digit_version(self):
        """場景 1.6：無效格式 - 版本號層級不足"""
        assert is_valid_ticket_id("0-W9-002") is False


class TestDeriveBranchName:
    """derive_branch_name 測試"""

    @pytest.mark.parametrize("ticket_id,expected", [
        ("0.1.1-W9-002", "feat/0.1.1-W9-002"),
        ("0.1.1-W9-002.1", "feat/0.1.1-W9-002.1"),
        ("0.1.1-W9-002.1.2.3", "feat/0.1.1-W9-002.1.2.3"),
        ("0.31.0-W3-001", "feat/0.31.0-W3-001"),
    ])
    def test_derive_branch_name_parametrized(self, ticket_id, expected):
        """場景 2.1-2.3：推導分支名稱"""
        assert derive_branch_name(ticket_id) == expected


class TestDeriveWorktreePath:
    """derive_worktree_path 測試"""

    def test_derive_worktree_path_basic(self, monkeypatch, tmp_path):
        """場景 3.1：基本路徑推導"""
        # Mock get_project_root
        def mock_get_project_root():
            return str(tmp_path / "ccsession")

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import worktree_manager
        monkeypatch.setattr(worktree_manager, "get_project_root", mock_get_project_root)

        # 測試推導
        ticket_id = "0.1.1-W9-002.1"
        result = derive_worktree_path(ticket_id)

        expected = str(tmp_path / f"ccsession-{ticket_id}")
        assert result == expected

    def test_derive_worktree_path_special_chars(self, monkeypatch, tmp_path):
        """場景 3.2：特殊字元目錄名"""
        # Mock get_project_root，模擬含點的目錄名
        def mock_get_project_root():
            return str(tmp_path / "my.project")

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import worktree_manager
        monkeypatch.setattr(worktree_manager, "get_project_root", mock_get_project_root)

        ticket_id = "0.1.0-W1-001"
        result = derive_worktree_path(ticket_id)

        expected = str(tmp_path / f"my.project-{ticket_id}")
        assert result == expected
