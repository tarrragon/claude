"""
測試 worktree cleanup 子命令

涵蓋 10 個場景，包括三層閘門、掃描模式、邊界條件。
"""

import pytest
import sys
from pathlib import Path

# 加入模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from worktree_manager import (
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
        monkeypatch.setattr("worktree_manager._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("worktree_manager._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

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
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

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
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

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
        monkeypatch.setattr("worktree_manager._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

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
        monkeypatch.setattr("worktree_manager._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("worktree_manager._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

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
        monkeypatch.setattr("worktree_manager._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("worktree_manager._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

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
        monkeypatch.setattr("worktree_manager._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("worktree_manager._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

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
        monkeypatch.setattr("worktree_manager._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("worktree_manager._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

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
        monkeypatch.setattr("worktree_manager._is_branch_pushed", mock_is_pushed)
        monkeypatch.setattr("worktree_manager._is_branch_merged_to_base", mock_is_merged)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_cleanup("0.1.1-W9-001")

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Worktree 已移除" in captured.out
        assert "刪除失敗" in captured.out or "git branch -D" in captured.out
