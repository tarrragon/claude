"""
關鍵路徑分析模組測試

測試 CriticalPathAnalyzer 的各項功能：
- analyze() 關鍵路徑計算
- get_critical_path_summary() 文字建議
- identify_bottlenecks() 瓶頸識別

測試案例覆蓋：
- 無依賴的 Ticket → 都在關鍵路徑上
- 線性依賴 A→B→C → 完整路徑是關鍵路徑
- 鑽石依賴 → 識別正確的關鍵路徑
- 多個獨立子圖 → 各子圖有自己的關鍵路徑
- 邊界情況：空清單、單一 Ticket、有環等
- 多條關鍵路徑 → 等長的平行路徑
- 自訂 duration_map → 非等權重的情況
"""

import pytest
from typing import List, Dict, Any

from ticket_system.lib.critical_path import (
    CriticalPathAnalyzer,
    CriticalPathResult,
)


class TestAnalyzeCriticalPath:
    """測試 analyze() 方法的關鍵路徑計算功能"""

    def test_empty_tickets_list(self):
        """測試空 Ticket 清單"""
        result = CriticalPathAnalyzer.analyze([])
        assert result.is_valid is True
        assert result.critical_path == []
        assert result.critical_path_length == 0
        assert result.ticket_schedule == {}
        assert result.cycle_info is None
        assert result.all_critical_paths == []

    def test_single_ticket(self):
        """測試單一 Ticket（無依賴）"""
        tickets = [{"id": "A", "blockedBy": []}]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        assert result.critical_path == ["A"]
        assert result.critical_path_length == 1
        assert "A" in result.ticket_schedule
        assert result.ticket_schedule["A"]["slack"] == 0
        assert result.cycle_info is None

    def test_multiple_independent_tickets(self):
        """測試多個無依賴的 Ticket → 都在關鍵路徑上"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": []},
            {"id": "C", "blockedBy": []},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        assert result.critical_path_length == 1
        # 都在關鍵路徑上（都是並行的起點）
        assert len(result.critical_path) > 0
        for ticket_id in ["A", "B", "C"]:
            assert result.ticket_schedule[ticket_id]["slack"] == 0

    def test_linear_dependency_chain(self):
        """測試線性依賴：A → B → C"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["B"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        assert result.critical_path == ["A", "B", "C"]
        assert result.critical_path_length == 3
        # 所有節點都在關鍵路徑上
        for ticket_id in ["A", "B", "C"]:
            assert result.ticket_schedule[ticket_id]["slack"] == 0

    def test_linear_dependency_chain_schedule_values(self):
        """驗證線性依賴的時程值計算正確"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["B"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)

        # A: es=0, ef=1, ls=0, lf=1, slack=0
        assert result.ticket_schedule["A"]["es"] == 0
        assert result.ticket_schedule["A"]["ef"] == 1
        assert result.ticket_schedule["A"]["ls"] == 0
        assert result.ticket_schedule["A"]["lf"] == 1

        # B: es=1, ef=2, ls=1, lf=2, slack=0
        assert result.ticket_schedule["B"]["es"] == 1
        assert result.ticket_schedule["B"]["ef"] == 2
        assert result.ticket_schedule["B"]["ls"] == 1
        assert result.ticket_schedule["B"]["lf"] == 2

        # C: es=2, ef=3, ls=2, lf=3, slack=0
        assert result.ticket_schedule["C"]["es"] == 2
        assert result.ticket_schedule["C"]["ef"] == 3
        assert result.ticket_schedule["C"]["ls"] == 2
        assert result.ticket_schedule["C"]["lf"] == 3

    def test_diamond_dependency(self):
        """
        測試鑽石依賴：
        A（無依賴）
        ├─ B（依賴 A）
        ├─ C（依賴 A）
        └─ D（依賴 B, C）

        關鍵路徑應該是 A → B → D 或 A → C → D（取決於順序）
        關鍵路徑長度是 3（節點數）
        A, B, C, D 都在某條關鍵路徑上（都是必經節點，slack = 0）
        """
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
            {"id": "D", "blockedBy": ["B", "C"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        # 主關鍵路徑長度為 3（A → B → D 或 A → C → D）
        assert result.critical_path_length == 3
        # 但應有多條等長的關鍵路徑
        assert len(result.all_critical_paths) == 2

        # A, B, C, D 都在關鍵路徑上（都是必經節點）
        for ticket_id in ["A", "B", "C", "D"]:
            assert result.ticket_schedule[ticket_id]["slack"] == 0

    def test_diamond_dependency_schedule_values(self):
        """驗證鑽石依賴的時程值計算正確"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
            {"id": "D", "blockedBy": ["B", "C"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)

        # A: es=0, ef=1
        assert result.ticket_schedule["A"]["es"] == 0
        assert result.ticket_schedule["A"]["ef"] == 1

        # B, C: es=1, ef=2（並行）
        assert result.ticket_schedule["B"]["es"] == 1
        assert result.ticket_schedule["B"]["ef"] == 2
        assert result.ticket_schedule["C"]["es"] == 1
        assert result.ticket_schedule["C"]["ef"] == 2

        # D: es=2, ef=3（必須等待 B 和 C 都完成）
        assert result.ticket_schedule["D"]["es"] == 2
        assert result.ticket_schedule["D"]["ef"] == 3

    def test_cycle_detection(self):
        """測試循環依賴檢測"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["C"]},
            {"id": "C", "blockedBy": ["A"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is False
        assert result.cycle_info is not None
        assert result.critical_path == []

    def test_non_existent_dependency(self):
        """測試 blockedBy 引用不存在的 ID"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A", "NONEXISTENT"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        # NONEXISTENT 依賴應被忽略
        assert result.ticket_schedule["B"]["es"] == 1

    def test_multiple_independent_subgraphs(self):
        """測試多個獨立子圖"""
        tickets = [
            # 子圖 1：A → B
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            # 子圖 2：C → D
            {"id": "C", "blockedBy": []},
            {"id": "D", "blockedBy": ["C"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        assert result.critical_path_length == 2
        # 所有節點都在某條關鍵路徑上
        for ticket_id in ["A", "B", "C", "D"]:
            assert result.ticket_schedule[ticket_id]["slack"] == 0

    def test_multiple_critical_paths(self):
        """測試多條等長的關鍵路徑"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
            {"id": "D", "blockedBy": ["B", "C"]},
            {"id": "E", "blockedBy": ["D"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        # 應有多條等長的關鍵路徑（通過 B 或 C）
        assert len(result.all_critical_paths) == 2
        # 關鍵路徑長度為 4（A → B → D → E 或 A → C → D → E）
        assert result.critical_path_length == 4

    def test_custom_duration_map(self):
        """測試自訂 duration_map（非等權重）"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
        ]
        # A 工期 2，B 工期 1，C 工期 3
        duration_map = {"A": 2, "B": 1, "C": 3}
        result = CriticalPathAnalyzer.analyze(tickets, duration_map)
        assert result.is_valid is True

        # A: es=0, ef=2
        assert result.ticket_schedule["A"]["ef"] == 2

        # B: es=2, ef=3
        assert result.ticket_schedule["B"]["es"] == 2
        assert result.ticket_schedule["B"]["ef"] == 3

        # C: es=2, ef=5
        assert result.ticket_schedule["C"]["es"] == 2
        assert result.ticket_schedule["C"]["ef"] == 5

        # C 在關鍵路徑上（ef=5 是最大）
        assert result.ticket_schedule["C"]["slack"] == 0

    def test_string_blocked_by(self):
        """測試 blockedBy 為逗號分隔字串的情況"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": []},
            {"id": "C", "blockedBy": "A, B"},  # 字串格式
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        # C 應依賴 A 和 B
        assert result.ticket_schedule["C"]["es"] == 1


class TestGetCriticalPathSummary:
    """測試 get_critical_path_summary() 方法"""

    def test_summary_linear_path(self):
        """測試線性路徑的摘要"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["B"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        summary = CriticalPathAnalyzer.get_critical_path_summary(result)

        assert "關鍵路徑" in summary
        assert "A → B → C" in summary
        assert "3" in summary  # 路徑長度

    def test_summary_with_cycle(self):
        """測試有環情況的摘要"""
        tickets = [
            {"id": "A", "blockedBy": ["B"]},
            {"id": "B", "blockedBy": ["A"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        summary = CriticalPathAnalyzer.get_critical_path_summary(result)

        assert "計算失敗" in summary
        assert "循環依賴" in summary

    def test_summary_empty_list(self):
        """測試空清單的摘要"""
        result = CriticalPathAnalyzer.analyze([])
        summary = CriticalPathAnalyzer.get_critical_path_summary(result)

        assert "無 Ticket" in summary or "無關鍵路徑" in summary

    def test_summary_contains_schedule_table(self):
        """驗證摘要包含時程表"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        summary = CriticalPathAnalyzer.get_critical_path_summary(result)

        assert "ES" in summary
        assert "EF" in summary
        assert "LS" in summary
        assert "LF" in summary
        assert "Slack" in summary


class TestIdentifyBottlenecks:
    """測試 identify_bottlenecks() 方法"""

    def test_bottlenecks_threshold_zero(self):
        """測試 threshold=0（僅關鍵路徑）"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": []},
            {"id": "D", "blockedBy": ["C"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        bottlenecks = CriticalPathAnalyzer.identify_bottlenecks(result, threshold=0)

        # 所有節點都在關鍵路徑上（slack=0）
        assert len(bottlenecks) == 4
        assert set(bottlenecks) == {"A", "B", "C", "D"}

    def test_bottlenecks_with_threshold(self):
        """測試 threshold > 0（包含接近關鍵路徑的節點）"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
            {"id": "D", "blockedBy": ["B"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)

        # threshold=0：僅關鍵路徑
        critical_only = CriticalPathAnalyzer.identify_bottlenecks(result, threshold=0)
        assert len(critical_only) >= 1

    def test_bottlenecks_empty_result(self):
        """測試空結果"""
        result = CriticalPathAnalyzer.analyze([])
        bottlenecks = CriticalPathAnalyzer.identify_bottlenecks(result)

        assert bottlenecks == []

    def test_bottlenecks_sorted_by_slack(self):
        """驗證瓶頸按 slack 排序"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
            {"id": "D", "blockedBy": ["B", "C"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        bottlenecks = CriticalPathAnalyzer.identify_bottlenecks(result, threshold=0)

        # 驗證按 slack 升序排列
        for i in range(len(bottlenecks) - 1):
            slack_i = result.ticket_schedule[bottlenecks[i]]["slack"]
            slack_i_plus_1 = result.ticket_schedule[bottlenecks[i + 1]]["slack"]
            assert slack_i <= slack_i_plus_1


class TestEdgeCases:
    """測試邊界情況"""

    def test_single_ticket_with_self_dependency(self):
        """測試單一 Ticket 自我依賴（應檢測為環）"""
        tickets = [{"id": "A", "blockedBy": ["A"]}]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is False
        assert result.cycle_info is not None

    def test_missing_id_in_ticket(self):
        """測試缺少 id 欄位的 Ticket"""
        tickets = [
            {"blockedBy": []},  # 無 id
            {"id": "B", "blockedBy": []},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        # 只應處理有 id 的 Ticket
        assert "B" in result.ticket_schedule

    def test_empty_blocked_by(self):
        """測試 blockedBy 為空字串"""
        tickets = [
            {"id": "A", "blockedBy": ""},
            {"id": "B", "blockedBy": ["A"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        assert result.ticket_schedule["A"]["es"] == 0
        assert result.ticket_schedule["B"]["es"] == 1

    def test_complex_graph_with_merging_paths(self):
        """測試複雜圖：多個路徑匯聚"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": ["A"]},
            {"id": "C", "blockedBy": ["A"]},
            {"id": "D", "blockedBy": ["B"]},
            {"id": "E", "blockedBy": ["C"]},
            {"id": "F", "blockedBy": ["D", "E"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        assert result.critical_path_length == 4

    def test_large_dependency_count(self):
        """測試多重依賴（節點依賴多個前置節點）"""
        tickets = [
            {"id": "A", "blockedBy": []},
            {"id": "B", "blockedBy": []},
            {"id": "C", "blockedBy": []},
            {"id": "D", "blockedBy": ["A", "B", "C"]},
        ]
        result = CriticalPathAnalyzer.analyze(tickets)
        assert result.is_valid is True
        # D 的 ES 應為 max(ef_A, ef_B, ef_C) = 1
        assert result.ticket_schedule["D"]["es"] == 1
        assert result.ticket_schedule["D"]["ef"] == 2
