"""5 支 hook 的 session 狀態鍵測試：鍵取自 hook 輸入的 session_id，不用 ppid。

以獨立子程序呼叫 hook（與 runtime 相同：每次呼叫是不同程序），驗證跨程序狀態延續。
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[2]
GUARD = CLAUDE_DIR / "hooks" / "session-context-guard-hook.py"
DISPATCH = CLAUDE_DIR / "hooks" / "dispatch-count-guard-hook.py"
LIFECYCLE = CLAUDE_DIR / "skills" / "ticket" / "hooks" / "post-ticket-lifecycle-hook.py"
REMINDER = CLAUDE_DIR / "skills" / "ticket" / "hooks" / "handoff-prompt-reminder-hook.py"
SESSION_MGMT_DIR = CLAUDE_DIR / "skills" / "ticket" / "hooks"

SID_A = "pytest-sid-a-278"
SID_B = "pytest-sid-b-278"
COUNTER = "/tmp/claude-session-completed-tickets-%s"
BATCH = "/tmp/claude-dispatch-batch-%s.json"


@pytest.fixture(autouse=True)
def _clean_state():
    def wipe():
        for sid in (SID_A, SID_B):
            Path(COUNTER % sid).unlink(missing_ok=True)
            Path(BATCH % sid).unlink(missing_ok=True)
            Path("/tmp/claude-handoff-reminded-%s" % sid).unlink(missing_ok=True)
    wipe()
    yield
    wipe()


def _run(script, payload, tmp_path):
    env = dict(os.environ, HOOK_TEST_ISOLATION="1", CLAUDE_PROJECT_DIR=str(tmp_path))
    return subprocess.run(
        [sys.executable, str(script)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=60,
    )


def _complete(sid=None):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "ticket track complete 0.1.0-W1-001"},
        "tool_response": {"stdout": "[OK] 0.1.0-W1-001 已完成", "stderr": ""},
    }
    if sid is not None:
        payload["session_id"] = sid
    return payload


def _context(result):
    return json.loads(result.stdout).get("hookSpecificOutput", {}).get("additionalContext", "")


# --- session-context-guard：E1 對照 ---

def test_guard_same_session_two_processes_accumulate(tmp_path):
    r1 = _run(GUARD, _complete(SID_A), tmp_path)
    assert r1.returncode == 0
    assert Path(COUNTER % SID_A).read_text().strip() == "1"
    r2 = _run(GUARD, _complete(SID_A), tmp_path)
    assert Path(COUNTER % SID_A).read_text().strip() == "2"
    assert "Session Context Guard" in _context(r2)


def test_guard_different_sessions_independent(tmp_path):
    _run(GUARD, _complete(SID_A), tmp_path)
    _run(GUARD, _complete(SID_A), tmp_path)
    r = _run(GUARD, _complete(SID_B), tmp_path)
    assert Path(COUNTER % SID_B).read_text().strip() == "1"
    assert Path(COUNTER % SID_A).read_text().strip() == "2"
    assert _context(r) == ""


def test_guard_missing_session_id_skips_state_warns_stderr(tmp_path):
    before = set(Path("/tmp").glob("claude-session-completed-tickets-*"))
    r = _run(GUARD, _complete(None), tmp_path)
    assert r.returncode == 0
    assert "session_id" in r.stderr
    assert set(Path("/tmp").glob("claude-session-completed-tickets-*")) == before


# --- 一次 complete 只計 1 ---

def test_one_complete_counts_once_across_guard_and_lifecycle(tmp_path):
    """兩支 hook 都註冊在 PostToolUse:Bash，對同一次 complete 各跑一次，計數只加 1。"""
    payload = _complete(SID_A)
    _run(GUARD, payload, tmp_path)
    _run(LIFECYCLE, payload, tmp_path)
    assert Path(COUNTER % SID_A).read_text().strip() == "1"


def test_lifecycle_has_no_counter_implementation():
    text = LIFECYCLE.read_text(encoding="utf-8")
    assert "increment_counter" not in text
    assert "claude-session-completed" not in text


# --- dispatch-count-guard：寫入與讀取在不同程序 ---

def _agent_post(sid):
    return {
        "hook_event_name": "PostToolUse", "session_id": sid, "tool_name": "Agent",
        "tool_input": {"prompt": "三人組多視角審查", "description": "review"},
    }


def _prompt(sid):
    return {"hook_event_name": "UserPromptSubmit", "session_id": sid, "prompt": "繼續"}


def test_dispatch_warning_across_processes(tmp_path):
    """正向對照：PostToolUse 只派 1 個、宣稱 3，另一程序的 UserPromptSubmit 輸出警告。"""
    _run(DISPATCH, _agent_post(SID_A), tmp_path)
    assert Path(BATCH % SID_A).exists()
    r = _run(DISPATCH, _prompt(SID_A), tmp_path)
    assert r.returncode == 0
    assert "Dispatch Count Guard" in _context(r)
    assert not Path(BATCH % SID_A).exists()


def test_dispatch_other_session_no_warning(tmp_path):
    _run(DISPATCH, _agent_post(SID_A), tmp_path)
    r = _run(DISPATCH, _prompt(SID_B), tmp_path)
    assert "Dispatch Count Guard" not in r.stdout
    assert Path(BATCH % SID_A).exists()


def test_dispatch_missing_session_id_skips(tmp_path):
    payload = _agent_post(SID_A)
    del payload["session_id"]
    r = _run(DISPATCH, payload, tmp_path)
    assert r.returncode == 0
    assert "session_id" in r.stderr
    assert not Path(BATCH % SID_A).exists()


# --- handoff-prompt-reminder / handoff_session_mgmt：路徑鍵 ---

def _load(path, name):
    for p in (str(CLAUDE_DIR), str(CLAUDE_DIR / "hooks"), str(SESSION_MGMT_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reminder_flag_keyed_by_session_id_not_ppid():
    mod = _load(REMINDER, "handoff_prompt_reminder_under_test")
    logger = MagicMock()
    with patch("os.getppid", return_value=1):
        assert not mod.has_reminded_this_session({"session_id": SID_A}, logger)
        mod.mark_reminded_this_session({"session_id": SID_A}, logger)
    with patch("os.getppid", return_value=2):
        assert mod.has_reminded_this_session({"session_id": SID_A}, logger)
        assert not mod.has_reminded_this_session({"session_id": SID_B}, logger)


def test_reminder_missing_session_id_skips_flag_io(capsys):
    mod = _load(REMINDER, "handoff_prompt_reminder_under_test2")
    logger = MagicMock()
    assert mod.has_reminded_this_session({}, logger) is False
    mod.mark_reminded_this_session({}, logger)
    assert "session_id" in capsys.readouterr().err
    assert logger.warning.called


def test_session_mgmt_state_file_keyed_by_session_id(capsys):
    mod = _load(SESSION_MGMT_DIR / "handoff_session_mgmt.py", "handoff_session_mgmt_under_test")
    with patch("os.getppid", return_value=7):
        a = mod.get_session_state_file({"session_id": SID_A})
    with patch("os.getppid", return_value=8):
        assert mod.get_session_state_file({"session_id": SID_A}) == a
        assert mod.get_session_state_file({"session_id": SID_B}) != a
    assert a == Path("/tmp/claude-handoff-state-%s.json" % SID_A)
    assert mod.get_session_state_file({}) is None
    assert mod.read_session_state(MagicMock(), {}) is None
    assert "session_id" in capsys.readouterr().err


def test_no_getppid_session_key_remaining_in_hooks():
    """repo 內的 hook 腳本不再以 os.getppid() 作 session 鍵。"""
    offenders = []
    roots = [CLAUDE_DIR / "hooks", CLAUDE_DIR / "skills" / "ticket" / "hooks", CLAUDE_DIR / "lib"]
    for root in roots:
        for py in root.rglob("*.py"):
            if "/tests/" in str(py) or "__pycache__" in str(py):
                continue
            if "os.getppid" in py.read_text(encoding="utf-8", errors="replace"):
                offenders.append(str(py))
    assert offenders == []
