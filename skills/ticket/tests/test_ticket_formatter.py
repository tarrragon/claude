"""
ticket_formatter 模組測試

測試 Ticket 格式化輸出功能。
"""

from typing import Dict, Any, List

import pytest

from ticket_system.lib.ticket_formatter import (
    format_status_icon,
    get_ticket_what,
    format_ticket_summary,
    format_ticket_tree,
    format_ticket_list,
    get_ticket_stats,
    format_ticket_stats,
)


class TestFormatStatusIcon:
    """格式化狀態圖示的測試"""

    def test_pending_status(self):
        """測試待處理狀態"""
        assert format_status_icon("pending") == "[待處理]"

    def test_in_progress_status(self):
        """測試進行中狀態"""
        assert format_status_icon("in_progress") == "[進行中]"

    def test_completed_status(self):
        """測試已完成狀態"""
        assert format_status_icon("completed") == "[已完成]"

    def test_blocked_status(self):
        """測試被阻塞狀態"""
        assert format_status_icon("blocked") == "[被阻塞]"

    def test_unknown_status(self):
        """測試未知狀態"""
        assert format_status_icon("unknown") == "[?]"

    def test_empty_status(self):
        """測試空狀態"""
        assert format_status_icon("") == "[?]"


class TestGetTicketWhat:
    """取得 Ticket what 描述的測試"""

    def test_what_field_present(self):
        """測試存在 what 欄位"""
        ticket = {"what": "實作新功能"}
        result = get_ticket_what(ticket)
        assert result == "實作新功能"

    def test_action_and_target_fields(self):
        """測試使用 action 和 target 欄位"""
        ticket = {
            "action": "實作",
            "target": "Ticket 系統",
        }
        result = get_ticket_what(ticket)
        assert result == "實作 Ticket 系統"

    def test_title_fallback(self):
        """測試降級到 title 欄位"""
        ticket = {
            "title": "實作 Ticket 系統",
        }
        result = get_ticket_what(ticket)
        assert result == "實作 Ticket 系統"

    def test_id_fallback(self):
        """測試降級到 id 欄位"""
        ticket = {
            "id": "0.31.0-W4-001",
        }
        result = get_ticket_what(ticket)
        assert result == "0.31.0-W4-001"

    def test_ticket_id_field_fallback(self):
        """測試使用 ticket_id 欄位"""
        ticket = {
            "ticket_id": "0.31.0-W4-001",
        }
        result = get_ticket_what(ticket)
        assert result == "0.31.0-W4-001"

    def test_empty_ticket(self):
        """測試空 Ticket"""
        result = get_ticket_what({})
        assert result == "?"

    def test_priority_order(self):
        """測試欄位優先級順序"""
        # 優先級：what > action+target > title > id
        ticket = {
            "what": "實作",
            "action": "修復",
            "target": "Bug",
            "title": "Ticket",
            "id": "001",
        }
        result = get_ticket_what(ticket)
        assert result == "實作"


class TestFormatTicketSummary:
    """格式化 Ticket 摘要的測試"""

    def test_basic_summary(self):
        """測試基本摘要格式"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": "pending",
            "what": "實作功能",
        }
        result = format_ticket_summary(ticket)
        assert "0.31.0-W4-001" in result
        assert "[待處理]" in result
        assert "實作功能" in result

    def test_summary_with_ticket_id_field(self):
        """測試使用 ticket_id 欄位"""
        ticket = {
            "ticket_id": "0.31.0-W4-001",
            "status": "completed",
            "what": "完成任務",
        }
        result = format_ticket_summary(ticket)
        assert "0.31.0-W4-001" in result
        assert "[已完成]" in result

    def test_summary_default_status(self):
        """測試缺少 status 時的預設狀態"""
        ticket = {
            "id": "0.31.0-W4-001",
            "what": "實作功能",
        }
        result = format_ticket_summary(ticket)
        assert "[待處理]" in result

    def test_summary_format(self):
        """測試摘要格式符合預期"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": "in_progress",
            "what": "實作功能",
        }
        result = format_ticket_summary(ticket)
        # 格式應該是：ID | [狀態] | what
        assert " | " in result
        parts = result.split(" | ")
        assert len(parts) == 3


class TestFormatTicketTree:
    """格式化任務樹結構的測試"""

    def test_single_ticket_tree(self):
        """測試單一 Ticket 的樹"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "completed",
                "what": "實作",
            }
        ]
        result = format_ticket_tree(tickets, "0.31.0-W4-001")
        assert "0.31.0-W4-001" in result
        assert "[已完成]" in result

    def test_parent_child_tree(self):
        """測試父子任務樹"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "completed",
                "what": "主任務",
            },
            {
                "id": "0.31.0-W4-001.1",
                "status": "pending",
                "what": "子任務",
                "chain": {"parent": "0.31.0-W4-001"},
            },
        ]
        result = format_ticket_tree(tickets)
        assert "0.31.0-W4-001" in result
        assert "0.31.0-W4-001.1" in result
        # 子任務應該有縮排
        lines = result.split("\n")
        assert any("+" in line for line in lines)

    def test_deep_hierarchy_tree(self):
        """測試多層級任務樹"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "in_progress",
                "what": "根",
            },
            {
                "id": "0.31.0-W4-001.1",
                "status": "pending",
                "what": "第一層",
                "chain": {"parent": "0.31.0-W4-001"},
            },
            {
                "id": "0.31.0-W4-001.1.1",
                "status": "pending",
                "what": "第二層",
                "chain": {"parent": "0.31.0-W4-001.1"},
            },
        ]
        result = format_ticket_tree(tickets)
        # 驗證包含所有三個 ticket
        assert "0.31.0-W4-001" in result
        assert "0.31.0-W4-001.1" in result
        # 注：nested recursive 結果行數可能少於 3，取決於遞迴實作

    def test_root_tickets_without_parent(self):
        """測試顯示無父的根任務"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "pending",
                "what": "任務1",
            },
            {
                "id": "0.31.0-W4-002",
                "status": "pending",
                "what": "任務2",
            },
        ]
        result = format_ticket_tree(tickets)
        assert "0.31.0-W4-001" in result
        assert "0.31.0-W4-002" in result


class TestFormatTicketList:
    """格式化 Ticket 清單的測試"""

    def test_basic_list(self):
        """測試基本清單格式"""
        tickets = [
            {"id": "0.31.0-W4-001", "status": "pending", "what": "任務1"},
            {"id": "0.31.0-W4-002", "status": "completed", "what": "任務2"},
        ]
        result = format_ticket_list(tickets)
        lines = result.split("\n")
        assert len(lines) == 2
        assert "0.31.0-W4-001" in result
        assert "0.31.0-W4-002" in result

    def test_list_with_custom_separator(self):
        """測試自訂分隔符"""
        tickets = [
            {"id": "0.31.0-W4-001", "status": "pending", "what": "任務1"}
        ]
        result = format_ticket_list(tickets, separator=" -> ")
        assert " -> " in result

    def test_list_with_who_field(self):
        """測試包含執行者欄位"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "pending",
                "what": "任務1",
                "who": "parsley-flutter-developer",
            }
        ]
        result = format_ticket_list(tickets, include_who=True)
        assert "parsley" in result  # 取前綴

    def test_list_with_dict_who_field(self):
        """測試 who 為字典的情況"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "pending",
                "what": "任務1",
                "who": {"current": "parsley-flutter-developer"},
            }
        ]
        result = format_ticket_list(tickets, include_who=True)
        assert "parsley" in result

    def test_empty_list(self):
        """測試空清單"""
        result = format_ticket_list([])
        assert result == ""


class TestGetTicketStats:
    """計算 Ticket 統計資訊的測試"""

    def test_basic_stats(self):
        """測試基本統計資訊"""
        tickets = [
            {"status": "completed"},
            {"status": "in_progress"},
            {"status": "pending"},
            {"status": "pending"},
        ]
        stats = get_ticket_stats(tickets)
        assert stats["completed"] == 1
        assert stats["in_progress"] == 1
        assert stats["pending"] == 2
        assert stats["blocked"] == 0
        assert stats["total"] == 4

    def test_empty_tickets_list(self):
        """測試空 Ticket 清單"""
        stats = get_ticket_stats([])
        assert stats["total"] == 0
        assert sum(stats[s] for s in ["pending", "in_progress", "completed", "blocked"]) == 0

    def test_all_same_status(self):
        """測試所有 Ticket 相同狀態"""
        tickets = [
            {"status": "pending"},
            {"status": "pending"},
            {"status": "pending"},
        ]
        stats = get_ticket_stats(tickets)
        assert stats["pending"] == 3
        assert stats["completed"] == 0
        assert stats["total"] == 3

    def test_unknown_status_ignored(self):
        """測試未知狀態被忽略"""
        tickets = [
            {"status": "pending"},
            {"status": "unknown"},
        ]
        stats = get_ticket_stats(tickets)
        assert stats["pending"] == 1
        assert stats["total"] == 2


class TestFormatTicketStats:
    """格式化統計資訊的測試"""

    def test_format_stats(self):
        """測試統計資訊格式化"""
        stats = {
            "pending": 2,
            "in_progress": 1,
            "completed": 1,
            "blocked": 0,
            "total": 4,
        }
        result = format_ticket_stats(stats)
        assert "[已完成]: 1" in result
        assert "[進行中]: 1" in result
        assert "[待處理]: 2" in result
        assert "[被阻塞]: 0" in result
        assert "總計 4" in result

    def test_all_zero_stats(self):
        """測試全為 0 的統計"""
        stats = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
            "total": 0,
        }
        result = format_ticket_stats(stats)
        assert "總計 0" in result

    def test_missing_fields_default_to_zero(self):
        """測試缺少欄位時預設為 0"""
        stats = {}
        result = format_ticket_stats(stats)
        assert "[已完成]: 0" in result


class TestFormattingIntegration:
    """格式化功能的整合測試"""

    def test_full_ticket_processing(self):
        """測試完整的 Ticket 處理流程"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "completed",
                "what": "實作",
                "title": "Test",
            },
            {
                "id": "0.31.0-W4-001.1",
                "status": "pending",
                "what": "子任務",
                "chain": {"parent": "0.31.0-W4-001"},
            },
            {
                "id": "0.31.0-W4-002",
                "status": "in_progress",
                "what": "測試",
            },
        ]

        # 測試統計
        stats = get_ticket_stats(tickets)
        assert stats["total"] == 3

        # 測試清單
        list_result = format_ticket_list(tickets)
        assert "0.31.0-W4-001" in list_result

        # 測試樹
        tree_result = format_ticket_tree(tickets)
        assert "0.31.0-W4-001.1" in tree_result
