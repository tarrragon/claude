"""
track_board.py 模組測試

測試 Kanban 看板的視覺化呈現功能，包括寬度計算、標題截斷、樹狀結構和看板渲染。
"""

import argparse
from typing import Dict, Any, List
from unittest.mock import Mock, patch

import pytest

from ticket_system.commands.track_board import (
    simplify_ticket_id,
    extract_wave_number,
    build_tree_structure,
    render_tree_node,
    filter_incomplete_tickets,
    group_by_wave,
    render_board_tree,
    execute_board,
)
from ticket_system.lib.command_tracking_messages import TrackBoardMessages


# ============================================================================
# Test Fixtures - 測試資料
# ============================================================================

@pytest.fixture
def ticket_simple() -> Dict[str, Any]:
    """簡單英文任務"""
    return {
        "id": "0.31.0-W1-001",
        "title": "Simple Task",
        "status": "pending",
        "priority": "P1"
    }


@pytest.fixture
def ticket_chinese() -> Dict[str, Any]:
    """純中文任務"""
    return {
        "id": "0.31.0-W2-001",
        "title": "複雜的中文任務標題",
        "status": "in_progress",
        "priority": "P0"
    }


@pytest.fixture
def ticket_mixed() -> Dict[str, Any]:
    """中英混合任務"""
    return {
        "id": "0.31.0-W3-001",
        "title": "Mixed 中文 and English Title",
        "status": "completed",
        "priority": "P2"
    }


@pytest.fixture
def ticket_subtask() -> Dict[str, Any]:
    """子任務"""
    return {
        "id": "0.31.0-W1-001.1",
        "title": "Subtask",
        "status": "pending",
        "priority": "P1"
    }


@pytest.fixture
def ticket_blocked() -> Dict[str, Any]:
    """被阻塞的任務"""
    return {
        "id": "0.31.0-W4-001",
        "title": "被阻塞的任務",
        "status": "blocked",
        "priority": "P0"
    }


@pytest.fixture
def ticket_long_title() -> Dict[str, Any]:
    """長標題（英文）"""
    return {
        "id": "0.31.0-W5-001",
        "title": "This is a very long English title that needs truncation",
        "status": "pending",
        "priority": "P2"
    }


@pytest.fixture
def ticket_chinese_long() -> Dict[str, Any]:
    """長標題（中文）"""
    return {
        "id": "0.31.0-W6-001",
        "title": "這是一個非常長的中文標題需要被截斷的例子",
        "status": "in_progress",
        "priority": "P1"
    }


# ============================================================================
# Layer 5 (Domain Logic) - 單元測試
# ============================================================================

# ============================================================================
# Layer 2 (Behavior Logic) - 業務邏輯測試
# ============================================================================

class TestSimplifyTicketId:
    """Ticket ID 簡化測試"""

    def test_standard_format(self):
        """標準格式簡化"""
        result = simplify_ticket_id("0.31.0-W7-001")
        assert result == "W7-001"

    def test_subtask_format(self):
        """子任務 ID 簡化"""
        result = simplify_ticket_id("0.31.0-W7-001.1")
        assert result == "W7-001.1"

    def test_multi_level_subtask(self):
        """多層子任務"""
        result = simplify_ticket_id("0.31.0-W7-001.1.1")
        assert result == "W7-001.1.1"

    def test_invalid_format(self):
        """無效格式回退"""
        result = simplify_ticket_id("invalid")
        assert result == "invalid"

    def test_empty_string(self):
        """空字串返回 Unknown"""
        result = simplify_ticket_id("")
        assert result == "Unknown"

    def test_short_version(self):
        """短版本號"""
        result = simplify_ticket_id("0.1.0-W1-001")
        assert result == "W1-001"

    def test_long_wave_number(self):
        """長波次號"""
        result = simplify_ticket_id("0.31.0-W123-001")
        assert result == "W123-001"


class TestExtractWaveNumber:
    """波次號提取測試"""

    def test_standard_wave(self):
        """標準波次號提取"""
        result = extract_wave_number("0.31.0-W7-001")
        assert result == "W7"

    def test_large_wave_number(self):
        """大波次號"""
        result = extract_wave_number("0.31.0-W123-001")
        assert result == "W123"

    def test_subtask_wave(self):
        """子任務波次號提取"""
        result = extract_wave_number("0.31.0-W7-001.1")
        assert result == "W7"

    def test_invalid_format(self):
        """無效格式返回 Unknown"""
        result = extract_wave_number("invalid")
        assert result == "Unknown"


class TestBuildTreeStructure:
    """樹狀結構構建測試"""

    def test_no_subtasks(self):
        """無子任務的根任務清單"""
        tickets = [
            {"id": "0.31.0-W1-001"},
            {"id": "0.31.0-W1-002"}
        ]
        tree_structure, root_ids = build_tree_structure(tickets)
        assert tree_structure == {}
        assert root_ids == ["0.31.0-W1-001", "0.31.0-W1-002"]

    def test_with_subtasks(self):
        """有子任務的結構"""
        tickets = [
            {"id": "0.31.0-W1-001"},
            {"id": "0.31.0-W1-001.1"},
            {"id": "0.31.0-W1-001.2"}
        ]
        tree_structure, root_ids = build_tree_structure(tickets)
        assert tree_structure == {"0.31.0-W1-001": ["0.31.0-W1-001.1", "0.31.0-W1-001.2"]}
        assert root_ids == ["0.31.0-W1-001"]

    def test_multi_level_subtasks(self):
        """多層子任務"""
        tickets = [
            {"id": "0.31.0-W1-001"},
            {"id": "0.31.0-W1-001.1"},
            {"id": "0.31.0-W1-001.1.1"}
        ]
        tree_structure, root_ids = build_tree_structure(tickets)
        assert "0.31.0-W1-001" in tree_structure
        assert "0.31.0-W1-001.1" in tree_structure
        assert root_ids == ["0.31.0-W1-001"]

    def test_orphan_subtask(self):
        """孤兒子任務（父任務缺失）"""
        tickets = [
            {"id": "0.31.0-W1-001.1"},  # 父任務缺失
            {"id": "0.31.0-W1-002"}
        ]
        tree_structure, root_ids = build_tree_structure(tickets)
        assert tree_structure == {}
        assert set(root_ids) == {"0.31.0-W1-001.1", "0.31.0-W1-002"}

    def test_empty_list(self):
        """空清單"""
        tree_structure, root_ids = build_tree_structure([])
        assert tree_structure == {}
        assert root_ids == []

    def test_mixed_roots_and_subtasks(self):
        """混合根任務和子任務"""
        tickets = [
            {"id": "0.31.0-W1-001"},
            {"id": "0.31.0-W1-001.1"},
            {"id": "0.31.0-W1-002"},
            {"id": "0.31.0-W1-002.1"},
            {"id": "0.31.0-W1-003"}
        ]
        tree_structure, root_ids = build_tree_structure(tickets)
        assert "0.31.0-W1-001" in tree_structure
        assert "0.31.0-W1-002" in tree_structure
        assert "0.31.0-W1-003" in root_ids
        assert len(root_ids) == 3


class TestRenderTreeNode:
    """樹節點渲染測試"""

    def test_single_root_node(self):
        """單一根節點（無子項）"""
        tickets_dict = {
            "0.31.0-W1-001": {
                "id": "0.31.0-W1-001",
                "title": "Task",
                "priority": "P1"
            }
        }
        result = render_tree_node("0.31.0-W1-001", tickets_dict, {}, "", True)
        assert len(result) == 1
        assert "W1-001" in result[0]
        assert "[P1]" in result[0]

    def test_node_with_children(self):
        """有子節點的根節點"""
        tickets_dict = {
            "0.31.0-W1-001": {
                "id": "0.31.0-W1-001",
                "title": "Parent Task",
                "priority": "P1"
            },
            "0.31.0-W1-001.1": {
                "id": "0.31.0-W1-001.1",
                "title": "Child Task",
                "priority": "P2"
            }
        }
        tree_structure = {"0.31.0-W1-001": ["0.31.0-W1-001.1"]}
        result = render_tree_node("0.31.0-W1-001", tickets_dict, tree_structure, "", True)
        assert len(result) >= 2
        assert "W1-001" in result[0]
        assert "W1-001.1" in result[1]

    def test_is_last_connector(self):
        """is_last 參數影響連接符"""
        tickets_dict = {
            "0.31.0-W1-001": {
                "id": "0.31.0-W1-001",
                "title": "Task",
                "priority": "P1"
            }
        }
        # is_last=True 應使用 "└──"
        result_last = render_tree_node("0.31.0-W1-001", tickets_dict, {}, "", True)
        assert "└──" in result_last[0]

        # is_last=False 應使用 "├──"
        result_not_last = render_tree_node("0.31.0-W1-001", tickets_dict, {}, "", False)
        assert "├──" in result_not_last[0]

    def test_non_existent_ticket(self):
        """不存在的 ticket"""
        result = render_tree_node("non-existent", {}, {})
        assert result == []

    def test_chinese_title(self):
        """中文標題渲染"""
        tickets_dict = {
            "0.31.0-W1-001": {
                "id": "0.31.0-W1-001",
                "title": "複雜的中文標題",
                "priority": "P1"
            }
        }
        result = render_tree_node("0.31.0-W1-001", tickets_dict, {}, "", True)
        assert "複雜的中文標題" in result[0]


class TestFilterIncompleteTickets:
    """未完成任務過濾測試"""

    def test_keeps_pending(self):
        """保留待處理任務"""
        tickets = [{"status": "pending"}]
        result = filter_incomplete_tickets(tickets)
        assert len(result) == 1

    def test_keeps_in_progress(self):
        """保留進行中任務"""
        tickets = [{"status": "in_progress"}]
        result = filter_incomplete_tickets(tickets)
        assert len(result) == 1

    def test_keeps_blocked(self):
        """保留被阻塞任務"""
        tickets = [{"status": "blocked"}]
        result = filter_incomplete_tickets(tickets)
        assert len(result) == 1

    def test_filters_completed(self):
        """過濾已完成任務"""
        tickets = [{"status": "completed"}]
        result = filter_incomplete_tickets(tickets)
        assert len(result) == 0

    def test_mixed_statuses(self):
        """混合狀態過濾"""
        tickets = [
            {"status": "pending"},
            {"status": "in_progress"},
            {"status": "completed"},
            {"status": "blocked"}
        ]
        result = filter_incomplete_tickets(tickets)
        assert len(result) == 3


class TestGroupByWave:
    """按波次分組測試"""

    def test_single_wave(self):
        """單個波次"""
        tickets = [
            {"id": "0.31.0-W1-001"},
            {"id": "0.31.0-W1-002"}
        ]
        result = group_by_wave(tickets)
        assert "W1" in result
        assert len(result["W1"]) == 2

    def test_multiple_waves_sorted(self):
        """多個波次升序排列"""
        tickets = [
            {"id": "0.31.0-W3-001"},
            {"id": "0.31.0-W1-001"},
            {"id": "0.31.0-W2-001"}
        ]
        result = group_by_wave(tickets)
        waves = list(result.keys())
        # 應按波次號升序：W1, W2, W3
        assert waves == ["W1", "W2", "W3"]

    def test_unknown_wave(self):
        """未知波次"""
        tickets = [{"id": "invalid"}]
        result = group_by_wave(tickets)
        assert "Unknown" in result


# ============================================================================
# Layer 1 (UI) - 整合測試
# ============================================================================

class TestRenderBoardTree:
    """樹狀看板渲染測試"""

    def test_renders_tree_view(self, ticket_simple, ticket_subtask):
        """渲染樹狀視圖"""
        tickets = [ticket_simple, ticket_subtask]

        with patch('ticket_system.commands.track_board.list_tickets', return_value=tickets):
            result = render_board_tree(tickets, "0.31.0", show_all=False)

        assert "W1-001" in result

    def test_filters_incomplete(self, ticket_simple, ticket_mixed):
        """過濾未完成任務"""
        # ticket_mixed 的狀態是 completed，應被過濾
        tickets = [ticket_simple, ticket_mixed]

        result = render_board_tree(tickets, "0.31.0", show_all=False)
        assert "W1-001" in result
        assert "W3-001" not in result  # ticket_mixed 應被過濾

    def test_shows_all_with_flag(self, ticket_simple, ticket_mixed):
        """show_all=True 顯示所有任務"""
        tickets = [ticket_simple, ticket_mixed]

        result = render_board_tree(tickets, "0.31.0", show_all=True)
        assert "W1-001" in result
        assert "W3-001" in result


# ============================================================================
# 整合測試
# ============================================================================

class TestTreeStructureIntegration:
    """樹狀結構整合測試"""

    def test_build_and_render_tree(self, ticket_simple, ticket_subtask):
        """構建和渲染樹結構"""
        tickets = [ticket_simple, ticket_subtask]
        tree_structure, root_ids = build_tree_structure(tickets)

        tickets_dict = {t["id"]: t for t in tickets}

        for root_id in root_ids:
            lines = render_tree_node(root_id, tickets_dict, tree_structure, "", True)
            assert len(lines) > 0


# ============================================================================
# 邊界條件測試
# ============================================================================

class TestBoundaryConditions:
    """邊界條件測試"""

    def test_build_tree_with_duplicate_ids(self):
        """重複 ID（應取一個）"""
        tickets = [
            {"id": "0.31.0-W1-001"},
            {"id": "0.31.0-W1-001"}  # 重複
        ]
        tree_structure, root_ids = build_tree_structure(tickets)
        # 應使用 set 去重
        assert len(root_ids) >= 1


# ============================================================================
# 回歸測試（針對已知問題）
# ============================================================================

class TestRegressionPreviously:
    """針對過去發現的 bug 進行回歸測試"""

    def test_render_tree_node_with_missing_ticket(self):
        """樹節點渲染時 ticket 缺失處理"""
        tickets_dict = {}
        tree_structure = {}
        result = render_tree_node("non-existent", tickets_dict, tree_structure)
        # 應返回空清單，不應崩潰
        assert result == []


# ============================================================================
# 補充測試 - 覆蓋未測試的路徑（W37-002）
# ============================================================================

class TestRenderBoardTreeEmptyFiltered:
    """測試當所有任務被過濾後的 NO_TASKS_TEXT 路徑（Lines 179-181）"""

    def test_all_completed_no_show_all(self):
        """當所有任務都是 completed 且 show_all=False 時顯示 NO_TASKS_TEXT"""
        # 建立 completed tickets
        tickets = [
            {
                "id": "0.31.0-W1-001",
                "title": "Completed Task 1",
                "status": "completed",
                "priority": "P1"
            },
            {
                "id": "0.31.0-W1-002",
                "title": "Completed Task 2",
                "status": "completed",
                "priority": "P2"
            }
        ]

        result = render_board_tree(tickets, "0.31.0", show_all=False)

        # 應包含 NO_TASKS_TEXT
        assert TrackBoardMessages.NO_TASKS_TEXT in result
        # 不應包含任何 ticket ID
        assert "W1-001" not in result
        assert "W1-002" not in result


class TestExecuteBoardMainFunction:
    """測試 execute_board 主入口函式（Lines 707-727）"""

    def test_execute_board_success(self):
        """正常執行 board 命令成功路徑"""
        args = argparse.Namespace(
            wave=None,
            all=False
        )

        # Mock list_tickets
        test_tickets = [
            {
                "id": "0.31.0-W1-001",
                "title": "Test Task",
                "status": "pending",
                "priority": "P1"
            }
        ]

        with patch('ticket_system.commands.track_board.list_tickets', return_value=test_tickets):
            with patch('builtins.print') as mock_print:
                result = execute_board(args, "0.31.0")

        # 應返回 0（成功）
        assert result == 0
        # 應調用 print
        assert mock_print.called

    def test_execute_board_with_wave_filter(self):
        """execute_board 應支援 Wave 過濾（Line 712-714）"""
        args = argparse.Namespace(
            wave="W1",
            all=False
        )

        test_tickets = [
            {
                "id": "0.31.0-W1-001",
                "title": "Wave 1 Task",
                "status": "pending",
                "priority": "P1"
            },
            {
                "id": "0.31.0-W2-001",
                "title": "Wave 2 Task",
                "status": "pending",
                "priority": "P1"
            }
        ]

        with patch('ticket_system.commands.track_board.list_tickets', return_value=test_tickets):
            with patch('builtins.print') as mock_print:
                result = execute_board(args, "0.31.0")

        # 應返回 0（成功）
        assert result == 0
        # print 輸出應只包含 W1
        output_calls = [str(call) for call in mock_print.call_args_list]
        combined_output = " ".join(output_calls)
        # W1-001 應在輸出中，W2-001 應被過濾
        assert "W1-001" in combined_output

    def test_execute_board_exception_handling(self):
        """execute_board 應捕獲異常並返回 1（Lines 725-727）"""
        args = argparse.Namespace(
            wave=None,
            all=False
        )

        # Mock list_tickets 拋出異常
        with patch('ticket_system.commands.track_board.list_tickets', side_effect=Exception("Load error")):
            with patch('builtins.print') as mock_print:
                result = execute_board(args, "0.31.0")

        # 應返回 1（失敗）
        assert result == 1
        # 應輸出錯誤訊息
        assert mock_print.called


class TestRenderBoardTreeWithAllFlag:
    """測試 render_board_tree show_all 參數的完整覆蓋"""

    def test_show_all_includes_completed_tasks(self):
        """show_all=True 應包含已完成任務"""
        tickets = [
            {
                "id": "0.31.0-W1-001",
                "title": "Pending Task",
                "status": "pending",
                "priority": "P1"
            },
            {
                "id": "0.31.0-W1-002",
                "title": "Completed Task",
                "status": "completed",
                "priority": "P1"
            }
        ]

        result = render_board_tree(tickets, "0.31.0", show_all=True)

        # 兩個任務都應在輸出中
        assert "W1-001" in result
        assert "W1-002" in result
        assert "Pending Task" in result
        assert "Completed Task" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
