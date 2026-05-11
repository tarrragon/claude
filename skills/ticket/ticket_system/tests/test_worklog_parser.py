"""RED tests for ticket_system/lib/worklog_parser.py (W17-083.1 Phase 2/3b).

對應 W17-083 Phase 2 sage §S1 12 測試案例（S1-T01 ~ S1-T12）。

API 契約（依 Phase 3a pepper 虛擬碼）：
- HANDOFF_KEYWORDS: tuple[str, ...]
- detect_handoff_keywords(content: str) -> bool
- extract_ticket_ids(content: str, active_version: str | None = None) -> list[str]
- extract_recent_content(worklog_path: Path, since_mtime: float) -> str

Phase 3b 實作後預期全部變綠。RED 原因：
- ticket_system/lib/worklog_parser.py 尚未存在
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# S1-T01 ~ S1-T04: detect_handoff_keywords()
# ---------------------------------------------------------------------------


class TestDetectHandoffKeywords:
    """關鍵字偵測函式測試（4 案例）"""

    def test_t01_title_style_keyword(self):
        """S1-T01 正常/關鍵字偵測：「下個 Session 接手 Context」"""
        from ticket_system.lib.worklog_parser import detect_handoff_keywords

        content = "## 下個 Session 接手 Context\n\n本次 session 結束\n"
        assert detect_handoff_keywords(content) is True

    def test_t02_advisory_style_keyword(self):
        """S1-T02 正常/關鍵字偵測：建議式「下 session 優先建議」"""
        from ticket_system.lib.worklog_parser import detect_handoff_keywords

        content = "下 session 優先建議：W17-079 補完成 PCB\n"
        assert detect_handoff_keywords(content) is True

    def test_t03_english_keyword(self):
        """S1-T03 正常/關鍵字偵測：英文「Handoff Context」"""
        from ticket_system.lib.worklog_parser import detect_handoff_keywords

        content = "## Handoff Context\n\nNext session pickup:\n"
        assert detect_handoff_keywords(content) is True

    def test_t04_no_keyword(self):
        """S1-T04 異常/無關鍵字：一般 worklog 文字"""
        from ticket_system.lib.worklog_parser import detect_handoff_keywords

        content = "## 2026-04-24 工作日誌\n\n完成 W17-080 重構\n"
        assert detect_handoff_keywords(content) is False


# ---------------------------------------------------------------------------
# S1-T05 ~ S1-T09, S1-T12: extract_ticket_ids()
# ---------------------------------------------------------------------------


class TestExtractTicketIds:
    """Ticket ID 提取函式測試（7 案例）"""

    def test_t05_full_id_extraction(self):
        """S1-T05 正常/ID 提取（完整）：「0.18.0-W17-079」"""
        from ticket_system.lib.worklog_parser import extract_ticket_ids

        content = "下 session 優先建議：0.18.0-W17-079 補完成"
        result = extract_ticket_ids(content)
        assert result == ["0.18.0-W17-079"]

    def test_t06_short_id_completion_with_active_version(self):
        """S1-T06 邊界/短 ID 補全：「W17-079」+ active_version="0.18.0" """
        from ticket_system.lib.worklog_parser import extract_ticket_ids

        content = "下 session 優先建議：W17-079 補完成"
        result = extract_ticket_ids(content, active_version="0.18.0")
        assert result == ["0.18.0-W17-079"]

    def test_t07_multi_id_dedup_preserve_order(self):
        """S1-T07 邊界/多 ID 去重：「W17-079」「W17-079」「W17-080」順序保留 + 去重"""
        from ticket_system.lib.worklog_parser import extract_ticket_ids

        content = (
            "下 session 優先建議：\n"
            "1. W17-079 補 PCB\n"
            "2. W17-079 同前項\n"
            "3. W17-080 後續處理\n"
        )
        result = extract_ticket_ids(content, active_version="0.18.0")
        assert result == ["0.18.0-W17-079", "0.18.0-W17-080"]

    def test_t08_sub_ticket_id_with_dot_n(self):
        """S1-T08 邊界/子 ticket ID：「W17-083.1」regex 必須容納 .\\d+ 後綴"""
        from ticket_system.lib.worklog_parser import extract_ticket_ids

        content = "下 session 優先建議：W17-083.1 實作 lib/worklog_parser.py"
        result = extract_ticket_ids(content, active_version="0.18.0")
        assert result == ["0.18.0-W17-083.1"]

    def test_t09_no_id_in_content(self):
        """S1-T09 異常/無 ID：「下個 Session 接手 Context」無 ticket"""
        from ticket_system.lib.worklog_parser import extract_ticket_ids

        content = "下個 Session 接手 Context\n（無具體 ticket，僅作背景說明）"
        result = extract_ticket_ids(content)
        assert result == []

    def test_t12_id_in_code_block(self):
        """S1-T12 中斷/regex 在 code block 內（簡化策略——不過濾，方案 D 接受誤報）"""
        from ticket_system.lib.worklog_parser import extract_ticket_ids

        content = (
            "建議執行：\n"
            "```\n"
            "ticket handoff W17-079\n"
            "```\n"
        )
        result = extract_ticket_ids(content, active_version="0.18.0")
        # sage 規格：不過濾 code block，仍應命中
        assert "0.18.0-W17-079" in result


# ---------------------------------------------------------------------------
# S1-T10 ~ S1-T11: extract_recent_content()
# ---------------------------------------------------------------------------


class TestExtractRecentContent:
    """worklog 最新內容擷取函式測試（2 案例）"""

    def test_t10_worklog_not_exist(self, tmp_path):
        """S1-T10 邊界/worklog 不存在：回 ""（契約二擇一，sage 建議回空字串配合 hook 靜默退出）"""
        from ticket_system.lib.worklog_parser import extract_recent_content

        missing_path = tmp_path / "non_existent_worklog.md"
        result = extract_recent_content(missing_path, since_mtime=0.0)
        assert result == ""

    def test_t11_worklog_mtime_older_than_session(self, tmp_path):
        """S1-T11 邊界/worklog mtime 早於 session：過濾掉非本 session 變更"""
        from ticket_system.lib.worklog_parser import extract_recent_content

        worklog_path = tmp_path / "worklog.md"
        worklog_path.write_text("含關鍵字：下個 Session 接手 Context\n", encoding="utf-8")

        # 將 since_mtime 設為未來時間（檔案 mtime 必早於它）
        future_mtime = time.time() + 10000.0
        result = extract_recent_content(worklog_path, since_mtime=future_mtime)
        assert result == ""


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
