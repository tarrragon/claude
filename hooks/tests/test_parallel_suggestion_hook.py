"""
parallel-suggestion-hook 測試套件（0.2.1-W3-233）

驗證：
1. extract_ticket_info() 回傳 dict 含 wave 欄位，既有欄位不受影響
2. count_current_wave_pending() 依 in_progress Ticket 判斷當前 Wave 並統計同 Wave pending 數
   （涵蓋 pending 為零、非零兩種情形）
3. build_wave_wrap_up_status_line() 依實查結果組出斷言語氣或降級查證指引
4. WAVE_WRAP_UP_REMINDER 常數支援 {status_line} 參數化，且不殘留 0.2.1-W3-061 移除的
   偽裝偵測表述
"""

import logging
from pathlib import Path
import importlib.util

import pytest

from lib.ask_user_question_reminders import AskUserQuestionReminders

hooks_path = Path(__file__).parent.parent

# 動態導入 parallel-suggestion-hook（檔案名含 dash，需用 importlib）
hook_file = hooks_path / "parallel-suggestion-hook.py"
spec = importlib.util.spec_from_file_location("parallel_suggestion_hook", hook_file)
parallel_suggestion_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parallel_suggestion_hook)


@pytest.fixture
def logger():
    return logging.getLogger("test")


def _write_ticket(tickets_dir: Path, filename: str, status: str, wave, extra: str = "") -> Path:
    ticket_file = tickets_dir / filename
    ticket_file.write_text(
        f"---\nid: {filename[:-3]}\nstatus: {status}\nwave: {wave}\n{extra}---\nContent",
        encoding="utf-8",
    )
    return ticket_file


# ============================================================================
# extract_ticket_info() 補 wave 欄位
# ============================================================================


def test_extract_ticket_info_includes_wave(tmp_path, logger):
    """驗證 extract_ticket_info() 回傳 dict 含 wave 欄位"""
    ticket_file = _write_ticket(tmp_path, "0.2.1-W3-999.md", "pending", 3)

    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    assert info is not None
    assert "wave" in info, "extract_ticket_info() 回傳缺少 wave 欄位"
    # 註：本專案自製 YAML-lite 解析器（hook_ticket._parse_yaml_lines）不做數值型別
    # 推斷，純量一律以字串保留，故 wave 欄位值為 "3" 而非 int 3（與
    # commit-handoff-hook.py detect_wave_completion() 的既有行為一致）。
    assert info["wave"] == "3"


def test_extract_ticket_info_existing_fields_unaffected(tmp_path, logger):
    """驗證新增 wave 欄位不影響既有欄位"""
    ticket_file = _write_ticket(tmp_path, "0.2.1-W3-998.md", "in_progress", 3)

    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    assert info["id"] == "0.2.1-W3-998"
    assert info["status"] == "in_progress"
    assert info["type"] == "unknown"
    assert info["priority"] == "P2"


def test_extract_ticket_info_missing_wave_defaults_none(tmp_path, logger):
    """驗證無 wave frontmatter 時安全降級為 None"""
    ticket_file = tmp_path / "0.2.1-W3-997.md"
    ticket_file.write_text(
        "---\nid: 0.2.1-W3-997\nstatus: pending\n---\nContent",
        encoding="utf-8",
    )

    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    assert info["wave"] is None


# ============================================================================
# count_current_wave_pending()：pending 為零 / 非零兩種情形
# ============================================================================


def test_count_current_wave_pending_nonzero(logger):
    """驗證同 Wave 有 pending Ticket 時回傳正確計數（非零情形）"""
    tickets_info = [
        {"id": "A", "status": "in_progress", "wave": 3},
        {"id": "B", "status": "pending", "wave": 3},
        {"id": "C", "status": "pending", "wave": 3},
        {"id": "D", "status": "pending", "wave": 2},  # 不同 Wave，不計入
        {"id": "E", "status": "completed", "wave": 3},  # 非 pending，不計入
    ]

    current_wave, pending_count = parallel_suggestion_hook.count_current_wave_pending(
        tickets_info, logger
    )

    assert current_wave == 3
    assert pending_count == 2


def test_count_current_wave_pending_zero(logger):
    """驗證同 Wave 無 pending Ticket 時回傳 0（零情形）"""
    tickets_info = [
        {"id": "A", "status": "in_progress", "wave": 3},
        {"id": "B", "status": "completed", "wave": 3},
        {"id": "C", "status": "pending", "wave": 2},  # 不同 Wave，不計入
    ]

    current_wave, pending_count = parallel_suggestion_hook.count_current_wave_pending(
        tickets_info, logger
    )

    assert current_wave == 3
    assert pending_count == 0


def test_count_current_wave_pending_no_in_progress(logger):
    """驗證找不到 in_progress Ticket 時安全降級為 (None, None)"""
    tickets_info = [
        {"id": "A", "status": "pending", "wave": 3},
        {"id": "B", "status": "completed", "wave": 3},
    ]

    current_wave, pending_count = parallel_suggestion_hook.count_current_wave_pending(
        tickets_info, logger
    )

    assert current_wave is None
    assert pending_count is None


# ============================================================================
# build_wave_wrap_up_status_line()
# ============================================================================


def test_build_status_line_nonzero_pending():
    """pending 非零時使用斷言語氣並帶入真實數字"""
    line = parallel_suggestion_hook.build_wave_wrap_up_status_line(3, 2)

    assert "偵測到 Wave 3" in line
    assert "2 個 pending Ticket" in line
    assert "ticket track list --wave 3 --status pending" in line


def test_build_status_line_zero_pending():
    """pending 為零時使用斷言語氣說明已無 pending"""
    line = parallel_suggestion_hook.build_wave_wrap_up_status_line(3, 0)

    assert "偵測到 Wave 3" in line
    assert "已無 pending Ticket" in line
    assert "ticket track list --wave 3 --status pending" in line


def test_build_status_line_unknown_wave_degrades_to_verification_hint():
    """無法判斷當前 Wave 時降級為條件式查證指引，不得使用斷言語氣"""
    line = parallel_suggestion_hook.build_wave_wrap_up_status_line(None, None)

    assert "偵測到" not in line
    assert "需自行查證" in line


# ============================================================================
# WAVE_WRAP_UP_REMINDER 常數參數化 + 偽裝偵測表述不得回歸
# ============================================================================


def test_wave_wrap_up_reminder_supports_status_line_placeholder():
    """驗證 WAVE_WRAP_UP_REMINDER 可用 status_line 參數格式化"""
    status_line = parallel_suggestion_hook.build_wave_wrap_up_status_line(3, 0)
    message = AskUserQuestionReminders.WAVE_WRAP_UP_REMINDER.format(status_line=status_line)

    assert "偵測到 Wave 3" in message
    assert "已無 pending Ticket" in message
    assert "AskUserQuestion" in message


def test_wave_wrap_up_reminder_no_fabricated_detection_claim():
    """驗證常數本體（未帶入真實數字前）不含 0.2.1-W3-061 移除的偽裝偵測表述"""
    raw_template = AskUserQuestionReminders.WAVE_WRAP_UP_REMINDER

    assert "偵測到 Wave 可能已完成" not in raw_template
    assert "{status_line}" in raw_template
