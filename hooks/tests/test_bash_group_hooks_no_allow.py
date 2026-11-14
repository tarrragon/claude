"""
PreToolUse:Bash 群組四支 hook 的放行路徑不輸出 permissionDecision（3.3.0-W1-013.1）。

dispatcher 依 deny > ask > allow 合併子 hook 的決定，任一支對任意命令輸出 allow，
allowlist 外的 Bash 就會略過權限提示，等於代用戶核可。四支 hook 的放行與提醒路徑
改為：不輸出（acceptance-gate 不檢查路徑、bash-write-boundary 放行、test-timeout-pre），
或只帶 additionalContext（bash-edit-guard 的 sed／perl 警告、acceptance-gate 非阻擋提醒）。

E2 正向對照：bash-write-boundary 寫入 lib/ 仍 deny、bash-edit-guard 裸 cd 仍 deny、
acceptance-gate should_block 仍 deny。
"""

from __future__ import annotations

import importlib.util
import io
import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
GATE_PATH = HOOKS_DIR.parent / "skills" / "ticket" / "hooks" / "acceptance-gate-hook.py"
REPO_ROOT = HOOKS_DIR.parent.parent


def _load(name: str, path: Path):
    for p in (str(HOOKS_DIR), str(HOOKS_DIR.parent)):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stdin(monkeypatch, payload: dict) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def _parse(out: str):
    out = out.strip()
    return json.loads(out) if out else None


@pytest.fixture
def logger():
    log = logging.getLogger("test-bash-group-no-allow")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


# ---------- bash-write-boundary-guard ----------

@pytest.fixture(scope="module")
def boundary():
    return _load("bwb_no_allow", HOOKS_DIR / "bash-write-boundary-guard-hook.py")


def _run_boundary(boundary, monkeypatch, capsys, command):
    _stdin(monkeypatch, {"tool_name": "Bash", "tool_input": {"command": command},
                         "cwd": str(REPO_ROOT)})
    with patch.object(boundary, "get_current_branch", return_value="main"):
        rc = boundary.main()
    return rc, _parse(capsys.readouterr().out)


def test_boundary_routine_command_emits_nothing(boundary, monkeypatch, capsys):
    rc, obj = _run_boundary(boundary, monkeypatch, capsys, "git status")
    assert rc == 0
    assert obj is None


def test_boundary_positive_control_scope_write_denied(boundary, monkeypatch, capsys):
    rc, obj = _run_boundary(boundary, monkeypatch, capsys, "echo x >> lib/a.dart")
    assert rc == 2
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------- test-timeout-pre ----------

def test_timeout_pre_test_command_emits_nothing(monkeypatch, capsys, tmp_path):
    pre = _load("ttp_no_allow", HOOKS_DIR / "test-timeout-pre.py")
    monkeypatch.setattr(pre, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(pre, "read_json_from_stdin", lambda _l: {
        "tool_name": "Bash", "tool_use_id": "tu-1",
        "tool_input": {"command": "uv run pytest -q tests/"},
    })
    assert pre.main() == 0
    assert capsys.readouterr().out == ""
    monitor_dir = tmp_path / ".claude" / "hook-logs" / "test-monitor"
    assert list(monitor_dir.glob("*.json")), "監控檔仍須寫入"


# ---------- bash-edit-guard ----------

@pytest.fixture(scope="module")
def edit_guard():
    return _load("beg_no_allow", HOOKS_DIR / "bash-edit-guard-hook.py")


def _run_edit_guard(edit_guard, monkeypatch, capsys, command):
    _stdin(monkeypatch, {"tool_name": "Bash", "tool_input": {"command": command}})
    rc = edit_guard.main()
    return rc, _parse(capsys.readouterr().out)


def test_edit_guard_sed_inplace_context_without_decision(edit_guard, monkeypatch, capsys):
    rc, obj = _run_edit_guard(edit_guard, monkeypatch, capsys, "sed -i 's/a/b/' f.txt")
    assert rc == 0
    hso = obj["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hso["additionalContext"]


def test_edit_guard_positive_control_bare_cd_denied(edit_guard, monkeypatch, capsys):
    _, obj = _run_edit_guard(edit_guard, monkeypatch, capsys, "cd subdir && ls")
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------- acceptance-gate ----------

@pytest.fixture(scope="module")
def gate():
    return _load("gate_no_allow", GATE_PATH)


def test_gate_non_ticket_command_emits_nothing(gate, monkeypatch, capsys):
    _stdin(monkeypatch, {"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    gate.main()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("should_block,expected", [(False, None), (True, "deny")])
def test_gate_generate_output_decision(gate, logger, tmp_path, should_block, expected):
    result = gate.AcceptanceCheckResult(
        should_block, True, None, False, [],
        block_source="children" if should_block else "",
    )
    output = gate.generate_hook_output("0.1.0-W1-001", result, tmp_path, logger, is_subagent=True)
    assert output["hookSpecificOutput"].get("permissionDecision") == expected
