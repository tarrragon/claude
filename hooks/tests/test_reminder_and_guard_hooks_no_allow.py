"""
file-type-permission、branch-verify、presence-detection 放行路徑不輸出
permissionDecision（3.3.0-W1-013.4）。

PreToolUse 的 allow 會略過平台權限提示，等於代用戶核可。三支 hook 的放行與提醒
路徑改為：只寫日誌（file-type-permission、branch-verify），或只帶
additionalContext（presence warn 模式）。

E2 正向對照：branch-verify 保護分支編輯非豁免檔仍 deny；presence block 模式仍 deny。
branch-verify 的 fail_closed 包裝（run_hook_safely）不在本檔改動範圍。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(module, monkeypatch, capsys, payload):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    out = capsys.readouterr().out.strip()
    return rc, (json.loads(out) if out else None)


# ---------- file-type-permission ----------

@pytest.mark.parametrize(
    "file_path",
    ["/repo/docs/work-logs/v1/x.md", "/repo/.claude/tickets/x.md", "/repo/lib/a.py"],
)
def test_file_type_permission_emits_nothing(monkeypatch, capsys, file_path):
    hook = _load("ftp_no_allow", "file-type-permission-hook.py")
    rc, obj = _run(hook, monkeypatch, capsys, {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "old_string": "a", "new_string": "b"},
    })
    assert rc == 0
    assert obj is None


# ---------- branch-verify ----------

@pytest.fixture
def branch_verify():
    return _load("branch_verify_no_allow", "branch-verify-hook.py")


def test_branch_verify_non_edit_tool_emits_nothing(branch_verify, monkeypatch, capsys):
    rc, obj = _run(branch_verify, monkeypatch, capsys,
                   {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}})
    assert rc == 0
    assert obj is None


@pytest.mark.parametrize("branch", ["feat/x", "some-other-branch"])
def test_branch_verify_allowed_branch_emits_nothing(branch_verify, monkeypatch, capsys, branch):
    monkeypatch.setattr(branch_verify, "get_current_branch", lambda cwd=None: branch)
    rc, obj = _run(branch_verify, monkeypatch, capsys, {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/repo/lib/a.py", "old_string": "a", "new_string": "b"},
    })
    assert rc == 0
    assert obj is None


def test_branch_verify_no_branch_info_emits_nothing(branch_verify, monkeypatch, capsys):
    monkeypatch.setattr(branch_verify, "get_current_branch", lambda cwd=None: None)
    rc, obj = _run(branch_verify, monkeypatch, capsys, {
        "tool_name": "Write", "tool_input": {"file_path": "/repo/lib/a.py", "content": "a"},
    })
    assert rc == 0
    assert obj is None


def test_branch_verify_exempt_path_on_protected_emits_nothing(branch_verify, monkeypatch, capsys):
    monkeypatch.setattr(branch_verify, "get_current_branch", lambda cwd=None: "main")
    monkeypatch.setattr(branch_verify, "is_exempt_path_on_protected_branch",
                        lambda *a, **k: True)
    rc, obj = _run(branch_verify, monkeypatch, capsys, {
        "tool_name": "Edit",
        "tool_input": {"file_path": "docs/a.md", "old_string": "a", "new_string": "b"},
    })
    assert rc == 0
    assert obj is None


def test_branch_verify_positive_control_protected_non_exempt_denied(branch_verify, monkeypatch, capsys):
    monkeypatch.setattr(branch_verify, "get_current_branch", lambda cwd=None: "main")
    monkeypatch.setattr(branch_verify, "is_exempt_path_on_protected_branch",
                        lambda *a, **k: False)
    rc, obj = _run(branch_verify, monkeypatch, capsys, {
        "tool_name": "Edit",
        "tool_input": {"file_path": "lib/a.dart", "old_string": "a", "new_string": "b"},
    })
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------- presence-detection ----------

_DART_VIOLATION = {
    "tool_name": "Write",
    "tool_input": {"file_path": "app/lib/login.dart", "content": 'Text("登入失敗")'},
}


def test_presence_warn_mode_context_without_decision(monkeypatch, capsys):
    monkeypatch.setenv("PRESENCE_HOOK_MODE", "warn")
    hook = _load("presence_no_allow_warn", "presence-detection-hook.py")
    rc, obj = _run(hook, monkeypatch, capsys, _DART_VIOLATION)
    assert rc == 0
    hso = obj["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hso["additionalContext"]


def test_presence_positive_control_block_mode_denied(monkeypatch, capsys):
    monkeypatch.delenv("PRESENCE_HOOK_MODE", raising=False)
    hook = _load("presence_no_allow_block", "presence-detection-hook.py")
    rc, obj = _run(hook, monkeypatch, capsys, _DART_VIOLATION)
    assert rc == 2
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
