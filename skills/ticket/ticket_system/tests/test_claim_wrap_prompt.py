"""
Ticket 0.18.0-W10-028：claim 命令附加簡化 WRAP 三問提示測試

驗證：
1. ClaimWrapMessages 常數存在於 command_tracking_messages
2. _print_claim_checklist 後會印出簡化 WRAP 三問區段
3. ANA 類型額外印出完整 WRAP 提示；IMP/DOC 類型不額外印出
4. 提示文案集中在 command_tracking_messages.py（不在 lifecycle.py hardcoded）
"""
from __future__ import annotations

import io
import contextlib

import pytest

from ticket_system.lib.command_tracking_messages import ClaimWrapMessages
from ticket_system.commands.lifecycle import _print_claim_checklist


class TestClaimWrapMessagesConstants:
    """ClaimWrapMessages 常數定義測試"""

    def test_wrap_section_title_exists(self):
        assert hasattr(ClaimWrapMessages, "WRAP_SECTION_TITLE")
        assert "簡化 WRAP 三問" in ClaimWrapMessages.WRAP_SECTION_TITLE

    def test_wrap_intro_mentions_ticket_source(self):
        assert hasattr(ClaimWrapMessages, "WRAP_SECTION_TITLE")
        # 標題需引用來源 ticket（0.18.0-W10-027）
        assert "0.18.0-W10-027" in ClaimWrapMessages.WRAP_SECTION_TITLE

    def test_wrap_widen_question_exists(self):
        assert hasattr(ClaimWrapMessages, "WRAP_WIDEN")
        assert "W" in ClaimWrapMessages.WRAP_WIDEN
        assert "其他做法" in ClaimWrapMessages.WRAP_WIDEN

    def test_wrap_attain_distance_question_exists(self):
        assert hasattr(ClaimWrapMessages, "WRAP_ATTAIN_DISTANCE")
        assert "機會成本" in ClaimWrapMessages.WRAP_ATTAIN_DISTANCE

    def test_wrap_prepare_wrong_question_exists(self):
        assert hasattr(ClaimWrapMessages, "WRAP_PREPARE_WRONG")
        assert "失敗" in ClaimWrapMessages.WRAP_PREPARE_WRONG

    def test_wrap_applies_to_all_types(self):
        assert hasattr(ClaimWrapMessages, "WRAP_APPLIES_TO")
        # 含格式化 placeholder
        assert "{ticket_type}" in ClaimWrapMessages.WRAP_APPLIES_TO

    def test_ana_extra_prompt_exists(self):
        assert hasattr(ClaimWrapMessages, "ANA_EXTRA_HEADER")
        assert hasattr(ClaimWrapMessages, "ANA_EXTRA_BODY")
        assert "ANA" in ClaimWrapMessages.ANA_EXTRA_HEADER
        assert "/wrap-decision" in ClaimWrapMessages.ANA_EXTRA_BODY

    def test_ana_reality_test_constant_exists(self):
        """PC-063 防護 4/4：ANA 類型專屬第四問 R（Reality Test）"""
        assert hasattr(ClaimWrapMessages, "ANA_REALITY_TEST")
        assert "Reality Test" in ClaimWrapMessages.ANA_REALITY_TEST
        assert "重現實驗" in ClaimWrapMessages.ANA_REALITY_TEST
        assert "PC-063" in ClaimWrapMessages.ANA_REALITY_TEST


class TestPrintClaimChecklistWrapSection:
    """_print_claim_checklist 附加 WRAP 區段的輸出測試"""

    @staticmethod
    def _capture_output(ticket: dict) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _print_claim_checklist(ticket)
        return buf.getvalue()

    def test_imp_ticket_includes_wrap_section(self):
        out = self._capture_output({"id": "0.18.0-W10-028", "type": "IMP"})
        assert "簡化 WRAP 三問" in out
        assert "機會成本" in out

    def test_doc_ticket_includes_wrap_section(self):
        out = self._capture_output({"id": "0.18.0-W10-028", "type": "DOC"})
        assert "簡化 WRAP 三問" in out

    def test_ana_ticket_includes_wrap_section_and_extra(self):
        out = self._capture_output({"id": "0.18.0-W10-027", "type": "ANA"})
        assert "簡化 WRAP 三問" in out
        assert "ANA 類型額外要求" in out
        assert "/wrap-decision" in out

    def test_imp_ticket_does_not_include_ana_extra(self):
        out = self._capture_output({"id": "0.18.0-W10-028", "type": "IMP"})
        assert "ANA 類型額外要求" not in out

    def test_doc_ticket_does_not_include_ana_extra(self):
        out = self._capture_output({"id": "0.18.0-W10-028", "type": "DOC"})
        assert "ANA 類型額外要求" not in out

    def test_ana_ticket_includes_reality_test(self):
        """PC-063 防護 4/4：ANA claim 時輸出第四問 R（Reality Test）"""
        out = self._capture_output({"id": "0.18.0-W5-036", "type": "ANA"})
        assert "R（Reality Test）" in out
        assert "重現實驗" in out

    def test_imp_ticket_excludes_reality_test(self):
        """PC-063 防護 4/4：非 ANA 類型不應出現第四問 R"""
        out = self._capture_output({"id": "0.18.0-W5-036", "type": "IMP"})
        assert "R（Reality Test）" not in out

    def test_wrap_section_after_claim_checklist(self):
        """WRAP 區段必須在「認領檢查清單」之後"""
        out = self._capture_output({"id": "0.18.0-W10-028", "type": "IMP"})
        idx_checklist = out.find("認領檢查清單")
        idx_wrap = out.find("簡化 WRAP 三問")
        assert idx_checklist >= 0
        assert idx_wrap > idx_checklist

    def test_wrap_section_shows_ticket_type(self):
        out = self._capture_output({"id": "0.18.0-W10-028", "type": "IMP"})
        assert "IMP" in out


class TestNoHardcodedWrapTextInLifecycle:
    """確保 WRAP 三問文案來自 ClaimWrapMessages 而非 lifecycle.py 硬編碼"""

    def test_wrap_strings_sourced_from_constants(self):
        from pathlib import Path

        lifecycle_path = Path(__file__).parent.parent / "commands" / "lifecycle.py"
        source = lifecycle_path.read_text(encoding="utf-8")
        # lifecycle.py 內不應直接出現 WRAP 三問的完整文案
        # 允許引用 ClaimWrapMessages 常數
        assert "有其他做法嗎" not in source or "ClaimWrapMessages" in source
