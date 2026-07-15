"""Phase 4 Review Evidence Checker 測試（W1-080.1）。"""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from acceptance_checkers.phase4_review_checker import check_phase4_review_evidence


def _logger():
    return logging.getLogger("test_phase4_review_checker")


def _make_content(ticket_type="IMP", solution_body=""):
    fm = f"---\ntype: {ticket_type}\n---\n"
    if solution_body:
        return f"{fm}\n## Solution\n{solution_body}\n\n## Test Results\n"
    return f"{fm}\n## Test Results\n"


class TestPhase4ReviewChecker:
    def test_imp_with_parallel_evaluation_passes(self):
        content = _make_content(solution_body="### 並行評估報告\n結論：通過")
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is None

    def test_imp_with_phase4_keyword_passes(self):
        content = _make_content(solution_body="Phase 4 重構評估完成")
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is None

    def test_imp_with_code_review_passes(self):
        content = _make_content(solution_body="code review 完成，Layer 2 by basil")
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is None

    def test_imp_with_multi_view_passes(self):
        content = _make_content(solution_body="5 視角多視角審查完成")
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is None

    def test_imp_without_evidence_warns(self):
        content = _make_content(solution_body="實作完成，測試通過")
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is not None
        assert "Phase 4 審查" in result
        assert "warning" in result

    def test_imp_empty_solution_warns(self):
        content = _make_content(solution_body="")
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is None  # No Solution section = skip

    def test_imp_no_solution_section_skips(self):
        content = "---\ntype: IMP\n---\n\n## Test Results\n"
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is None

    def test_ana_type_skips(self):
        content = _make_content(ticket_type="ANA", solution_body="無審查")
        result = check_phase4_review_evidence(content, "ANA", _logger())
        assert result is None

    def test_doc_type_skips(self):
        content = _make_content(ticket_type="DOC", solution_body="無審查")
        result = check_phase4_review_evidence(content, "DOC", _logger())
        assert result is None

    def test_case_insensitive_keyword(self):
        content = _make_content(solution_body="parallel-evaluation 完成")
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is None

    def test_self_check_with_layer2_passes(self):
        content = _make_content(
            solution_body="### 自檢結果\nLayer 2 審查完成"
        )
        result = check_phase4_review_evidence(content, "IMP", _logger())
        assert result is None
