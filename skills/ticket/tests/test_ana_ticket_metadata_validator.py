"""Ticket metadata 品質驗證（遷自 ana-ticket-metadata-validation-hook.py，PC-058）。

驗證三項檢查邏輯搬入 CLI 後行為與原 hook 一致，並涵蓋新增的 who 欄位範疇
限縮（`.claude/` 框架 ticket 略過 who 檢查——見模組 docstring 的量測依據）。
"""

from ticket_system.lib.ana_ticket_metadata_validator import (
    get_project_implementation_agent,
    validate_acceptance,
    validate_tdd_phase,
    validate_ticket_metadata,
    validate_who_field,
)


# ============================================================================
# get_project_implementation_agent
# ============================================================================


class TestGetProjectImplementationAgent:
    def test_parse_real_claude_md(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# Project\n\n"
            "| 項目 | 值 |\n"
            "|------|------|\n"
            "| **語言** | Flutter/Dart |\n"
            "| **實作代理人** | parsley-flutter-developer（Flutter 專精） |\n",
            encoding="utf-8",
        )
        assert get_project_implementation_agent(tmp_path) == "parsley-flutter-developer"

    def test_missing_claude_md(self, tmp_path):
        assert get_project_implementation_agent(tmp_path) is None

    def test_claude_md_without_field(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project\n無實作代理人欄位\n", encoding="utf-8")
        assert get_project_implementation_agent(tmp_path) is None


# ============================================================================
# validate_who_field（含範疇限縮：.claude/ 框架 ticket 略過）
# ============================================================================


class TestValidateWhoField:
    def test_framework_scoped_ticket_skipped_even_on_mismatch(self):
        """where.files 命中 .claude/ 時，即使 who.current 非預期代理人也不
        警告——本專案框架基礎設施類 ticket 依領域分工指派給專責代理人，
        非 CLAUDE.md 的單一「實作代理人」欄位所轄範圍。"""
        ticket = {
            "type": "IMP",
            "who": {"current": "thyme-python-developer"},
            "where": {"files": [".claude/skills/ticket/hooks/foo.py"]},
        }
        assert validate_who_field(ticket, "parsley-flutter-developer") is None

    def test_product_scoped_mismatch_warns(self):
        """where.files 為產品程式碼（非 .claude/）時，who 不符仍應警告。"""
        ticket = {
            "type": "IMP",
            "who": {"current": "thyme-python-developer"},
            "where": {"files": ["lib/domain/models.dart"]},
        }
        warn = validate_who_field(ticket, "parsley-flutter-developer")
        assert warn is not None
        assert "thyme-python-developer" in warn
        assert "parsley-flutter-developer" in warn
        assert "PC-058" in warn

    def test_product_scoped_match_no_warn(self):
        ticket = {
            "type": "IMP",
            "who": {"current": "parsley-flutter-developer"},
            "where": {"files": ["lib/domain/models.dart"]},
        }
        assert validate_who_field(ticket, "parsley-flutter-developer") is None

    def test_no_expected_agent_skipped(self):
        ticket = {
            "type": "IMP",
            "who": {"current": "thyme-python-developer"},
            "where": {"files": ["lib/x.dart"]},
        }
        assert validate_who_field(ticket, None) is None

    def test_doc_type_skipped(self):
        """非 IMP/FEAT/BUG 類型不檢查 who（DOC/ANA 等不受此檢查限制）。"""
        ticket = {
            "type": "DOC",
            "who": {"current": "thyme-python-developer"},
            "where": {"files": ["lib/x.dart"]},
        }
        assert validate_who_field(ticket, "parsley-flutter-developer") is None

    def test_mixed_where_files_still_skipped(self):
        """where.files 混合 .claude/ 與產品路徑時，仍算框架範疇略過
        （避免混合路徑的 ticket 誤觸發，寧可保守略過）。"""
        ticket = {
            "type": "IMP",
            "who": {"current": "thyme-python-developer"},
            "where": {"files": ["lib/x.dart", ".claude/hooks/y.py"]},
        }
        assert validate_who_field(ticket, "parsley-flutter-developer") is None


# ============================================================================
# validate_acceptance
# ============================================================================


class TestValidateAcceptance:
    def test_short_items_no_warn(self):
        ticket = {"acceptance": ["[ ] 短驗收條件"]}
        assert validate_acceptance(ticket) == []

    def test_long_item_warns(self):
        ticket = {"acceptance": ["[ ] " + "x" * 110]}
        warns = validate_acceptance(ticket)
        assert len(warns) == 1
        assert "110" in warns[0] or "長度" in warns[0]
        assert "PC-058" in warns[0]

    def test_semicolon_separator_warns(self):
        ticket = {"acceptance": ["[ ] 完成 A；完成 B"]}
        warns = validate_acceptance(ticket)
        assert any("分隔符" in w for w in warns)

    def test_empty_acceptance(self):
        assert validate_acceptance({"acceptance": []}) == []
        assert validate_acceptance({}) == []


# ============================================================================
# validate_tdd_phase
# ============================================================================


class TestValidateTddPhase:
    def test_doc_with_tdd_phase_warns(self):
        ticket = {"type": "DOC", "tdd_phase": "phase1"}
        warn = validate_tdd_phase(ticket)
        assert warn is not None
        assert "DOC" in warn

    def test_doc_without_tdd_phase_ok(self):
        ticket = {"type": "DOC", "tdd_phase": None}
        assert validate_tdd_phase(ticket) is None

    def test_full_phase_with_short_what_warns(self):
        ticket = {
            "type": "IMP",
            "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b"],
            "what": "修小 bug",
        }
        warn = validate_tdd_phase(ticket)
        assert warn is not None
        assert "PC-058" in warn

    def test_full_phase_with_long_what_ok(self):
        ticket = {
            "type": "IMP",
            "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b"],
            "what": "新增 2FA 設定開關，支援 TOTP 與 email 驗證碼兩種模式",
        }
        assert validate_tdd_phase(ticket) is None


# ============================================================================
# validate_ticket_metadata（彙整入口）
# ============================================================================


class TestValidateTicketMetadata:
    def test_clean_ticket_no_warnings(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "| **實作代理人** | parsley-flutter-developer |\n", encoding="utf-8"
        )
        ticket = {
            "type": "IMP",
            "who": {"current": "parsley-flutter-developer"},
            "where": {"files": ["lib/x.dart"]},
            "acceptance": ["[ ] 短驗收條件"],
            "tdd_phase": "phase1",
            "tdd_stage": ["phase1"],
            "what": "新增功能 X",
        }
        assert validate_ticket_metadata(ticket, tmp_path) == []

    def test_multiple_issues_all_reported(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "| **實作代理人** | parsley-flutter-developer |\n", encoding="utf-8"
        )
        ticket = {
            "type": "IMP",
            "who": {"current": "thyme-python-developer"},
            "where": {"files": ["lib/x.dart"]},
            "acceptance": ["[ ] " + "x" * 110 + "；分隔"],
            "tdd_phase": "phase1",
            "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b"],
            "what": "短",
        }
        warnings = validate_ticket_metadata(ticket, tmp_path)
        # who 不符 + acceptance 過長 + acceptance 分隔符 + tdd_stage 可疑預設
        assert len(warnings) == 4
        assert all(w.startswith("[WARNING]") for w in warnings)

    def test_framework_scoped_ticket_only_acceptance_and_tdd_checked(self, tmp_path):
        """框架範疇 ticket：who 略過，但 acceptance／tdd_phase 仍正常檢查
        （範疇限縮只影響 who 檢查，不影響其餘兩項）。"""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "| **實作代理人** | parsley-flutter-developer |\n", encoding="utf-8"
        )
        ticket = {
            "type": "IMP",
            "who": {"current": "thyme-python-developer"},
            "where": {"files": [".claude/hooks/foo.py"]},
            "acceptance": ["[ ] " + "x" * 110],
        }
        warnings = validate_ticket_metadata(ticket, tmp_path)
        assert len(warnings) == 1
        assert "acceptance" in warnings[0]
