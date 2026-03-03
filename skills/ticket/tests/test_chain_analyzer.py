"""
ChainAnalyzer 模組測試

測試 Ticket 任務鏈分析邏輯：
- determine_direction() 五種情境
- _has_pending_children() 子任務檢查
- _get_sibling_status() 兄弟任務檢查
- get_recommendation() 建議生成
"""

import pytest
from unittest.mock import patch, MagicMock

from ticket_system.lib.chain_analyzer import ChainAnalyzer, Recommendation
from ticket_system.lib.constants import STATUS_COMPLETED, STATUS_IN_PROGRESS, STATUS_PENDING, STATUS_BLOCKED


class TestDetermineDirection:
    """測試 determine_direction() 方法"""

    def test_situation_5_blocked_status_returns_wait(self):
        """情境 5：被阻塞狀態 → wait"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_BLOCKED,
            "chain": {"parent": "0.31.0-W4-001"},
            "children": []
        }
        assert ChainAnalyzer.determine_direction(ticket) == "wait"

    def test_situation_1_has_pending_children_returns_to_child(self):
        """情境 1：有待完成子任務 → to-child"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_IN_PROGRESS,
            "chain": {"parent": None},
            "children": [
                {"id": "0.31.0-W4-001.1", "status": STATUS_PENDING}
            ]
        }
        assert ChainAnalyzer.determine_direction(ticket) == "to-child"

    def test_situation_3_no_parent_returns_completed(self):
        """情境 3：無父任務 → completed"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_COMPLETED,
            "chain": {"parent": None},
            "children": []
        }
        assert ChainAnalyzer.determine_direction(ticket) == "completed"

    def test_situation_3_root_node_returns_completed(self):
        """情境 3：根節點 → completed"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_COMPLETED,
            "chain": {"root": "0.31.0-W4-001"},
            "children": []
        }
        assert ChainAnalyzer.determine_direction(ticket) == "completed"

    @patch('ticket_system.lib.chain_analyzer.load_ticket')
    def test_situation_4_has_pending_siblings_returns_to_sibling(self, mock_load_ticket):
        """情境 4：有待完成兄弟任務 → to-sibling"""
        # 設置模擬
        parent_ticket = {
            "id": "0.31.0-W4-001",
            "children": [
                "0.31.0-W4-001.1",
                "0.31.0-W4-001.2"  # 兄弟，待完成
            ]
        }
        sibling_ticket = {
            "id": "0.31.0-W4-001.2",
            "status": STATUS_PENDING
        }

        def load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.31.0-W4-001":
                return parent_ticket
            elif ticket_id == "0.31.0-W4-001.2":
                return sibling_ticket
            return None

        mock_load_ticket.side_effect = load_ticket_side_effect

        ticket = {
            "id": "0.31.0-W4-001.1",
            "status": STATUS_COMPLETED,
            "chain": {"parent": "0.31.0-W4-001"},
            "children": []
        }

        assert ChainAnalyzer.determine_direction(ticket, "0.31.0") == "to-sibling"

    @patch('ticket_system.lib.chain_analyzer.load_ticket')
    def test_situation_3_all_siblings_done_returns_to_parent(self, mock_load_ticket):
        """情境 3：所有兄弟完成 → to-parent"""
        # 設置模擬
        parent_ticket = {
            "id": "0.31.0-W4-001",
            "children": [
                "0.31.0-W4-001.1",
                "0.31.0-W4-001.2"  # 兄弟，已完成
            ]
        }
        sibling_ticket = {
            "id": "0.31.0-W4-001.2",
            "status": STATUS_COMPLETED
        }

        def load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.31.0-W4-001":
                return parent_ticket
            elif ticket_id == "0.31.0-W4-001.2":
                return sibling_ticket
            return None

        mock_load_ticket.side_effect = load_ticket_side_effect

        ticket = {
            "id": "0.31.0-W4-001.1",
            "status": STATUS_COMPLETED,
            "chain": {"parent": "0.31.0-W4-001"},
            "children": []
        }

        assert ChainAnalyzer.determine_direction(ticket, "0.31.0") == "to-parent"


class TestHasPendingChildren:
    """測試 _has_pending_children() 方法"""

    def test_empty_children_returns_false(self):
        """空子任務列表 → False"""
        assert ChainAnalyzer._has_pending_children([]) is False
        assert ChainAnalyzer._has_pending_children(None) is False

    def test_all_completed_children_returns_false(self):
        """所有子任務都完成 → False"""
        children = [
            {"id": "0.31.0-W4-001.1", "status": STATUS_COMPLETED},
            {"id": "0.31.0-W4-001.2", "status": STATUS_COMPLETED}
        ]
        assert ChainAnalyzer._has_pending_children(children) is False

    def test_has_pending_children_returns_true(self):
        """有待完成子任務 → True"""
        children = [
            {"id": "0.31.0-W4-001.1", "status": STATUS_COMPLETED},
            {"id": "0.31.0-W4-001.2", "status": STATUS_PENDING}
        ]
        assert ChainAnalyzer._has_pending_children(children) is True

    @patch('ticket_system.lib.chain_analyzer.load_ticket')
    def test_string_child_id_with_version(self, mock_load_ticket):
        """字串子任務 ID（需要載入檢查）"""
        mock_load_ticket.return_value = {
            "id": "0.31.0-W4-001.1",
            "status": STATUS_PENDING
        }
        children = ["0.31.0-W4-001.1"]
        assert ChainAnalyzer._has_pending_children(children, "0.31.0") is True


class TestGetSiblingStatus:
    """測試 _get_sibling_status() 方法"""

    def test_no_parent_returns_all_done(self):
        """無父任務 → all_done"""
        ticket = {
            "id": "0.31.0-W4-001",
            "chain": {"parent": None},
            "children": []
        }
        assert ChainAnalyzer._get_sibling_status(ticket) == "all_done"

    @patch('ticket_system.lib.chain_analyzer.load_ticket')
    def test_all_siblings_completed_returns_all_done(self, mock_load_ticket):
        """所有兄弟完成 → all_done"""
        parent_ticket = {
            "id": "0.31.0-W4-001",
            "children": [
                "0.31.0-W4-001.1",
                "0.31.0-W4-001.2"
            ]
        }
        sibling_ticket = {
            "id": "0.31.0-W4-001.2",
            "status": STATUS_COMPLETED
        }

        def load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.31.0-W4-001":
                return parent_ticket
            elif ticket_id == "0.31.0-W4-001.2":
                return sibling_ticket
            return None

        mock_load_ticket.side_effect = load_ticket_side_effect

        ticket = {
            "id": "0.31.0-W4-001.1",
            "chain": {"parent": "0.31.0-W4-001"},
            "children": []
        }
        assert ChainAnalyzer._get_sibling_status(ticket, "0.31.0") == "all_done"

    @patch('ticket_system.lib.chain_analyzer.load_ticket')
    def test_has_pending_sibling_returns_has_pending(self, mock_load_ticket):
        """有待完成兄弟 → has_pending"""
        parent_ticket = {
            "id": "0.31.0-W4-001",
            "children": [
                "0.31.0-W4-001.1",
                "0.31.0-W4-001.2"
            ]
        }
        sibling_ticket = {
            "id": "0.31.0-W4-001.2",
            "status": STATUS_PENDING
        }

        def load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.31.0-W4-001":
                return parent_ticket
            elif ticket_id == "0.31.0-W4-001.2":
                return sibling_ticket
            return None

        mock_load_ticket.side_effect = load_ticket_side_effect

        ticket = {
            "id": "0.31.0-W4-001.1",
            "chain": {"parent": "0.31.0-W4-001"},
            "children": []
        }
        assert ChainAnalyzer._get_sibling_status(ticket, "0.31.0") == "has_pending"

    @patch('ticket_system.lib.chain_analyzer.load_ticket')
    def test_dict_sibling_format(self, mock_load_ticket):
        """相容 dict 格式的兄弟任務"""
        parent_ticket = {
            "id": "0.31.0-W4-001",
            "children": [
                {"id": "0.31.0-W4-001.1"},
                {"id": "0.31.0-W4-001.2", "status": STATUS_PENDING}
            ]
        }

        mock_load_ticket.return_value = parent_ticket

        ticket = {
            "id": "0.31.0-W4-001.1",
            "chain": {"parent": "0.31.0-W4-001"},
            "children": []
        }
        assert ChainAnalyzer._get_sibling_status(ticket, "0.31.0") == "has_pending"


class TestGetRecommendation:
    """測試 get_recommendation() 方法"""

    def test_to_child_recommendation(self):
        """to-child 方向建議"""
        ticket = {
            "id": "0.31.0-W4-001",
            "children": [
                {"id": "0.31.0-W4-001.1", "status": STATUS_PENDING, "title": "Subtask 1"}
            ],
            "chain": {}
        }
        rec = ChainAnalyzer.get_recommendation("to-child", ticket)
        assert rec.direction == "to-child"
        assert rec.next_target_id == "0.31.0-W4-001.1"
        assert rec.command == "/ticket handoff 0.31.0-W4-001 --to-child 0.31.0-W4-001.1"

    def test_to_parent_recommendation(self):
        """to-parent 方向建議"""
        ticket = {
            "id": "0.31.0-W4-001.1",
            "chain": {"parent": "0.31.0-W4-001"},
            "children": []
        }

        with patch('ticket_system.lib.chain_analyzer.load_ticket') as mock_load:
            mock_load.return_value = {
                "id": "0.31.0-W4-001",
                "title": "Parent Task"
            }
            rec = ChainAnalyzer.get_recommendation("to-parent", ticket, "0.31.0")
            assert rec.direction == "to-parent"
            assert rec.next_target_id == "0.31.0-W4-001"
            assert rec.command == "/ticket handoff 0.31.0-W4-001.1 --to-parent"

    def test_wait_recommendation(self):
        """wait 方向建議"""
        ticket = {
            "id": "0.31.0-W4-001",
            "blockedBy": ["0.31.0-W4-002"],
            "chain": {}
        }
        rec = ChainAnalyzer.get_recommendation("wait", ticket)
        assert rec.direction == "wait"
        assert rec.blocked_by == ["0.31.0-W4-002"]
        assert rec.command == "/ticket track query 0.31.0-W4-002"

    def test_completed_recommendation(self):
        """completed 方向建議"""
        ticket = {
            "id": "0.31.0-W4-001",
            "chain": {"root": "0.31.0-W4-001"}
        }
        rec = ChainAnalyzer.get_recommendation("completed", ticket)
        assert rec.direction == "completed"
        assert rec.command == "/ticket track complete 0.31.0-W4-001"

    @patch('ticket_system.lib.chain_analyzer.load_ticket')
    def test_to_sibling_recommendation(self, mock_load_ticket):
        """to-sibling 方向建議"""
        parent_ticket = {
            "id": "0.31.0-W4-001",
            "children": [
                "0.31.0-W4-001.1",
                "0.31.0-W4-001.2"
            ]
        }
        sibling_ticket = {
            "id": "0.31.0-W4-001.2",
            "status": STATUS_PENDING,
            "title": "Sibling Task"
        }

        def load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.31.0-W4-001":
                return parent_ticket
            elif ticket_id == "0.31.0-W4-001.2":
                return sibling_ticket
            return None

        mock_load_ticket.side_effect = load_ticket_side_effect

        ticket = {
            "id": "0.31.0-W4-001.1",
            "chain": {"parent": "0.31.0-W4-001"},
            "children": []
        }
        rec = ChainAnalyzer.get_recommendation("to-sibling", ticket, "0.31.0")
        assert rec.direction == "to-sibling"
        assert rec.next_target_id == "0.31.0-W4-001.2"


class TestDetermineNextStep:
    """測試 determine_next_step() 別名方法"""

    def test_determine_next_step_is_alias_for_determine_direction(self):
        """determine_next_step() 是 determine_direction() 的別名"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_BLOCKED,
            "chain": {},
            "children": []
        }
        assert ChainAnalyzer.determine_next_step(ticket) == ChainAnalyzer.determine_direction(ticket)


class TestVersionExtraction:
    """測試從 Ticket ID 提取版本"""

    def test_version_extraction_from_ticket_id(self):
        """從 Ticket ID 自動提取版本"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_COMPLETED,
            "chain": {},
            "children": []
        }
        # 應該從 ticket_id 自動提取版本 "0.31.0"
        direction = ChainAnalyzer.determine_direction(ticket)
        assert direction == "completed"

    def test_version_extraction_with_subtask(self):
        """從 Ticket ID 提取版本（子任務）"""
        ticket = {
            "id": "0.31.0-W4-001.1.2",
            "status": STATUS_COMPLETED,
            "chain": {},
            "children": []
        }
        direction = ChainAnalyzer.determine_direction(ticket)
        assert direction == "completed"


class TestEdgeCases:
    """邊界案例測試"""

    def test_empty_ticket_defaults_to_completed(self):
        """空 Ticket → completed（無父任務）"""
        ticket = {}
        assert ChainAnalyzer.determine_direction(ticket) == "completed"

    def test_recommendation_with_no_version(self):
        """無版本資訊時的建議生成"""
        ticket = {
            "id": "0.31.0-W4-001",
            "chain": {"parent": None},
            "children": []
        }
        rec = ChainAnalyzer.get_recommendation("completed", ticket)
        assert rec.direction == "completed"
        assert rec.command is not None

    def test_mixed_children_format(self):
        """混合 string 和 dict 格式的子任務"""
        children = [
            "0.31.0-W4-001.1",
            {"id": "0.31.0-W4-001.2", "status": STATUS_PENDING}
        ]
        # string 型子任務需要載入，但沒有版本資訊時應被跳過
        # dict 型子任務直接檢查狀態
        assert ChainAnalyzer._has_pending_children(children) is True

    def test_parent_id_is_string(self):
        """parent_id 為字串型"""
        ticket = {
            "id": "0.31.0-W4-001.1",
            "chain": {"parent": "0.31.0-W4-001"},
            "status": STATUS_COMPLETED,
            "children": []
        }
        with patch('ticket_system.lib.chain_analyzer.load_ticket') as mock_load:
            mock_load.return_value = {
                "id": "0.31.0-W4-001",
                "children": ["0.31.0-W4-001.1"],
                "title": "Parent"
            }
            direction = ChainAnalyzer.determine_direction(ticket, "0.31.0")
            assert direction == "to-parent"
