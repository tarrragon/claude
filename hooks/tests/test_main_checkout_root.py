"""MR（主 checkout 根）取法與 isolated-subagent 判定的測試（3.3.0-W1-204.1.5.2）。

用真實 git worktree（MAIN 與 sibling WT、.claude/worktrees 內 WT），不 monkeypatch 根。
"""

import importlib.util
import json
import logging
import subprocess
from pathlib import Path

import pytest

from lib import dispatch_tracker
from lib.hook_base import get_main_checkout_root

HOOK_FILE = Path(__file__).parent.parent / "isolated-subagent-main-write-guard-hook.py"
_spec = importlib.util.spec_from_file_location("isolated_guard_mr", HOOK_FILE)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

AGENT_ID = "a8a4e24138605a3d3"


def _git(*args, cwd):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git("init", "-q", "-b", "main", cwd=main)
    _git("-c", "user.email=a@b", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i", cwd=main)
    (main / ".claude").mkdir()
    sibling = tmp_path / "main-sibling"
    inside = main / ".claude" / "worktrees" / "agent-x"
    _git("worktree", "add", "-q", "-b", "sib", str(sibling), cwd=main)
    _git("worktree", "add", "-q", "-b", "ins", str(inside), cwd=main)
    return {"main": main, "sibling": sibling.resolve(), "inside": inside.resolve()}


@pytest.fixture
def log():
    return logging.getLogger("test-mr")


def _entry():
    return {"agent_description": "d", "agent_id": AGENT_ID, "agent_handle": "",
            "branch_name": "worktree", "ticket_id": "T", "turn_ended_at": None}


def _write_state(main, entries):
    (main / ".claude" / "dispatch-active.json").write_text(json.dumps({"dispatches": entries}), encoding="utf-8")
    dispatch_tracker.reset_cache()


class TestGetMainCheckoutRoot:
    def test_from_main(self, repo):
        assert get_main_checkout_root(repo["main"]) == repo["main"]

    def test_from_sibling_worktree(self, repo):
        assert get_main_checkout_root(repo["sibling"]) == repo["main"]

    def test_from_worktree_inside_claude_worktrees(self, repo):
        assert get_main_checkout_root(repo["inside"]) == repo["main"]

    def test_from_file_path_in_sibling(self, repo):
        assert get_main_checkout_root(repo["sibling"] / ".claude" / "x.md") == repo["main"]

    def test_non_repo_returns_none(self, tmp_path):
        assert get_main_checkout_root(tmp_path / "nowhere") is None


class TestIsolatedGuardSiblingWorktree:
    def test_resolve_main_root_from_sibling_cwd_is_main(self, repo):
        assert hook.resolve_main_root(str(repo["sibling"])) == repo["main"]

    def test_positive_write_main_denied_from_sibling(self, repo, log):
        _write_state(repo["main"], [_entry()])
        main_root = hook.resolve_main_root(str(repo["sibling"]))
        payload = {"agent_id": AGENT_ID, "tool_name": "Write", "cwd": str(repo["sibling"]),
                   "tool_input": {"file_path": str(repo["main"] / "docs" / "a.md")}}
        assert hook.evaluate(payload, main_root, log) is not None

    def test_negative_write_own_worktree_allowed(self, repo, log):
        _write_state(repo["main"], [_entry()])
        main_root = hook.resolve_main_root(str(repo["sibling"]))
        payload = {"agent_id": AGENT_ID, "tool_name": "Write", "cwd": str(repo["sibling"]),
                   "tool_input": {"file_path": str(repo["sibling"] / "docs" / "a.md")}}
        assert hook.evaluate(payload, main_root, log) is None

    def test_inside_claude_worktrees_unchanged(self, repo, log):
        _write_state(repo["main"], [_entry()])
        main_root = hook.resolve_main_root(str(repo["inside"]))
        assert main_root == repo["main"]
        own = {"agent_id": AGENT_ID, "tool_name": "Write", "cwd": str(repo["inside"]),
               "tool_input": {"file_path": str(repo["inside"] / "docs" / "a.md")}}
        assert hook.evaluate(own, main_root, log) is None


DISPATCH_HOOK = Path(__file__).parents[2] / "skills" / "ticket" / "hooks" / "agent-dispatch-validation-hook.py"
_dspec = importlib.util.spec_from_file_location("dispatch_validation_mr", DISPATCH_HOOK)
dispatch = importlib.util.module_from_spec(_dspec)
_dspec.loader.exec_module(dispatch)


class TestDispatchValidationMainRoot:
    """判定 2：.claude 路徑是否屬主 repo（hook 專案根 AR 在 .claude/worktrees 內時）。"""

    def test_claude_path_under_mr_from_inside_worktree_is_main(self, repo):
        path = str(repo["main"] / ".claude" / "hooks" / "x.py")
        assert dispatch._classify_paths([path], str(repo["inside"])) == (True, False, False)

    def test_sibling_claude_path_from_sibling_is_main(self, repo):
        path = str(repo["sibling"] / ".claude" / "hooks" / "x.py")
        assert dispatch._classify_paths([path], str(repo["sibling"])) == (True, False, False)

    def test_root_at_main_sibling_claude_path_is_main(self, repo, monkeypatch):
        """hook 根在 MAIN、指向同層 sibling worktree 的 .claude：新舊皆 main（不變）。"""
        path = str(repo["sibling"] / ".claude" / "hooks" / "x.py")
        assert dispatch._classify_paths([path], str(repo["main"])) == (True, False, False)
        monkeypatch.setattr(dispatch, "get_project_root", lambda: repo["main"])
        assert dispatch._classify_prompt_paths("edit " + path) == (True, False, False)

    def test_other_repo_claude_path_stays_external(self, repo, tmp_path):
        other = tmp_path / "other"
        (other / ".claude").mkdir(parents=True)
        _git("init", "-q", cwd=other)
        path = str(other / ".claude" / "x.py")
        assert dispatch._classify_paths([path], str(repo["inside"])) == (False, True, False)

    def test_outside_parent_worktree_stays_external(self, repo, tmp_path):
        """ARCH-015：不在 MR 樹內、也不與 MR 同層的 worktree 維持阻擋。"""
        far = tmp_path / "deep" / "far"
        far.parent.mkdir()
        _git("worktree", "add", "-q", "-b", "far", str(far), cwd=repo["main"])
        path = str(far.resolve() / ".claude" / "x.py")
        assert dispatch._classify_paths([path], str(repo["main"])) == (False, True, False)
