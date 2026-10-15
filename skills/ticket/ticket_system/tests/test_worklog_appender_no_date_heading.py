"""
worklog_appender 無日期標題處理測試（0.5.0-W1-222）

背景：日誌只有章節標題而無 `### YYYY-MM-DD` 時，舊版整段跳過，
版本工作日誌永遠不被寫入。修正後於「## 開發日誌」下建立當日標題再追加。
"""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import ticket_system.lib.worklog_appender as wa

WORKLOG_REL = "docs/work-logs/v0/v0.5/v0.5.0/v0.5.0-main.md"

NO_DATE_LOG = """# v0.5.0 版本工作日誌

---

## 前情提要

範圍說明

---

## 開發日誌
"""

NO_DEV_SECTION_LOG = """# v0.5.0 版本工作日誌

---

## 前情提要

範圍說明
"""

WITH_DATE_LOG = """# v0.5.0 版本工作日誌

## 開發日誌

### 2026-10-05

- 2026-10-05: 0.5.0-W1-001 完成 -- 既有

---
"""


def _write(root: Path, text: str) -> Path:
    path = root / WORKLOG_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _append(root: Path, ticket_id: str):
    with patch.object(wa, "get_ticket_state_root", return_value=root):
        return wa.append_worklog_progress("0.5.0", ticket_id, "標題")


def test_no_date_heading_creates_today_heading_and_appends(tmp_path):
    path = _write(tmp_path, NO_DATE_LOG)
    result = _append(tmp_path, "0.5.0-W1-100")
    today = date.today().isoformat()
    content = path.read_text(encoding="utf-8")
    assert result is not None
    assert f"### {today}\n\n- {today}: 0.5.0-W1-100 完成 -- 標題\n" in content
    assert content.index("## 開發日誌") < content.index(f"### {today}")


def test_no_date_heading_is_idempotent_and_reuses_heading(tmp_path):
    path = _write(tmp_path, NO_DATE_LOG)
    _append(tmp_path, "0.5.0-W1-100")
    assert _append(tmp_path, "0.5.0-W1-100") is None
    _append(tmp_path, "0.5.0-W1-101")
    content = path.read_text(encoding="utf-8")
    assert content.count("0.5.0-W1-100 完成") == 1
    assert content.count(f"### {date.today().isoformat()}") == 1
    assert "0.5.0-W1-101 完成" in content


def test_no_dev_section_reports_path_and_missing_structure(tmp_path, capsys):
    path = _write(tmp_path, NO_DEV_SECTION_LOG)
    assert _append(tmp_path, "0.5.0-W1-100") is None
    assert path.read_text(encoding="utf-8") == NO_DEV_SECTION_LOG
    out = capsys.readouterr().out
    assert str(path) in out and "## 開發日誌" in out


def test_existing_date_heading_behavior_unchanged(tmp_path):
    """新舊並排：已有日期標題時，仍插在最後日期區段末尾，不新增標題。"""
    path = _write(tmp_path, WITH_DATE_LOG)
    _append(tmp_path, "0.5.0-W1-100")
    today = date.today().isoformat()
    expected = WITH_DATE_LOG.replace(
        "既有\n", f"既有\n- {today}: 0.5.0-W1-100 完成 -- 標題\n"
    )
    assert path.read_text(encoding="utf-8") == expected


def test_replay_creates_heading_when_none(tmp_path):
    text = wa._build_new_date_block("2026-10-14", "- x\n")
    out = wa._replay_progress_lines(NO_DATE_LOG, text)
    assert "### 2026-10-14\n\n- x\n" in out
