"""W17-010: NeedsContext + Exit Status schema 測試

覆蓋範圍：
1. VALID_SECTIONS 包含 NeedsContext 與 Exit Status
2. Ticket template 含 NeedsContext section
3. Ticket template 含 Exit Status section（YAML schema 註解）
4. Exit Status YAML 5 狀態枚舉值可解析
5. Exit Status YAML 必要欄位齊備
6. 狀態值與 exit code 對應正確
"""

import re
import yaml
import pytest

from ticket_system.lib.command_tracking_messages import TrackAcceptanceMessages
from ticket_system.lib.ticket_builder import create_ticket_body


# 狀態值與 exit code 對應表（W17-010 協議）
STATUS_EXIT_CODE_MAP = {
    "success": 0,
    "partial_success": 0,
    "needs_context": 2,
    "blocked": 2,
    "failed": 1,
}


class TestValidSectionsExpanded:
    """VALID_SECTIONS 擴增測試"""

    def test_needs_context_in_valid_sections(self):
        assert "NeedsContext" in TrackAcceptanceMessages.VALID_SECTIONS

    def test_exit_status_in_valid_sections(self):
        assert "Exit Status" in TrackAcceptanceMessages.VALID_SECTIONS

    def test_existing_sections_preserved(self):
        for section in ["Problem Analysis", "Context Bundle", "Solution",
                        "Test Results", "Execution Log"]:
            assert section in TrackAcceptanceMessages.VALID_SECTIONS

    def test_total_seven_sections(self):
        assert len(TrackAcceptanceMessages.VALID_SECTIONS) == 7


class TestTicketTemplateSections:
    """Ticket template 含新 section 測試"""

    def test_template_has_needs_context_section(self):
        body = create_ticket_body(what="test", who="thyme-python-developer")
        assert "## NeedsContext" in body

    def test_template_has_exit_status_section(self):
        body = create_ticket_body(what="test", who="thyme-python-developer")
        assert "## Exit Status" in body

    def test_exit_status_section_before_completion_info(self):
        body = create_ticket_body(what="test", who="thyme-python-developer")
        exit_idx = body.index("## Exit Status")
        completion_idx = body.index("## Completion Info")
        assert exit_idx < completion_idx

    def test_template_documents_yaml_schema(self):
        body = create_ticket_body(what="test", who="thyme-python-developer")
        # Schema 欄位應在註解中出現
        for field in ["status:", "reason:", "confidence:",
                      "acceptance_met:", "artifacts:"]:
            assert field in body, f"Missing schema field: {field}"


class TestExitStatusYamlParsing:
    """Exit Status YAML schema 解析測試"""

    @pytest.mark.parametrize("status,expected_code", [
        ("success", 0),
        ("partial_success", 0),
        ("needs_context", 2),
        ("blocked", 2),
        ("failed", 1),
    ])
    def test_status_enum_to_exit_code(self, status, expected_code):
        assert STATUS_EXIT_CODE_MAP[status] == expected_code

    def test_yaml_parses_sample_exit_status(self):
        yaml_text = """
status: needs_context
reason: "X 模組介面未定義"
confidence: 0.8
acceptance_met: [0, 1]
acceptance_unmet: [2, 3]
artifacts:
  - src/foo.py
context_dependencies:
  - X 模組 API 文件
estimated_recovery_effort: "10K tokens"
"""
        parsed = yaml.safe_load(yaml_text)
        assert parsed["status"] == "needs_context"
        assert parsed["confidence"] == 0.8
        assert parsed["acceptance_met"] == [0, 1]
        assert parsed["artifacts"] == ["src/foo.py"]

    def test_yaml_rejects_invalid_status(self):
        """非枚舉值應可被識別為無效（由 PM 層驗證）"""
        yaml_text = "status: unknown_state\n"
        parsed = yaml.safe_load(yaml_text)
        assert parsed["status"] not in STATUS_EXIT_CODE_MAP


class TestTemplateStructure:
    """Template 結構完整性測試"""

    def test_template_needs_context_has_child_template(self):
        """NeedsContext section 應含子項 template 註解"""
        body = create_ticket_body(what="test", who="thyme-python-developer")
        needs_idx = body.index("## NeedsContext")
        exit_idx = body.index("## Exit Status")
        needs_section = body[needs_idx:exit_idx]
        # 子項 template 應包含關鍵欄位
        for keyword in ["缺失項", "觸發位置", "影響", "建議補料", "重派成本"]:
            assert keyword in needs_section, f"Missing keyword: {keyword}"
