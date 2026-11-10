"""完成類 hook 對 PostToolUseFailure 結束碼 75 的補處理（0.5.0-W1-281.5）。

結束碼 75 = ticket CLI 動作已完成、僅 auto-commit 失敗，平台走 PostToolUseFailure。
E2：斷言具體副作用（handoff 檔被刪、計數檔值、checkpoint 提醒輸出），不以輸出子字串
判定處理與否。對照組：結束碼 1 不處理；payload 異常 fail-open。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
_TICKET_HOOKS_DIR = _HOOKS_DIR.parent / "skills" / "ticket" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
if str(_HOOKS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR.parent))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cleanup = _load("handoff_cleanup_hook_e75", _TICKET_HOOKS_DIR / "handoff-cleanup-hook.py")
_lifecycle = _load("post_ticket_lifecycle_hook_e75", _TICKET_HOOKS_DIR / "post-ticket-lifecycle-hook.py")
_guard = _load("session_context_guard_hook_e75", _HOOKS_DIR / "session-context-guard-hook.py")

TICKET = "0.5.0-W1-999"
COMMAND = "ticket track complete " + TICKET


def _failure_payload(code, command=COMMAND):
    return {
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "error": "Exit code {}\n[OK] 已完成 Ticket {}\nauto-commit 失敗".format(code, TICKET),
        "is_interrupt": False,
    }


def _feed(monkeypatch, payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))


@pytest.fixture
def handoff_file(tmp_path, monkeypatch):
    f = tmp_path / ".claude" / "handoff" / "pending" / (TICKET + ".json")
    f.parent.mkdir(parents=True)
    f.write_text("{}")
    monkeypatch.setattr(_cleanup, "get_project_root", lambda: tmp_path)
    return f


@pytest.fixture
def counter(tmp_path, monkeypatch):
    f = tmp_path / "counter"
    monkeypatch.setattr(_guard, "get_counter_file", lambda *a, **kw: f)
    return f


def _count(counter):
    return int(counter.read_text()) if counter.exists() else 0


# ---- handoff-cleanup ----

def test_cleanup_exit75_deletes_handoff(monkeypatch, handoff_file):
    _feed(monkeypatch, _failure_payload(75))
    assert _cleanup.main() == 0
    assert not handoff_file.exists()


def test_cleanup_exit1_keeps_handoff(monkeypatch, handoff_file):
    _feed(monkeypatch, _failure_payload(1))
    assert _cleanup.main() == 0
    assert handoff_file.exists()


# ---- session-context-guard ----

def test_guard_exit75_increments_counter(monkeypatch, counter):
    _feed(monkeypatch, _failure_payload(75))
    assert _guard.main() == 0
    assert _count(counter) == 1


def test_guard_exit1_does_not_increment(monkeypatch, counter):
    _feed(monkeypatch, _failure_payload(1))
    assert _guard.main() == 0
    assert _count(counter) == 0


# ---- post-ticket-lifecycle ----

def _lifecycle_output(monkeypatch, capsys, payload):
    _feed(monkeypatch, payload)
    assert _lifecycle.main() == 0
    return json.loads(capsys.readouterr().out)


def test_lifecycle_exit75_emits_checkpoint_under_failure_event(monkeypatch, capsys):
    out = _lifecycle_output(monkeypatch, capsys, _failure_payload(75))
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PostToolUseFailure"
    assert hso.get("additionalContext")


def test_lifecycle_exit1_emits_no_context(monkeypatch, capsys):
    out = _lifecycle_output(monkeypatch, capsys, _failure_payload(1))
    assert "additionalContext" not in out["hookSpecificOutput"]


# ---- fail-open：payload 異常不阻擋、不處理 ----

@pytest.mark.parametrize("error", [None, 5, "no exit line\n[OK] 已完成", "Exit code abc\n"])
def test_malformed_error_is_noop(monkeypatch, handoff_file, counter, capsys, error):
    payload = _failure_payload(75)
    payload["error"] = error
    for hook in (_cleanup, _guard, _lifecycle):
        _feed(monkeypatch, payload)
        assert hook.main() == 0
    capsys.readouterr()
    assert handoff_file.exists()
    assert _count(counter) == 0


def test_unparseable_stdin_is_noop(monkeypatch, handoff_file, counter, capsys):
    for hook in (_cleanup, _guard, _lifecycle):
        _feed(monkeypatch, "{not json")
        assert hook.main() == 0
    capsys.readouterr()
    assert handoff_file.exists()
    assert _count(counter) == 0


def test_registry_lists_hooks_in_failure_group():
    registry = json.loads((_HOOKS_DIR / "hook-dispatch-registry.json").read_text())
    paths = [h["path"] for h in registry["groups"]["PostToolUseFailure:Bash"]["hooks"]]
    for name in ("handoff-cleanup-hook.py", "post-ticket-lifecycle-hook.py", "session-context-guard-hook.py"):
        assert any(p.endswith(name) for p in paths)
