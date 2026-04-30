"""
ANA Ticket Metadata Validation Hook 測試（W11-004.5 / PC-058）

對應 Acceptance Criteria：
- 偵測 ANA 代理人完成後是否建立新 Ticket
- 驗證 who 是否符合 CLAUDE.md 指定語言實作代理人
- 驗證 acceptance 每項 < 100 字元、無「;」分隔多條件
- 驗證 tdd_phase 與 ticket type 合理
- 發現不符時輸出 warning（不 block）
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


@pytest.fixture
def hook_module():
    """動態載入 ana-ticket-metadata-validation-hook 模組（檔名含連字號）"""
    spec = importlib.util.spec_from_file_location(
        "ana_ticket_metadata_validation_hook",
        _HOOKS_DIR / "ana-ticket-metadata-validation-hook.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_logger():
    logger = MagicMock()
    return logger


# ============================================================================
# is_ana_created_ticket
# ============================================================================

class TestIsAnaCreatedTicket:
    def test_who_current_saffron(self, hook_module):
        fm = {"who": {"current": "saffron-system-analyst"}}
        assert hook_module.is_ana_created_ticket(fm) is True

    def test_who_contains_saffron_substring(self, hook_module):
        fm = {"who": {"current": "saffron-analyst"}}
        assert hook_module.is_ana_created_ticket(fm) is True

    def test_source_ticket_set(self, hook_module):
        fm = {"who": {"current": "thyme-extension-engineer"}, "source_ticket": "0.18.0-W1-001"}
        assert hook_module.is_ana_created_ticket(fm) is True

    def test_normal_imp_ticket(self, hook_module):
        fm = {"who": {"current": "thyme-extension-engineer"}, "source_ticket": None}
        assert hook_module.is_ana_created_ticket(fm) is False

    def test_empty_frontmatter(self, hook_module):
        assert hook_module.is_ana_created_ticket({}) is False


# ============================================================================
# validate_who_field
# ============================================================================

class TestValidateWho:
    def test_imp_who_mismatch_warns(self, hook_module):
        fm = {
            "type": "IMP",
            "who": {"current": "parsley-flutter-developer"},
        }
        warn = hook_module.validate_who_field(fm, "thyme-extension-engineer")
        assert warn is not None
        assert "parsley-flutter-developer" in warn
        assert "thyme-extension-engineer" in warn

    def test_imp_who_match_no_warn(self, hook_module):
        fm = {"type": "IMP", "who": {"current": "thyme-extension-engineer"}}
        assert hook_module.validate_who_field(fm, "thyme-extension-engineer") is None

    def test_doc_type_skipped(self, hook_module):
        fm = {"type": "DOC", "who": {"current": "parsley-flutter-developer"}}
        assert hook_module.validate_who_field(fm, "thyme-extension-engineer") is None

    def test_ana_agent_self_skipped(self, hook_module):
        fm = {"type": "IMP", "who": {"current": "saffron-system-analyst"}}
        assert hook_module.validate_who_field(fm, "thyme-extension-engineer") is None

    def test_no_expected_agent_skipped(self, hook_module):
        fm = {"type": "IMP", "who": {"current": "parsley-flutter-developer"}}
        assert hook_module.validate_who_field(fm, None) is None


# ============================================================================
# validate_acceptance
# ============================================================================

class TestValidateAcceptance:
    def test_short_items_no_warn(self, hook_module):
        fm = {"acceptance": ["[ ] 完成 X 功能", "[ ] 測試通過"]}
        assert hook_module.validate_acceptance(fm) == []

    def test_long_item_warns(self, hook_module):
        long_item = "[ ] " + "A" * 120
        fm = {"acceptance": [long_item]}
        warns = hook_module.validate_acceptance(fm)
        assert len(warns) == 1
        assert "長度" in warns[0]

    def test_semicolon_separator_warns(self, hook_module):
        fm = {"acceptance": ["[ ] 完成 X; 完成 Y; 完成 Z"]}
        warns = hook_module.validate_acceptance(fm)
        assert any("分隔符" in w for w in warns)

    def test_chinese_semicolon_warns(self, hook_module):
        fm = {"acceptance": ["[ ] 完成 X；完成 Y"]}
        warns = hook_module.validate_acceptance(fm)
        assert any("分隔符" in w for w in warns)

    def test_empty_acceptance(self, hook_module):
        assert hook_module.validate_acceptance({"acceptance": []}) == []
        assert hook_module.validate_acceptance({}) == []


# ============================================================================
# validate_tdd_phase
# ============================================================================

class TestValidateTddPhase:
    def test_doc_with_tdd_phase_warns(self, hook_module):
        fm = {"type": "DOC", "tdd_phase": "phase1"}
        warn = hook_module.validate_tdd_phase(fm)
        assert warn is not None
        assert "DOC" in warn

    def test_doc_without_tdd_phase_ok(self, hook_module):
        fm = {"type": "DOC", "tdd_phase": None}
        assert hook_module.validate_tdd_phase(fm) is None

    def test_full_phase_with_short_what_warns(self, hook_module):
        fm = {
            "type": "IMP",
            "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b", "phase4"],
            "what": "修個小 bug",
        }
        warn = hook_module.validate_tdd_phase(fm)
        assert warn is not None

    def test_full_phase_with_long_what_ok(self, hook_module):
        fm = {
            "type": "IMP",
            "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b"],
            "what": "重構 ticket validator 全模組並調整所有相關測試套件以反映新邏輯",
        }
        assert hook_module.validate_tdd_phase(fm) is None


# ============================================================================
# is_ticket_file
# ============================================================================

class TestIsTicketFile:
    def test_valid_path(self, hook_module):
        p = Path("docs/work-logs/v0.18.0/tickets/0.18.0-W11-004.5.md")
        assert hook_module.is_ticket_file(p) is True

    def test_non_ticket_path(self, hook_module):
        assert hook_module.is_ticket_file(Path("src/foo.py")) is False
        assert hook_module.is_ticket_file(Path("docs/spec.md")) is False


# ============================================================================
# 整合測試：validate_ana_ticket
# ============================================================================

class TestValidateAnaTicketIntegration:
    def test_clean_ticket_no_warnings(self, hook_module):
        fm = {
            "type": "IMP",
            "who": {"current": "thyme-extension-engineer"},
            "acceptance": ["[ ] 完成 A", "[ ] 完成 B"],
            "tdd_phase": "phase1",
            "tdd_stage": ["phase1"],
            "what": "新增功能 X",
        }
        warns = hook_module.validate_ana_ticket(fm, "thyme-extension-engineer")
        assert warns == []

    def test_pc058_classic_case(self, hook_module):
        """重現 PC-058 案例：who 錯、acceptance 多條件塞一格"""
        fm = {
            "type": "IMP",
            "who": {"current": "parsley-flutter-developer"},
            "acceptance": [
                "[ ] 完成 A; 完成 B; 完成 C; 完成 D; 完成 E; 完成 F"
            ],
            "what": "修小 bug",
        }
        warns = hook_module.validate_ana_ticket(fm, "thyme-extension-engineer")
        # 至少 2 個 warning：who 錯誤 + acceptance 分隔符
        assert len(warns) >= 2
        joined = " ".join(warns)
        assert "parsley-flutter-developer" in joined
        assert "分隔符" in joined


# ============================================================================
# CLAUDE.md 解析
# ============================================================================

class TestImplementationAgentParsing:
    def test_parse_real_claude_md(self, hook_module, tmp_path, mock_logger):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# Project\n\n"
            "| 項目 | 值 |\n"
            "|------|------|\n"
            "| **語言** | JavaScript |\n"
            "| **實作代理人** | thyme-extension-engineer（Chrome Extension 開發） |\n",
            encoding="utf-8",
        )
        agent = hook_module.get_project_implementation_agent(tmp_path, mock_logger)
        assert agent == "thyme-extension-engineer"

    def test_missing_claude_md(self, hook_module, tmp_path, mock_logger):
        agent = hook_module.get_project_implementation_agent(tmp_path, mock_logger)
        assert agent is None

    def test_claude_md_without_field(self, hook_module, tmp_path, mock_logger):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project\n無實作代理人欄位\n", encoding="utf-8")
        agent = hook_module.get_project_implementation_agent(tmp_path, mock_logger)
        assert agent is None
