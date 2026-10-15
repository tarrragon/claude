"""acceptance-gate-hook 在 linked worktree 內讀主倉庫票面（0.5.0-W1-264.1）。

主倉庫票面 acceptance 全勾、worktree 副本全未勾；gate 必須讀到主倉庫那份。
"""
import importlib.util
import logging
import subprocess
from pathlib import Path

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


def _load_hook_module():
    path = Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook_wt", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _ticket_path(root: Path) -> Path:
    d = root / "docs" / "work-logs" / "v0.0.0" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    return d / (TICKET_ID + ".md")


@pytest.fixture
def worktree_pair(tmp_path, monkeypatch):
    _load_hook_module()  # 副作用：把 .claude 加入 sys.path 供 import lib
    from lib import hook_base

    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("x", encoding="utf-8")
    _ticket_path(main).write_text(BODY.format(mark="[ ]"), encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    # 主倉庫票面推進為全勾；worktree 副本維持舊的全未勾
    _ticket_path(main).write_text(BODY.format(mark="[x]"), encoding="utf-8")
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(wt)
    hook_base.clear_project_root_cache()
    yield main, wt
    hook_base.clear_project_root_cache()


def _check(module, root):
    return module.check_acceptance_status(
        TICKET_ID, root, logging.getLogger("t"), "ticket track complete " + TICKET_ID
    )


def test_gate_reads_main_repo_ticket_from_worktree(worktree_pair):
    from lib.hook_base import get_project_root, get_shared_state_root

    main, wt = worktree_pair
    module = _load_hook_module()
    assert get_project_root() == wt
    state_root = get_shared_state_root(get_project_root())
    assert state_root == main

    # 對照輸入：worktree 舊副本（全未勾）與主倉庫（全勾）的判定必須不同
    stale = _check(module, wt)
    fresh = _check(module, state_root)
    assert stale.has_acceptance != fresh.has_acceptance or stale.message != fresh.message


def test_main_entry_uses_shared_state_root(worktree_pair):
    """main() 的 project_dir 來源：模擬 get_project_root 回 worktree 時仍取主倉庫。"""
    main, wt = worktree_pair
    module = _load_hook_module()
    seen = {}

    def spy(ticket_id, project_dir, logger, command=""):
        seen["dir"] = project_dir
        return module.AcceptanceCheckResult(False, True, None, False, [])

    payload = {"tool_name": "Bash", "tool_input": {"command": "ticket track complete " + TICKET_ID}}
    from unittest.mock import patch

    with patch.object(module, "read_json_from_stdin", return_value=payload), \
         patch.object(module, "check_acceptance_status", side_effect=spy), \
         patch.object(module, "save_check_log"):
        module.main()
    assert seen["dir"] == main
