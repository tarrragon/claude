"""
循環依賴檢測模組測試

測試 CycleDetector 的各項功能：
- has_cycle() 環檢測
- detect_cycles_in_all_tickets() 全面掃描
- validate_blocked_by() 驗證

測試案例覆蓋：
- 無循環的簡單依賴鏈
- 直接自我依賴
- 兩節點循環
- 多節點循環
- 複雜 DAG 中的部分循環
- 邊界情況
"""

import pytest
from typing import List, Dict, Any

from ticket_system.lib.cycle_detector import CycleDetector


class TestHasCycle:
    """測試 has_cycle() 方法的環檢測功能"""

    def test_no_cycle_simple_chain(self):
        """測試無循環的簡單依賴鏈：A → B → C"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B"],
                "B": ["C"],
                "C": []
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is False
        assert path is None

    def test_direct_self_dependency(self):
        """測試直接自我依賴：A → A"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["A"]
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True
        assert path == ["A", "A"]

    def test_two_node_cycle(self):
        """測試兩節點循環：A → B → A"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B"],
                "B": ["A"]
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True
        assert "A" in path
        assert "B" in path
        assert path[0] == path[-1]  # 首尾相同

    def test_three_node_cycle(self):
        """測試三節點循環：A → B → C → A"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B"],
                "B": ["C"],
                "C": ["A"]
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True
        assert path == ["A", "B", "C", "A"]

    def test_complex_dag_no_cycle(self):
        """測試複雜的無環 DAG"""
        # 結構：
        #   A → B → D
        #   ↓   ↘    ↗
        #   C → E
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B", "C"],
                "B": ["D", "E"],
                "C": ["E"],
                "D": [],
                "E": []
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is False
        assert path is None

    def test_complex_dag_with_cycle(self):
        """測試複雜 DAG 中的循環"""
        # 結構：
        #   A → B → D
        #   ↓   ↘ ↗  ↓
        #   C → E ← (循環：D → E → B)
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B", "C"],
                "B": ["D", "E"],
                "C": ["E"],
                "D": ["E"],
                "E": ["B"]  # 循環：E → B
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True
        assert path is not None
        assert "B" in path
        assert "E" in path

    def test_empty_dependencies(self):
        """測試依賴為空的 Ticket"""
        def get_deps(ticket_id: str) -> List[str]:
            return []

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is False
        assert path is None

    def test_invalid_ticket_id(self):
        """測試無效的 Ticket ID"""
        def get_deps(ticket_id: str) -> List[str]:
            return []

        has_cycle, path = CycleDetector.has_cycle("", get_deps)
        assert has_cycle is False
        assert path is None

    def test_invalid_callback_function(self):
        """測試無效的回呼函式"""
        has_cycle, path = CycleDetector.has_cycle("A", None)
        assert has_cycle is False
        assert path is None

    def test_cycle_with_intermediate_nodes(self):
        """測試多個依賴中的循環"""
        # A → B, C
        # C → A (循環)
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B", "C"],
                "B": [],
                "C": ["A"]
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True
        assert "C" in path
        assert "A" in path


class TestDetectCyclesInAllTickets:
    """測試 detect_cycles_in_all_tickets() 全面掃描功能"""

    def test_no_cycles_in_all_tickets(self):
        """測試無環的所有 Ticket"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["C"]},
            {"id": "C", "blockedBy": []}
        ]
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        assert cycles == []

    def test_single_cycle_detected(self):
        """測試偵測單一循環"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["C"]},
            {"id": "C", "blockedBy": ["A"]}
        ]
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        assert len(cycles) >= 1
        # 檢查環包含所有三個節點
        start_id, cycle_path = cycles[0]
        assert set(cycle_path[:-1]) == {"A", "B", "C"}

    def test_multiple_cycles(self):
        """測試多個獨立的循環"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["D"]},
            {"id": "D", "blockedBy": ["C"]}
        ]
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        # 應該偵測到至少 1-2 個循環（取決於遍歷順序）
        assert len(cycles) >= 1

    def test_empty_tickets_list(self):
        """測試空的 Ticket 清單"""
        cycles = CycleDetector.detect_cycles_in_all_tickets([])
        assert cycles == []

    def test_ticket_with_string_blocked_by(self):
        """測試 blockedBy 為逗號分隔字串的情況"""
        tickets = [
            {"id": "A", "blockedBy": "B,C"},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": []}
        ]
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        assert len(cycles) >= 1

    def test_ticket_with_missing_blocked_by(self):
        """測試缺少 blockedBy 欄位的 Ticket"""
        tickets = [
            {"id": "A"},  # 無 blockedBy
            {"id": "B", "blockedBy": []}
        ]
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        assert cycles == []

    def test_ticket_with_invalid_id(self):
        """測試包含無效 ID 的 Ticket"""
        tickets = [
            {"id": None, "blockedBy": []},
            {"id": "", "blockedBy": []},
            {"id": "A", "blockedBy": []}
        ]
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        assert cycles == []

    def test_self_dependency_in_all_tickets(self):
        """測試全面掃描中的自我依賴"""
        tickets = [
            {"id": "A", "blockedBy": ["A"]},
            {"id": "B", "blockedBy": []}
        ]
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        assert len(cycles) >= 1
        assert cycles[0][1] == ["A", "A"]


class TestValidateBlockedBy:
    """測試 validate_blocked_by() 驗證功能"""

    def test_valid_dependency_no_cycle(self):
        """測試有效的依賴（無環）"""
        tickets = [
            {"id": "B", "blockedBy": ["C"]},
            {"id": "C", "blockedBy": []}
        ]
        valid, msg, path = CycleDetector.validate_blocked_by("A", ["B"], tickets)
        assert valid is True
        assert msg is None
        assert path is None

    def test_invalid_dependency_creates_cycle(self):
        """測試無效的依賴（會產生環）"""
        tickets = [
            {"id": "B", "blockedBy": ["C"]},
            {"id": "C", "blockedBy": ["A"]}
        ]
        # 嘗試設定 A -> B（會產生 A -> B -> C -> A）
        valid, msg, path = CycleDetector.validate_blocked_by("A", ["B"], tickets)
        assert valid is False
        assert msg is not None
        assert path is not None
        assert "循環" in msg

    def test_validate_direct_self_dependency(self):
        """測試直接自我依賴的驗證"""
        tickets = []
        valid, msg, path = CycleDetector.validate_blocked_by("A", ["A"], tickets)
        assert valid is False
        assert msg is not None
        assert path is not None

    def test_validate_empty_blocked_by(self):
        """測試空的 blockedBy 驗證"""
        tickets = [{"id": "B", "blockedBy": []}]
        valid, msg, path = CycleDetector.validate_blocked_by("A", [], tickets)
        assert valid is True
        assert msg is None

    def test_validate_with_empty_tickets(self):
        """測試空的 Ticket 清單驗證"""
        valid, msg, path = CycleDetector.validate_blocked_by("A", ["B"], [])
        assert valid is True
        assert msg is None

    def test_validate_multiple_dependencies_no_cycle(self):
        """測試多個依賴的驗證（無環）"""
        tickets = [
            {"id": "B", "blockedBy": ["D"]},
            {"id": "C", "blockedBy": ["D"]},
            {"id": "D", "blockedBy": []}
        ]
        valid, msg, path = CycleDetector.validate_blocked_by("A", ["B", "C"], tickets)
        assert valid is True

    def test_validate_update_existing_ticket(self):
        """測試更新現有 Ticket 的依賴"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["C"]},
            {"id": "C", "blockedBy": []}
        ]
        # 嘗試更新 A 的依賴為 ["C"]（無環）
        valid, msg, path = CycleDetector.validate_blocked_by("A", ["C"], tickets)
        assert valid is True

    def test_validate_with_invalid_input(self):
        """測試無效的輸入"""
        # 空 ticket_id
        valid, msg, path = CycleDetector.validate_blocked_by("", ["B"], [])
        assert valid is True  # Guard Clause 返回通過

        # None ticket_id
        valid, msg, path = CycleDetector.validate_blocked_by(None, ["B"], [])
        assert valid is True


class TestCyclePath:
    """測試環路路徑的準確性"""

    def test_cycle_path_includes_all_nodes(self):
        """測試環路包含所有節點"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B"],
                "B": ["C"],
                "C": ["D"],
                "D": ["A"]
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True
        # 環路應包含 A, B, C, D，最後回到 A
        assert path[0] == path[-1]
        assert len(set(path[:-1])) == 4  # 4 個不同的節點

    def test_cycle_path_starts_with_first_node_in_cycle(self):
        """測試環路從發現環的節點開始"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B"],
                "B": ["C"],
                "C": ["B"]  # 循環：B -> C -> B
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("B", get_deps)
        assert has_cycle is True
        # 從 B 開始的循環應該是 B -> C -> B
        assert path[0] == "B"
        assert path[-1] == "B"

    def test_cycle_path_message_format(self):
        """測試錯誤訊息的格式"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["A"]}
        ]
        valid, msg, path = CycleDetector.validate_blocked_by("C", ["A"], tickets)
        # 若驗證失敗，訊息應包含箭頭
        if not valid and msg:
            assert "→" in msg


class TestEdgeCases:
    """測試邊界情況"""

    def test_cycle_with_duplicate_dependencies(self):
        """測試含有重複依賴的情況"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B", "B"],  # 重複依賴
                "B": ["A"]
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True

    def test_cycle_with_empty_string_dependency(self):
        """測試含有空字串依賴的情況"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B", ""],  # 空字串依賴
                "B": ["A"]
            }
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True
        # 應該忽略空字串，只檢測 A -> B -> A

    def test_cycle_with_none_dependency(self):
        """測試含有 None 依賴的情況"""
        tickets = [
            {"id": "A", "blockedBy": ["B", None]},
            {"id": "B", "blockedBy": ["A"]}
        ]
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        assert len(cycles) >= 1

    def test_very_long_cycle_path(self):
        """測試很長的循環路徑"""
        # 建立一個很長的循環：A -> B -> ... -> Z -> A
        nodes = [chr(ord("A") + i) for i in range(26)]
        deps = {}
        for i, node in enumerate(nodes):
            next_node = nodes[(i + 1) % len(nodes)]
            deps[node] = [next_node]

        def get_deps(ticket_id: str) -> List[str]:
            return deps.get(ticket_id, [])

        has_cycle, path = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle is True
        # 路徑應包含所有 26 個節點（最後回到 A）
        assert len(path) == 27  # 26 個節點 + 1 個重複的首節點

    def test_cycle_starting_from_middle_node(self):
        """測試從循環中間節點開始的檢測"""
        def get_deps(ticket_id: str) -> List[str]:
            deps = {
                "A": ["B"],
                "B": ["C"],
                "C": ["B"]  # 循環：B -> C -> B
            }
            return deps.get(ticket_id, [])

        # 從 A 開始檢測
        has_cycle_from_a, path_a = CycleDetector.has_cycle("A", get_deps)
        assert has_cycle_from_a is True

        # 從循環中間 B 開始檢測
        has_cycle_from_b, path_b = CycleDetector.has_cycle("B", get_deps)
        assert has_cycle_from_b is True
        # 不同的起點會產生不同的路徑
        assert "B" in path_b and "C" in path_b
