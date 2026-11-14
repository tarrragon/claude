"""
ticket-path-guard 放行路徑不輸出 permissionDecision（3.3.0-W1-013.3）。

PreToolUse 的 allow 會略過平台權限提示，等於代用戶核可。本 hook 只擋
`.claude/tickets/` 下的 Write/Edit；其餘情況交回平台權限流程。

改前範圍外工具分支以錯誤參數數呼叫本地 generate_hook_output，拋 TypeError
後落入例外分支輸出 allow；本測試鎖定改後該分支無輸出。

E2 正向對照：Write `.claude/tickets/x.md` 仍 deny + exit 2。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


def _load():
    hook_path = (
        Path(__file__).resolve().parents[2] / "skills" / "ticket" / "hooks" / "ticket-path-guard-hook.py"
    )
    spec = importlib.util.spec_from_file_location("ticket_path_guard_no_allow", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(monkeypatch, capsys, raw):
    hook = _load()
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw if isinstance(raw, str) else json.dumps(raw)))
    rc = hook.main()
    captured = capsys.readouterr()
    return hook, rc, captured


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}},
        {"tool_name": "Write", "tool_input": {"file_path": "/etc/x.txt", "content": "a"}},
        {"tool_name": "Edit", "tool_input": {"file_path": "docs/a.md", "old_string": "a", "new_string": "b"}},
        "",
    ],
)
def test_pass_paths_emit_nothing(monkeypatch, capsys, payload):
    _hook, rc, captured = _run(monkeypatch, capsys, payload)
    assert rc == 0
    assert captured.out == ""


def test_exception_path_emits_no_decision_and_writes_stderr(monkeypatch, capsys):
    hook = _load()

    def boom(*_args, **_kwargs):
        raise RuntimeError("probe")

    monkeypatch.setattr(hook, "check_write_permission", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": "/etc/x.txt", "content": "a"}})))
    rc = hook.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
    assert "Hook 執行錯誤" in captured.err


def test_positive_control_forbidden_path_still_denied(monkeypatch, capsys):
    hook, rc, captured = _run(
        monkeypatch, capsys,
        {"tool_name": "Write", "tool_input": {"file_path": ".claude/tickets/x.md", "content": "a"}},
    )
    assert rc == hook.EXIT_BLOCK
    assert json.loads(captured.out)["hookSpecificOutput"]["permissionDecision"] == "deny"
