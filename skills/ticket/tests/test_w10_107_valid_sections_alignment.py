"""W10-107: 對齊 VALID_SECTIONS 與 ticket-body-schema.md 權威 schema

差距：ticket-body-schema.md 中 ANA type 必填「重現實驗結果」章節，但
VALID_SECTIONS 不含此值；ANA 執行者被迫 workaround 寫到 Solution。

本測試確保：
1. VALID_SECTIONS 包含 ANA 必填的「重現實驗結果」
2. 既有 7 個 section 仍存在（無 regression）
3. 總長度更新為 8
"""

from ticket_system.lib.command_tracking_messages import TrackAcceptanceMessages


class TestValidSectionsSchemaAlignment:
    """W10-107: VALID_SECTIONS ↔ ticket-body-schema.md 對齊"""

    def test_reproduction_experiment_section_included(self):
        """ANA 必填章節「重現實驗結果」應在 VALID_SECTIONS（schema 對齊）"""
        assert "重現實驗結果" in TrackAcceptanceMessages.VALID_SECTIONS

    def test_existing_seven_sections_preserved(self):
        """既有 7 個 section 仍存在，無 regression"""
        for section in [
            "Problem Analysis",
            "Context Bundle",
            "Solution",
            "Test Results",
            "Execution Log",
            "NeedsContext",
            "Exit Status",
        ]:
            assert section in TrackAcceptanceMessages.VALID_SECTIONS, (
                f"既有 section '{section}' 被誤刪"
            )

    def test_total_ten_sections(self):
        """W3-099 補入 'Task Summary' 與 'Completion Info' 後總數為 10
        （W10-107 原為 8，本次補完成 IMP/ANA/DOC 三類型必填章節 SSOT 對齊）
        """
        assert len(TrackAcceptanceMessages.VALID_SECTIONS) == 10
