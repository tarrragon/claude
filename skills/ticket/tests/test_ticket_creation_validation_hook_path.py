"""ticket-creation-validation-hook 票檔路徑判斷與日誌位置測試。

對照組：
- E1：三層階層路徑的新票缺 decision_tree_path 時觸發
- E2：tickets 目錄外的 md 不觸發
- 單層路徑仍觸發
"""

import importlib.util
import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[1] / "hooks" / "ticket-creation-validation-hook.py"
)

NO_DTP = "---\nid: 0.5.0-W1-999\ntype: IMP\nparent_id: null\n---\n# x"


@pytest.fixture(scope="module")
def hook_module():
    spec = importlib.util.spec_from_file_location("ticket_creation_validation_hook", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(file_path: str, content: str = NO_DTP):
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout


def _context(stdout: str) -> str:
    return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize(
    "path,expected",
    [
        ("docs/work-logs/v0/v0.5/v0.5.0/tickets/0.5.0-W1-999.md", True),  # E1
        ("docs/work-logs/v0.5.0/tickets/0.5.0-W1-999.md", True),  # 單層
        ("/abs/proj/docs/work-logs/v0/v0.5/v0.5.0/tickets/a.md", True),
        ("docs/work-logs/v0/v0.5/v0.5.0/notes.md", False),  # E2 tickets 外
        ("docs/work-logs/tickets/a.md", False),  # 無版本目錄
        ("docs/work-logs/v0.5.0/tickets/sub/a.md", False),  # tickets 之後有子目錄
        ("docs/other/v0.5.0/tickets/a.md", False),
    ],
)
def test_is_ticket_file(hook_module, path, expected):
    assert hook_module.is_ticket_file(Path(path)) is expected


def test_e1_three_level_path_triggers(hook_module):
    rc, out = _run("docs/work-logs/v0/v0.5/v0.5.0/tickets/0.5.0-W1-999.md")
    assert rc == 0
    assert "decision_tree_path" in _context(out)


def test_single_level_path_still_triggers():
    rc, out = _run("docs/work-logs/v0.5.0/tickets/0.5.0-W1-999.md")
    assert rc == 0
    assert "decision_tree_path" in _context(out)


def test_e2_outside_tickets_dir_silent():
    rc, out = _run("docs/work-logs/v0/v0.5/v0.5.0/notes.md")
    assert rc == 0
    assert out.strip() == ""


def test_log_goes_to_project_hook_logs_not_home(hook_module):
    paths = [
        Path(h.baseFilename).resolve()
        for h in logging.getLogger("ticket-creation-validation").handlers
        if isinstance(h, logging.FileHandler)
    ]
    assert paths, "應有 FileHandler"
    for p in paths:
        assert ".claude/hook-logs/ticket-creation-validation" in p.as_posix()
        assert not p.is_relative_to(Path.home() / ".claude" / "hook-logs")
