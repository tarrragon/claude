"""
worktree-zombie-cleanup-hook 分支刪除測試（0.32.0-W3-020）

涵蓋 worktree remove 成功後對應分支處理兩路徑：
- ahead=0（已併入 main）→ git branch -d 自動刪除
- ahead>0（含未併入提交）→ 保留並警告，不誤刪未落地工作
"""

import importlib.util
import logging
from pathlib import Path

import pytest

# 動態導入 hook（檔案名含 dash）
_HOOK_FILE = (
    Path(__file__).resolve().parent.parent / "hooks" / "worktree-zombie-cleanup-hook.py"
)
_spec = importlib.util.spec_from_file_location("worktree_zombie_cleanup_hook", _HOOK_FILE)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


@pytest.fixture
def logger():
    return logging.getLogger("test-wzc")


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestGetWorktreeBranch:
    def test_extracts_branch_ref_for_matching_worktree(self, monkeypatch):
        target = Path("/repo/.claude/worktrees/agent-abc")

        def fake_run(cmd, **kwargs):
            out = (
                f"worktree {target}\n"
                "branch refs/heads/worktree-agent-abc\n"
                "\n"
                "worktree /repo\n"
                "branch refs/heads/main\n"
            )
            return FakeProc(returncode=0, stdout=out)

        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        branch = hook.get_worktree_branch(Path("/repo"), target)
        assert branch == "worktree-agent-abc"

    def test_returns_none_when_not_found(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            return FakeProc(returncode=0, stdout="worktree /repo\nbranch refs/heads/main\n")

        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        branch = hook.get_worktree_branch(Path("/repo"), Path("/repo/.claude/worktrees/agent-x"))
        assert branch is None


class TestDeleteBranchIfMerged:
    def test_deletes_branch_when_ahead_zero(self, monkeypatch, logger):
        """ahead=0：git log main..branch 空輸出，應 git branch -d 並回傳 True。"""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if "log" in cmd:
                return FakeProc(returncode=0, stdout="")  # ahead=0
            if "branch" in cmd and "-d" in cmd:
                return FakeProc(returncode=0, stdout="Deleted branch")
            return FakeProc(returncode=0)

        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        deleted = hook.delete_branch_if_merged(
            Path("/repo"), "worktree-agent-abc", "agent-abc", logger
        )
        assert deleted is True
        assert any("branch" in c and "-d" in c for c in calls)

    def test_keeps_branch_when_ahead_positive(self, monkeypatch, logger):
        """ahead>0：git log main..branch 有輸出，應保留分支、不執行 branch -d。"""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if "log" in cmd:
                return FakeProc(returncode=0, stdout="abc123 wip commit")  # ahead>0
            return FakeProc(returncode=0)

        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        deleted = hook.delete_branch_if_merged(
            Path("/repo"), "worktree-agent-abc", "agent-abc", logger
        )
        assert deleted is False
        assert not any("branch" in c and "-d" in c for c in calls)

    def test_returns_false_when_branch_none(self, monkeypatch, logger):
        deleted = hook.delete_branch_if_merged(Path("/repo"), None, "agent-abc", logger)
        assert deleted is False

    def test_returns_false_when_delete_fails(self, monkeypatch, logger):
        def fake_run(cmd, **kwargs):
            if "log" in cmd:
                return FakeProc(returncode=0, stdout="")  # ahead=0
            if "branch" in cmd and "-d" in cmd:
                return FakeProc(returncode=1, stderr="error: cannot delete")
            return FakeProc(returncode=0)

        monkeypatch.setattr(hook.subprocess, "run", fake_run)
        deleted = hook.delete_branch_if_merged(
            Path("/repo"), "worktree-agent-abc", "agent-abc", logger
        )
        assert deleted is False


class TestProcessWorktreeBranchDeletion:
    def test_clean_path_deletes_merged_branch(self, monkeypatch, logger, tmp_path):
        """clean 動作下 worktree 移除成功後，ahead=0 分支應被刪除並記入 result。"""
        wt = tmp_path / "agent-abc"
        wt.mkdir()

        monkeypatch.setattr(hook, "read_locked_pid", lambda r, n: 12345)
        monkeypatch.setattr(hook, "is_recent", lambda d, now, **k: False)
        monkeypatch.setattr(hook, "check_pid_alive", lambda pid: (False, ""))
        monkeypatch.setattr(hook, "is_worktree_dirty", lambda p: False)
        monkeypatch.setattr(hook, "get_worktree_branch", lambda r, p: "worktree-agent-abc")
        monkeypatch.setattr(hook, "remove_worktree", lambda r, p, n, lg: True)
        monkeypatch.setattr(hook, "delete_branch_if_merged", lambda r, b, n, lg: True)

        result = hook.process_worktree(tmp_path, wt, 9999999999.0, logger)
        assert result["action"] == "clean"
        assert result["success"] is True
        assert result["branch_deleted"] is True

    def test_summarize_reports_deleted_branch_count(self):
        results = [
            {"name": "agent-a", "action": "clean", "success": True, "branch_deleted": True},
            {"name": "agent-b", "action": "clean", "success": True, "branch_deleted": False},
        ]
        summary = hook.summarize(results)
        assert "已清理: 2 個" in summary
        assert "已刪分支: 1 個" in summary
