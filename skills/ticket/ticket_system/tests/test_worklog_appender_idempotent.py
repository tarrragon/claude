"""
worklog_appender 冪等性測試（0.31.1-W8-048）

驗證 append_worklog_progress 對同一 ticket_id 重複呼叫時不產生重複行。

背景：complete metadata-sync 觀察到 worklog 被重複 append 同一 ticket 的完成記錄
（W1-001.1/.2 已累積 8 份重複）。根因為 append_worklog_progress 無 dedup，
任一呼叫端重複呼叫即產生重複行。冪等化此函式即可從源頭杜絕重複。
"""

from pathlib import Path
from unittest.mock import patch

import ticket_system.lib.worklog_appender as wa

WORKLOG_REL = "docs/work-logs/v0/v0.31/v0.31.1/v0.31.1-main.md"

WORKLOG_TEMPLATE = """# v0.31.1 main worklog

### 2026-06-08

- 2026-06-08: 0.31.1-W8-040 完成 -- 既有記錄

---
"""


def _setup_worklog(root: Path) -> Path:
    worklog = root / WORKLOG_REL
    worklog.parent.mkdir(parents=True, exist_ok=True)
    worklog.write_text(WORKLOG_TEMPLATE, encoding="utf-8")
    return worklog


def _count_lines_for(worklog: Path, ticket_id: str) -> int:
    content = worklog.read_text(encoding="utf-8")
    return sum(
        1 for line in content.splitlines() if f"{ticket_id} 完成" in line
    )


def test_double_call_same_ticket_appends_only_once(tmp_path):
    """對同一 ticket_id 連續呼叫兩次 → worklog 只有一行（冪等）。"""
    worklog = _setup_worklog(tmp_path)

    with patch.object(wa, "get_project_root", return_value=tmp_path):
        wa.append_worklog_progress("0.31.1", "0.31.1-W8-099", "first call")
        wa.append_worklog_progress("0.31.1", "0.31.1-W8-099", "second call")

    assert _count_lines_for(worklog, "0.31.1-W8-099") == 1


def test_empty_title_double_call_appends_only_once(tmp_path):
    """空 title 的重複呼叫（重現 W1-001.1/.2 症狀）同樣只保留一行。"""
    worklog = _setup_worklog(tmp_path)

    with patch.object(wa, "get_project_root", return_value=tmp_path):
        wa.append_worklog_progress("0.31.1", "0.31.1-W1-001.1", "")
        wa.append_worklog_progress("0.31.1", "0.31.1-W1-001.1", "")

    assert _count_lines_for(worklog, "0.31.1-W1-001.1") == 1


def test_distinct_tickets_each_append_once(tmp_path):
    """不同 ticket_id 各自正常 append，冪等不影響正常記錄。"""
    worklog = _setup_worklog(tmp_path)

    with patch.object(wa, "get_project_root", return_value=tmp_path):
        wa.append_worklog_progress("0.31.1", "0.31.1-W8-099", "t1")
        wa.append_worklog_progress("0.31.1", "0.31.1-W8-100", "t2")

    assert _count_lines_for(worklog, "0.31.1-W8-099") == 1
    assert _count_lines_for(worklog, "0.31.1-W8-100") == 1


def test_existing_record_blocks_reappend(tmp_path):
    """worklog 既有該 ticket 的完成行時，後續呼叫 skip（同日期區段內）。"""
    worklog = _setup_worklog(tmp_path)
    # 預先植入一筆完成記錄（模擬先前 complete 已寫入）
    content = worklog.read_text(encoding="utf-8").replace(
        "- 2026-06-08: 0.31.1-W8-040 完成 -- 既有記錄\n",
        "- 2026-06-08: 0.31.1-W8-040 完成 -- 既有記錄\n"
        "- 2026-06-08: 0.31.1-W8-099 完成 -- 已存在\n",
    )
    worklog.write_text(content, encoding="utf-8")

    with patch.object(wa, "get_project_root", return_value=tmp_path):
        wa.append_worklog_progress("0.31.1", "0.31.1-W8-099", "重複嘗試")

    assert _count_lines_for(worklog, "0.31.1-W8-099") == 1
