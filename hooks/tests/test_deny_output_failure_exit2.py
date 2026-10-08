"""PreToolUse 守衛 deny 輸出失敗兜底測試（E1 / E2）

背景：emit_hook_output 在 deny 輸出（stdout 寫入）失敗時以 SystemExit(2) 阻擋；
直接 print deny JSON 的守衛則因寫入失敗落入 run_hook_safely 或自身 except
而回 exit 1（非阻擋，等同放行）。本檔涵蓋該類守衛：

- E2：stdout 寫入失敗時，deny 路徑必須以 exit 2 結束（遷移前紅燈、遷移後綠燈）
- E1：遷移前後 stdout 逐位元組等價
  - 可等價遷移（單行 JSON、無額外欄位）者：以舊建構方式組出預期位元組後比對
  - 不可等價遷移（indent=2 / 含額外欄位）者：鎖定既有輸出形狀（indent=2）不變，
    並以自行 try/except 兜底 exit 2
"""

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_TICKET_HOOKS_DIR = _HOOKS_DIR.parent / "skills" / "ticket" / "hooks"
for _p in (str(_HOOKS_DIR), str(_HOOKS_DIR.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FailingStdout:
    """write 一律失敗的 stdout（模擬管線斷裂 / 磁碟寫滿）。"""

    def write(self, _text):
        raise OSError(28, "No space left on device")

    def flush(self):
        pass


def _exit_code(call):
    """執行 call，回傳 SystemExit.code 或其回傳值。"""
    try:
        return call()
    except SystemExit as exc:
        return exc.code


def _run_safely(mod, name):
    return _exit_code(lambda: mod.run_hook_safely(mod.main, name))


def _set_stdin(monkeypatch, payload):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def _single_line_bytes(decision, reason):
    """遷移前的手建 JSON 位元組（單行、ensure_ascii=False、print 尾端換行）。"""
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        },
        ensure_ascii=False,
    ) + "\n"


# ============================================================================
# presence-detection（可等價遷移）
# ============================================================================

_PRESENCE_PAYLOAD = {
    "tool_name": "Write",
    "tool_input": {"file_path": "app/messages.py", "content": 'msg = "登入失敗，請重試"'},
}


@pytest.fixture
def presence(monkeypatch):
    monkeypatch.delenv("PRESENCE_HOOK_MODE", raising=False)
    monkeypatch.syspath_prepend(str(_HOOKS_DIR.parent / "config"))
    return _load("presence_deny_exit2", _HOOKS_DIR / "presence-detection-hook.py")


def test_presence_deny_output_failure_exits_2(presence, monkeypatch):
    _set_stdin(monkeypatch, _PRESENCE_PAYLOAD)
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(presence, "presence-detection") == 2


def test_presence_deny_bytes_unchanged(presence, monkeypatch, capsys):
    _set_stdin(monkeypatch, _PRESENCE_PAYLOAD)
    assert _exit_code(presence.main) == 2
    out = capsys.readouterr().out
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert out == _single_line_bytes("deny", reason)


# ============================================================================
# proposal-evaluation-gate（可等價遷移）
# ============================================================================


@pytest.fixture
def proposal():
    return _load("proposal_deny_exit2", _HOOKS_DIR / "proposal-evaluation-gate-hook.py")


def _proposal_payload(tmp_path):
    d = tmp_path / "docs" / "proposals"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "PROP-300.md"
    f.write_text(
        "---\nid: PROP-300\nevaluation_level: heavy\nstatus: discussing\n---\n\n"
        "# 動機\n只有動機，缺所有 heavy 章節。\n",
        encoding="utf-8",
    )
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(f),
            "old_string": "status: discussing",
            "new_string": "status: confirmed",
        },
    }


def test_proposal_deny_output_failure_exits_2(proposal, monkeypatch, tmp_path):
    _set_stdin(monkeypatch, _proposal_payload(tmp_path))
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(proposal, "proposal-evaluation-gate") == 2


def test_proposal_deny_bytes_unchanged(proposal, monkeypatch, capsys, tmp_path):
    _set_stdin(monkeypatch, _proposal_payload(tmp_path))
    proposal.main()
    out = capsys.readouterr().out
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert out == _single_line_bytes("deny", reason)


def test_proposal_allow_bytes_unchanged(proposal, capsys):
    proposal.emit_decision("allow", "ok 通過")
    assert capsys.readouterr().out == _single_line_bytes("allow", "ok 通過")


# ============================================================================
# ticket-path-guard（可等價遷移；整個 main 包在 except Exception -> allow）
# ============================================================================


@pytest.fixture
def path_guard():
    return _load("path_guard_deny_exit2", _TICKET_HOOKS_DIR / "ticket-path-guard-hook.py")


_PATH_GUARD_DENY = {
    "tool_name": "Write",
    "tool_input": {"file_path": ".claude/tickets/x.md"},
}
_PATH_GUARD_ALLOW = {
    "tool_name": "Write",
    "tool_input": {"file_path": "docs/work-logs/v0.1.0/tickets/x.md"},
}


def test_path_guard_deny_output_failure_exits_2(path_guard, monkeypatch):
    _set_stdin(monkeypatch, _PATH_GUARD_DENY)
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(path_guard, "ticket-path-guard") == 2


def test_path_guard_deny_bytes_unchanged(path_guard, monkeypatch, capsys):
    _set_stdin(monkeypatch, _PATH_GUARD_DENY)
    assert path_guard.main() == 2
    out = capsys.readouterr().out
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert out == _single_line_bytes("deny", reason)


def test_path_guard_allow_bytes_unchanged(path_guard, monkeypatch, capsys):
    _set_stdin(monkeypatch, _PATH_GUARD_ALLOW)
    assert path_guard.main() == 0
    out = capsys.readouterr().out
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert out == _single_line_bytes("allow", reason)


# ============================================================================
# task-dispatch-readiness-check（不可等價遷移：indent=2 + systemMessage）
# ============================================================================


@pytest.fixture
def task_dispatch():
    return _load(
        "task_dispatch_deny_exit2", _HOOKS_DIR / "task-dispatch-readiness-check.py"
    )


def _strict_dispatch_setup(mod, monkeypatch):
    monkeypatch.setattr(mod, "prompt_references_handoff_ticket", lambda prompt, logger=None, project_root=None: False)
    monkeypatch.setattr(mod, "load_agents_config", lambda: {})
    monkeypatch.setattr(mod, "get_hook_mode", lambda logger: mod.HOOK_MODE_STRICT)
    monkeypatch.setattr(
        mod,
        "check_agent_dispatch",
        lambda prompt, subagent_type, config, logger: {
            "is_error": True,
            "error_message": "分派錯誤測試",
        },
    )


_NO_PROMPT = {"tool_name": "Agent", "tool_input": {}}
_STRICT = {
    "tool_name": "Agent",
    "tool_input": {"prompt": "do x", "subagent_type": "wrong-agent"},
}


def test_task_dispatch_no_prompt_deny_failure_exits_2(task_dispatch, monkeypatch):
    _set_stdin(monkeypatch, _NO_PROMPT)
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(task_dispatch, "agent-dispatch-check") == 2


def test_task_dispatch_strict_deny_failure_exits_2(task_dispatch, monkeypatch):
    _strict_dispatch_setup(task_dispatch, monkeypatch)
    _set_stdin(monkeypatch, _STRICT)
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(task_dispatch, "agent-dispatch-check") == 2


def test_task_dispatch_deny_shape_unchanged(task_dispatch, monkeypatch, capsys):
    _set_stdin(monkeypatch, _NO_PROMPT)
    assert _exit_code(task_dispatch.main) == 0
    out = capsys.readouterr().out
    assert out == json.dumps(json.loads(out), ensure_ascii=False, indent=2) + "\n"
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ============================================================================
# acceptance-gate（不可等價遷移：indent=2，allow/deny 共用同一輸出）
# ============================================================================


@pytest.fixture
def acceptance_gate():
    return _load("acceptance_gate_deny_exit2", _TICKET_HOOKS_DIR / "acceptance-gate-hook.py")


def _acceptance_setup(mod, monkeypatch, should_block):
    monkeypatch.setattr(
        mod,
        "check_acceptance_status",
        lambda ticket_id, project_dir, logger, command: SimpleNamespace(
            should_block=should_block,
            has_acceptance=True,
            has_new_error_patterns=False,
            pending_sibling_tickets=[],
        ),
    )
    decision = "deny" if should_block else "allow"
    monkeypatch.setattr(
        mod,
        "generate_hook_output",
        lambda *a, **k: {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
            }
        },
    )
    monkeypatch.setattr(mod, "save_check_log", lambda *a, **k: None)


# 以拼接組出 ticket ID 形狀（框架檔不實例化專案 ticket ID）
_TICKET_ID = "0.1.0" + "-W" + "1" + "-001"
_COMPLETE = {
    "tool_name": "Bash",
    "tool_input": {"command": "ticket track complete " + _TICKET_ID},
}


def test_acceptance_gate_deny_failure_exits_2(acceptance_gate, monkeypatch):
    _acceptance_setup(acceptance_gate, monkeypatch, True)
    _set_stdin(monkeypatch, _COMPLETE)
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(acceptance_gate, "acceptance-gate") == 2


def test_acceptance_gate_allow_failure_not_blocked(acceptance_gate, monkeypatch):
    """allow 輸出失敗維持 fail-open（回 1），不被誤升為阻擋。"""
    _acceptance_setup(acceptance_gate, monkeypatch, False)
    _set_stdin(monkeypatch, _COMPLETE)
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(acceptance_gate, "acceptance-gate") != 2


def test_acceptance_gate_deny_shape_unchanged(acceptance_gate, monkeypatch, capsys):
    _acceptance_setup(acceptance_gate, monkeypatch, True)
    _set_stdin(monkeypatch, _COMPLETE)
    assert acceptance_gate.main() == 2
    out = capsys.readouterr().out
    assert out == json.dumps(json.loads(out), ensure_ascii=False, indent=2) + "\n"


# ============================================================================
# agent-ticket-validation（不可等價遷移：indent=2 + checkResult.timestamp）
# ============================================================================


@pytest.fixture
def ticket_validation():
    return _load(
        "ticket_validation_deny_exit2", _TICKET_HOOKS_DIR / "agent-ticket-validation-hook.py"
    )


def _validation_setup(mod, monkeypatch, is_valid):
    monkeypatch.setattr(mod, "validate_hook_input", lambda *a, **k: True)
    monkeypatch.setattr(
        mod,
        "validate_task_dispatch",
        lambda tool_input, logger: (is_valid, None if is_valid else "派發驗證失敗測試", "tid"),
    )
    monkeypatch.setattr(mod, "save_check_log", lambda *a, **k: None)


_DISPATCH = {"tool_input": {"prompt": "x", "subagent_type": "thyme-python-developer"}}


def test_ticket_validation_deny_failure_exits_2(ticket_validation, monkeypatch):
    _validation_setup(ticket_validation, monkeypatch, False)
    _set_stdin(monkeypatch, _DISPATCH)
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(ticket_validation, "agent-ticket-validation") == 2


def test_ticket_validation_allow_failure_not_blocked(ticket_validation, monkeypatch):
    _validation_setup(ticket_validation, monkeypatch, True)
    _set_stdin(monkeypatch, _DISPATCH)
    monkeypatch.setattr(sys, "stdout", _FailingStdout())
    assert _run_safely(ticket_validation, "agent-ticket-validation") != 2


def test_ticket_validation_deny_shape_unchanged(ticket_validation, monkeypatch, capsys):
    _validation_setup(ticket_validation, monkeypatch, False)
    _set_stdin(monkeypatch, _DISPATCH)
    assert ticket_validation.main() == 2
    out = capsys.readouterr().out
    assert out == json.dumps(json.loads(out), ensure_ascii=False, indent=2) + "\n"


# ============================================================================
# branch-verify（已由 run_hook_safely(fail_closed=True) 兜底；鎖定現況，不遷移）
# ============================================================================


def test_branch_verify_deny_failure_exits_2_via_fail_closed(monkeypatch):
    mod = _load("branch_verify_deny_exit2", _HOOKS_DIR / "branch-verify-hook.py")
    attempted = []

    def _fail(output):
        attempted.append(output["hookSpecificOutput"]["permissionDecision"])
        raise OSError("x")

    monkeypatch.setattr(mod, "write_hook_output", _fail)
    monkeypatch.setattr(mod, "get_current_branch", lambda cwd=None: "main")
    monkeypatch.setattr(mod, "is_allowed_branch", lambda branch: False)
    monkeypatch.setattr(mod, "is_protected_branch", lambda branch: True)
    monkeypatch.setattr(mod, "find_target_repo", lambda path: None)
    monkeypatch.setattr(mod, "is_exempt_path_on_protected_branch", lambda *a, **k: False)
    _set_stdin(
        monkeypatch,
        {"tool_name": "Edit", "tool_input": {"file_path": "/repo/src/foo.py"}},
    )
    code = _exit_code(lambda: mod.run_hook_safely(mod.main, "branch-verify", fail_closed=True))
    assert attempted == ["deny"]  # 確認確實走到 deny 輸出而非其他例外
    assert code == 2
