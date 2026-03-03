"""
Wave 自動計算模組測試

測試 WaveCalculator 的各項功能：
- calculate_waves() Wave 計算
- suggest_optimal_waves() 文字建議

測試案例覆蓋：
- 無依賴的 Ticket → 全部 Wave 1
- 線性依賴 A.blockedBy=[B], B.blockedBy=[C] → 分散到多個 Wave
- 鑽石依賴 D.blockedBy=[B,C], B.blockedBy=[A], C.blockedBy=[A]
- 多個獨立子圖
- 邊界情況：空清單、單一 Ticket、有環等
- blockedBy 引用不存在的 ID
"""

import pytest
from typing import List, Dict, Any

from ticket_system.lib.wave_calculator import WaveCalculator, WaveCalculationResult


class TestCalculateWaves:
    """測試 calculate_waves() 方法的 Wave 計算功能"""

    def test_empty_tickets_list(self):
        """測試空 Ticket 清單"""
        result = WaveCalculator.calculate_waves([])
        assert result.total_waves == 0
        assert result.is_valid is True
        assert result.waves == {}
        assert result.ticket_wave_map == {}
        assert result.cycle_info is None

    def test_single_ticket(self):
        """測試單一 Ticket（無依賴）"""
        tickets = [{"id": "A", "blockedBy": []}]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 1
        assert result.is_valid is True
        assert result.waves == {1: ["A"]}
        assert result.ticket_wave_map == {"A": 1}
        assert result.cycle_info is None

    def test_no_dependencies_multiple_tickets(self):
        """測試多個無依賴的 Ticket → 全部 Wave 1"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": []},
            {"id": "C", "blockedBy": []},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 1
        assert result.is_valid is True
        assert set(result.waves[1]) == {"A", "B", "C"}
        assert result.ticket_wave_map["A"] == 1
        assert result.ticket_wave_map["B"] == 1
        assert result.ticket_wave_map["C"] == 1
        assert result.cycle_info is None

    def test_linear_dependency_chain(self):
        """測試線性依賴：A → B → C（C 依賴 B，B 依賴 A）"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["B"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 3
        assert result.is_valid is True
        assert result.waves[1] == ["A"]
        assert result.waves[2] == ["B"]
        assert result.waves[3] == ["C"]
        assert result.ticket_wave_map["A"] == 1
        assert result.ticket_wave_map["B"] == 2
        assert result.ticket_wave_map["C"] == 3
        assert result.cycle_info is None

    def test_diamond_dependency(self):
        """
        測試鑽石依賴：
        A（無依賴）
        ├─ B（依賴 A）
        ├─ C（依賴 A）
        └─ D（依賴 B, C）

        預期：Wave 1: [A], Wave 2: [B, C], Wave 3: [D]
        """
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
            {"id": "D", "blockedBy": ["B", "C"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 3
        assert result.is_valid is True
        assert result.waves[1] == ["A"]
        assert set(result.waves[2]) == {"B", "C"}
        assert result.waves[3] == ["D"]
        assert result.ticket_wave_map["A"] == 1
        assert result.ticket_wave_map["B"] == 2
        assert result.ticket_wave_map["C"] == 2
        assert result.ticket_wave_map["D"] == 3
        assert result.cycle_info is None

    def test_multiple_independent_subgraphs(self):
        """
        測試多個獨立子圖：
        子圖 1：A → B
        子圖 2：C → D → E
        子圖 3：F（孤立）

        預期：
        Wave 1: [A, C, F]
        Wave 2: [B, D]
        Wave 3: [E]
        """
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": []},
            {"id": "D", "blockedBy": ["C"]},
            {"id": "E", "blockedBy": ["D"]},
            {"id": "F", "blockedBy": []},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 3
        assert result.is_valid is True
        assert set(result.waves[1]) == {"A", "C", "F"}
        assert set(result.waves[2]) == {"B", "D"}
        assert result.waves[3] == ["E"]
        assert result.cycle_info is None

    def test_wide_dependency_graph(self):
        """
        測試寬依賴圖（一個節點被多個節點依賴）：
        A（無依賴）
        ├─ B（依賴 A）
        ├─ C（依賴 A）
        ├─ D（依賴 A）
        └─ E（依賴 B, C, D）

        預期：Wave 1: [A], Wave 2: [B, C, D], Wave 3: [E]
        """
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
            {"id": "D", "blockedBy": ["A"]},
            {"id": "E", "blockedBy": ["B", "C", "D"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 3
        assert result.is_valid is True
        assert result.waves[1] == ["A"]
        assert set(result.waves[2]) == {"B", "C", "D"}
        assert result.waves[3] == ["E"]
        assert result.cycle_info is None

    def test_complex_dag(self):
        """
        測試複雜 DAG（無環有向圖）：
        A, B → C → E
             ↓      ↗
             D ────→ F

        預期：
        Wave 1: [A, B]
        Wave 2: [C, D]
        Wave 3: [E, F]（E 依賴 C，F 依賴 D 和 E，但由於 E 已完成，同 Wave）

        實際上 F 需要在 E 之後，所以：
        Wave 1: [A, B]
        Wave 2: [C, D]
        Wave 3: [E]
        Wave 4: [F]
        """
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": []},
            {"id": "C", "blockedBy": ["A", "B"]},
            {"id": "D", "blockedBy": ["C"]},
            {"id": "E", "blockedBy": ["C"]},
            {"id": "F", "blockedBy": ["D", "E"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 4
        assert result.is_valid is True
        assert set(result.waves[1]) == {"A", "B"}
        assert result.waves[2] == ["C"]
        assert set(result.waves[3]) == {"D", "E"}
        assert result.waves[4] == ["F"]
        assert result.cycle_info is None

    def test_cycle_detection_self_dependency(self):
        """測試循環檢測：自我依賴（A → A）"""
        tickets = [
            {"id": "A", "blockedBy": ["A"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.is_valid is False
        assert result.total_waves == 0
        assert result.cycle_info is not None
        assert "A" in result.cycle_info

    def test_cycle_detection_two_node_cycle(self):
        """測試循環檢測：兩節點循環（A → B → A）"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["A"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.is_valid is False
        assert result.total_waves == 0
        assert result.cycle_info is not None
        assert "A" in result.cycle_info
        assert "B" in result.cycle_info

    def test_cycle_detection_three_node_cycle(self):
        """測試循環檢測：三節點循環（A → B → C → A）"""
        tickets = [
            {"id": "A", "blockedBy": ["C"]},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["B"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.is_valid is False
        assert result.total_waves == 0
        assert result.cycle_info is not None

    def test_nonexistent_dependency_ignored(self):
        """測試 blockedBy 引用不存在的 ID 時，忽略該依賴"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A", "NONEXISTENT"]},  # 引用不存在的 ID
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 2
        assert result.is_valid is True
        assert result.waves[1] == ["A"]
        assert result.waves[2] == ["B"]
        assert result.ticket_wave_map["B"] == 2

    def test_blocked_by_string_format(self):
        """測試 blockedBy 為逗號分隔字串格式"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": "A"},  # 字串格式
            {"id": "C", "blockedBy": "A, B"},  # 逗號分隔
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 3
        assert result.is_valid is True
        assert result.waves[1] == ["A"]
        assert result.waves[2] == ["B"]
        assert result.waves[3] == ["C"]

    def test_blocked_by_missing_field(self):
        """測試 blockedBy 欄位缺失時，預設為無依賴"""
        tickets = [
            {"id": "A"},  # 無 blockedBy 欄位
            {"id": "B", "blockedBy": ["A"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 2
        assert result.is_valid is True
        assert result.waves[1] == ["A"]
        assert result.waves[2] == ["B"]

    def test_invalid_ticket_without_id(self):
        """測試無 id 欄位的無效 Ticket 會被忽略"""
        tickets = [
            {"blockedBy": []},  # 無 id
            {"id": "A", "blockedBy": []},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 1
        assert result.is_valid is True
        assert result.waves[1] == ["A"]

    def test_empty_blocked_by_list(self):
        """測試 blockedBy 為空清單"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": []},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 1
        assert result.is_valid is True
        assert set(result.waves[1]) == {"A", "B"}

    def test_ticket_ids_with_real_format(self):
        """測試使用真實 Ticket ID 格式（0.31.0-W4-001）"""
        tickets = [
            {"id": "0.31.0-W4-001", "blockedBy": []},
            {"id": "0.31.0-W4-002", "blockedBy": ["0.31.0-W4-001"]},
            {"id": "0.31.0-W4-003", "blockedBy": ["0.31.0-W4-001"]},
            {"id": "0.31.0-W4-004", "blockedBy": ["0.31.0-W4-002", "0.31.0-W4-003"]},
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 3
        assert result.is_valid is True
        assert result.waves[1] == ["0.31.0-W4-001"]
        assert set(result.waves[2]) == {"0.31.0-W4-002", "0.31.0-W4-003"}
        assert result.waves[3] == ["0.31.0-W4-004"]


class TestSuggestOptimalWaves:
    """測試 suggest_optimal_waves() 方法的文字建議功能"""

    def test_suggestion_empty_list(self):
        """測試空 Ticket 清單的建議"""
        suggestion = WaveCalculator.suggest_optimal_waves([])
        assert "無 Ticket" in suggestion

    def test_suggestion_single_ticket(self):
        """測試單一 Ticket 的建議文字"""
        tickets = [{"id": "A", "blockedBy": []}]
        suggestion = WaveCalculator.suggest_optimal_waves(tickets)
        assert "Wave 1" in suggestion
        assert "A" in suggestion

    def test_suggestion_linear_dependency(self):
        """測試線性依賴的建議文字"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["B"]},
        ]
        suggestion = WaveCalculator.suggest_optimal_waves(tickets)
        assert "Wave 1" in suggestion
        assert "Wave 2" in suggestion
        assert "Wave 3" in suggestion
        assert "A" in suggestion
        assert "B" in suggestion
        assert "C" in suggestion
        assert "3 個 Wave" in suggestion

    def test_suggestion_contains_ticket_counts(self):
        """測試建議文字包含每個 Wave 的 Ticket 數"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
        ]
        suggestion = WaveCalculator.suggest_optimal_waves(tickets)
        assert "1 個 Ticket" in suggestion  # Wave 1 有 1 個
        assert "2 個 Ticket" in suggestion  # Wave 2 有 2 個

    def test_suggestion_cycle_error(self):
        """測試有環時的建議錯誤訊息"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["A"]},
        ]
        suggestion = WaveCalculator.suggest_optimal_waves(tickets)
        assert "計算失敗" in suggestion
        assert "循環依賴" in suggestion
        assert "環路" in suggestion

    def test_suggestion_formatting(self):
        """測試建議文字的格式（清單符號、縮排）"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
        ]
        suggestion = WaveCalculator.suggest_optimal_waves(tickets)
        assert "  - " in suggestion  # 清單項目縮排
        assert "=" in suggestion  # 分隔線


class TestWaveCalculationResult:
    """測試 WaveCalculationResult 資料類別"""

    def test_result_dataclass_creation(self):
        """測試結果物件建立"""
        result = WaveCalculationResult()
        assert result.waves == {}
        assert result.ticket_wave_map == {}
        assert result.total_waves == 0
        assert result.is_valid is True
        assert result.cycle_info is None

    def test_result_with_custom_values(self):
        """測試使用自訂值建立結果"""
        waves = {1: ["A"], 2: ["B"]}
        wave_map = {"A": 1, "B": 2}
        result = WaveCalculationResult(
            waves=waves,
            ticket_wave_map=wave_map,
            total_waves=2,
            is_valid=True
        )
        assert result.waves == waves
        assert result.ticket_wave_map == wave_map
        assert result.total_waves == 2
        assert result.is_valid is True

    def test_result_invalid_state(self):
        """測試無效狀態（有環）"""
        cycle_path = ["A", "B", "A"]
        result = WaveCalculationResult(
            is_valid=False,
            cycle_info=cycle_path
        )
        assert result.is_valid is False
        assert result.cycle_info == cycle_path
        assert result.total_waves == 0


class TestEdgeCases:
    """邊界情況測試"""

    def test_very_large_chain(self):
        """測試很長的依賴鏈（50 個節點）"""
        tickets = []
        for i in range(50):
            ticket_id = f"T{i:03d}"
            blocked_by = [f"T{i-1:03d}"] if i > 0 else []
            tickets.append({"id": ticket_id, "blockedBy": blocked_by})

        result = WaveCalculator.calculate_waves(tickets)
        assert result.total_waves == 50
        assert result.is_valid is True
        for i in range(50):
            assert result.ticket_wave_map[f"T{i:03d}"] == i + 1

    def test_duplicate_dependencies(self):
        """測試重複的依賴（B 的 blockedBy 中 A 重複出現）"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A", "A"]},  # A 重複
        ]
        result = WaveCalculator.calculate_waves(tickets)
        # 應該被視為同一依賴，不影響結果
        assert result.total_waves == 2
        assert result.is_valid is True
        assert result.waves[1] == ["A"]
        assert result.waves[2] == ["B"]

    def test_whitespace_in_blocked_by_string(self):
        """測試 blockedBy 字串中的多餘空白"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": "  A  ,  "},  # 多餘空白
        ]
        result = WaveCalculator.calculate_waves(tickets)
        assert result.is_valid is True
        assert result.ticket_wave_map["B"] == 2
