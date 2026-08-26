"""
Active Dispatch Tracker Hook - PostToolUse(Agent) 派發記錄 + Housekeeping 測試

幽靈派發記錄修復票後，此 hook 的職責為：
1. 記錄派發到 dispatch-active.json（含 agent_id，取代原 dispatch-record-hook.py
   的 PreToolUse 寫入 + 原 update_dispatch_agent_id 的補寫兩步）
2. Housekeeping（超時清理 + orphan 偵測）
3. 不再做 clear_dispatch、不再做 [OK]/[WAIT] 廣播（由 SubagentStop handler 負責）

背景：見 active-dispatch-tracker-hook.py 頂部 docstring（PreToolUse deny
彙總導致幽靈記錄，比照 who.current 綁定遷移票的先例移至 PostToolUse）。
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


def _make_input(
    tool_use_id="tu_1",
    agent_id="ag_1",
    is_background=False,
    description="test-agent",
    isolation="",
    prompt="",
):
    """建構 PostToolUse(Agent) stdin payload。"""
    return {
        "tool_use_id": tool_use_id,
        "tool_input": {
            "description": description,
            "isolation": isolation,
            "prompt": prompt,
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


def _patch_common(monkeypatch, record_calls=None, where_files=None):
    """套用共同 monkeypatch：is_subagent_environment / get_project_root /
    record_dispatch / cleanup_expired / detect_orphan_branches / extract_where_files。
    """
    monkeypatch.setattr(_hook, "is_subagent_environment", lambda _d: False)
    monkeypatch.setattr(_hook, "get_project_root", lambda: Path("."))
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: [])
    monkeypatch.setattr(
        _hook, "extract_where_files", lambda *a, **k: where_files or []
    )

    if record_calls is not None:

        def _mock_record(**kwargs):
            record_calls.append(kwargs)

        monkeypatch.setattr(_hook, "record_dispatch", _mock_record)


# ---------------------------------------------------------------------------
# 測試：記錄派發（含 agent_id）
# ---------------------------------------------------------------------------


def test_records_dispatch_with_agent_id(monkeypatch, capsys):
    """PostToolUse 呼叫 record_dispatch，agent_id 取自 tool_response.agentId。"""
    record_calls = []
    _patch_common(monkeypatch, record_calls=record_calls)

    payload = _make_input(tool_use_id="tu_abc", agent_id="ag_xyz")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert len(record_calls) == 1
    kwargs = record_calls[0]
    assert kwargs["tool_use_id"] == "tu_abc"
    assert kwargs["agent_id"] == "ag_xyz"
    assert kwargs["agent_description"] == "test-agent"


def test_no_agent_id_in_response_still_records(monkeypatch, capsys):
    """tool_response 無 agentId 時記 warning，但仍記錄（agent_id=None）。"""
    record_calls = []
    _patch_common(monkeypatch, record_calls=record_calls)

    payload = {
        "tool_use_id": "tu_1",
        "tool_input": {"description": "test", "isolation": ""},
        "tool_response": {"isAsync": False},  # 無 agentId
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert record_calls[0]["agent_id"] is None


def test_worktree_isolation_sets_branch_name(monkeypatch):
    record_calls = []
    _patch_common(monkeypatch, record_calls=record_calls)

    payload = _make_input(isolation="worktree", description="worktree 派發")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert record_calls[0]["branch_name"] == "worktree"


def test_ticket_id_extracted_from_prompt_and_files_looked_up(monkeypatch):
    record_calls = []
    _patch_common(
        monkeypatch, record_calls=record_calls, where_files=[".claude/hooks/"]
    )

    payload = _make_input(prompt="0.2.1-W3-547 依規格實作")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert record_calls[0]["ticket_id"] == "0.2.1-W3-547"
    assert record_calls[0]["files"] == [".claude/hooks/"]


def test_no_ticket_id_skips_where_files_lookup(monkeypatch):
    record_calls = []
    where_files_calls = []
    _patch_common(monkeypatch, record_calls=record_calls)
    monkeypatch.setattr(
        _hook,
        "extract_where_files",
        lambda *a, **k: where_files_calls.append(1) or [],
    )

    payload = _make_input(prompt="沒有 id")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert where_files_calls == []
    assert record_calls[0]["ticket_id"] == ""
    assert record_calls[0]["files"] == []


def test_subagent_environment_skips_recording(monkeypatch):
    record_calls = []
    monkeypatch.setattr(_hook, "is_subagent_environment", lambda _d: True)
    monkeypatch.setattr(_hook, "get_project_root", lambda: Path("."))
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: [])

    def _mock_record(**kwargs):
        record_calls.append(kwargs)

    monkeypatch.setattr(_hook, "record_dispatch", _mock_record)

    payload = _make_input()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert record_calls == []


def test_record_dispatch_failure_does_not_block(monkeypatch):
    """record_dispatch 拋例外不阻擋（housekeeping 仍執行、exit 仍為 0）。"""
    monkeypatch.setattr(_hook, "is_subagent_environment", lambda _d: False)
    monkeypatch.setattr(_hook, "get_project_root", lambda: Path("."))
    monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: [])

    def _boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(_hook, "record_dispatch", _boom)

    payload = _make_input()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert _hook.main() == 0


# ---------------------------------------------------------------------------
# 測試：不區分 background/前台（統一記錄）
# ---------------------------------------------------------------------------


def test_background_also_records(monkeypatch):
    """background 派發也記錄（不再跳過）。"""
    record_calls = []
    _patch_common(monkeypatch, record_calls=record_calls)

    payload = _make_input(is_background=True)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    assert exit_code == 0
    assert len(record_calls) == 1


# ---------------------------------------------------------------------------
# 測試：Housekeeping
# ---------------------------------------------------------------------------


def test_housekeeping_outputs(monkeypatch, capsys):
    """超時清理和 orphan 偵測仍正常輸出。"""
    record_calls = []
    _patch_common(monkeypatch, record_calls=record_calls)
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
    record_calls = []
    _patch_common(monkeypatch, record_calls=record_calls)

    payload = _make_input()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = _hook.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    ctx = _parse_additional_context(captured.out)
    # 無 housekeeping 訊息時不輸出
    assert ctx is None


def test_uses_git_utils_get_project_root_for_dispatch_write():
    """dispatch-active.json 為跨 worktree 全域狀態，本 hook 的
    get_project_root 必須來自 lib.git_utils（CLAUDE_PROJECT_DIR 導向，
    恆指主 repo），而非 lib.hook_base 的 worktree 感知版本
    （0.2.1-W3-1093 / ARCH-BAL-020）。"""
    from lib import git_utils

    assert _hook.get_project_root is git_utils.get_project_root
