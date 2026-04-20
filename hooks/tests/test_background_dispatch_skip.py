"""
W10-060: PostToolUse(Agent) 背景派發時機修正測試

對應 Ticket 0.18.0-W10-060 Acceptance:
- is_background_dispatch helper 正確判斷 run_in_background
- agent-commit-verification-hook 在 background 派發時跳過完成判定檢查
- agent-dispatch-logger-hook 在 background 派發時跳過日誌記錄

參考：W10-024 (active-dispatch-tracker-hook) 修復模板。
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


def _load_hook(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(
        module_name, _HOOKS_DIR / file_name
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# is_background_dispatch helper 測試
# ---------------------------------------------------------------------------


def test_is_background_dispatch_helper():
    """helper 正確偵測 run_in_background=true。"""
    from hook_utils import is_background_dispatch

    assert is_background_dispatch({"run_in_background": True}) is True
    assert is_background_dispatch({"run_in_background": False}) is False
    assert is_background_dispatch({}) is False
    assert is_background_dispatch(None) is False
    # 其他 truthy 值視為 True（寬鬆處理）
    assert is_background_dispatch({"run_in_background": 1}) is True


# ---------------------------------------------------------------------------
# agent-commit-verification-hook 背景派發跳過測試
# ---------------------------------------------------------------------------


def test_agent_commit_verification_skips_background_dispatch(monkeypatch, capsys):
    """background 派發時輸出 DEFAULT_OUTPUT，不執行代理人完成檢查（uncommitted/worktree/branch）。"""
    hook = _load_hook(
        "agent_commit_verification_hook", "agent-commit-verification-hook.py"
    )

    # 攔截 hook 內部的檢查函式（非底層 subprocess，避免與 setup_hook_logging 衝突）
    check_calls = []
    monkeypatch.setattr(
        hook, "get_uncommitted_files",
        lambda *a, **kw: check_calls.append("uncommitted") or [],
    )
    monkeypatch.setattr(
        hook, "get_unmerged_worktrees",
        lambda *a, **kw: check_calls.append("worktrees") or [],
    )
    monkeypatch.setattr(
        hook, "get_unmerged_feature_branches",
        lambda *a, **kw: check_calls.append("branches") or [],
    )
    monkeypatch.setattr(
        hook, "scan_hook_errors",
        lambda *a, **kw: check_calls.append("hook_errors") or [],
    )

    payload = {
        "tool_input": {
            "description": "bg-agent",
            "run_in_background": True,
            "prompt": "some prompt",
        }
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as excinfo:
        hook.main()

    assert excinfo.value.code == 0
    # 完全未執行任何完成檢查
    assert check_calls == []

    captured = capsys.readouterr()
    out = json.loads(captured.out.strip())
    assert out == hook.DEFAULT_OUTPUT


def test_agent_commit_verification_still_runs_for_foreground(monkeypatch, capsys):
    """foreground 派發仍執行完整檢查邏輯（未跳過）。"""
    hook = _load_hook(
        "agent_commit_verification_hook_fg", "agent-commit-verification-hook.py"
    )

    check_calls = []
    monkeypatch.setattr(
        hook, "get_uncommitted_files",
        lambda *a, **kw: check_calls.append("uncommitted") or [],
    )
    monkeypatch.setattr(
        hook, "get_unmerged_worktrees",
        lambda *a, **kw: check_calls.append("worktrees") or [],
    )
    monkeypatch.setattr(
        hook, "get_unmerged_feature_branches",
        lambda *a, **kw: check_calls.append("branches") or [],
    )
    monkeypatch.setattr(hook, "scan_hook_errors", lambda *_a, **_kw: [])

    payload = {
        "tool_input": {
            "description": "fg-agent",
            # 明確未設定 run_in_background
        }
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as excinfo:
        hook.main()

    assert excinfo.value.code == 0
    # foreground 會執行所有完成判定檢查
    assert "uncommitted" in check_calls
    assert "worktrees" in check_calls
    assert "branches" in check_calls


# ---------------------------------------------------------------------------
# agent-dispatch-logger-hook 背景派發跳過測試
# ---------------------------------------------------------------------------


def test_agent_dispatch_logger_skips_background_dispatch(monkeypatch, capsys, tmp_path):
    """background 派發時不寫入 JSONL（response 尚未產生）。"""
    hook = _load_hook(
        "agent_dispatch_logger_hook", "agent-dispatch-logger-hook.py"
    )

    write_calls = []
    monkeypatch.setattr(
        hook, "write_log_entry", lambda *a, **kw: write_calls.append(a)
    )
    monkeypatch.setattr(hook, "get_project_root", lambda: str(tmp_path))

    payload = {
        "tool_input": {
            "description": "bg-logger",
            "run_in_background": True,
            "prompt": "ticket 0.18.0-W10-060",
        }
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as excinfo:
        hook.main()

    assert excinfo.value.code == 0
    assert write_calls == []

    captured = capsys.readouterr()
    out = json.loads(captured.out.strip())
    assert out == hook.DEFAULT_OUTPUT


def test_agent_dispatch_logger_still_logs_for_foreground(monkeypatch, capsys, tmp_path):
    """foreground 派發仍寫入 JSONL。"""
    hook = _load_hook(
        "agent_dispatch_logger_hook_fg", "agent-dispatch-logger-hook.py"
    )

    write_calls = []
    monkeypatch.setattr(
        hook, "write_log_entry", lambda path, entry: write_calls.append(entry)
    )
    monkeypatch.setattr(hook, "get_project_root", lambda: str(tmp_path))

    payload = {
        "tool_input": {
            "description": "fg-logger",
            "prompt": "ticket 0.18.0-W10-060 foreground",
        },
        "tool_response": {"result": "some result text"},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as excinfo:
        hook.main()

    assert excinfo.value.code == 0
    assert len(write_calls) == 1
    entry = write_calls[0]
    assert entry["agent_description"] == "fg-logger"
    assert entry["ticket_id"] == "0.18.0-W10-060"


# ---------------------------------------------------------------------------
# dispatch-count-guard-hook 背景派發保持計數（語意備註驗證）
# ---------------------------------------------------------------------------


def test_dispatch_count_guard_counts_background_dispatch(monkeypatch, tmp_path):
    """background 派發時 counter 仍遞增（語意：計「已派發」非「已完成」）。"""
    hook = _load_hook(
        "dispatch_count_guard_hook", "dispatch-count-guard-hook.py"
    )

    # 隔離狀態檔到 tmp_path
    state_file = tmp_path / "batch-state.json"
    monkeypatch.setattr(hook, "get_batch_state_file", lambda: state_file)

    payload = {
        "hookEventName": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {
            "description": "多視角分析 agent",
            "prompt": "請使用三人組多視角分析這個問題",
            "run_in_background": True,
        },
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    exit_code = hook.main()
    assert exit_code == 0

    # 狀態檔應被建立，actual=1
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["actual"] == 1
    assert state["expected"] >= 2  # 多視角 / 三人組 至少 2
