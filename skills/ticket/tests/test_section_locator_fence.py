"""section_locator 的 code fence 判定：fence 內的 `## ` 行不是章節標題。

涵蓋：
- find_section 的起點與邊界都略過 fence 內的 `## ` 行（``` 與 ~~~、長 fence、未關閉 fence）
- append-log 的 H2 降級只降 fence 外的行
- append-log append / --replace 後，目標章節以外的 body 逐位元組不變
- 降級與 find_section 共用同一個 fence 判定（無平行實作）
"""

import argparse
import inspect
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands import track_acceptance
from ticket_system.commands.track_acceptance import execute_append_log
from ticket_system.lib.section_locator import (
    demote_h2_outside_fences,
    fenced_line_flags,
    find_section,
)

_LOCK_TARGET = Path(tempfile.gettempdir()) / "section_locator_fence_lock_target.md"


@pytest.fixture(autouse=True)
def _isolate_auto_commit():
    with patch("ticket_system.lib.git_utils.commit_ticket_md_reporting", return_value=False):
        yield


# ---------- fenced_line_flags ----------


def test_flags_mark_backtick_fence_including_markers():
    lines = ["a", "```bash", "## x", "```", "b"]
    assert fenced_line_flags(lines) == [False, True, True, True, False]


def test_flags_mark_tilde_fence():
    lines = ["~~~", "## x", "~~~"]
    assert fenced_line_flags(lines) == [True, True, True]


def test_flags_shorter_marker_does_not_close_longer_fence():
    lines = ["````", "```", "## x", "````", "## y"]
    assert fenced_line_flags(lines) == [True, True, True, True, False]


def test_flags_unclosed_fence_is_not_a_fence():
    """未關閉的 fence 不視為 fence，維持既有行為（避免吞掉其後所有章節）。"""
    lines = ["```", "## x", "text"]
    assert fenced_line_flags(lines) == [False, False, False]


def test_flags_mixed_markers_do_not_close_each_other():
    lines = ["```", "~~~", "## x", "```"]
    assert fenced_line_flags(lines) == [True, True, True, True]


# ---------- find_section ----------

_BODY_WITH_FENCE = (
    "## Solution\n"
    "前言\n"
    "```markdown\n"
    "## Test Results\n"
    "## 範例標題\n"
    "```\n"
    "結尾\n"
    "## Test Results\n"
    "真的測試結果\n"
)


def test_fenced_h2_does_not_end_section():
    result = find_section(_BODY_WITH_FENCE, "Solution")
    assert result.found
    assert "結尾" in result.content
    assert "真的測試結果" not in result.content


def test_fenced_h2_is_not_matched_as_section_start():
    result = find_section(_BODY_WITH_FENCE, "Test Results")
    assert result.found
    assert result.content.strip() == "真的測試結果"


def test_fenced_h2_not_listed_in_all_headers():
    result = find_section(_BODY_WITH_FENCE, "Missing")
    assert not result.found
    assert result.all_headers == ["## Solution", "## Test Results"]


def test_tilde_fence_respected():
    body = "## Solution\n~~~\n## Next\n~~~\n尾\n## Next\n下一節\n"
    result = find_section(body, "Solution")
    assert "尾" in result.content
    assert "下一節" not in result.content


def test_unclosed_fence_keeps_previous_behaviour():
    body = "## Solution\n```\n內容\n## Next\n下一節\n"
    result = find_section(body, "Solution")
    assert "下一節" not in result.content


# ---------- demote_h2_outside_fences ----------


def test_demote_skips_fence_interior():
    content = "## 外面\n```\n## 裡面\n```\n## 外面二"
    demoted, changed = demote_h2_outside_fences(content)
    assert changed
    assert demoted == "### 外面\n```\n## 裡面\n```\n### 外面二"


def test_demote_only_fenced_h2_reports_unchanged():
    content = "說明\n```\n## 裡面\n```"
    demoted, changed = demote_h2_outside_fences(content)
    assert not changed
    assert demoted == content


def test_demote_leaves_h3_and_h4():
    content = "### 三\n#### 四"
    assert demote_h2_outside_fences(content) == (content, False)


# ---------- dedupe_schema_sections ----------


def test_dedupe_ignores_schema_heading_inside_fence():
    """fence 內的 `## Solution` 不是重複章節，dedupe 不可合併或搬動它。"""
    from ticket_system.lib.ticket_builder import dedupe_schema_sections

    body = (
        "## Problem Analysis\n\n```\n## Solution\n範例\n```\n\n"
        "## Solution\n\n真方案\n"
    )
    assert dedupe_schema_sections(body) == body


# ---------- append-log 整合 ----------

_TICKET_BODY = (
    "# Execution Log\n\n"
    "## Problem Analysis\n\n"
    "分析\n"
    "```markdown\n"
    "## Solution\n"
    "（fence 內的假章節）\n"
    "```\n\n"
    "## Solution\n\n"
    "既有方案\n"
    "```\n"
    "## Test Results\n"
    "```\n"
    "方案尾\n\n"
    "## Test Results\n\n"
    "既有結果\n"
)


def _append(section: str, content: str, replace: bool, capsys):
    args = argparse.Namespace(
        ticket_id="0.31.0-W4-001",
        version="0.31.0",
        section=section,
        content=content,
        content_file=None,
        replace=replace,
        force=False,
    )
    ticket = {
        "id": args.ticket_id,
        "status": "in_progress",
        "type": "IMP",
        "_path": "/p/t.md",
        "_body": _TICKET_BODY,
    }
    with patch.object(track_acceptance, "load_ticket", return_value=ticket), \
         patch.object(track_acceptance, "get_ticket_path", return_value=_LOCK_TARGET), \
         patch.object(track_acceptance, "save_ticket") as mock_save:
        rc = execute_append_log(args, "0.31.0")
    captured = capsys.readouterr()
    assert rc == 0, captured.out + captured.err
    return mock_save.call_args[0][0]["_body"], captured


def _outside(body: str, section: str) -> tuple[str, str]:
    match = find_section(body, section)
    assert match.found
    return body[: match.start], body[match.end:]


@pytest.mark.parametrize("replace", [False, True])
def test_append_log_keeps_body_outside_target_section(replace, capsys):
    new_body, _ = _append("Solution", "### 新增\n補充", replace, capsys)
    assert _outside(new_body, "Solution") == _outside(_TICKET_BODY, "Solution")
    assert "補充" in find_section(new_body, "Solution").content


@pytest.mark.parametrize("replace", [False, True])
def test_append_log_into_section_after_fake_fenced_heading(replace, capsys):
    """Problem Analysis 的 fence 內有 `## Solution`，寫入目標不可落到 fence 裡。"""
    new_body, _ = _append("Solution", "### 新增\n補充", replace, capsys)
    pa = find_section(new_body, "Problem Analysis")
    assert "補充" not in pa.content
    assert "（fence 內的假章節）" in pa.content


def test_append_log_content_fence_kept_and_outside_h2_demoted(capsys):
    content = "## 外面\n```markdown\n## 範例\n```"
    new_body, captured = _append("Solution", content, False, capsys)
    assert "### 外面\n```markdown\n## 範例\n```" in new_body
    assert "自動降級" in captured.err


def test_append_log_content_with_only_fenced_h2_no_warning(capsys):
    content = "範例：\n```markdown\n## 範例\n```"
    new_body, captured = _append("Solution", content, False, capsys)
    assert content in new_body
    assert "自動降級" not in captured.err


def test_demotion_has_no_parallel_regex_in_append_log():
    """降級邏輯集中在 section_locator，append-log 不再自帶行首 H2 regex。"""
    source = inspect.getsource(track_acceptance._execute_append_log_locked)
    assert "demote_h2_outside_fences" in source
    assert "(?m)^## " not in source
