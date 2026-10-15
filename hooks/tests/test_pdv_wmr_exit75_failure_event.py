"""parallel-dispatch-verification 與 worktree-merge-reminder 對 PostToolUseFailure
結束碼 75 的補處理（0.5.0-W1-298）。

斷言結構化結果（輸出 JSON 的 hookEventName 與 additionalContext），不以子字串判定。
對照組：結束碼 1 不處理、payload 異常 fail-open。成功判定沿用 286.2 的 completed 驗證器，
測試以替身驗證器注入「票面已 completed」。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
_CLAUDE_DIR = _HOOKS_DIR.parent
for p in (_HOOKS_DIR, _CLAUDE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_pdv = _load("pdv_hook_e75", _HOOKS_DIR / "parallel-dispatch-verification-hook.py")
_wmr = _load(
    "wmr_hook_e75",
    _CLAUDE_DIR / "skills" / "worktree" / "hooks" / "worktree-merge-reminder-hook.py",
)

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
def pdv_env(monkeypatch):
    """票面已 completed；where.files 有檔但 git diff 為空，使 pdv 必產生警告。"""
    monkeypatch.setattr(_pdv, "make_completed_verifier", lambda command: (lambda: True))
    monkeypatch.setattr(_pdv, "read_ticket_where_files", lambda *a, **k: ["src/a.py"])
    monkeypatch.setattr(_pdv, "read_ticket_type_and_children", lambda *a, **k: ("IMP", False))
    monkeypatch.setattr(_pdv, "get_git_changed_files", lambda *a, **k: [])
    monkeypatch.setattr(_pdv, "save_analysis_log", lambda *a, **k: None)
    monkeypatch.setattr(_pdv, "is_subagent_environment", lambda d: False)


@pytest.fixture
def wmr_env(monkeypatch):
    monkeypatch.setattr(_wmr, "is_subagent_environment", lambda d: False)
    monkeypatch.setattr(_wmr, "parse_worktree_list", lambda logger: [("/wt/x", "br-x")])
    monkeypatch.setattr(
        _wmr, "classify_worktrees",
        lambda wts, logger: ([("/wt/x", "br-x", ["abc1234 commit"])], [], []),
    )


def _run(hook, monkeypatch, capsys, payload):
    _feed(monkeypatch, payload)
    assert hook.main() == 0
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


def _context(out):
    return (out or {}).get("hookSpecificOutput", {}).get("additionalContext")


# ---- parallel-dispatch-verification ----

def test_pdv_exit75_runs_verification(monkeypatch, capsys, pdv_env):
    out = _run(_pdv, monkeypatch, capsys, _failure_payload(75))
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PostToolUseFailure"
    assert "src/a.py" in hso["additionalContext"]


def test_pdv_exit75_respects_completed_verifier(monkeypatch, capsys, pdv_env):
    """成功判定仍走 286.2 驗證器：票面未 completed 時不觸發。"""
    monkeypatch.setattr(_pdv, "make_completed_verifier", lambda command: (lambda: False))
    out = _run(_pdv, monkeypatch, capsys, _failure_payload(75))
    assert _context(out) is None


def test_pdv_exit1_not_processed(monkeypatch, capsys, pdv_env):
    out = _run(_pdv, monkeypatch, capsys, _failure_payload(1))
    assert _context(out) is None


def test_pdv_success_event_unchanged(monkeypatch, capsys, pdv_env):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": COMMAND},
        "tool_response": {"stdout": "[OK] 已完成 Ticket " + TICKET, "stderr": ""},
    }
    out = _run(_pdv, monkeypatch, capsys, payload)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


# ---- worktree-merge-reminder ----

def test_wmr_exit75_emits_reminder(monkeypatch, capsys, wmr_env):
    out = _run(_wmr, monkeypatch, capsys, _failure_payload(75))
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PostToolUseFailure"
    assert "br-x" in hso["additionalContext"]


def test_wmr_exit1_not_processed(monkeypatch, capsys, wmr_env):
    assert _run(_wmr, monkeypatch, capsys, _failure_payload(1)) is None


def test_wmr_success_event_unchanged(monkeypatch, capsys, wmr_env):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": COMMAND},
        "tool_response": {"stdout": "ok", "stderr": ""},
    }
    out = _run(_wmr, monkeypatch, capsys, payload)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


# ---- fail-open ----

@pytest.mark.parametrize("error", [None, 5, "no exit line\n[OK] 已完成", "Exit code abc\n"])
def test_malformed_error_is_noop(monkeypatch, capsys, pdv_env, wmr_env, error):
    payload = _failure_payload(75)
    payload["error"] = error
    for hook in (_pdv, _wmr):
        out = _run(hook, monkeypatch, capsys, payload)
        assert _context(out) is None


def test_unparseable_stdin_is_noop(monkeypatch, capsys, pdv_env, wmr_env):
    for hook in (_pdv, _wmr):
        out = _run(hook, monkeypatch, capsys, "{not json")
        assert _context(out) is None


def test_registry_lists_hooks_in_failure_group():
    registry = json.loads((_HOOKS_DIR / "hook-dispatch-registry.json").read_text())
    paths = [h["path"] for h in registry["groups"]["PostToolUseFailure:Bash"]["hooks"]]
    for name in ("parallel-dispatch-verification-hook.py", "worktree-merge-reminder-hook.py"):
        assert any(p.endswith(name) for p in paths)
