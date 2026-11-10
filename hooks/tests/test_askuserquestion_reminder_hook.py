"""
AskUserQuestion Reminder Hook 測試（1.5.0-W5-002.1 回歸測試）

背景：CC subagent 派發工具表面名已由 Task 改為 Agent（見 1.5.0-W5-002 分析）。
main() 內部曾以 `tool_name != "Task"` 字面守衛在任何實質邏輯前早退，
導致多任務派發提醒對 Agent 派發從未實際觸發（功能性死亡）。

驗收：
- tool_name="Agent" 且 prompt 含 2+ Ticket ID 應輸出提醒（additionalContext）
- tool_name="Task" 既有行為不得 regression
- 非 Agent/Task 工具仍在守衛早退，不輸出提醒
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "askuserquestion_reminder_hook",
    _HOOKS_DIR / "askuserquestion-reminder-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

main = _hook.main


def _run_hook(monkeypatch, tool_name: str, prompt: str) -> dict:
    """以 monkeypatch 模擬 stdin 輸入並執行 main()，回傳解析後的 stdout JSON。"""
    payload = {"tool_name": tool_name, "tool_input": {"prompt": prompt}}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    exit_code = main()
    return exit_code


def test_agent_tool_name_with_multiple_ticket_ids_triggers_reminder(monkeypatch, capsys):
    """tool_name="Agent" 且 prompt 含 2+ Ticket ID 應輸出提醒（守衛不得早退）。"""
    prompt = "處理 1.5.0-W5-001 與 1.5.0-W5-002 兩個 Ticket"
    exit_code = _run_hook(monkeypatch, "Agent", prompt)
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert exit_code == 0
    assert "additionalContext" in output["hookSpecificOutput"]


def test_task_tool_name_with_multiple_ticket_ids_still_triggers_reminder(monkeypatch, capsys):
    """既有 tool_name="Task" 行為不得 regression。"""
    prompt = "處理 1.5.0-W5-001 與 1.5.0-W5-002 兩個 Ticket"
    exit_code = _run_hook(monkeypatch, "Task", prompt)
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert exit_code == 0
    assert "additionalContext" in output["hookSpecificOutput"]


def test_unrelated_tool_name_skips_without_reminder(monkeypatch, capsys):
    """非 Agent/Task 工具仍在守衛早退，不含提醒。"""
    prompt = "處理 1.5.0-W5-001 與 1.5.0-W5-002 兩個 Ticket"
    exit_code = _run_hook(monkeypatch, "Bash", prompt)
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert exit_code == 0
    assert "additionalContext" not in output["hookSpecificOutput"]


def test_agent_tool_name_with_single_ticket_id_no_reminder(monkeypatch, capsys):
    """tool_name="Agent" 但只有 1 個 Ticket ID，不輸出提醒。"""
    prompt = "處理 1.5.0-W5-001 這個 Ticket"
    exit_code = _run_hook(monkeypatch, "Agent", prompt)
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert exit_code == 0
    assert "additionalContext" not in output["hookSpecificOutput"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
