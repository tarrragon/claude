"""
測試 worktree cleanup 子命令

涵蓋 10 個場景，包括三層閘門、掃描模式、邊界條件。
"""

import pytest
import sys
from pathlib import Path

# 加入模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from cleanup_command import (
    cmd_cleanup,
    _cleanup_check_level1,
    _cleanup_check_level2,
    _cleanup_check_level3,
)
from messages import CleanupMessages


class TestCleanupSuccess:
    """cleanup 成功場景"""

    def test_cleanup_exact_success_all_gates_pass(self, monkeypatch, capsys):
        """場景 9: cleanup — 精確清理成功（正常流程）

        三層閘門全通過、git 命令成功，應輸出清理完成訊息，exit code 為 0。
        """
        def mock_get_uncommitted(path):
            return 0

        def mock_is_pushed(branch):
            return True

        def mock_is_merged(branch, base="main"):
            return True

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W9-001 (branch refs/heads/feat/0.1.1-W9-001)")
            elif "worktree" in args and "remove" in args:
                return (True, "")
            elif "branch" in args and "-d" in args:
                return (True, "")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-001", "branch": "feat/0.1.1-W9-001"}]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("cleanup_command._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("cleanup_command.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W9-001")

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "清理完成" in captured.out


class TestCleanupLevel1:
    """cleanup Level 1 閘門測試"""

    def test_cleanup_level1_rejected_without_force(self, monkeypatch, capsys):
        """場景 10: cleanup — Level 1 拒絕（無 --force）

        有未 commit 變更時，應拒絕，exit code 為 1。
        """
        def mock_get_uncommitted(path):
            return 3

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W10-001.1 (branch refs/heads/feat/0.1.1-W10-001.1)")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W10-001.1", "branch": "feat/0.1.1-W10-001.1"}]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("cleanup_command.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W10-001.1", force=False)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "拒絕" in captured.out
        assert "3" in captured.out

    def test_cleanup_level1_rejected_with_force(self, monkeypatch, capsys):
        """場景 10b: cleanup — Level 1 拒絕（加 --force 仍無效）

        即使加 --force，Level 1 永不可繞過，exit code 為 1。
        """
        def mock_get_uncommitted(path):
            return 3

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W10-001.1 (branch refs/heads/feat/0.1.1-W10-001.1)")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W10-001.1", "branch": "feat/0.1.1-W10-001.1"}]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("cleanup_command.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W10-001.1", force=True)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "拒絕" in captured.out


class TestCleanupLevel2:
    """cleanup Level 2 閘門測試"""

    def test_cleanup_level2_warning_not_pushed_without_force(self, monkeypatch, capsys):
        """場景 11: cleanup — Level 2 警告，無 --force

        未 push 時，應警告並拒絕，exit code 為 1。
        """
        def mock_get_uncommitted(path):
            return 0

        def mock_is_pushed(branch):
            return False

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W9-002 (branch refs/heads/feat/0.1.1-W9-002)")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("cleanup_command._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("cleanup_command.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W9-002", force=False)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "警告" in captured.out

    def test_cleanup_level2_warning_with_force_proceed(self, monkeypatch, capsys):
        """場景 12: cleanup — Level 2 警告，加 --force

        加 --force 後應略過警告並執行清理，exit code 為 0。
        """
        def mock_get_uncommitted(path):
            return 0

        def mock_is_pushed(branch):
            return False

        def mock_is_merged(branch, base="main"):
            return True

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W9-002 (branch refs/heads/feat/0.1.1-W9-002)")
            elif "worktree" in args and "remove" in args:
                return (True, "")
            elif "branch" in args and "-d" in args:
                return (True, "")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("cleanup_command._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("cleanup_command.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W9-002", force=True)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "清理完成" in captured.out


class TestCleanupLevel3:
    """cleanup Level 3 閘門測試"""

    def test_cleanup_level3_warning_not_merged_without_force(self, monkeypatch, capsys):
        """場景 13: cleanup — Level 3 警告，無 --force

        未合併時，應警告並拒絕，exit code 為 1。
        """
        def mock_get_uncommitted(path):
            return 0

        def mock_is_pushed(branch):
            return True

        def mock_is_merged(branch, base="main"):
            return False

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W9-002 (branch refs/heads/feat/0.1.1-W9-002)")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("cleanup_command._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("cleanup_command.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W9-002", force=False)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "警告" in captured.out

    def test_cleanup_level3_warning_with_force_proceed(self, monkeypatch, capsys):
        """場景 14: cleanup — Level 3 警告，加 --force

        加 --force 後應略過警告並執行清理，exit code 為 0。
        """
        def mock_get_uncommitted(path):
            return 0

        def mock_is_pushed(branch):
            return True

        def mock_is_merged(branch, base="main"):
            return False

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W9-002 (branch refs/heads/feat/0.1.1-W9-002)")
            elif "worktree" in args and "remove" in args:
                return (True, "")
            elif "branch" in args and "-d" in args:
                return (True, "")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("cleanup_command._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("cleanup_command.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W9-002", force=True)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "清理完成" in captured.out


class TestCleanupScan:
    """cleanup 掃描模式測試"""

    def test_cleanup_scan_mode_mixed_status_worktrees(self, monkeypatch, capsys):
        """場景 15: cleanup — 掃描模式，混合狀態 worktree

        應輸出分類報告（建議清理、警告、不安全），exit code 為 0。
        """
        def mock_get_uncommitted(path):
            if "W9-001" in path:
                return 0
            elif "W9-002" in path:
                return 0
            elif "W10-001" in path:
                return 3
            return 0

        def mock_is_pushed(branch):
            return True

        def mock_is_merged(branch, base="main"):
            if "W9-001" in branch:
                return True
            elif "W9-002" in branch:
                return False
            return False

        def mock_get_worktree_list():
            return [
                {"path": "/path/ccsession", "branch": "main"},
                {"path": "/path/ccsession-0.1.1-W9-001", "branch": "feat/0.1.1-W9-001"},
                {"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"},
                {"path": "/path/ccsession-0.1.1-W10-001.1", "branch": "feat/0.1.1-W10-001.1"}
            ]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("cleanup_command._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup(None)  # 掃描模式

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "建議清理" in captured.out
        assert "需注意" in captured.out
        assert "不安全" in captured.out

    def test_cleanup_scan_mode_no_worktree(self, monkeypatch, capsys):
        """場景 16: cleanup — 掃描模式，無任何 worktree

        應輸出提示訊息，exit code 為 0。
        """
        def mock_get_worktree_list():
            return [{"path": "/path/ccsession", "branch": "main"}]

        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup(None)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "沒有需要清理" in captured.out


class TestCleanupError:
    """cleanup 錯誤場景"""

    def test_cleanup_error_worktree_not_found(self, monkeypatch, capsys):
        """場景 17: cleanup — 找不到對應的 worktree（精確模式）

        worktree 不存在時，應輸出錯誤，exit code 為 1。
        """
        def mock_get_worktree_list():
            return [
                {"path": "/path/ccsession", "branch": "main"},
                {"path": "/path/ccsession-0.1.1-W9-001", "branch": "feat/0.1.1-W9-001"}
            ]

        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W9-999")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "錯誤" in captured.out

    def test_cleanup_partial_success_branch_delete_failed(self, monkeypatch, capsys):
        """場景 18: cleanup — 部分成功，git branch -d 失敗

        worktree 移除成功但分支刪除失敗時，應輸出部分成功訊息，exit code 為 0。
        """
        def mock_get_uncommitted(path):
            return 0

        def mock_is_pushed(branch):
            return True

        def mock_is_merged(branch, base="main"):
            return True

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W9-001 (branch refs/heads/feat/0.1.1-W9-001)")
            elif "worktree" in args and "remove" in args:
                return (True, "")
            elif "branch" in args and "-d" in args:
                return (False, "error: branch not merged")  # 失敗
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-001", "branch": "feat/0.1.1-W9-001"}]

        monkeypatch.setattr("worktree_manager.get_worktree_uncommitted_count", mock_get_uncommitted)
        monkeypatch.setattr("cleanup_command._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("cleanup_command.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)
        monkeypatch.setattr("cleanup_command.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W9-001")

        # 分支殘留屬清理未完成：rc 非 0（原行為回 0，失敗被當成功）
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Worktree 已移除" in captured.out
        assert "刪除失敗" in captured.out or "git branch -D" in captured.out


# ===== 以臨時 git repo 驗證移除逾時、半刪收尾、鎖處理 =====

import os
import subprocess

import cleanup_command
import worktree_manager


def _git(cwd, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """main repo（含 a.txt、b.txt）與一個位於 main HEAD 的 worktree。"""
    root = tmp_path / "main"
    root.mkdir()
    _git(root, "init", "-b", "main")
    (root / "a.txt").write_text("a")
    (root / "b.txt").write_text("b")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")
    wt = tmp_path / "wt"
    _git(root, "worktree", "add", "-b", "worktree-agent-x", str(wt))
    monkeypatch.chdir(root)
    monkeypatch.setattr(worktree_manager, "get_project_root", lambda: str(tmp_path / "logroot"))
    monkeypatch.setattr(cleanup_command, "get_project_root", lambda: str(tmp_path / "logroot"))
    return {"root": root, "wt": wt, "log": tmp_path / "logroot"}


def _registered(root, wt):
    return os.path.realpath(str(wt)) in [
        os.path.realpath(line[len("worktree "):])
        for line in _git(root, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    ]


def _branches(root):
    return _git(root, "branch", "--list", "worktree-agent-x").strip()


def _inject_remove_timeout(monkeypatch, repo, delete_tracked=True, untracked=False):
    """首次非 --force 的 remove 模擬逾時被殺：留下半刪（刪光 tracked）後回傳逾時失敗；其餘命令走真實 git。"""
    real = worktree_manager.run_git_command
    seen = {"timeouts": []}

    def fake(args, cwd=None, timeout=10):
        if args[:2] == ["worktree", "remove"] and "--force" not in args:
            seen["timeouts"].append(timeout)
            if delete_tracked:
                for name in ("a.txt", "b.txt"):
                    (repo["wt"] / name).unlink()
            if untracked:
                (repo["wt"] / "scratch.txt").write_text("u")
            return False, f"Command timed out after {timeout}s"
        return real(args, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(worktree_manager, "run_git_command", fake)
    monkeypatch.setattr(cleanup_command, "run_git_command", fake)
    return seen


class TestRemoveTimeoutAndRecovery:
    def test_remove_timeout_constant_is_300(self):
        assert cleanup_command.WORKTREE_REMOVE_TIMEOUT_SECONDS == 300

    def test_remove_uses_constant_and_logs_elapsed(self, repo, monkeypatch):
        monkeypatch.setattr(cleanup_command, "WORKTREE_REMOVE_TIMEOUT_SECONDS", 7)
        seen = _inject_remove_timeout(monkeypatch, repo)
        cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert seen["timeouts"] == [7]
        log = next(repo["log"].rglob("worktree-merge.log"))
        assert "耗時" in log.read_text(encoding="utf-8")

    def test_half_removed_with_both_conditions_is_recovered(self, repo, monkeypatch):
        """E1 正向：逾時半刪 + 兩條件成立 → 目錄、登記、分支皆清除。"""
        _inject_remove_timeout(monkeypatch, repo)
        ok, _ = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert ok
        assert not repo["wt"].exists()
        assert not _registered(repo["root"], repo["wt"])
        assert _branches(repo["root"]) == ""

    def test_half_removed_stays_when_recovery_disabled(self, repo, monkeypatch):
        """E1 對照：同 fixture 關閉收尾 → 半刪殘留且 rc 非 0。"""
        _inject_remove_timeout(monkeypatch, repo)
        monkeypatch.setattr(cleanup_command, "_cleanup_recover", lambda p, e: (False, e))
        ok, _ = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok
        assert repo["wt"].exists()
        assert _registered(repo["root"], repo["wt"])
        assert "D" in _git(repo["wt"], "status", "--porcelain")

    def test_untracked_blocks_recovery(self, repo, monkeypatch):
        """E2：存在 untracked 時不收尾，並列出不成立項。"""
        _inject_remove_timeout(monkeypatch, repo, untracked=True)
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok
        assert "非 tracked 刪除" in msg
        assert repo["wt"].exists() and _registered(repo["root"], repo["wt"])

    def test_modified_blocks_recovery(self, repo, monkeypatch):
        """E2：存在 modified 時不收尾。"""
        _inject_remove_timeout(monkeypatch, repo, delete_tracked=False)
        (repo["wt"] / "a.txt").write_text("changed")
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok
        assert "非 tracked 刪除" in msg
        assert repo["wt"].exists()

    def test_head_not_ancestor_blocks_recovery(self, repo, monkeypatch):
        """E2：HEAD 未併入 main 時不收尾。"""
        (repo["wt"] / "c.txt").write_text("c")
        _git(repo["wt"], "add", "c.txt")
        _git(repo["wt"], "commit", "-m", "extra")
        _inject_remove_timeout(monkeypatch, repo)
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok
        assert "不是 main 的祖先" in msg
        assert repo["wt"].exists()


class TestLevel1HalfRemoved:
    def _half_delete(self, repo, untracked=False):
        for name in ("a.txt", "b.txt"):
            (repo["wt"] / name).unlink()
        if untracked:
            (repo["wt"] / "scratch.txt").write_text("u")

    def test_half_removed_cleaned_by_fresh_run(self, repo):
        """E1：先前留下的半刪 worktree，全新一次 cleanup 即可清除。"""
        self._half_delete(repo)
        rc = cmd_cleanup(branch="worktree-agent-x", force=True)
        assert rc == 0
        assert not repo["wt"].exists()
        assert not _registered(repo["root"], repo["wt"])
        assert _branches(repo["root"]) == ""

    def test_half_removed_with_untracked_blocked_by_level1(self, repo, capsys):
        """E2：半刪但有 untracked，Level 1 擋下、不移除。"""
        self._half_delete(repo, untracked=True)
        rc = cmd_cleanup(branch="worktree-agent-x", force=True)
        assert rc == 1
        assert "拒絕" in capsys.readouterr().out
        assert repo["wt"].exists()


class TestWorktreeLock:
    def _lock(self, repo, pid):
        _git(repo["root"], "worktree", "lock", "--reason", f"claude agent x (pid {pid})", str(repo["wt"]))

    def test_locked_worktree_is_not_removed_by_default(self, repo):
        self._lock(repo, os.getpid())
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok
        assert "claude agent x" in msg
        assert f"pid {os.getpid()} 存活" in msg
        assert repo["wt"].exists()

    def test_dead_pid_reported(self, repo):
        self._lock(repo, 99999999)
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok
        assert "已不存在" in msg

    def test_unlock_flag_unlocks_then_removes(self, repo):
        self._lock(repo, os.getpid())
        ok, _ = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x", unlock=True)
        assert ok
        assert not repo["wt"].exists()
        assert _branches(repo["root"]) == ""


class TestFailurePathsReturnNonZero:
    def test_branch_delete_failure_after_remove_is_nonzero(self, repo, capsys):
        """A4 第一例 rc=0 路徑：worktree 已移除、分支因未併入而 branch -d 失敗，原回 0。"""
        (repo["wt"] / "c.txt").write_text("c")
        _git(repo["wt"], "add", "c.txt")
        _git(repo["wt"], "commit", "-m", "extra")
        rc = cmd_cleanup(branch="worktree-agent-x", force=True)
        assert rc == 1
        assert not repo["wt"].exists()
        assert _branches(repo["root"]) != ""

    def test_locked_cleanup_via_cmd_is_nonzero_and_unlock_is_zero(self, repo):
        _git(repo["root"], "worktree", "lock", "--reason", "claude agent x", str(repo["wt"]))
        assert cmd_cleanup(branch="worktree-agent-x", force=True) == 1
        assert repo["wt"].exists()
        assert cmd_cleanup(branch="worktree-agent-x", force=True, unlock=True) == 0
        assert not repo["wt"].exists()
