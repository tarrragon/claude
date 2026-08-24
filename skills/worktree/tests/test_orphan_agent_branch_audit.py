"""
session-start-merged-worktree-audit-hook 孤兒分支偵測測試（0.32.0-W3-021 擴充）

涵蓋路徑：
- ahead=0：無對應 worktree 的孤兒分支 → 列建議 git branch -d
- ahead>0：含未落地 commit → 標記需人工確認，不建議直接刪
- 無孤兒：所有分支仍有對應 worktree（或無分支）→ 不列入訊息
- 人工命名分支（非 worktree-agent-* 前綴）：ahead=0 / ahead>0 兩種情境
- 保護分支（main/master）與當前 checkout 分支排除在掃描外
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


def _make_fake_run(local_branches, worktree_branches, unmerged_map, current_branch="main"):
    """建立統一的 fake subprocess.run。

    local_branches: git branch --list 回傳的所有本地分支名
    worktree_branches: git worktree list --porcelain 中仍存在的分支
    unmerged_map: {branch: [unmerged commit lines]}
    current_branch: git branch --show-current 回傳的當前分支
    """

    def fake_run(cmd, **kwargs):
        if "branch" in cmd and "--show-current" in cmd:
            return FakeProc(returncode=0, stdout=current_branch + "\n")
        if "branch" in cmd and "--list" in cmd:
            return FakeProc(returncode=0, stdout="\n".join(local_branches) + "\n")
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
        """孤兒 agent 分支 ahead=0：列入並標記可安全刪除（has_unmerged=False，agent 前綴）。"""
        fake_run = _make_fake_run(
            local_branches=["main", "worktree-agent-abc"],
            worktree_branches=["main"],  # 無對應 worktree
            unmerged_map={},  # ahead=0
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == [("worktree-agent-abc", False, True)]

    def test_ahead_positive_orphan_marked_unmerged(self, monkeypatch, logger):
        """孤兒 agent 分支 ahead>0：列入並標記含未落地 commit（has_unmerged=True，agent 前綴）。"""
        fake_run = _make_fake_run(
            local_branches=["main", "worktree-agent-xyz"],
            worktree_branches=["main"],
            unmerged_map={"worktree-agent-xyz": ["abc123 wip commit"]},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == [("worktree-agent-xyz", True, True)]

    def test_no_orphan_when_branch_has_active_worktree(self, monkeypatch, logger):
        """agent 分支仍有對應 worktree：不視為孤兒，回傳空。"""
        fake_run = _make_fake_run(
            local_branches=["main", "worktree-agent-live"],
            worktree_branches=["main", "worktree-agent-live"],
            unmerged_map={},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == []

    def test_no_orphan_when_no_extra_branches(self, monkeypatch, logger):
        """本地分支僅剩 main：回傳空。"""
        fake_run = _make_fake_run(
            local_branches=["main"],
            worktree_branches=["main"],
            unmerged_map={},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == []

    def test_manual_named_branch_ahead_zero_listed_as_deletable(self, monkeypatch, logger):
        """人工命名孤兒分支 ahead=0：列入並標記可安全刪除（is_agent_prefixed=False）。"""
        fake_run = _make_fake_run(
            local_branches=["main", "feat/manual-work"],
            worktree_branches=["main"],
            unmerged_map={},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == [("feat/manual-work", False, False)]

    def test_manual_named_branch_ahead_positive_marked_unmerged(self, monkeypatch, logger):
        """人工命名孤兒分支 ahead>0（本次事件形態：5 個未合併 commit）：標記需人工確認。"""
        fake_run = _make_fake_run(
            local_branches=["main", "w4-002-work"],
            worktree_branches=["main"],
            unmerged_map={
                "w4-002-work": [
                    "c1 commit 1",
                    "c2 commit 2",
                    "c3 commit 3",
                    "c4 commit 4",
                    "c5 commit 5",
                ]
            },
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == [("w4-002-work", True, False)]

    def test_protected_branches_excluded(self, monkeypatch, logger):
        """main / master 為保護分支：即使無對應 worktree 也不列入。"""
        fake_run = _make_fake_run(
            local_branches=["main", "master"],
            worktree_branches=[],  # 兩者皆無對應 worktree
            unmerged_map={},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == []

    def test_current_checkout_branch_excluded(self, monkeypatch, logger):
        """當前 checkout 分支（非 worktree list 中）不視為孤兒。"""
        fake_run = _make_fake_run(
            local_branches=["main", "wip-current"],
            worktree_branches=["main"],  # wip-current 無對應 worktree entry
            unmerged_map={},
            current_branch="wip-current",
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == []


class TestGetUnmergedCommitsFailurePaths:
    """get_unmerged_commits 三種失敗路徑：判定失敗須回傳 None，不得等同 ahead=0。"""

    def test_timeout_returns_none(self, monkeypatch, logger):
        import subprocess as real_subprocess

        def fake_run(cmd, **kwargs):
            raise real_subprocess.TimeoutExpired(cmd=cmd, timeout=10)

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.get_unmerged_commits("some-branch", logger)
        assert result is None

    def test_file_not_found_returns_none(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.get_unmerged_commits("some-branch", logger)
        assert result is None

    def test_nonzero_returncode_returns_none(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            return FakeProc(returncode=128, stdout="", stderr="fatal: bad revision")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.get_unmerged_commits("some-branch", logger)
        assert result is None

    def test_success_empty_returns_empty_list_not_none(self, monkeypatch, logger):
        """判定成功且 ahead=0 時回傳空清單，與判定失敗（None）明確區分。"""
        def fake_run(cmd, **kwargs):
            return FakeProc(returncode=0, stdout="")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.get_unmerged_commits("some-branch", logger)
        assert result == []
        assert result is not None


class TestCollectOrphanAgentBranchesUndetermined:
    def test_undetermined_branch_not_marked_deletable(self, monkeypatch, logger):
        """git log 判定失敗（returncode 非 0）的孤兒分支：ahead_state=None，不得等同 ahead=0。"""

        def fake_run(cmd, **kwargs):
            if "branch" in cmd and "--show-current" in cmd:
                return FakeProc(returncode=0, stdout="main\n")
            if "branch" in cmd and "--list" in cmd:
                return FakeProc(returncode=0, stdout="main\nworktree-agent-broken\n")
            if "worktree" in cmd and "list" in cmd:
                return FakeProc(
                    returncode=0,
                    stdout="worktree /repo/.claude/worktrees/main\nbranch refs/heads/main\n\n",
                )
            if "log" in cmd:
                return FakeProc(returncode=128, stdout="", stderr="fatal: bad revision")
            return FakeProc(returncode=0, stdout="")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans == [("worktree-agent-broken", None, True)]


class TestOrphanBranchesReasonOut:
    """collect_orphan_agent_branches 的 reason_out 須依實際失敗點回填不同代碼，
    build_message 依代碼輸出可區分的訊息文字（非固定單一原因）。"""

    def test_local_branches_failure_sets_reason(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            if "branch" in cmd and "--list" in cmd:
                return FakeProc(returncode=128, stdout="", stderr="fatal")
            return FakeProc(returncode=0, stdout="")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        reason_out = {}
        result = hook.collect_orphan_agent_branches(logger, reason_out=reason_out)
        assert result is None
        assert reason_out["reason"] == hook.ORPHAN_BRANCHES_REASON_LOCAL_BRANCHES

    def test_worktree_branches_failure_sets_reason(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            if "branch" in cmd and "--show-current" in cmd:
                return FakeProc(returncode=0, stdout="main\n")
            if "branch" in cmd and "--list" in cmd:
                return FakeProc(returncode=0, stdout="main\nworktree-agent-abc\n")
            if "worktree" in cmd and "list" in cmd:
                return FakeProc(returncode=128, stdout="", stderr="fatal")
            return FakeProc(returncode=0, stdout="")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        reason_out = {}
        result = hook.collect_orphan_agent_branches(logger, reason_out=reason_out)
        assert result is None
        assert reason_out["reason"] == hook.ORPHAN_BRANCHES_REASON_WORKTREE_BRANCHES

    def test_current_branch_failure_sets_reason(self, monkeypatch, logger):
        fake_run = _make_fake_run(
            local_branches=["main", "wip-current"],
            worktree_branches=["main"],
            unmerged_map={},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        monkeypatch.setattr(hook, "get_current_branch", lambda: None)
        reason_out = {}
        result = hook.collect_orphan_agent_branches(logger, reason_out=reason_out)
        assert result is None
        assert reason_out["reason"] == hook.ORPHAN_BRANCHES_REASON_CURRENT_BRANCH

    def test_build_message_reason_texts_are_distinct(self):
        """三種失敗因的訊息文字必須互不相同，且各自對應正確的指令名稱。"""
        msg_local = hook.build_message(
            [], [], [], orphan_branches_undetermined=True,
            orphan_branches_reason=hook.ORPHAN_BRANCHES_REASON_LOCAL_BRANCHES,
        )
        msg_worktree = hook.build_message(
            [], [], [], orphan_branches_undetermined=True,
            orphan_branches_reason=hook.ORPHAN_BRANCHES_REASON_WORKTREE_BRANCHES,
        )
        msg_current = hook.build_message(
            [], [], [], orphan_branches_undetermined=True,
            orphan_branches_reason=hook.ORPHAN_BRANCHES_REASON_CURRENT_BRANCH,
        )

        assert "git branch --list" in msg_local
        assert "git worktree list" not in msg_local

        assert "git worktree list" in msg_worktree
        assert "git branch --list" not in msg_worktree

        assert "當前 checkout 分支" in msg_current
        assert "git worktree list" not in msg_current
        assert "git branch --list" not in msg_current

        assert msg_local != msg_worktree != msg_current

    def test_build_message_unknown_reason_falls_back_to_generic(self):
        """未提供 reason（既有呼叫端）時，沿用原本的通用訊息，維持相容輸出。"""
        msg = hook.build_message([], [], [], orphan_branches_undetermined=True)
        assert "無法判定 worktree 分支清單（git worktree list 執行失敗）" in msg


class TestCollectOrphanAgentBranchesCurrentBranchUndetermined:
    """get_current_branch 判定失敗（回傳 None）時：collect_orphan_agent_branches
    須整體中止（回傳 None），不得因排除守衛短路而把當前 checkout 分支誤列孤兒。"""

    def test_current_branch_none_returns_none_not_partial_result(self, monkeypatch, logger):
        fake_run = _make_fake_run(
            local_branches=["main", "wip-current"],
            worktree_branches=["main"],  # wip-current 無對應 worktree entry
            unmerged_map={},
        )
        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        monkeypatch.setattr(hook, "get_current_branch", lambda: None)

        orphans = hook.collect_orphan_agent_branches(logger)
        assert orphans is None

    def test_current_branch_none_wip_branch_not_in_deletable_output(self, monkeypatch, logger):
        """即使 collect_orphan_agent_branches 因故未中止，仍需驗證訊息組裝層不輸出刪除建議。"""
        msg = hook.build_message([], [], [], orphan_branches_undetermined=True)
        assert "無法判定" in msg
        assert "可安全刪除" not in msg
        assert "git branch -d" not in msg


class TestListWorktreeBranchesFailurePaths:
    """list_worktree_branches 三種失敗路徑：判定失敗須回傳 None，不得等同無 worktree。"""

    def test_timeout_returns_none(self, monkeypatch, logger):
        import subprocess as real_subprocess

        def fake_run(cmd, **kwargs):
            raise real_subprocess.TimeoutExpired(cmd=cmd, timeout=10)

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.list_worktree_branches(logger)
        assert result is None

    def test_file_not_found_returns_none(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.list_worktree_branches(logger)
        assert result is None

    def test_nonzero_returncode_returns_none(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            return FakeProc(returncode=128, stdout="", stderr="fatal: not a git repository")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.list_worktree_branches(logger)
        assert result is None

    def test_success_returns_branch_list_not_none(self, monkeypatch, logger):
        """判定成功時回傳分支清單，與判定失敗（None）明確區分。"""
        def fake_run(cmd, **kwargs):
            return FakeProc(
                returncode=0,
                stdout="worktree /repo\nbranch refs/heads/main\n\n",
            )

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.list_worktree_branches(logger)
        assert result == ["main"]
        assert result is not None


class TestCollectOrphanAgentBranchesUndeterminedWorktreeList:
    """list_worktree_branches 判定失敗時：collect_orphan_agent_branches 回傳 None，
    不得輸出任何孤兒分支結論或刪除建議。"""

    def test_worktree_list_failure_returns_none(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            if "branch" in cmd and "--show-current" in cmd:
                return FakeProc(returncode=0, stdout="main\n")
            if "branch" in cmd and "--list" in cmd:
                return FakeProc(returncode=0, stdout="main\nworktree-agent-abc\n")
            if "worktree" in cmd and "list" in cmd:
                return FakeProc(returncode=128, stdout="", stderr="fatal: not a git repository")
            return FakeProc(returncode=0, stdout="")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.collect_orphan_agent_branches(logger)
        assert result is None

    def test_build_message_no_delete_suggestion_when_undetermined(self):
        """判定失敗時的訊息不得含孤兒分支結論或刪除建議，僅說明無法判定。"""
        msg = hook.build_message([], [], [], orphan_branches_undetermined=True)
        assert "無法判定" in msg
        assert "可安全刪除" not in msg
        assert "git branch -d" not in msg
        assert "孤兒分支：" not in msg


class TestBuildMessageOrphanBranches:
    def test_ahead_zero_shows_branch_d_suggestion(self):
        """ahead=0 孤兒分支：訊息含 git branch -d 建議。"""
        msg = hook.build_message([], [], [("worktree-agent-abc", False, True)])
        assert "孤兒分支" in msg
        assert "ahead=0 可安全刪除" in msg
        assert "git branch -d worktree-agent-abc" in msg

    def test_ahead_positive_marks_unmerged_no_delete(self):
        """ahead>0 孤兒分支：標記需人工確認，不含直接刪除指令。"""
        msg = hook.build_message([], [], [("worktree-agent-xyz", True, True)])
        assert "含未落地 commit" in msg
        assert "需人工確認" in msg
        assert "git branch -d worktree-agent-xyz" not in msg

    def test_manual_named_branch_source_labeled(self):
        """人工命名分支訊息需標示與 worktree-agent-* 不同的來源標籤。"""
        msg = hook.build_message(
            [], [],
            [("worktree-agent-abc", False, True), ("w4-002-work", True, False)],
        )
        assert "[worktree-agent-*]" in msg
        assert "[人工命名]" in msg

    def test_no_orphan_branches_no_section(self):
        """無孤兒分支：訊息不含本 section。"""
        msg = hook.build_message([], [], [])
        assert "孤兒分支" not in msg

    def test_undetermined_state_no_delete_suggestion(self):
        """ahead_state=None（判定失敗）：不得輸出可安全刪除或 git branch -d 建議。"""
        msg = hook.build_message([], [], [("worktree-agent-broken", None, True)])
        assert "無法判定" in msg
        assert "需人工確認" in msg
        assert "可安全刪除" not in msg
        assert "git branch -d worktree-agent-broken" not in msg


class TestListLocalBranchesFailurePaths:
    """list_local_branches 三種失敗路徑：判定失敗須回傳 None，不得等同無分支。"""

    def test_timeout_returns_none(self, monkeypatch, logger):
        import subprocess as real_subprocess

        def fake_run(cmd, **kwargs):
            raise real_subprocess.TimeoutExpired(cmd=cmd, timeout=10)

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.list_local_branches(logger)
        assert result is None

    def test_file_not_found_returns_none(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.list_local_branches(logger)
        assert result is None

    def test_nonzero_returncode_returns_none(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            return FakeProc(returncode=128, stdout="", stderr="fatal: not a git repository")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.list_local_branches(logger)
        assert result is None

    def test_success_returns_branch_list_not_none(self, monkeypatch, logger):
        """判定成功時回傳分支清單，與判定失敗（None）明確區分。"""
        def fake_run(cmd, **kwargs):
            return FakeProc(returncode=0, stdout="main\nworktree-agent-abc\n")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.list_local_branches(logger)
        assert result == ["main", "worktree-agent-abc"]
        assert result is not None


class TestCollectOrphanAgentBranchesLocalBranchesUndetermined:
    """list_local_branches 判定失敗時：collect_orphan_agent_branches 須整體中止
    （回傳 None），不得將部分結果或空清單當作正常結論輸出。"""

    def test_local_branches_none_returns_none_not_empty_list(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            if "branch" in cmd and "--show-current" in cmd:
                return FakeProc(returncode=0, stdout="main\n")
            if "branch" in cmd and "--list" in cmd:
                return FakeProc(returncode=128, stdout="", stderr="fatal: bad revision")
            if "worktree" in cmd and "list" in cmd:
                return FakeProc(
                    returncode=0,
                    stdout="worktree /repo/.claude/worktrees/main\nbranch refs/heads/main\n\n",
                )
            return FakeProc(returncode=0, stdout="")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)

        result = hook.collect_orphan_agent_branches(logger)
        assert result is None


class TestParseWorktreeListFailurePaths:
    """parse_worktree_list 判定失敗須回傳 None，不得等同無 worktree。"""

    def test_get_worktree_list_exception_returns_none(self, monkeypatch, logger):
        def fake_get_worktree_list(exclude_main=True):
            raise RuntimeError("git worktree list 失敗")

        monkeypatch.setattr(hook, "get_worktree_list", fake_get_worktree_list)

        result = hook.parse_worktree_list(logger)
        assert result is None

    def test_success_returns_list_not_none(self, monkeypatch, logger):
        def fake_get_worktree_list(exclude_main=True):
            return [{"path": "/repo/.wt/foo", "branch": "foo"}]

        monkeypatch.setattr(hook, "get_worktree_list", fake_get_worktree_list)

        result = hook.parse_worktree_list(logger)
        assert result == [("/repo/.wt/foo", "foo")]
        assert result is not None


class TestCollectMergedUserWorktreesUndetermined:
    """parse_worktree_list 判定失敗時：collect_merged_user_worktrees 須回傳 None，
    不得將判定失敗誤讀為「無 merged worktree」。"""

    def test_parse_worktree_list_none_returns_none(self, monkeypatch, logger):
        monkeypatch.setattr(hook, "parse_worktree_list", lambda logger: None)

        result = hook.collect_merged_user_worktrees(logger)
        assert result is None


class TestCollectModifiedTicketPathsFailurePaths:
    """collect_modified_ticket_paths 判定失敗須回傳 None，不得等同無 modified 檔案。"""

    def test_get_uncommitted_files_exception_returns_none(self, monkeypatch, logger, tmp_path):
        def fake_get_uncommitted_files(cwd=None):
            raise RuntimeError("git status 失敗")

        monkeypatch.setattr(hook, "get_uncommitted_files", fake_get_uncommitted_files)

        result = hook.collect_modified_ticket_paths(tmp_path, logger)
        assert result is None

    def test_success_returns_list_not_none(self, monkeypatch, logger, tmp_path):
        class FakeFileStatus:
            def __init__(self, file_path, is_modified=False, is_added=False):
                self.file_path = file_path
                self.is_modified = is_modified
                self.is_added = is_added

        def fake_get_uncommitted_files(cwd=None):
            return [FakeFileStatus("docs/work-logs/v1/tickets/0.1.0-W1-001.md", is_modified=True)]

        monkeypatch.setattr(hook, "get_uncommitted_files", fake_get_uncommitted_files)

        result = hook.collect_modified_ticket_paths(tmp_path, logger)
        assert result == ["docs/work-logs/v1/tickets/0.1.0-W1-001.md"]
        assert result is not None


class TestCollectOrphanTicketsUndetermined:
    """collect_modified_ticket_paths 判定失敗時：collect_orphan_tickets 須回傳 None，
    不得將判定失敗誤讀為「無 metadata orphan ticket」。"""

    def test_modified_paths_none_returns_none(self, monkeypatch, logger, tmp_path):
        monkeypatch.setattr(hook, "collect_modified_ticket_paths", lambda root, logger: None)

        result = hook.collect_orphan_tickets(tmp_path, logger)
        assert result is None


class TestMainOrphanBranchesExceptionWrapper:
    """main() 內 collect_orphan_agent_branches 的 except 分支：捕獲例外時須設
    orphan_result=None（非 []），否則 undetermined 判斷被繞過，例外會被誤讀為
    「判定成功且無孤兒分支」（fail-open）。"""

    def test_exception_sets_undetermined_true(self, monkeypatch, logger, capsys):
        def fake_collect(logger):
            raise RuntimeError("boom")

        monkeypatch.setattr(hook, "collect_orphan_agent_branches", fake_collect)
        monkeypatch.setattr(hook, "collect_merged_user_worktrees", lambda logger: [])
        monkeypatch.setattr(hook, "collect_orphan_tickets", lambda root, logger: [])
        monkeypatch.setattr(hook, "read_json_from_stdin", lambda logger: {})

        hook.main()
        captured = capsys.readouterr()
        assert "suppressOutput" not in captured.out
        assert "無法判定" in captured.out


class TestBuildMessageSectionUndetermined:
    """merged_worktrees / orphan_tickets 判定失敗時：build_message 不得輸出正常結論。"""

    def test_merged_worktrees_undetermined_no_normal_conclusion(self):
        msg = hook.build_message([], [], [], merged_worktrees_undetermined=True)
        assert "無法判定" in msg
        assert "已完全合併" not in msg
        assert "git worktree remove" not in msg

    def test_orphan_tickets_undetermined_no_normal_conclusion(self):
        msg = hook.build_message([], [], [], orphan_tickets_undetermined=True)
        assert "無法判定" in msg
        assert "metadata orphan ticket" not in msg
        assert "git commit" not in msg
