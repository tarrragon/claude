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
    """非 Agent/Task 工具仍在守衛早退，不輸出任何 JSON（不提醒、不代為放行）。"""
    prompt = "處理 1.5.0-W5-001 與 1.5.0-W5-002 兩個 Ticket"
    exit_code = _run_hook(monkeypatch, "Bash", prompt)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == ""


def test_agent_tool_name_with_single_ticket_id_no_reminder(monkeypatch, capsys):
    """tool_name="Agent" 但只有 1 個 Ticket ID，不輸出任何 JSON。"""
    prompt = "處理 1.5.0-W5-001 這個 Ticket"
    exit_code = _run_hook(monkeypatch, "Agent", prompt)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == ""


# ---------------------------------------------------------------------------
# 3.2.0-W1-029：提醒類 hook 不得輸出 permissionDecision（不代用戶作權限決定）
# ---------------------------------------------------------------------------

def _assert_no_permission_decision(stdout: str) -> None:
    """stdout 為空或為不含 permissionDecision 的 JSON 才通過。"""
    if not stdout.strip():
        return
    output = json.loads(stdout)
    assert "permissionDecision" not in output.get("hookSpecificOutput", {})


def test_reminder_path_has_no_permission_decision(monkeypatch, capsys):
    """提醒路徑只帶 additionalContext，不帶 permissionDecision。"""
    _run_hook(monkeypatch, "Agent", "處理 1.5.0-W5-001 與 1.5.0-W5-002")
    _assert_no_permission_decision(capsys.readouterr().out)


def test_subagent_path_has_no_permission_decision(monkeypatch, capsys):
    """subagent 略過路徑不輸出 permissionDecision。"""
    payload = {"agent_id": "a1", "tool_name": "Agent",
               "tool_input": {"prompt": "處理 1.5.0-W5-001 與 1.5.0-W5-002"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert main() == 0
    _assert_no_permission_decision(capsys.readouterr().out)


def test_exception_path_has_no_permission_decision(monkeypatch, capsys):
    """異常路徑不代為放行：不輸出 permissionDecision，exit 0 不阻擋。"""
    def _boom(_logger):
        raise RuntimeError("boom")
    monkeypatch.setattr(_hook, "read_json_from_stdin", _boom)
    assert main() == 0
    _assert_no_permission_decision(capsys.readouterr().out)


def test_assertion_rejects_legacy_allow_output():
    """正向對照（E2）：舊版輸出含 permissionDecision allow 時，斷言必須失敗。"""
    import pytest
    legacy = json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "allow"}})
    with pytest.raises(AssertionError):
        _assert_no_permission_decision(legacy)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
