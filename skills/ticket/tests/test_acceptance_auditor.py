"""
Acceptance Auditor 單元測試

測試四步驟驗收檢查：
1. 結構完整性檢查
2. 子任務完成狀態檢查
3. 執行日誌完整性檢查
4. 驗收條件一致性檢查
"""
import pytest
from pathlib import Path
from typing import Dict, Any

from ticket_system.lib.acceptance_auditor import (
    validate_structure,
    validate_children_completed,
    validate_execution_log_completeness,
    validate_acceptance_consistency,
    run_audit,
    AuditStep,
    AuditReport,
)


# ============================================================
# Step 1: 結構完整性檢查
# ============================================================

class TestValidateStructure:
    """結構完整性檢查測試"""

    def test_valid_structure_all_required_fields(self):
        """完整的有效結構"""
        ticket = {
            "id": "0.31.0-W4-001",
            "title": "實作功能",
            "type": "IMP",
            "status": "in_progress",
            "version": "0.31.0",
            "wave": "W4",
            "priority": "P0",
            "who": {"current": "parsley-flutter-developer"},
            "what": "實作新功能",
            "why": "滿足需求",
            "acceptance": ["[x] 功能完成", "[ ] 測試完成"],
            "assigned": True,
            "started_at": "2026-02-01T10:00:00",
        }
        passed, issues = validate_structure(ticket)
        assert passed is True
        assert len(issues) == 0

    def test_missing_id_field(self):
        """缺失 id 欄位"""
        ticket = {
            "title": "Test",
            "type": "IMP",
            "status": "in_progress",
            "version": "0.31.0",
            "wave": "W4",
            "priority": "P0",
            "who": {"current": "agent"},
            "what": "Do something",
            "why": "Need to",
            "acceptance": ["Item"],
            "assigned": True,
            "started_at": "2026-02-01T10:00:00",
        }
        passed, issues = validate_structure(ticket)
        assert passed is False
        assert any("id" in issue for issue in issues)

    def test_missing_who_current(self):
        """缺失 who.current"""
        ticket = {
            "id": "0.31.0-W4-001",
            "title": "Test",
            "type": "IMP",
            "status": "in_progress",
            "version": "0.31.0",
            "wave": "W4",
            "priority": "P0",
            "who": {},
            "what": "Do something",
            "why": "Need to",
            "acceptance": ["Item"],
            "assigned": True,
            "started_at": "2026-02-01T10:00:00",
        }
        passed, issues = validate_structure(ticket)
        assert passed is False
        assert any("who.current" in issue for issue in issues)

    def test_empty_acceptance_array(self):
        """空的 acceptance 陣列"""
        ticket = {
            "id": "0.31.0-W4-001",
            "title": "Test",
            "type": "IMP",
            "status": "in_progress",
            "version": "0.31.0",
            "wave": "W4",
            "priority": "P0",
            "who": {"current": "agent"},
            "what": "Do something",
            "why": "Need to",
            "acceptance": [],
            "assigned": True,
            "started_at": "2026-02-01T10:00:00",
        }
        passed, issues = validate_structure(ticket)
        assert passed is False
        assert any("acceptance" in issue for issue in issues)

    def test_invalid_type(self):
        """無效的 type"""
        ticket = {
            "id": "0.31.0-W4-001",
            "title": "Test",
            "type": "INVALID",
            "status": "in_progress",
            "version": "0.31.0",
            "wave": "W4",
            "priority": "P0",
            "who": {"current": "agent"},
            "what": "Do something",
            "why": "Need to",
            "acceptance": ["Item"],
            "assigned": True,
            "started_at": "2026-02-01T10:00:00",
        }
        passed, issues = validate_structure(ticket)
        assert passed is False
        assert any("type" in issue for issue in issues)

    def test_assigned_false(self):
        """assigned 為 false"""
        ticket = {
            "id": "0.31.0-W4-001",
            "title": "Test",
            "type": "IMP",
            "status": "in_progress",
            "version": "0.31.0",
            "wave": "W4",
            "priority": "P0",
            "who": {"current": "agent"},
            "what": "Do something",
            "why": "Need to",
            "acceptance": ["Item"],
            "assigned": False,
            "started_at": "2026-02-01T10:00:00",
        }
        passed, issues = validate_structure(ticket)
        assert passed is False
        assert any("assigned" in issue for issue in issues)


# ============================================================
# Step 2: 子任務完成狀態檢查
# ============================================================

class TestValidateChildrenCompleted:
    """子任務完成狀態檢查測試"""

    def test_no_children_skipped(self, tmp_path, monkeypatch):
        """無子任務時跳過檢查"""
        # 設定工作目錄
        monkeypatch.chdir(tmp_path)

        ticket = {"children": []}
        passed, issues, skipped = validate_children_completed(ticket, "0.31.0")
        assert passed is True
        assert len(issues) == 0
        assert skipped is True

    def test_children_missing_returns_failed(self, tmp_path, monkeypatch):
        """找不到子任務檔案"""
        monkeypatch.chdir(tmp_path)

        ticket = {"children": ["0.31.0-W4-002"]}
        passed, issues, skipped = validate_children_completed(ticket, "0.31.0")
        assert passed is False
        assert skipped is False


# ============================================================
# Step 3: 執行日誌完整性檢查
# ============================================================

class TestValidateExecutionLogCompleteness:
    """執行日誌完整性檢查測試"""

    def test_all_sections_present_and_filled(self):
        """所有區段都存在且填寫"""
        body = """## Problem Analysis
This is the problem analysis.

## Solution
This is the solution.

## Test Results
All tests passed.
"""
        passed, issues = validate_execution_log_completeness(body)
        assert passed is True
        assert len(issues) == 0

    def test_missing_problem_analysis_section(self):
        """缺失 Problem Analysis 區段"""
        body = """## Solution
This is the solution.

## Test Results
All tests passed.
"""
        passed, issues = validate_execution_log_completeness(body)
        assert passed is False
        assert "Problem Analysis" in issues[0]

    def test_placeholder_in_solution(self):
        """Solution 區段包含佔位符"""
        body = """## Problem Analysis
This is the problem analysis.

## Solution
<!-- To be filled by executing agent -->

## Test Results
All tests passed.
"""
        passed, issues = validate_execution_log_completeness(body)
        assert passed is False
        assert "Solution" in issues[0]

    def test_pending_marker(self):
        """Test Results 包含 (pending) 標記"""
        body = """## Problem Analysis
This is the problem analysis.

## Solution
This is the solution.

## Test Results
(pending)
"""
        passed, issues = validate_execution_log_completeness(body)
        assert passed is False
        assert "Test Results" in issues[0]

    def test_empty_body(self):
        """空的 body"""
        passed, issues = validate_execution_log_completeness("")
        assert passed is False
        assert len(issues) == 1

    def test_support_h3_headings(self):
        """支援 ### 層級標題"""
        body = """### Problem Analysis
Analysis here

### Solution
Solution here

### Test Results
Results here
"""
        passed, issues = validate_execution_log_completeness(body)
        assert passed is True


# ============================================================
# Step 4: 驗收條件一致性檢查
# ============================================================

class TestValidateAcceptanceConsistency:
    """驗收條件一致性檢查測試"""

    def test_all_conditions_found_in_logs(self):
        """所有驗收條件都在日誌中找到"""
        acceptance = [
            "validate_structure 檢查",
            "子任務完成",
            "佔位符",
        ]
        solution = "實作 validate_structure() 函式檢查 YAML 欄位"
        test_results = "測試子任務完成狀態和佔位符偵測，通過"

        passed, warnings = validate_acceptance_consistency(
            acceptance, solution, test_results
        )
        assert passed is True
        assert len(warnings) == 0

    def test_some_conditions_not_found(self):
        """某些驗收條件找不到"""
        acceptance = [
            "validate_structure() 檢查必填欄位",
            "未在日誌中提到的條件",
        ]
        solution = "實作 validate_structure() 函式"
        test_results = "測試通過"

        passed, warnings = validate_acceptance_consistency(
            acceptance, solution, test_results
        )
        assert passed is True  # 仍視為通過，但有警告
        assert len(warnings) > 0
        assert "未在日誌中提到的條件" in warnings[0] or "無法自動確認" in warnings[0]

    def test_empty_acceptance_list(self):
        """空的 acceptance 清單"""
        passed, warnings = validate_acceptance_consistency(None, "Solution", "Results")
        assert passed is True
        assert len(warnings) == 0

    def test_case_insensitive_matching(self):
        """關鍵詞比對應不分大小寫"""
        acceptance = ["Validate Structure Function"]
        solution = "實作 validate_structure 函式"
        test_results = "測試通過"

        passed, warnings = validate_acceptance_consistency(
            acceptance, solution, test_results
        )
        assert passed is True
        assert len(warnings) == 0


# ============================================================
# 整合測試
# ============================================================

class TestAuditReport:
    """AuditReport 資料結構測試"""

    def test_audit_report_creation(self):
        """建立審計報告"""
        report = AuditReport(
            ticket_id="0.31.0-W4-001",
            title="Test Ticket",
            timestamp="2026-02-01T10:00:00"
        )
        assert report.ticket_id == "0.31.0-W4-001"
        assert report.title == "Test Ticket"
        assert report.overall_passed is False

    def test_audit_step_success_status(self):
        """成功的 audit step"""
        step = AuditStep(
            name="Test Step",
            passed=True,
            issues=[]
        )
        assert step.is_success() is True
        assert step.get_status_label() == "PASS"

    def test_audit_step_failure_status(self):
        """失敗的 audit step"""
        step = AuditStep(
            name="Test Step",
            passed=False,
            issues=["Issue 1"]
        )
        assert step.is_success() is False
        assert step.get_status_label() == "FAIL"

    def test_audit_step_with_warnings(self):
        """有警告的成功 step"""
        step = AuditStep(
            name="Test Step",
            passed=True,
            issues=[],
            warnings=["Warning 1"]
        )
        assert step.is_success() is True
        assert step.get_status_label() == "WARN"

    def test_audit_report_overall_failed_when_any_step_failed(self):
        """任一 step 失敗時報告失敗"""
        report = AuditReport(
            ticket_id="0.31.0-W4-001",
            title="Test",
            timestamp="2026-02-01T10:00:00"
        )
        report.add_step(AuditStep(name="Step 1", passed=True))
        report.add_step(AuditStep(name="Step 2", passed=False, issues=["Issue"]))
        report.add_step(AuditStep(name="Step 3", passed=True))

        report.overall_passed = len([s for s in report.steps if not s.passed and not s.skipped]) == 0
        assert report.overall_passed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
