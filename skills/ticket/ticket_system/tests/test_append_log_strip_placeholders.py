"""append-log 寫入時逐行剝除目標章節裡的舊形態可見佔位符行。

舊版只在整章都是佔位符時才替換；章節裡只要有查重紀錄或其他實質內容，
「（選填：…）」這類行就永遠留在開頭。本測試涵蓋：
- 含查重紀錄的 Problem Analysis 寫入後不剩可見佔位符行
- 以 <!-- 開頭的行、Schema 行逐字保留
- fence 內的佔位符形式文字是範例，保留
- 同一批 fixture 票，validator 判定改前改後相同
"""

import argparse
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands import track_acceptance
from ticket_system.commands.track_acceptance import (
    _replace_or_append_section_content,
    execute_append_log,
)
from ticket_system.lib.section_locator import find_section
from ticket_system.lib.ticket_validator import validate_execution_log_by_type

_LOCK_TARGET = Path(tempfile.gettempdir()) / "strip_placeholders_lock_target.md"

_PLACEHOLDER_PREFIXES = ("（待填寫：", "（必填：", "（選填：", "（免填：")

_SCHEMA_PA = "<!-- Schema[DOC/Problem Analysis]: 選填（若 DOC 起因於缺陷或盤點結論可填）（.claude/pm-rules/ticket-body-schema.md） -->"

_PA_WITH_DEDUP = (
    "## Problem Analysis\n"
    f"{_SCHEMA_PA}\n"
    "\n"
    "### 問題根因\n"
    "\n"
    "（選填：文件變更的背景和原因）\n"
    "\n"
    "### 影響範圍\n"
    "\n"
    "（選填：哪些文件或章節受影響？）\n"
    "\n"
    "<!-- 調查過程記錄（可選）：\n"
    "（選填：這行在註解裡，不是可見佔位符）\n"
    "-->\n"
    "\n"
    "```text\n"
    "（必填：fence 內的範例）\n"
    "```\n"
    "\n"
    "### 查重紀錄\n"
    "\n"
    "`--dedup-checked none`，查重關鍵字（逐字）：\n"
    "\n"
    "- `fence`\n"
)

_BODY = (
    "# Execution Log\n\n"
    + _PA_WITH_DEDUP
    + "\n---\n\n"
    "## Solution\n"
    "<!-- Schema[DOC/Solution]: 必填（.claude/pm-rules/ticket-body-schema.md） -->\n\n"
    "既有方案\n\n"
    "（待填寫：舊票殘留）\n\n"
    "---\n\n"
    "## Test Results\n"
    "<!-- Schema[DOC/Test Results]: 選填（.claude/pm-rules/ticket-body-schema.md） -->\n\n"
    "（選填：測試執行指令）\n"
)


@pytest.fixture(autouse=True)
def _isolate_auto_commit():
    with patch("ticket_system.lib.git_utils.commit_ticket_md_reporting", return_value=False):
        yield


def _append(body: str, section: str, content: str) -> str:
    args = argparse.Namespace(
        ticket_id="0.31.0-W4-001",
        version="0.31.0",
        section=section,
        content=content,
        content_file=None,
        replace=False,
        force=False,
    )
    ticket = {"id": args.ticket_id, "status": "in_progress", "type": "DOC",
              "_path": "/p/t.md", "_body": body}
    with patch.object(track_acceptance, "load_ticket", return_value=ticket), \
         patch.object(track_acceptance, "get_ticket_path", return_value=_LOCK_TARGET), \
         patch.object(track_acceptance, "save_ticket") as mock_save:
        assert execute_append_log(args, "0.31.0") == 0
    return mock_save.call_args[0][0]["_body"]


def _visible_placeholder_lines(text: str) -> list[str]:
    return [line for line in text.split("\n") if line.startswith(_PLACEHOLDER_PREFIXES)]


def test_problem_analysis_with_dedup_record_drops_visible_placeholders():
    new_body = _append(_BODY, "Problem Analysis", "### 補充\n實際分析")
    pa = find_section(new_body, "Problem Analysis").text
    # 剩下的兩行都受保護：一行在 HTML 註解內，一行在 fence 內（範例）
    assert _visible_placeholder_lines(pa) == [
        "（選填：這行在註解裡，不是可見佔位符）",
        "（必填：fence 內的範例）",
    ]
    assert "實際分析" in pa
    assert "- `fence`" in pa


def test_html_comment_lines_kept_verbatim():
    new_body = _append(_BODY, "Problem Analysis", "### 補充\n實際分析")
    before = [l for l in _BODY.split("\n") if l.startswith("<!--")]
    after = [l for l in new_body.split("\n") if l.startswith("<!--")]
    assert after == before
    assert "（選填：這行在註解裡，不是可見佔位符）" in new_body


def test_schema_lines_identical():
    new_body = _append(_BODY, "Problem Analysis", "### 補充\n實際分析")
    def schema_lines(text):
        return [l for l in text.split("\n") if "Schema[" in l]
    assert schema_lines(new_body) == schema_lines(_BODY)


def test_other_sections_untouched():
    new_body = _append(_BODY, "Problem Analysis", "### 補充\n實際分析")
    for name in ("Solution", "Test Results"):
        assert find_section(new_body, name).text == find_section(_BODY, name).text


def test_no_triple_blank_lines_left_behind():
    new_body = _append(_BODY, "Problem Analysis", "### 補充\n實際分析")
    assert "\n\n\n" not in find_section(new_body, "Problem Analysis").text


def test_section_without_placeholders_unchanged_before_new_entry():
    section = "## Solution\n\n既有方案\n"
    result = _replace_or_append_section_content(
        section_text=section, section_content=section[len("## Solution"):],
        new_entry="\n新增",
    )
    assert result == section + "\n新增"


_FIXTURES = [
    ("DOC", _BODY, "Problem Analysis"),
    ("DOC", _BODY, "Solution"),
    ("IMP", _BODY.replace("DOC/", "IMP/"), "Solution"),
    ("ANA", _BODY.replace("DOC/", "ANA/"), "Problem Analysis"),
]


@pytest.mark.parametrize(
    "ticket_type,body,section", _FIXTURES,
    ids=[f"{t}-{s}" for t, _, s in _FIXTURES],
)
def test_validator_verdict_unchanged(ticket_type, body, section):
    """改前（整章 append、不剝佔位符）與改後的 body，validator 判定相同。"""
    entry = "\n### 補充\n實際內容"
    match = find_section(body, section)
    old_body = body[: match.start] + match.text + entry + body[match.end:]
    new_section = _replace_or_append_section_content(
        section_text=match.text, section_content=match.content, new_entry=entry,
    )
    new_body = body[: match.start] + new_section + body[match.end:]
    assert new_body != old_body
    assert validate_execution_log_by_type(ticket_type, new_body) == \
        validate_execution_log_by_type(ticket_type, old_body)
