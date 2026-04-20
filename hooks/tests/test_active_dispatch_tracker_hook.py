"""
Active Dispatch Tracker Hook - PostToolUse(Agent) 補 agent_id + Housekeeping 測試

W10-066 重構後，此 hook 的職責為：
1. 從 tool_response.agentId 補寫 agent_id 到 dispatch-active.json
2. Housekeeping（超時清理 + orphan 偵測）
3. 不再做 clear_dispatch、不再做 [OK]/[WAIT] 廣播（由 SubagentStop handler 負責）
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "active_dispatch_tracker_hook",
    _HOOKS_DIR / "active-dispatch-tracker-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------


class _StateFileStub:
    def exists(self) -> bool:
        return True


def _make_input(tool_use_id="tu_1", agent_id="ag_1", is_background=False):
    """建構 PostToolUse(Agent) stdin payload。"""
    return {
        "tool_use_id": tool_use_id,
        "tool_input": {
            "description": "test-agent",
            "run_in_background": is_background,
        },
        "tool_response": {
            "agentId": agent_id,
            "isAsync": is_background,
        },
    }


def _parse_additional_context(stdout_text: str):
    stdout_text = stdout_text.strip()
    if not stdout_text:
        return None
    data = json.loads(stdout_text)
    return data["hookSpecificOutput"].get("additionalContext")


# ---------------------------------------------------------------------------
# 測試：補 agent_id
# ---------------------------------------------------------------------------


def test_updates_agent_id_via_tool_response(monkeypatch, capsys):
    """PostToolUse 從 tool_response.agentId 補寫 agent_id。"""
    update_calls = []

    def _mock_update(_root, tuid, aid):
        update_calls.append((tuid, aid))
        return True

    monkeypatch.setattr(_hook, "get_state_file_path", lambda _r: _StateFileStub())
    monkeypatch.setattr(_hook, "update_dispatch_agent_id", _mock_update)
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: [])

    payload = _make_input(tool_use_id="tu_abc", agent_id="ag_xyz")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert update_calls == [("tu_abc", "ag_xyz")]


def test_no_agent_id_in_response_logs_warning(monkeypatch, capsys):
    """tool_response 無 agentId 時記 warning，不 crash。"""
    monkeypatch.setattr(_hook, "get_state_file_path", lambda _r: _StateFileStub())
    monkeypatch.setattr(_hook, "update_dispatch_agent_id", lambda *a: False)
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: [])

    payload = {
        "tool_use_id": "tu_1",
        "tool_input": {"description": "test"},
        "tool_response": {"isAsync": False},  # 無 agentId
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0


def test_update_not_found_is_normal(monkeypatch, capsys):
    """update 回傳 False（entry 已被 SubagentStop 清理）記 debug 不中斷。"""
    monkeypatch.setattr(_hook, "get_state_file_path", lambda _r: _StateFileStub())
    monkeypatch.setattr(_hook, "update_dispatch_agent_id", lambda *a: False)
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: [])

    payload = _make_input()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0


# ---------------------------------------------------------------------------
# 測試：不區分 background/前台（統一補 agent_id）
# ---------------------------------------------------------------------------


def test_background_also_updates_agent_id(monkeypatch, capsys):
    """background 派發也補 agent_id（不再跳過）。"""
    update_calls = []

    monkeypatch.setattr(_hook, "get_state_file_path", lambda _r: _StateFileStub())
    monkeypatch.setattr(_hook, "update_dispatch_agent_id", lambda _r, t, a: (update_calls.append((t, a)) or True))
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: [])

    payload = _make_input(is_background=True)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert len(update_calls) == 1


# ---------------------------------------------------------------------------
# 測試：Housekeeping
# ---------------------------------------------------------------------------


def test_housekeeping_outputs(monkeypatch, capsys):
    """超時清理和 orphan 偵測仍正常輸出。"""
    monkeypatch.setattr(_hook, "get_state_file_path", lambda _r: _StateFileStub())
    monkeypatch.setattr(_hook, "update_dispatch_agent_id", lambda *a: True)
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 3)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: ["orphan-X"])

    payload = _make_input()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    ctx = _parse_additional_context(captured.out)
    assert ctx is not None
    assert "超時" in ctx
    assert "orphan" in ctx.lower() or "orphan-X" in ctx


def test_no_broadcast_ok_or_wait(monkeypatch, capsys):
    """確認不再輸出 [OK] 或 [WAIT] 訊息。"""
    monkeypatch.setattr(_hook, "get_state_file_path", lambda _r: _StateFileStub())
    monkeypatch.setattr(_hook, "update_dispatch_agent_id", lambda *a: True)
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: [])

    payload = _make_input()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    ctx = _parse_additional_context(captured.out)
    # 無 housekeeping 訊息時不輸出
    assert ctx is None
