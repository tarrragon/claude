"""
session-start-merged-worktree-audit-hook 孤兒 worktree-agent 分支偵測測試（0.32.0-W3-021）

涵蓋三路徑：
- ahead=0：無對應 worktree 的孤兒分支 → 列建議 git branch -d
- ahead>0：含未落地 commit → 標記需人工確認，不建議直接刪
- 無孤兒：所有 agent 分支仍有對應 worktree（或無 agent 分支）→ 不列入訊息
"""

import importlib.util
import logging
from pathlib import Path

import pytest

# 動態導入 hook（檔案名含 dash）
_HOOK_FILE = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "session-start-merged-worktree-audit-hook.py"
)
_spec = importlib.util.spec_from_file_location(
    "session_start_merged_worktree_audit_hook", _HOOK_FILE
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


@pytest.fixture
def logger():
    return logging.getLogger("test-orphan-agent-branch")


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_fake_run(agent_branches, worktree_branches, unmerged_map):
    """建立統一的 fake subprocess.run。

    agent_branches: git branch --list 回傳的分支名
    worktree_branches: git worktree list --porcelain 中仍存在的分支
    unmerged_map: {branch: [unmerged commit lines]}
    """

    def fake_run(cmd, **kwargs):
        if "branch" in cmd and "--list" in cmd:
            return FakeProc(returncode=0, stdout="\n".join(agent_branches) + "\n")
        if "worktree" in cmd and "list" in cmd:
            out_lines = []
            for br in worktree_branches:
                out_lines.append(f"worktree /repo/.claude/worktrees/{br}")
                out_lines.append(f"branch refs/heads/{br}")
                out_lines.append("")
            return FakeProc(returncode=0, stdout="\n".join(out_lines) + "\n")
        if "log" in cmd:
            # cmd 形如 ["git", "log", "main..<branch>", "--oneline"]
            target = cmd[2].split("..", 1)[1]
            lines = unmerged_map.get(target, [])
            return FakeProc(returncode=0, stdout="\n".join(lines))
        return FakeProc(returncode=0, stdout="")

    return fake_run


class TestCollectOrphanAgentBranches:
    def test_ahead_zero_orphan_listed_as_deletable(self, monkeypatch, logger):
        """孤兒分支 ahead=0：列入並標記可安全刪除（has_unmerged=False）。"""
        fake_run = _make_fake_run(
            agent_branches=["worktree-agent-abc"],
            worktree_branches=["main"],  # 無對應 worktree
            unmerged_map={},  # ahead=0
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == [("worktree-agent-abc", False)]

    def test_ahead_positive_orphan_marked_unmerged(self, monkeypatch, logger):
        """孤兒分支 ahead>0：列入並標記含未落地 commit（has_unmerged=True）。"""
        fake_run = _make_fake_run(
            agent_branches=["worktree-agent-xyz"],
            worktree_branches=["main"],
            unmerged_map={"worktree-agent-xyz": ["abc123 wip commit"]},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == [("worktree-agent-xyz", True)]

    def test_no_orphan_when_branch_has_active_worktree(self, monkeypatch, logger):
        """agent 分支仍有對應 worktree：不視為孤兒，回傳空。"""
        fake_run = _make_fake_run(
            agent_branches=["worktree-agent-live"],
            worktree_branches=["main", "worktree-agent-live"],
            unmerged_map={},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == []

    def test_no_orphan_when_no_agent_branches(self, monkeypatch, logger):
        """無任何 agent 分支：回傳空。"""
        fake_run = _make_fake_run(
            agent_branches=[],
            worktree_branches=["main"],
            unmerged_map={},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == []


class TestBuildMessageOrphanBranches:
    def test_ahead_zero_shows_branch_d_suggestion(self):
        """ahead=0 孤兒分支：訊息含 git branch -d 建議。"""
        msg = hook.build_message([], [], [("worktree-agent-abc", False)])
        assert "孤兒 worktree-agent-* 分支" in msg
        assert "ahead=0 可安全刪除" in msg
        assert "git branch -d worktree-agent-abc" in msg

    def test_ahead_positive_marks_unmerged_no_delete(self):
        """ahead>0 孤兒分支：標記需人工確認，不含直接刪除指令。"""
        msg = hook.build_message([], [], [("worktree-agent-xyz", True)])
        assert "含未落地 commit" in msg
        assert "需人工確認" in msg
        assert "git branch -d worktree-agent-xyz" not in msg

    def test_no_orphan_branches_no_section(self):
        """無孤兒分支：訊息不含本 section。"""
        msg = hook.build_message([], [], [])
        assert "孤兒 worktree-agent-* 分支" not in msg
