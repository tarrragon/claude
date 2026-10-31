"""
cleanup --branch 與掃描報告建議指令的可執行性（0.5.0-W1-348, PC-GPD-034）

主防線：掃描端實際產出的建議指令，拆成 argv 餵回 main() 的 parser，
斷言可解析並定位到該 worktree。
"""

import shlex
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import cleanup_command  # noqa: E402
import worktree_manager  # noqa: E402
from cleanup_command import cmd_cleanup  # noqa: E402
from worktree_manager import main  # noqa: E402

AGENT_BRANCH = "worktree-agent-a1b2c3d4"
AGENT_PATH = "/path/.claude/worktrees/agent-a1b2c3d4"
TICKET_BRANCH = "feat/0.1.1-W9-001"
TICKET_PATH = "/path/ccsession-0.1.1-W9-001"


@pytest.fixture
def env(monkeypatch):
    """兩個 worktree（agent 分支 + ticket 分支），三閘門全過，記錄實際清理的 path。"""
    removed = []
    worktrees = [
        {"path": "/path/ccsession", "branch": "main"},
        {"path": AGENT_PATH, "branch": AGENT_BRANCH},
        {"path": TICKET_PATH, "branch": TICKET_BRANCH},
    ]
    monkeypatch.setattr("worktree_manager.get_worktree_list", lambda: worktrees)
    monkeypatch.setattr("cleanup_command.get_worktree_list", lambda: worktrees)
    monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", lambda p: 0)
    monkeypatch.setattr("cleanup_command._is_branch_pushed", lambda b: True)
    monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", lambda b, base="main": True)

    def fake_execute(path, branch, unlock=False):
        removed.append((path, branch))
        return True, "ok"

    monkeypatch.setattr("cleanup_command._cleanup_execute", fake_execute)
    return removed


def _suggested_commands(capsys):
    out = capsys.readouterr().out
    return [l.strip() for l in out.splitlines() if "/worktree cleanup" in l]


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["worktree_manager.py"] + argv)
    return main()


class TestSuggestedCommandRoundTrip:
    def test_scan_suggestion_for_agent_branch_parses_and_locates(self, env, monkeypatch, capsys):
        """主防線：掃描建議指令照原文執行，可解析並清理到該 worktree"""
        assert cleanup_command._cleanup_scan_all() == 0
        cmds = [c for c in _suggested_commands(capsys) if AGENT_BRANCH in c]
        assert cmds, "掃描報告應對 agent 分支印出建議指令"
        for cmd in cmds:
            argv = shlex.split(cmd.split("：", 1)[-1])
            assert argv[0] == "/worktree"
            capsys.readouterr()
            env.clear()
            code = _run_main(monkeypatch, argv[1:])
            out = capsys.readouterr().out
            assert code == 0, out
            assert "INVALID" not in out and "格式" not in out
            assert env == [(AGENT_PATH, AGENT_BRANCH)]

    def test_scan_suggestion_for_ticket_unchanged(self, env, capsys):
        """E2：ticket 分支仍印 ticket ID 用法，不帶 --branch"""
        cleanup_command._cleanup_scan_all()
        cmds = [c for c in _suggested_commands(capsys) if "0.1.1-W9-001" in c]
        assert cmds and all("--branch" not in c for c in cmds)

    def test_force_suggestion_for_agent_branch_parses(self, env, monkeypatch, capsys):
        """warnings 清單（未合併）的 --force 建議同樣可解析"""
        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", lambda b, base="main": False)
        cleanup_command._cleanup_scan_all()
        cmds = [c for c in _suggested_commands(capsys) if AGENT_BRANCH in c and "--force" in c]
        assert cmds
        argv = shlex.split(cmds[0].split("：", 1)[-1])
        capsys.readouterr()
        assert _run_main(monkeypatch, argv[1:]) == 0
        assert env == [(AGENT_PATH, AGENT_BRANCH)]


class TestCleanupBranchOption:
    def test_branch_cleans_matching_worktree(self, env):
        assert cmd_cleanup(None, branch=AGENT_BRANCH) == 0
        assert env == [(AGENT_PATH, AGENT_BRANCH)]

    def test_unknown_branch_reports_not_found(self, env, capsys):
        """E2 正向對照：亂寫的分支名仍須報找不到，且不清理任何東西"""
        assert cmd_cleanup(None, branch="worktree-agent-nope") == 1
        assert "找不到" in capsys.readouterr().out
        assert env == []

    def test_branch_and_ticket_id_mutually_exclusive(self, env, monkeypatch, capsys):
        code = _run_main(monkeypatch, ["cleanup", "0.1.1-W9-001", "--branch", AGENT_BRANCH])
        assert code == 1
        assert env == []

    def test_ticket_id_usage_unchanged(self, env):
        assert cmd_cleanup("0.1.1-W9-001") == 0
        assert env == [(TICKET_PATH, TICKET_BRANCH)]

    def test_branch_level1_gate_not_bypassed(self, env, monkeypatch):
        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", lambda p: 2)
        assert cmd_cleanup(None, force=True, branch=AGENT_BRANCH) == 1
        assert env == []
