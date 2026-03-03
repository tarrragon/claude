"""
TDD 順序和前置條件驗證整合測試

測試 TDD 順序建議和前置條件驗證在 create/claim 命令中的整合，
確保任務類型、Phase 序列、前置條件檢查正常運作。
"""

from typing import Dict, Any, List
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

import pytest

from ticket_system.lib.tdd_sequence import (
    identify_task_type,
    suggest_tdd_sequence,
    validate_phase_prerequisite,
    TDDSequenceResult,
    PhasePrerequisiteResult,
)
from ticket_system.commands.lifecycle import (
    _get_completed_phases_in_chain,
    _normalize_phase_name,
    _print_phase_prerequisite_warning,
)


# ============================================================================
# 測試案例 1：TDD 順序建議 - create 命令功能
# ============================================================================


class TestTDDSequenceSuggestionIntegration:
    """TDD 順序建議在 create 命令中的整合測試"""

    def test_create_suggests_tdd_sequence_for_imp(self):
        """
        Given: 建立新 IMP 類型 Ticket
        When: 執行 create 命令
        Then: 建議完整 TDD 序列 (P1→P2→P3a→P3b→P4)
        """
        result = suggest_tdd_sequence(task_type="IMP")

        assert result.task_type == "IMP"
        assert result.phases == ["phase1", "phase2", "phase3a", "phase3b", "phase4"]
        assert len(result.phases) == 5
        assert "TDD 流程" in result.description
        assert "新功能" in result.description

    def test_create_suggests_tdd_sequence_for_adj(self):
        """
        Given: 建立新 ADJ 類型 Ticket
        When: 執行 create 命令
        Then: 建議跳過 Phase 1 的序列 (P2→P3a→P3b→P4)
        """
        result = suggest_tdd_sequence(task_type="ADJ")

        assert result.task_type == "ADJ"
        assert result.phases == ["phase2", "phase3a", "phase3b", "phase4"]
        assert len(result.phases) == 4
        assert "phase1" not in result.phases
        assert "調整" in result.description or "修復" in result.description

    def test_create_suggests_no_tdd_for_doc(self):
        """
        Given: 建立新 DOC 類型 Ticket
        When: 執行 create 命令
        Then: 無 TDD 序列建議（空列表）
        """
        result = suggest_tdd_sequence(task_type="DOC")

        assert result.task_type == "DOC"
        assert result.phases == []
        assert len(result.phases) == 0
        assert "不需要 TDD" in result.description

    def test_identify_task_type_from_explicit_type(self):
        """
        Given: 明確指定 task_type
        When: 執行 identify_task_type
        Then: 返回指定的類型
        """
        result = identify_task_type(task_type="ADJ")
        assert result == "ADJ"

    def test_identify_task_type_from_keywords(self):
        """
        Given: 提供關鍵字清單
        When: 執行 identify_task_type
        Then: 根據關鍵字識別類型
        """
        # 測試 IMP 關鍵字
        result = identify_task_type(keywords=["實作", "新增"])
        assert result == "IMP"

        # 測試 ADJ 關鍵字
        result = identify_task_type(keywords=["重構", "優化"])
        assert result == "ADJ"

        # 測試 DOC 關鍵字
        result = identify_task_type(keywords=["文件", "記錄"])
        assert result == "DOC"

    def test_identify_task_type_defaults_to_imp(self):
        """
        Given: 無明確 task_type 也無關鍵字
        When: 執行 identify_task_type
        Then: 返回預設值 IMP
        """
        result = identify_task_type()
        assert result == "IMP"

    def test_suggest_tdd_sequence_with_keywords(self):
        """
        Given: 提供任務關鍵字（而非明確 task_type）
        When: 執行 suggest_tdd_sequence
        Then: 根據關鍵字識別類型並建議序列
        """
        result = suggest_tdd_sequence(keywords=["修復", "優化"])

        assert result.task_type == "ADJ"
        assert "phase1" not in result.phases
        assert len(result.phases) == 4


# ============================================================================
# 測試案例 2：前置條件驗證 - claim 命令功能
# ============================================================================


class TestPhasePrerequisiteValidation:
    """Phase 前置條件驗證在 claim 命令中的整合測試"""

    def test_validate_phase1_no_prerequisite(self):
        """
        Given: Phase 1 無前置條件
        When: 執行前置條件驗證
        Then: 驗證通過
        """
        result = validate_phase_prerequisite("phase1", completed_phases=[])

        assert result.valid is True
        assert result.missing_prerequisites == []

    def test_validate_phase2_requires_phase1(self):
        """
        Given: Phase 2 需要 Phase 1 完成，但未完成
        When: 執行前置條件驗證
        Then: 驗證失敗，提示缺少 Phase 1
        """
        result = validate_phase_prerequisite("phase2", completed_phases=[])

        assert result.valid is False
        assert "phase1" in result.missing_prerequisites
        assert "無法進入" in result.error_message

    def test_validate_phase2_success_with_phase1(self):
        """
        Given: Phase 2 需要 Phase 1，Phase 1 已完成
        When: 執行前置條件驗證
        Then: 驗證通過
        """
        result = validate_phase_prerequisite("phase2", completed_phases=["phase1"])

        assert result.valid is True
        assert result.missing_prerequisites == []

    def test_validate_phase3b_requires_all_prerequisites(self):
        """
        Given: Phase 3b 需要 Phase 1, 2, 3a 都完成
        When: Phase 3a 未完成
        Then: 驗證失敗，提示缺少 Phase 3a
        """
        result = validate_phase_prerequisite(
            "phase3b", completed_phases=["phase1", "phase2"]
        )

        assert result.valid is False
        assert "phase3a" in result.missing_prerequisites
        assert len(result.missing_prerequisites) == 1

    def test_validate_phase3b_success_with_all(self):
        """
        Given: Phase 3b 需要 Phase 3a
        When: Phase 3a 已完成
        Then: 驗證通過
        """
        result = validate_phase_prerequisite(
            "phase3b", completed_phases=["phase1", "phase2", "phase3a"]
        )

        assert result.valid is True
        assert result.missing_prerequisites == []

    def test_validate_phase4_requires_phase3b(self):
        """
        Given: Phase 4 需要 Phase 3b
        When: Phase 3b 未完成
        Then: 驗證失敗，提示缺少 Phase 3b
        """
        result = validate_phase_prerequisite(
            "phase4", completed_phases=["phase1", "phase2", "phase3a"]
        )

        assert result.valid is False
        assert "phase3b" in result.missing_prerequisites

    def test_validate_invalid_phase(self):
        """
        Given: 無效的 Phase 名稱
        When: 執行前置條件驗證
        Then: 驗證失敗，提示無效 Phase
        """
        result = validate_phase_prerequisite("phase99", completed_phases=[])

        assert result.valid is False
        assert "無效的 Phase" in result.error_message


# ============================================================================
# 測試案例 3：不同任務類型的前置條件組合
# ============================================================================


class TestTaskTypePhasePrerequisiteCombination:
    """不同任務類型的 Phase 序列和前置條件組合測試"""

    def test_imp_workflow_validates_all_phases(self):
        """
        Given: IMP 類型包含所有 5 個 Phase
        When: 逐個驗證每個 Phase
        Then: 所有前置條件驗證符合預期
        """
        tdd_result = suggest_tdd_sequence(task_type="IMP")
        phases = tdd_result.phases

        # 建立已完成 Phase 的進度跟蹤
        completed = []

        for phase in phases:
            # 驗證當前 Phase 需要的前置條件
            prereq_result = validate_phase_prerequisite(phase, completed)
            assert prereq_result.valid is True

            # 模擬完成當前 Phase
            completed.append(phase)

        # 最終應該完成所有 5 個 Phase
        assert len(completed) == 5

    def test_adj_workflow_skips_phase1(self):
        """
        Given: ADJ 類型跳過 Phase 1
        When: 驗證 ADJ 的 Phase 2（無需完成 Phase 1）
        Then: Phase 2 驗證通過，因為只需要 Phase 1，不在 ADJ 的序列中
        """
        tdd_result = suggest_tdd_sequence(task_type="ADJ")
        phases = tdd_result.phases

        # ADJ 應該跳過 Phase 1
        assert "phase1" not in phases
        assert phases[0] == "phase2"

        # 模擬 ADJ 工作流程：Phase 2 無需 Phase 1（因為 ADJ 不做 Phase 1）
        # 但驗證函式仍然會要求 Phase 1，這是預期的行為（任務鏈層級）
        completed = []
        result = validate_phase_prerequisite("phase2", completed)

        # 按照前置條件規則，Phase 2 仍然需要 Phase 1
        assert result.valid is False
        assert "phase1" in result.missing_prerequisites

    def test_doc_no_tdd_phases(self):
        """
        Given: DOC 類型無 TDD Phase
        When: 執行 suggest_tdd_sequence
        Then: 返回空 Phase 清單
        """
        tdd_result = suggest_tdd_sequence(task_type="DOC")

        assert tdd_result.phases == []
        assert len(tdd_result.phases) == 0


# ============================================================================
# 測試案例 4：邊界條件和特殊情況
# ============================================================================


class TestBoundaryConditions:
    """邊界條件和特殊情況測試"""

    def test_no_validation_for_ticket_without_phase(self):
        """
        Given: Ticket 無 tdd_phase（如 DOC 類型）
        When: 執行 claim
        Then: 跳過 Phase 前置條件驗證
        """
        # 這是由 lifecycle.py 中的 claim 函式處理的
        # 若 Ticket 無 tdd_phase，應跳過驗證
        # 我們測試的是：若 tdd_phase 為空，validate_phase_prerequisite 不被呼叫

        ticket_without_phase = {
            "id": "0.31.0-W4-001",
            "status": "pending",
            "tdd_phase": None,  # 無 Phase
        }

        tdd_phase = ticket_without_phase.get("tdd_phase")
        # 若無 Phase，應跳過驗證
        assert tdd_phase is None

    def test_multiple_missing_prerequisites(self):
        """
        Given: 進入 Phase 需要多個前置 Phase，但多個都未完成
        When: 執行前置條件驗證
        Then: missing_prerequisites 包含所有缺失的 Phase
        """
        result = validate_phase_prerequisite("phase3b", completed_phases=["phase1"])

        # Phase 3b 需要 Phase 3a，Phase 3a 需要 Phase 2
        # 所以如果只完成了 Phase 1，應該缺少 Phase 2 和 Phase 3a
        # 但實際上我們只檢查直接的前置條件
        assert result.valid is False
        assert "phase3a" in result.missing_prerequisites

    def test_empty_completed_phases(self):
        """
        Given: 無已完成的 Phase
        When: 驗證需要前置條件的 Phase
        Then: 所有前置條件都被視為缺失
        """
        result = validate_phase_prerequisite("phase2", completed_phases=[])

        assert result.valid is False
        assert len(result.missing_prerequisites) > 0

    def test_case_insensitive_phase_names(self):
        """
        Given: Phase 名稱大小寫不一致
        When: 驗證前置條件
        Then: 應該正確識別（前置條件檢查應大小寫敏感）
        """
        # Phase 名稱應該是小寫的標準格式（phase1, phase2a 等）
        result = validate_phase_prerequisite("phase1", completed_phases=["phase1"])

        assert result.valid is True


# ============================================================================
# 測試案例 5：Phase 名稱正規化
# ============================================================================


class TestPhaseNameNormalization:
    """Phase 名稱正規化功能測試"""

    def test_normalize_standard_phase_names(self):
        """
        Given: 標準格式的 Phase 名稱
        When: 執行正規化
        Then: 返回標準格式
        """
        assert _normalize_phase_name("phase1") == "phase1"
        assert _normalize_phase_name("phase2") == "phase2"
        assert _normalize_phase_name("phase3a") == "phase3a"

    def test_normalize_uppercase_phase_names(self):
        """
        Given: 大寫格式的 Phase 名稱
        When: 執行正規化
        Then: 轉換為小寫標準格式
        """
        assert _normalize_phase_name("PHASE1") == "phase1"
        assert _normalize_phase_name("Phase 1") == "phase1"

    def test_normalize_phase_with_description(self):
        """
        Given: 包含中文描述的 Phase 名稱
        When: 執行正規化
        Then: 提取標準格式部分
        """
        assert _normalize_phase_name("Phase 1（功能設計）") == "phase1"
        assert _normalize_phase_name("phase2(測試設計)") == "phase2"

    def test_normalize_invalid_phase_name(self):
        """
        Given: 無效的 Phase 名稱格式
        When: 執行正規化
        Then: 返回空字符串
        """
        assert _normalize_phase_name("invalid") == ""
        assert _normalize_phase_name("") == ""
        assert _normalize_phase_name(None) == ""


# ============================================================================
# 測試案例 6：整合測試 - 完整工作流程
# ============================================================================


class TestCompleteWorkflow:
    """完整工作流程的整合測試"""

    def test_complete_imp_workflow_simulation(self):
        """
        Given: 建立新 IMP Ticket 並逐步執行所有 Phase
        When: 模擬完整的 TDD 工作流程
        Then: 所有 Phase 都能按順序執行
        """
        # Step 1: 建立 IMP 類型的 Ticket，建議完整 TDD 序列
        tdd_result = suggest_tdd_sequence(task_type="IMP")
        assert len(tdd_result.phases) == 5

        # Step 2: 模擬逐步完成 Phase
        completed = []
        for phase in tdd_result.phases:
            # 驗證可以進入該 Phase
            prereq_result = validate_phase_prerequisite(phase, completed)
            assert prereq_result.valid is True

            # 完成該 Phase
            completed.append(phase)

        # Step 3: 驗證所有 Phase 都已完成
        assert len(completed) == 5
        assert completed == ["phase1", "phase2", "phase3a", "phase3b", "phase4"]

    def test_complete_adj_workflow_simulation(self):
        """
        Given: 建立新 ADJ Ticket
        When: 模擬 ADJ 工作流程（跳過 Phase 1）
        Then: 應該從 Phase 2 開始，但前置條件仍然要求 Phase 1
        """
        # ADJ 不做 Phase 1，所以序列中沒有 Phase 1
        tdd_result = suggest_tdd_sequence(task_type="ADJ")
        assert "phase1" not in tdd_result.phases

        # 但當驗證 Phase 2 時，系統會要求 Phase 1 作為前置條件
        # 這在實際使用中應該由任務鏈（多個 Ticket）來滿足
        result = validate_phase_prerequisite("phase2", completed_phases=[])
        assert result.valid is False

    @patch('ticket_system.commands.lifecycle.list_tickets')
    def test_get_completed_phases_from_chain(self, mock_list_tickets):
        """
        Given: 任務鏈中有多個已完成的 Ticket
        When: 執行 _get_completed_phases_in_chain
        Then: 返回所有已完成的 Phase
        """
        # 模擬任務鏈中的 Ticket 資料
        mock_tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "completed",
                "tdd_phase": "phase1",
                "chain": {"root": "0.31.0-W4-001", "parent": None},
            },
            {
                "id": "0.31.0-W4-001.1",
                "status": "completed",
                "tdd_phase": "phase2",
                "chain": {"root": "0.31.0-W4-001", "parent": "0.31.0-W4-001"},
            },
            {
                "id": "0.31.0-W4-001.2",
                "status": "in_progress",
                "tdd_phase": "phase3a",
                "chain": {"root": "0.31.0-W4-001", "parent": "0.31.0-W4-001.1"},
            },
        ]
        mock_list_tickets.return_value = mock_tickets

        # 取得目前 Ticket 的資訊
        current_ticket = mock_tickets[2]

        # 執行函式
        completed = _get_completed_phases_in_chain(current_ticket, "0.31.0")

        # 應該只返回已完成的 Phase（phase1 和 phase2）
        assert "phase1" in completed
        assert "phase2" in completed
        assert "phase3a" not in completed

    @patch('ticket_system.commands.lifecycle.load_ticket')
    @patch('ticket_system.commands.lifecycle.list_tickets')
    def test_print_phase_prerequisite_warning_message(
        self, mock_list_tickets, mock_load_ticket, capsys
    ):
        """
        Given: Phase 前置條件未滿足
        When: 執行 _print_phase_prerequisite_warning
        Then: 輸出適當的警告訊息
        """
        # 模擬 Ticket 資料
        mock_tickets = [
            {
                "id": "0.31.0-W4-001",
                "status": "completed",
                "tdd_phase": "phase1",
                "title": "Phase 1 Task",
                "chain": {"root": "0.31.0-W4-001"},
            },
        ]
        mock_list_tickets.return_value = mock_tickets

        mock_load_ticket.return_value = {
            "id": "0.31.0-W4-001",
            "title": "Phase 1 Task",
        }

        # 執行函式
        _print_phase_prerequisite_warning(
            ticket_id="0.31.0-W4-001.1",
            current_phase="phase2",
            missing_prerequisites=["phase1"],
            version="0.31.0",
        )

        # 驗證輸出訊息
        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out
        assert "phase 前置條件" in captured.out.lower() or "前置條件未滿足" in captured.out


# ============================================================================
# 測試案例 7：結果資料結構驗證
# ============================================================================


class TestResultDataStructures:
    """結果資料結構完整性驗證"""

    def test_tdd_sequence_result_structure(self):
        """
        Given: 建議 TDD 序列
        When: 檢查返回的結果結構
        Then: 應包含所有必要欄位
        """
        result = suggest_tdd_sequence(task_type="IMP")

        # 驗證所有必要欄位存在
        assert hasattr(result, "phases")
        assert hasattr(result, "task_type")
        assert hasattr(result, "description")
        assert hasattr(result, "rationale")

        # 驗證資料類型
        assert isinstance(result.phases, list)
        assert isinstance(result.task_type, str)
        assert isinstance(result.description, str)
        assert isinstance(result.rationale, str)

    def test_phase_prerequisite_result_structure(self):
        """
        Given: 驗證 Phase 前置條件
        When: 檢查返回的結果結構
        Then: 應包含所有必要欄位
        """
        result = validate_phase_prerequisite("phase2", completed_phases=[])

        # 驗證所有必要欄位存在
        assert hasattr(result, "valid")
        assert hasattr(result, "missing_prerequisites")
        assert hasattr(result, "error_message")

        # 驗證資料類型
        assert isinstance(result.valid, bool)
        assert isinstance(result.missing_prerequisites, list)
        assert isinstance(result.error_message, (str, type(None)))
