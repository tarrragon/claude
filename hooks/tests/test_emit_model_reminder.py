"""emit_model_reminder 六事件輸出形狀測試（0.5.0-W1-306.2）。

emit_model_reminder 是 emit_hook_output 的薄包裝；本測試驗證六事件皆輸出
hookSpecificOutput.additionalContext JSON（模型可見管道），且 Pre/Post 類
事件不輸出純文字 stdout（對照組），並確認受眾過濾仍只由 emit_hook_output 承擔。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from lib import hook_io  # noqa: E402

SIX_EVENTS = [
    "UserPromptSubmit",
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
]
TOOL_EVENTS = ["PreToolUse", "PostToolUse", "PostToolUseFailure"]


@pytest.mark.parametrize("event", SIX_EVENTS)
def test_six_events_emit_additional_context_json(event, capsys):
    hook_io.emit_model_reminder(event, "提醒內容")
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data == {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": "提醒內容",
        }
    }


@pytest.mark.parametrize("event", TOOL_EVENTS)
def test_tool_events_stdout_is_json_not_plain_text(event, capsys):
    hook_io.emit_model_reminder(event, "提醒內容")
    out = capsys.readouterr().out.strip()
    # 對照組：不得是純文字 stdout；整段必須可解析為 JSON object
    assert out.startswith("{")
    assert isinstance(json.loads(out), dict)
    assert out != "提醒內容"


def test_unknown_event_raises(capsys):
    with pytest.raises(ValueError):
        hook_io.emit_model_reminder("PreToolUs", "x")
    assert capsys.readouterr().out == ""


def test_matches_emit_hook_output_byte_for_byte(capsys):
    hook_io.emit_model_reminder("Stop", "t")
    a = capsys.readouterr().out
    hook_io.emit_hook_output("Stop", "t")
    b = capsys.readouterr().out
    assert a == b


def test_pm_only_delegates_filtering(capsys):
    hook_io.emit_model_reminder(
        "PostToolUse", "t", audience="pm_only", input_data={"agent_id": "a1"}
    )
    sub = json.loads(capsys.readouterr().out)
    assert "additionalContext" not in sub["hookSpecificOutput"]
    hook_io.emit_model_reminder(
        "PostToolUse", "t", audience="pm_only", input_data={}
    )
    pm = json.loads(capsys.readouterr().out)
    assert pm["hookSpecificOutput"]["additionalContext"] == hook_io.PM_ONLY_PREFIX + "t"


def test_exported_from_lib_package():
    import lib

    assert lib.emit_model_reminder is hook_io.emit_model_reminder
