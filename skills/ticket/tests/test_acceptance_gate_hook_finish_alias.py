"""acceptance-gate-hook 辨識 finish 別名與 heredoc 誤判（0.5.0-W1-270.2）。"""
import importlib.util
import io
import json
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

TICKET_ID = "0.0.0-W1-900"
BODY = """---
id: 0.0.0-W1-900
title: t
type: IMP
status: in_progress
version: 0.0.0
priority: P2
acceptance:
- '{mark} a'
- '{mark} b'
---

## Solution

x
"""


def _load():
    path = Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook_fa", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _write_ticket(root: Path, mark: str):
    d = root / "docs" / "work-logs" / "v0.0.0" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    (d / (TICKET_ID + ".md")).write_text(BODY.format(mark=mark), encoding="utf-8")


@pytest.mark.parametrize("cmd", [
    "ticket track complete X",
    "ticket track finish X",
    "ticket track batch-complete X",
    "env A=1 nohup ticket track finish X",
    "git add a && ticket track finish X",
])
def test_completion_commands_recognized(cmd):
    assert _load().is_complete_command(cmd) is True


@pytest.mark.parametrize("cmd", [
    'ticket track create --why "run ticket track finish later"',
    "ticket track append-log X --section S \"$(cat <<'EOF'\nticket track finish X\nEOF\n)\"",
    "ticket track append-log X --section S \"$(cat <<'EOF'\nticket track complete X\nEOF\n)\"",
    "echo hi",
])
def test_non_completion_commands_ignored(cmd):
    assert _load().is_complete_command(cmd) is False


def test_unparsable_command_fail_closed():
    # 未閉合引號：解析失敗時退回字面比對，完成類命令仍視為完成命令
    assert _load().is_complete_command("ticket track finish X 'oops") is True


def test_chained_write_detection_with_finish():
    m = _load()
    assert m.detect_chained_pre_complete_write(
        "ticket track set-acceptance X --check 1 && ticket track finish X") is True
    assert m.detect_chained_pre_complete_write("ticket track finish X") is False


def _run_main(module, command):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    with patch.object(module, "read_json_from_stdin", return_value=payload), \
         patch.object(module, "save_check_log"):
        return module.main()


CHILD_ID = TICKET_ID + ".1"
PARENT_WITH_CHILD = BODY.replace("priority: P2", "priority: P2\nchildren: [" + CHILD_ID + "]")
CHILD_BODY = """---
id: 0.0.0-W1-900.1
title: child
type: IMP
status: pending
version: 0.0.0
children: []
---

# Body
"""


def _write_pending_child(root: Path):
    d = root / "docs" / "work-logs" / "v0.0.0" / "tickets"
    (d / (CHILD_ID + ".md")).write_text(CHILD_BODY, encoding="utf-8")


def _decision(out: str) -> str:
    """取最後一個 JSON 物件的 permissionDecision。"""
    dec = json.loads(out[out.rindex("\n{") + 1:] if "\n{" in out else out)
    return dec["hookSpecificOutput"]["permissionDecision"]


def test_finish_blocked_by_pending_children_E2(tmp_path):
    """正向對照：children 未完成時 finish 被擋（修正前 Fast-path skip 放行）。"""
    module = _load()
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    (root / "CLAUDE.md").write_text("x", encoding="utf-8")
    _write_ticket(root, "[x]")
    (root / "docs/work-logs/v0.0.0/tickets" / (TICKET_ID + ".md")).write_text(
        PARENT_WITH_CHILD.format(mark="[x]"), encoding="utf-8")
    _write_pending_child(root)
    payload = {"tool_name": "Bash", "tool_input": {"command": "ticket track finish " + TICKET_ID}}
    buf = io.StringIO()
    with patch.object(module, "read_json_from_stdin", return_value=payload), \
         patch.object(module, "get_project_root", return_value=root), \
         patch.object(module, "save_check_log"), \
         redirect_stdout(buf):
        module.main()
    assert _decision(buf.getvalue()) == "deny", buf.getvalue()


def test_finish_in_linked_worktree_blocked_by_main_ticket_children(tmp_path, monkeypatch):
    """組合情境：主倉庫票面有未完成 children，worktree 舊副本沒有；
    finish 必須讀主倉庫票面而被擋（讀到副本會放行）。"""
    module = _load()
    from lib import hook_base
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("x", encoding="utf-8")
    _write_ticket(main, "[x]")  # 副本：無 children
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    (main / "docs/work-logs/v0.0.0/tickets" / (TICKET_ID + ".md")).write_text(
        PARENT_WITH_CHILD.format(mark="[x]"), encoding="utf-8")
    _write_pending_child(main)
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(wt)
    hook_base.clear_project_root_cache()
    payload = {"tool_name": "Bash", "tool_input": {"command": "ticket track finish " + TICKET_ID}}
    buf = io.StringIO()
    try:
        with patch.object(module, "read_json_from_stdin", return_value=payload), \
             patch.object(module, "save_check_log"), \
             redirect_stdout(buf):
            module.main()
    finally:
        hook_base.clear_project_root_cache()
    assert _decision(buf.getvalue()) == "deny", buf.getvalue()
