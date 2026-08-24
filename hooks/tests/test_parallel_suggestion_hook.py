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
    # 註：parse_ticket_frontmatter() 已改用 yaml.safe_load（0.2.1-W3-665.2），
    # 純量依 YAML 規範原生推斷型別，故 wave 欄位值為 int 3 而非字串 "3"。
    assert info["wave"] == 3


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


# ============================================================================
# find_parallelizable_tickets()：seed_tickets（在飛票）納入衝突判定
# ============================================================================


def _make_ticket(ticket_id, files, blocked_by=""):
    return {
        "id": ticket_id,
        "path": Path(f"/tmp/{ticket_id}.md"),
        "status": "pending",
        "type": "IMP",
        "priority": "P1",
        "title": ticket_id,
        "blockedBy": blocked_by,
        "where_files": files,
        "where_layer": "",
        "chain": {},
        "wave": 3,
    }


def test_find_parallelizable_tickets_excludes_conflict_with_seed(logger):
    """在飛票（seed）存在時，並行建議不含與其檔案重疊的候選票"""
    pending = [
        _make_ticket("A", "lib/a.dart"),
        _make_ticket("B", "lib/b.dart"),
    ]
    seed = [_make_ticket("SEED", "lib/a.dart")]
    # SEED 本身狀態應為 in_progress，_make_ticket 預設 pending，這裡覆寫
    seed[0]["status"] = "in_progress"

    groups = parallel_suggestion_hook.find_parallelizable_tickets(
        pending, logger, seed_tickets=seed
    )

    # A 與在飛票 SEED 檔案重疊被排除，僅剩 B 一個候選（< 2 無法成組）
    assert groups == []


def test_find_parallelizable_tickets_seed_not_in_output_group(logger):
    """seed 本身不出現於回傳分組，僅作為排除依據"""
    pending = [
        _make_ticket("A", "lib/a.dart"),
        _make_ticket("B", "lib/b.dart"),
        _make_ticket("C", "lib/c.dart"),
    ]
    seed = [_make_ticket("SEED", "lib/a.dart")]
    seed[0]["status"] = "in_progress"

    groups = parallel_suggestion_hook.find_parallelizable_tickets(
        pending, logger, seed_tickets=seed
    )

    assert groups, "B 與 C 檔案無重疊，且皆與 seed 無重疊，應可並行"
    all_ids = {t["id"] for group in groups for t in group}
    assert "SEED" not in all_ids
    assert "A" not in all_ids
    assert {"B", "C"} <= all_ids


def test_find_parallelizable_tickets_no_seed_unaffected(logger):
    """無 seed_tickets（預設 None）時行為與既有邏輯一致"""
    pending = [
        _make_ticket("A", "lib/a.dart"),
        _make_ticket("B", "lib/b.dart"),
    ]

    groups = parallel_suggestion_hook.find_parallelizable_tickets(pending, logger)

    assert len(groups) == 1
    assert {t["id"] for t in groups[0]} == {"A", "B"}


# ============================================================================
# where.files 讀寫意圖判定改 import ticket_system 共用實作
# ============================================================================


def test_filter_write_files_uses_shared_parse_file_intent():
    """驗證 _filter_write_files 透過共用 parse_file_intent 正確過濾 ::read 標記"""
    files = {"lib/a.dart::read", "lib/b.dart::write", "lib/c.dart"}
    ticket_info = {"type": "IMP"}

    result = parallel_suggestion_hook._filter_write_files(files, ticket_info)

    assert result == {"lib/b.dart", "lib/c.dart"}


def test_filter_write_files_ana_default_read():
    """驗證 ANA 型別未標記路徑預設 read，故被過濾（同 file_conflict._default_intent）"""
    files = {"lib/a.dart", "lib/b.dart::write"}
    ticket_info = {"type": "ANA"}

    result = parallel_suggestion_hook._filter_write_files(files, ticket_info)

    assert result == {"lib/b.dart"}


# ============================================================================
# extract_ticket_files()：現行巢狀 where.files schema（0.2.1-W3-883）
#
# 修復前 extract_ticket_files 僅讀平面鍵 frontmatter["where_files"]，現行
# schema 為巢狀 where: {files: [...]}，平面鍵恆為空，優先路徑永遠落入
# extract_ticket_info() 從未寫入巢狀 where 的舊行為，故此處同時涵蓋
# extract_ticket_info() 是否正確保留巢狀 dict，以及 extract_ticket_files()
# 是否優先採用巢狀路徑。
# ============================================================================


def test_extract_ticket_info_preserves_nested_where_dict(tmp_path, logger):
    """驗證 extract_ticket_info() 回傳 dict 保留巢狀 where.files（非空平面鍵）"""
    ticket_file = tmp_path / "0.2.1-W3-996.md"
    ticket_file.write_text(
        "---\nid: 0.2.1-W3-996\nstatus: pending\nwhere:\n  files:\n"
        "  - lib/a.dart\n  - lib/b.dart\n---\nContent",
        encoding="utf-8",
    )

    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    assert info["where"] == {"files": ["lib/a.dart", "lib/b.dart"]}
    # 平面鍵在現行 schema 下恆為空字串（未提供 frontmatter["where_files"]）
    assert info["where_files"] == ""


def test_extract_ticket_files_reads_nested_where_files(tmp_path, logger):
    """驗證 extract_ticket_files() 對現行巢狀 where.files schema 正確抽取寫入檔案集合"""
    ticket_file = tmp_path / "0.2.1-W3-995.md"
    ticket_file.write_text(
        "---\nid: 0.2.1-W3-995\nstatus: pending\ntype: IMP\nwhere:\n  files:\n"
        "  - lib/a.dart\n  - lib/b.dart\n---\nContent",
        encoding="utf-8",
    )
    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    files = parallel_suggestion_hook.extract_ticket_files(info, logger)

    assert files == {"lib/a.dart", "lib/b.dart"}


def test_extract_ticket_files_nested_where_respects_read_intent(tmp_path, logger):
    """驗證巢狀 where.files 路徑仍套用讀寫意圖標記（::read 排除、ANA 預設 read）"""
    ticket_file = tmp_path / "0.2.1-W3-994.md"
    ticket_file.write_text(
        "---\nid: 0.2.1-W3-994\nstatus: pending\ntype: ANA\nwhere:\n  files:\n"
        "  - lib/a.dart\n  - lib/b.dart::write\n---\nContent",
        encoding="utf-8",
    )
    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    files = parallel_suggestion_hook.extract_ticket_files(info, logger)

    # ANA 型別未標記路徑預設 read 被過濾，僅保留逐檔標記 ::write 的路徑
    assert files == {"lib/b.dart"}
