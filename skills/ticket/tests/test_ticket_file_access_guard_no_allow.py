"""
ticket-file-access-guard 放行路徑不輸出 permissionDecision（3.3.0-W1-013.2）。

PreToolUse 的 allow 會略過平台權限提示（例如工作目錄外的 Read），等於代用戶核可。
本 hook 只擋 ticket 檔案的違規寫入；放行時交回平台權限流程，有提示才輸出
additionalContext。

E2 正向對照：Write ticket md、Edit frontmatter 仍輸出 deny。
隔離：CLAUDE_PROJECT_DIR 指向 tmp_path，日誌寫入 tmp_path，不動真實 hook-logs。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


TICKET_RELPATH = "docs/work-logs/v0/v0.2/v0.2.1/tickets/0.2.1-W3-549.md"
TICKET_CONTENT = "---\nid: 0.2.1-W3-549\nstatus: in_progress\n---\n\n# Body\n\n## Solution\n\n內容\n"


def _load_hook_module():
    hook_path = (
        Path(__file__).resolve().parents[1] / "hooks" / "ticket-file-access-guard-hook.py"
    )
    spec = importlib.util.spec_from_file_location("ticket_file_access_guard_no_allow", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("TICKET_TRACKER_INTERNAL", raising=False)
    ticket = tmp_path / TICKET_RELPATH
    ticket.parent.mkdir(parents=True)
    ticket.write_text(TICKET_CONTENT, encoding="utf-8")
    return tmp_path


def _run(hook, monkeypatch, capsys, payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    rc = hook.main()
    out = capsys.readouterr().out.strip()
    return rc, (json.loads(out) if out else None)


def _decision(obj):
    if obj is None:
        return None
    return (obj.get("hookSpecificOutput") or {}).get("permissionDecision")


@pytest.mark.parametrize(
    "tool_name,tool_input",
    [
        ("Read", {"file_path": "/etc/hosts"}),
        ("Edit", {"file_path": "/etc/x.txt", "old_string": "a", "new_string": "b"}),
        ("Write", {"file_path": "/etc/x.txt", "content": "a"}),
        ("Glob", {"pattern": "*.md"}),
    ],
)
def test_pass_paths_emit_no_permission_decision(project, monkeypatch, capsys, tool_name, tool_input):
    hook = _load_hook_module()
    rc, obj = _run(hook, monkeypatch, capsys, {"tool_name": tool_name, "tool_input": tool_input})
    assert rc == 0
    assert obj is None, f"放行路徑不應輸出任何 JSON，實得 {obj}"


def test_read_ticket_keeps_hint_without_decision(project, monkeypatch, capsys):
    hook = _load_hook_module()
    rc, obj = _run(
        hook, monkeypatch, capsys,
        {"tool_name": "Read", "tool_input": {"file_path": str(project / TICKET_RELPATH)}},
    )
    assert rc == 0
    assert _decision(obj) is None
    assert "ticket track full" in obj["hookSpecificOutput"]["additionalContext"]


def test_body_edit_emits_no_decision(project, monkeypatch, capsys):
    hook = _load_hook_module()
    rc, obj = _run(
        hook, monkeypatch, capsys,
        {"tool_name": "Edit", "tool_input": {
            "file_path": str(project / TICKET_RELPATH), "old_string": "內容", "new_string": "新內容"}},
    )
    assert rc == 0
    assert obj is None


def test_empty_input_emits_nothing(project, monkeypatch, capsys):
    hook = _load_hook_module()
    rc, obj = _run(hook, monkeypatch, capsys, "")
    assert rc == 0
    assert obj is None


def test_exception_path_emits_no_decision_and_writes_stderr(project, monkeypatch, capsys):
    hook = _load_hook_module()

    def boom(*_args, **_kwargs):
        raise RuntimeError("probe")

    monkeypatch.setattr(hook, "check_read_permission", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}})))
    rc = hook.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == ""
    assert "Hook 執行錯誤" in captured.err


def test_positive_control_write_ticket_still_denied(project, monkeypatch, capsys):
    hook = _load_hook_module()
    rc, obj = _run(
        hook, monkeypatch, capsys,
        {"tool_name": "Write", "tool_input": {"file_path": str(project / TICKET_RELPATH), "content": "x"}},
    )
    assert rc == 2
    assert _decision(obj) == "deny"


def test_positive_control_edit_frontmatter_still_denied(project, monkeypatch, capsys):
    hook = _load_hook_module()
    rc, obj = _run(
        hook, monkeypatch, capsys,
        {"tool_name": "Edit", "tool_input": {
            "file_path": str(project / TICKET_RELPATH),
            "old_string": "status: in_progress", "new_string": "status: completed"}},
    )
    assert rc == 2
    assert _decision(obj) == "deny"
