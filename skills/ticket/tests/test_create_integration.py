"""
Ticket create 命令的整合測試

測試並行分析和 TDD 順序建議功能的整合。
"""

import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock
import pytest

from ticket_system.commands.create import (
    _print_tdd_sequence_suggestion,
    _print_parallel_analysis_result,
    _print_create_checklist,
)
from ticket_system.lib.parallel_analyzer import ParallelAnalyzer
from ticket_system.lib.tdd_sequence import suggest_tdd_sequence


class TestTDDSequenceSuggestion:
    """TDD 順序建議功能測試"""

    def test_suggest_tdd_sequence_imp_type(self):
        """測試 IMP 類型的 TDD 順序建議"""
        result = suggest_tdd_sequence(task_type="IMP")

        assert result.task_type == "IMP"
        assert len(result.phases) == 5
        assert result.phases == ["phase1", "phase2", "phase3a", "phase3b", "phase4"]
        assert "TDD 流程" in result.description

    def test_suggest_tdd_sequence_adj_type(self):
        """測試 ADJ 類型的 TDD 順序建議"""
        result = suggest_tdd_sequence(task_type="ADJ")

        assert result.task_type == "ADJ"
        assert len(result.phases) == 4
        assert result.phases == ["phase2", "phase3a", "phase3b", "phase4"]

    def test_suggest_tdd_sequence_doc_type(self):
        """測試 DOC 類型無需 TDD 流程"""
        result = suggest_tdd_sequence(task_type="DOC")

        assert result.task_type == "DOC"
        assert len(result.phases) == 0
        assert "不需要 TDD 流程" in result.description

    def test_print_tdd_sequence_suggestion_imp(self, capsys):
        """測試輸出 IMP 類型的 TDD 順序建議"""
        _print_tdd_sequence_suggestion("IMP")

        captured = capsys.readouterr()
        assert "TDD 順序建議" in captured.out
        assert "Phase 1" in captured.out
        assert "Phase 2" in captured.out
        assert "Phase 3a" in captured.out
        assert "Phase 3b" in captured.out
        assert "Phase 4" in captured.out
        assert "lavender" in captured.out
        assert "parsley" in captured.out

    def test_print_tdd_sequence_suggestion_doc(self, capsys):
        """測試 DOC 類型不輸出 TDD 建議"""
        _print_tdd_sequence_suggestion("DOC")

        captured = capsys.readouterr()
        # DOC 類型無需 TDD 流程，函式應直接返回
        assert "TDD 順序建議" not in captured.out


class TestParallelAnalysis:
    """並行分析功能測試"""

    def test_analyze_single_task(self):
        """測試單一子任務無需並行分析"""
        tasks = [
            {"task_id": "001", "where_files": ["a.py"]},
        ]

        result = ParallelAnalyzer.analyze_tasks(tasks)
        # 單一任務時，can_parallel 為 True（因為 <= 1 個任務時返回 True）
        # 但 parallel_groups 會是空的
        assert result.can_parallel is True
        assert len(result.parallel_groups) == 0

    def test_analyze_two_independent_tasks(self):
        """測試兩個獨立任務可以並行"""
        tasks = [
            {"task_id": "001", "where_files": ["a.py", "b.py"]},
            {"task_id": "002", "where_files": ["c.py", "d.py"]},
        ]

        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert result.can_parallel
        assert len(result.parallel_groups) == 1
        assert set(result.parallel_groups[0]) == {"001", "002"}

    def test_analyze_tasks_with_file_overlap(self):
        """測試檔案重疊的任務無法並行"""
        tasks = [
            {"task_id": "001", "where_files": ["a.py", "common.py"]},
            {"task_id": "002", "where_files": ["b.py", "common.py"]},
        ]

        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert not result.can_parallel
        assert len(result.blocked_pairs) > 0

    def test_analyze_tasks_with_dependencies(self):
        """測試有依賴關係的任務無法並行"""
        tasks = [
            {"task_id": "001", "where_files": ["a.py"]},
            {"task_id": "002", "where_files": ["b.py"], "blockedBy": ["001"]},
        ]

        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert not result.can_parallel

    def test_print_parallel_analysis_result_no_children(self, capsys):
        """測試少於 2 個子任務時無需並行分析"""
        parent_info = {
            "version": "0.31.0",
            "children": [],
        }
        new_ticket = {}
        new_ticket_id = "001"

        _print_parallel_analysis_result(parent_info, new_ticket, new_ticket_id)

        captured = capsys.readouterr()
        # 少於 2 個子任務，應該沒有輸出
        assert "並行分析" not in captured.out

    @patch("ticket_system.commands.create.load_ticket")
    def test_print_parallel_analysis_result_with_children(
        self, mock_load_ticket, capsys
    ):
        """測試輸出子任務的並行分析結果"""
        # 設定 mock 返回值
        def load_ticket_side_effect(version, ticket_id):
            if ticket_id == "037.1":
                return {
                    "title": "Task 1",
                    "where": {"files": ["lib/a.py"]},
                    "blockedBy": [],
                }
            elif ticket_id == "037.2":
                return {
                    "title": "Task 2",
                    "where": {"files": ["lib/b.py"]},
                    "blockedBy": [],
                }
            return None

        mock_load_ticket.side_effect = load_ticket_side_effect

        parent_info = {
            "version": "0.31.0",
            "children": ["037.1"],
        }
        new_ticket = {
            "title": "Task 2",
            "where": {"files": ["lib/b.py"]},
        }
        new_ticket_id = "037.2"

        _print_parallel_analysis_result(parent_info, new_ticket, new_ticket_id)

        captured = capsys.readouterr()
        assert "並行分析" in captured.out
        assert "分析結果:" in captured.out
        assert "理由:" in captured.out


class TestPrintCreateChecklist:
    """建立檢查清單功能測試"""

    def test_print_create_checklist_root_task_imp(self, capsys):
        """測試根任務 IMP 類型的檢查清單"""
        _print_create_checklist(
            ticket_id="0.31.0-W4-001",
            ticket_type="IMP",
            parent_id=None,
        )

        captured = capsys.readouterr()
        assert "建立檢查清單" in captured.out
        assert "SA 前置審查" in captured.out
        assert "拆分子任務" in captured.out
        assert "TDD 順序建議" in captured.out

    def test_print_create_checklist_root_task_doc(self, capsys):
        """測試根任務 DOC 類型的檢查清單"""
        _print_create_checklist(
            ticket_id="0.31.0-W4-001",
            ticket_type="DOC",
            parent_id=None,
        )

        captured = capsys.readouterr()
        assert "建立檢查清單" in captured.out
        # DOC 類型無需 SA 審查
        assert "SA 前置審查" not in captured.out
        # DOC 類型無需 TDD 流程，所以不輸出建議
        # （_print_tdd_sequence_suggestion 會直接返回）

    def test_print_create_checklist_child_task(self, capsys):
        """測試子任務的檢查清單"""
        _print_create_checklist(
            ticket_id="0.31.0-W4-001.1",
            ticket_type="IMP",
            parent_id="0.31.0-W4-001",
            parent_info=None,
            new_ticket=None,
        )

        captured = capsys.readouterr()
        assert "建立檢查清單" in captured.out
        # 子任務不需要 SA 前置審查
        assert "SA 前置審查" not in captured.out


class TestCreateCommandIntegration:
    """create 命令整合測試"""

    def test_integration_tdd_and_parallel(self):
        """測試 TDD 建議和並行分析的完整整合"""
        # 測試 IMP 類型的 TDD 建議
        tdd_result = suggest_tdd_sequence(task_type="IMP")
        assert len(tdd_result.phases) == 5

        # 測試並行分析
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.py"]},
            {"task_id": "002", "where_files": ["lib/b.py"]},
        ]
        parallel_result = ParallelAnalyzer.analyze_tasks(tasks)
        assert parallel_result.can_parallel

        # 驗證整合邏輯
        assert len(tdd_result.phases) > 0
        assert parallel_result.can_parallel is True
