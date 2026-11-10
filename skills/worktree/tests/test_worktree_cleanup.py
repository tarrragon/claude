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

        未 push 也未併入本機 base 時，應警告並拒絕，exit code 為 1。
        （3.1.0-W1-050 起已併入 base 視為已保存；本場景須明示未併入）
        """
        def mock_get_uncommitted(path):
            return 0

        def mock_is_pushed(branch):
            return False

        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", lambda b, base="main": False)

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

    def test_unlock_flag_unlocks_then_removes(self, repo, capsys):
        self._lock(repo, os.getpid())
        ok, _ = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x", unlock=True)
        assert ok
        assert not repo["wt"].exists()
        assert _branches(repo["root"]) == ""
        assert "已解鎖（--unlock）" in capsys.readouterr().out

    def _deliver(self, repo):
        """代理人交回：分支上有自己的提交，且已快轉併入 main。"""
        (repo["wt"] / "delivered.txt").write_text("d")
        _git(repo["wt"], "add", "delivered.txt")
        _git(repo["wt"], "commit", "-m", "agent work")
        _git(repo["root"], "merge", "--ff-only", "worktree-agent-x")

    def test_lock_held_by_parent_session_is_unlocked(self, repo, capsys):
        """派發方 session（呼叫者的祖先行程）持有的鎖、分支已交回：不需 --unlock，解鎖後完成並寫明。"""
        parent = os.getppid()
        self._deliver(repo)
        self._lock(repo, parent)
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert ok, msg
        assert not repo["wt"].exists() and _branches(repo["root"]) == ""
        assert f"已解鎖：鎖的 pid {parent} 是呼叫者的祖先行程" in capsys.readouterr().out

    def test_lock_held_by_grandparent_is_unlocked(self, repo):
        grandparent = cleanup_command._parent_pid(os.getppid())
        if grandparent is None or grandparent <= 1:
            pytest.skip("測試環境的行程鏈不足兩層")
        self._deliver(repo)
        self._lock(repo, grandparent)
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert ok, msg

    def test_parent_lock_on_undelivered_branch_still_stops(self, repo):
        """正向對照：祖先持有但分支尚無自己的提交（代理人可能仍在執行），停手。

        此分支等於 main，Level 3 會判為已合併；只看 pid 會刪掉執行中代理人的 worktree。
        """
        self._lock(repo, os.getppid())
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok and "[停手]" in msg
        assert "代理人可能仍在執行" in msg
        assert repo["wt"].exists()

    def test_parent_lock_on_unmerged_commits_still_stops(self, repo):
        """祖先持有、分支有提交但未併入 main：停手。"""
        (repo["wt"] / "wip.txt").write_text("w")
        _git(repo["wt"], "add", "wip.txt")
        _git(repo["wt"], "commit", "-m", "wip")
        self._lock(repo, os.getppid())
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok and "代理人可能仍在執行" in msg

    def test_lock_held_by_other_live_process_still_stops(self, repo):
        """正向對照：存活但不在祖先鏈上的行程持有的鎖，仍停手並說明持有者。"""
        other = subprocess.Popen(["sleep", "30"])
        try:
            self._lock(repo, other.pid)
            ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        finally:
            other.kill()
            other.wait()
        assert not ok
        assert f"pid {other.pid} 存活" in msg and "[停手]" in msg
        assert repo["wt"].exists()

    def test_ancestor_walk_failure_falls_back_to_stop(self, repo, monkeypatch):
        """ps 查不到父行程時只認直接父行程；更上層的鎖當成他人持有，停手。"""
        grandparent = cleanup_command._parent_pid(os.getppid())
        if grandparent is None or grandparent <= 1:
            pytest.skip("測試環境的行程鏈不足兩層")
        monkeypatch.setattr(cleanup_command, "_parent_pid", lambda pid: None)
        self._deliver(repo)
        self._lock(repo, grandparent)
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert not ok and "[停手]" in msg

    def test_pid_one_is_never_treated_as_own(self, monkeypatch):
        monkeypatch.setattr(cleanup_command.os, "getppid", lambda: 1)
        assert cleanup_command._ancestor_pids() == set()


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


class TestLevel1StatusFailure:
    """Level 1 在 git status 失敗時阻擋，通過訊息依實際檢查結果（3.1.0-W1-050）"""

    WT = "/path/ccsession-0.1.1-W9-001"

    def _setup(self, monkeypatch, status_result):
        removed = []

        def mock_run_git(args, cwd=None, timeout=10):
            if args[:2] == ["status", "--porcelain"]:
                return status_result
            if "remove" in args or "-d" in args or "-D" in args:
                removed.append(args)
            return (True, "")

        wts = lambda: [{"path": self.WT, "branch": "feat/0.1.1-W9-001"}]  # noqa: E731
        for mod in ("worktree_manager", "cleanup_command"):
            monkeypatch.setattr(f"{mod}.run_git_command", mock_run_git)
            monkeypatch.setattr(f"{mod}.get_worktree_list", wts)
        monkeypatch.setattr("cleanup_command._is_branch_pushed", lambda b: True)
        monkeypatch.setattr("cleanup_command._is_branch_merged_to_base", lambda b, base="main": True)
        return removed

    def test_status_failure_blocks_even_with_force(self, monkeypatch, capsys):
        """E2 正向對照：git status 失敗時 Level 1 擋下（--force 無效），不執行移除。"""
        removed = self._setup(monkeypatch, (False, "fatal: not a git repository"))
        assert cmd_cleanup("0.1.1-W9-001", force=True) == 1
        out = capsys.readouterr().out
        assert "not a git repository" in out and "無法確認" in out
        assert "Level 1 檢查：通過" not in out and removed == []

    def test_level1_helper_returns_reason_on_failure(self, monkeypatch):
        self._setup(monkeypatch, (False, "Command timed out after 10s"))
        passed, detail = _cleanup_check_level1(self.WT)
        assert not passed and "timed out" in detail

    def test_pass_message_only_when_zero_changes(self, monkeypatch, capsys):
        self._setup(monkeypatch, (True, ""))
        assert cmd_cleanup("0.1.1-W9-001") == 0
        assert "Level 1 檢查：通過（無未 commit 變更）" in capsys.readouterr().out

    def test_half_removed_worktree_pass_message_states_changes(self, monkeypatch, capsys):
        """半刪 worktree 走收尾路徑時有變更，不得印「無未 commit 變更」。"""
        self._setup(monkeypatch, (True, " D a.txt\n D b.txt"))
        monkeypatch.setattr("cleanup_command._recovery_unmet_conditions", lambda p: [])
        cmd_cleanup("0.1.1-W9-001")
        out = capsys.readouterr().out
        assert "無未 commit 變更" not in out and "2 個變更皆為已追蹤檔刪除" in out


# ===== DerivedData：只刪 WorkspacePath 位於該 worktree 內的目錄 =====

import plistlib

import xcode_derived_data


def _derived_entry(root, name, workspace=None, fmt=plistlib.FMT_XML):
    """建立一個 DerivedData 子目錄；workspace 為 None 時不寫 info.plist（如 ModuleCache.noindex）。"""
    entry = root / name
    entry.mkdir(parents=True)
    (entry / "Build").mkdir()
    if workspace is not None:
        with open(entry / "info.plist", "wb") as fh:
            plistlib.dump({"WorkspacePath": str(workspace), "LastAccessedDate": "x"}, fh, fmt=fmt)
    return entry


@pytest.fixture
def derived(repo, tmp_path, monkeypatch):
    """DerivedData 根目錄含：指向 wt 的（XML 與 binary 各一）、指向前綴相同的 wt2、指向主 repo、無 info.plist。"""
    root = tmp_path / "DerivedData"
    monkeypatch.setattr(xcode_derived_data, "DERIVED_DATA_ROOT", root)
    monkeypatch.setattr(xcode_derived_data, "PLATFORM", "darwin")
    wt = repo["wt"]
    return {
        "root": root,
        "hit_xml": _derived_entry(root, "Runner-aaa", wt / "ios" / "Runner.xcworkspace"),
        "hit_bin": _derived_entry(root, "Runner-bbb", wt / "macos" / "Runner.xcodeproj", plistlib.FMT_BINARY),
        "sibling": _derived_entry(root, "Runner-ccc", f"{wt}2/ios/Runner.xcworkspace"),
        "main": _derived_entry(root, "Runner-ddd", repo["root"] / "ios" / "Runner.xcworkspace"),
        "no_plist": _derived_entry(root, "ModuleCache.noindex"),
    }


class TestDerivedDataCleanup:
    def test_cleanup_uses_the_patched_module(self):
        assert cleanup_command.remove_derived_data_for is xcode_derived_data.remove_derived_data_for

    def test_only_entries_inside_worktree_are_removed(self, repo, derived):
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert ok, msg
        assert not derived["hit_xml"].exists() and not derived["hit_bin"].exists()
        for kept in ("sibling", "main", "no_plist"):
            assert derived[kept].exists(), kept
        assert f"已移除 DerivedData：{derived['hit_xml']}" in msg
        assert f"已移除 DerivedData：{derived['hit_bin']}" in msg

    def test_symlinked_worktree_path_still_matches(self, repo, derived, tmp_path):
        link = tmp_path / "wt-link"
        link.symlink_to(repo["wt"])
        assert [e.name for e in xcode_derived_data.find_derived_data_for(str(link))] == ["Runner-aaa", "Runner-bbb"]

    def test_non_macos_leaves_derived_data(self, repo, derived, monkeypatch):
        monkeypatch.setattr(xcode_derived_data, "PLATFORM", "linux")
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert ok, msg
        assert derived["hit_xml"].exists() and derived["hit_bin"].exists()
        assert msg == CleanupMessages.CLEANUP_SUCCESS.format(path=str(repo["wt"]), branch="worktree-agent-x")

    def test_missing_root_leaves_message_unchanged(self, repo, tmp_path, monkeypatch):
        monkeypatch.setattr(xcode_derived_data, "DERIVED_DATA_ROOT", tmp_path / "absent")
        monkeypatch.setattr(xcode_derived_data, "PLATFORM", "darwin")
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert ok, msg
        assert msg == CleanupMessages.CLEANUP_SUCCESS.format(path=str(repo["wt"]), branch="worktree-agent-x")

    def test_removal_failure_is_reported_without_failing_cleanup(self, repo, derived, monkeypatch, capsys):
        def deny(path):
            raise PermissionError(13, "Permission denied", str(path))

        monkeypatch.setattr(xcode_derived_data.shutil, "rmtree", deny)
        ok, msg = cleanup_command._cleanup_execute(str(repo["wt"]), "worktree-agent-x")
        assert ok, msg
        assert f"DerivedData 未移除：{derived['hit_xml']}" in msg
        assert "DerivedData 移除失敗" in capsys.readouterr().err
        assert derived["hit_xml"].exists()
