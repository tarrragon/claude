"""
測試 worktree merge 子命令

涵蓋 8 個場景的驗證邏輯和邊界條件。
"""

import pytest
import sys
from pathlib import Path

# 加入模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from worktree_manager import (
    cmd_merge,
    _merge_validate_ticket_status,
    _check_working_tree_clean,
)
from messages import MergeMessages


class TestMergeSuccess:
    """merge 成功場景"""

    def test_merge_success_all_checks_pass(self, monkeypatch, capsys):
        """場景 1: merge — 成功輸出指令（正常流程）

        Ticket 狀態為 completed、working tree 乾淨、ahead=3、behind=0
        應輸出完整的 git merge 指令，exit code 為 0。
        """
        # Mock 查詢函式
        def mock_query_status(ticket_id):
            return "completed"

        def mock_run_git(args, cwd=None, timeout=10):
            if "status" in args and "--porcelain" in args:
                return (True, "")  # 乾淨
            elif "rev-list" in args and "--count" in args:
                if "^" in args:  # ahead
                    return (True, "3")
                else:  # behind
                    return (True, "0")
            elif "worktree" in args and "list" in args:
                return (True, "/path/ccsession (branch refs/heads/main)\n/path/ccsession-0.1.1-W9-002 (branch refs/heads/feat/0.1.1-W9-002)")
            return (True, "")

        def mock_get_worktree_list():
            return [
                {"path": "/path/ccsession", "branch": "main"},
                {"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}
            ]

        monkeypatch.setattr("worktree_manager._query_ticket_status", mock_query_status)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

        # 執行
        exit_code = cmd_merge("0.1.1-W9-002")

        # 驗證
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "git checkout main" in captured.out
        assert "git merge --no-ff" in captured.out


class TestMergeBlocked:
    """merge 被阻擋的場景"""

    def test_merge_blocked_ticket_not_completed(self, monkeypatch, capsys):
        """場景 2: merge — Ticket 未完成被阻擋

        Ticket 狀態為 in_progress 時，應輸出阻擋訊息，exit code 為 1。
        """
        def mock_query_status(ticket_id):
            return "in_progress"

        def mock_run_git(args, cwd=None, timeout=10):
            if "worktree" in args and "list" in args:
                return (True, "/path/ccsession-0.1.1-W9-002 (branch refs/heads/feat/0.1.1-W9-002)")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager._query_ticket_status", mock_query_status)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_merge("0.1.1-W9-002")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "阻擋" in captured.out
        assert "in_progress" in captured.out
        assert "git merge" not in captured.out

    def test_merge_blocked_dirty_working_tree(self, monkeypatch, capsys):
        """場景 3: merge — working tree 有未 commit 變更（阻擋）

        有 2 個未 commit 變更時，應輸出阻擋訊息，exit code 為 1。
        """
        def mock_query_status(ticket_id):
            return "completed"

        def mock_run_git(args, cwd=None, timeout=10):
            if "status" in args and "--porcelain" in args:
                return (True, " M file1.py\n M file2.py\n")  # 2 個未 commit
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager._query_ticket_status", mock_query_status)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_merge("0.1.1-W9-002")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "阻擋" in captured.out
        assert "2" in captured.out
        assert "git merge" not in captured.out


class TestMergeWarning:
    """merge 警告和邊界場景"""

    def test_merge_downgrade_ticket_cli_unavailable(self, monkeypatch, capsys):
        """場景 4: merge — Ticket CLI 不可用（降級警告）

        ticket CLI 超時時，應輸出警告但仍給出 merge 指令，exit code 為 0。
        """
        def mock_query_status(ticket_id):
            return None  # 查詢失敗

        def mock_run_git(args, cwd=None, timeout=10):
            if "status" in args and "--porcelain" in args:
                return (True, "")
            elif "rev-list" in args and "--count" in args:
                if "^" in args:
                    return (True, "3")
                else:
                    return (True, "0")
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager._query_ticket_status", mock_query_status)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_merge("0.1.1-W9-002")

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "警告" in captured.out
        assert "git merge" in captured.out

    def test_merge_hint_branch_behind_main(self, monkeypatch, capsys):
        """場景 5: merge — 分支落後 main（提示但不阻擋）

        behind=2 時，應輸出提示但仍給出 merge 指令，exit code 為 0。
        """
        def mock_query_status(ticket_id):
            return "completed"

        def mock_run_git(args, cwd=None, timeout=10):
            if "status" in args and "--porcelain" in args:
                return (True, "")
            elif "rev-list" in args and "--count" in args:
                if "^" in args:
                    return (True, "3")
                else:
                    return (True, "2")  # behind=2
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager._query_ticket_status", mock_query_status)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_merge("0.1.1-W9-002")

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "提示" in captured.out or "rebase" in captured.out
        assert "git merge" in captured.out

    def test_merge_hint_no_new_commits(self, monkeypatch, capsys):
        """場景 6: merge — 分支無新 commit（警告）

        ahead=0 時，應輸出提示但仍給出 merge 指令，exit code 為 0。
        """
        def mock_query_status(ticket_id):
            return "completed"

        def mock_run_git(args, cwd=None, timeout=10):
            if "status" in args and "--porcelain" in args:
                return (True, "")
            elif "rev-list" in args and "--count" in args:
                return (True, "0")  # ahead 和 behind 都是 0
            return (True, "")

        def mock_get_worktree_list():
            return [{"path": "/path/ccsession-0.1.1-W9-002", "branch": "feat/0.1.1-W9-002"}]

        monkeypatch.setattr("worktree_manager._query_ticket_status", mock_query_status)
        monkeypatch.setattr("worktree_manager.run_git_command", mock_run_git)
        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_merge("0.1.1-W9-002")

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "提示" in captured.out or "新 commit" in captured.out
        assert "git merge" in captured.out


class TestMergeError:
    """merge 錯誤場景"""

    def test_merge_error_worktree_not_found(self, monkeypatch, capsys):
        """場景 7: merge — 找不到對應的 worktree（錯誤）

        worktree 不存在時，應輸出錯誤和 worktree 列表，exit code 為 1。
        """
        def mock_get_worktree_list():
            return [
                {"path": "/path/ccsession", "branch": "main"},
                {"path": "/path/ccsession-0.1.1-W9-001", "branch": "feat/0.1.1-W9-001"}
            ]

        monkeypatch.setattr("worktree_manager.get_worktree_list", mock_get_worktree_list)

        exit_code = cmd_merge("0.1.1-W9-999")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "錯誤" in captured.out
        assert "找不到" in captured.out

    def test_merge_error_invalid_ticket_id(self, monkeypatch, capsys):
        """場景 8: merge — Ticket ID 格式無效（錯誤）

        格式無效時，應輸出格式說明，exit code 為 1。
        """
        exit_code = cmd_merge("my-feature")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "錯誤" in captured.out
        assert "格式" in captured.out
