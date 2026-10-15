"""session-context-guard-hook：完成命令辨識（含 finish 別名）。

E2：斷言計數檔的實際計數值與 exit code，不以輸出字樣判定。
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
    "session_context_guard_hook", _HOOKS_DIR / "session-context-guard-hook.py"
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


@pytest.fixture
def counter(tmp_path, monkeypatch):
    f = tmp_path / "counter"
    monkeypatch.setattr(_hook, "get_counter_file", lambda *a, **kw: f)
    return f


def _run(monkeypatch, command, stdout="Ticket X 已完成"):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return _hook.main()


def _count(counter):
    return int(counter.read_text()) if counter.exists() else 0


@pytest.mark.parametrize("command", [
    "ticket track complete T-1",
    "ticket track finish T-1",
    "ticket track batch-complete T-1 T-2",
    "FOO=1 ticket track finish T-1",
    "cd /x && ticket track finish T-1",
])
def test_completion_commands_increment(monkeypatch, counter, command):
    assert _run(monkeypatch, command) == 0
    assert _count(counter) == 1


@pytest.mark.parametrize("command", [
    'ticket track append-log T-1 --section S "ticket track finish T-2"',
    "cat <<'EOF'\nticket track complete T-2\nEOF",
    'ticket track finish "unterminated',
])
def test_non_command_text_does_not_increment(monkeypatch, counter, command):
    assert _run(monkeypatch, command) == 0
    assert _count(counter) == 0


def test_failure_marker_absent_does_not_increment(monkeypatch, counter):
    # 被遮蔽且無票號可讀（退回標記判定）：stdout 無標記不計數
    assert _run(monkeypatch, "ticket track finish T-1; echo rc=$?", stdout="error") == 0
    assert _count(counter) == 0


def test_unmasked_counts_once_regardless_of_stdout(monkeypatch, counter):
    assert _run(monkeypatch, "ticket track finish T-1", stdout="") == 0
    assert _count(counter) == 1


def test_unmasked_recomplete_outside_window_not_counted(monkeypatch, counter):
    """E1：未遮蔽、stdout 為「已完成於 ...」，completed_at 在窗外不計數、窗內計數"""
    out = "0.5.0-W1-286.1 已完成於 2026-10-15T11:52:55"
    monkeypatch.setattr(_hook, "make_completed_verifier", lambda cmd: (lambda: False))
    assert _run(monkeypatch, "ticket track complete 0.5.0-W1-286.1", stdout=out) == 0
    assert _count(counter) == 0
    monkeypatch.setattr(_hook, "make_completed_verifier", lambda cmd: (lambda: True))
    assert _run(monkeypatch, "ticket track complete 0.5.0-W1-286.1", stdout=out) == 0
    assert _count(counter) == 1


@pytest.mark.parametrize("command", [
    "ticket track finish T > log 2>&1; echo rc=$?",
    "out=$(ticket track complete T 2>&1); rc=$?",
])
def test_masked_forms_follow_ticket_state(monkeypatch, counter, command):
    """E1：同一 stdout（rc=0）下，票面已完成計數 1、票面未完成不計數"""
    monkeypatch.setattr(_hook, "make_completed_verifier", lambda cmd: (lambda: True))
    assert _run(monkeypatch, command, stdout="rc=0") == 0
    assert _count(counter) == 1
    counter.unlink()
    monkeypatch.setattr(_hook, "make_completed_verifier", lambda cmd: (lambda: False))
    assert _run(monkeypatch, command, stdout="rc=0") == 0
    assert _count(counter) == 0
