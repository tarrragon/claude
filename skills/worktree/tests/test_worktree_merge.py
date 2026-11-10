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
    MergeOutcome,
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

        monkeypatch.setattr(
            "worktree_manager.merge_branch_cas",
            lambda *a, **k: MergeOutcome(ok=True, commit_sha="abc123", attempts=1),
        )
        monkeypatch.setattr("worktree_manager._verify_three_planes", lambda *a, **k: [])

        # 執行
        exit_code = cmd_merge("0.1.1-W9-002")

        # 驗證
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "合併提交：abc123" in captured.out
        assert "合併成功" in captured.out


class TestCleanupSuggestion:
    """合併成功後的 cleanup 建議命令須能被 cleanup 的參數解析原樣接受（3.1.0-W1-048）"""

    TICKET = "0.1.1-W9-002"
    BRANCH = "worktree-agent-a1b2c3"

    def _merge(self, monkeypatch, capsys, **kwargs) -> str:
        import worktree_manager as wm

        def mock_run_git(args, cwd=None, timeout=10):
            if "rev-list" in args and "--count" in args:
                return (True, "0")
            return (True, "")

        monkeypatch.setattr(wm, "_query_ticket_status", lambda _t: "completed")
        monkeypatch.setattr(wm, "run_git_command", mock_run_git)
        monkeypatch.setattr(wm, "get_worktree_list", lambda: [
            {"path": "/p/main", "branch": "main"},
            {"path": f"/p/{self.TICKET}", "branch": f"feat/{self.TICKET}"},
            {"path": f"/p/{self.BRANCH}", "branch": self.BRANCH},
        ])
        monkeypatch.setattr(wm, "merge_branch_cas", lambda *a, **k: MergeOutcome(ok=True, commit_sha="abc", attempts=1))
        monkeypatch.setattr(wm, "_verify_three_planes", lambda *a, **k: [])
        assert cmd_merge(pre_merge_check=lambda *a: None, **kwargs) == 0
        line = next(ln for ln in capsys.readouterr().out.splitlines() if "/worktree cleanup" in ln)
        return line.split("/worktree cleanup ", 1)[1].rsplit(" 清理", 1)[0]

    def _parse_cleanup(self, monkeypatch, args: str) -> dict:
        """以 worktree CLI 的 main() 解析建議參數，攔下 cmd_cleanup 取得解析結果。"""
        import shlex
        import worktree_manager as wm

        seen = {}

        class FakeCleanup:
            @staticmethod
            def cmd_cleanup(ticket_id, **kw):
                seen.update(ticket_id=ticket_id, **kw)
                return 0

        monkeypatch.setattr(wm, "_load_cleanup_command", lambda: FakeCleanup)
        monkeypatch.setattr(sys, "argv", ["worktree", "cleanup", *shlex.split(args)])
        assert wm.main() == 0
        return seen

    def test_ticket_merge_suggests_ticket_id(self, monkeypatch, capsys):
        args = self._merge(monkeypatch, capsys, ticket_id=self.TICKET)
        assert args == self.TICKET
        seen = self._parse_cleanup(monkeypatch, args)
        assert seen["ticket_id"] == self.TICKET and seen["branch"] is None

    def test_branch_merge_suggests_branch_flag(self, monkeypatch, capsys):
        """正向對照：以分支合併時，建議命令把分支放在 --branch，而非票號槽位。"""
        args = self._merge(monkeypatch, capsys, ticket_id=None, branch=self.BRANCH)
        assert args == f"--branch {self.BRANCH}"
        seen = self._parse_cleanup(monkeypatch, args)
        assert seen["ticket_id"] is None and seen["branch"] == self.BRANCH


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

    def test_merge_blocked_when_status_unavailable(self, monkeypatch, capsys):
        """場景 4: merge — 讀不到票狀態時不放行（3.1.0-W1-049 起 fail-closed）

        原行為為降級警告後照常合併；改為阻擋並寫明原因，merge_branch_cas 不被呼叫。
        """
        import worktree_manager as wm

        def mock_query_status(ticket_id):
            raise wm.TicketStatusUnavailable("找不到 ticket CLI")

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

        merged = []
        monkeypatch.setattr(
            "worktree_manager.merge_branch_cas",
            lambda *a, **k: merged.append(1) or MergeOutcome(ok=True, commit_sha="abc123", attempts=1),
        )
        monkeypatch.setattr("worktree_manager._verify_three_planes", lambda *a, **k: [])

        exit_code = cmd_merge("0.1.1-W9-002")

        assert exit_code == 1 and merged == []
        captured = capsys.readouterr()
        assert "[阻擋]" in captured.out and "找不到 ticket CLI" in captured.out
        assert "合併成功" not in captured.out

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

        monkeypatch.setattr(
            "worktree_manager.merge_branch_cas",
            lambda *a, **k: MergeOutcome(ok=True, commit_sha="abc123", attempts=1),
        )
        monkeypatch.setattr("worktree_manager._verify_three_planes", lambda *a, **k: [])

        exit_code = cmd_merge("0.1.1-W9-002")

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "落後" in captured.out
        assert "合併成功" in captured.out

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

        monkeypatch.setattr(
            "worktree_manager.merge_branch_cas",
            lambda *a, **k: MergeOutcome(ok=True, commit_sha="abc123", attempts=1),
        )
        monkeypatch.setattr("worktree_manager._verify_three_planes", lambda *a, **k: [])

        exit_code = cmd_merge("0.1.1-W9-002")

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "提示" in captured.out or "新 commit" in captured.out
        assert "合併成功" in captured.out


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


def _ticket_md(status: str, what: str = "修正某功能") -> str:
    return (f"---\nid: 0.1.1-W9-002\ntitle: t\ntype: IMP\nstatus: {status}\nwhat: {what}\n"
            "why: |\n  說明\n  status: completed\n---\n\n# Execution Log\n\nstatus: completed\n")


class TestTicketStatusSource:
    """合併前 completed 檢查讀 ticket show -r 的 frontmatter（3.1.0-W1-049）"""

    def _fake_cli(self, monkeypatch, rc=0, stdout="", stderr="", raise_exc=None):
        import subprocess as sp
        import worktree_manager as wm
        calls = []

        def run(argv, **kw):
            calls.append(argv)
            if raise_exc is not None:
                raise raise_exc
            return sp.CompletedProcess(argv, rc, stdout=stdout, stderr=stderr)

        monkeypatch.setattr(wm, "get_project_root", lambda: "/repo")  # 免得其 git 呼叫落入替身
        monkeypatch.setattr(wm.subprocess, "run", run)
        return calls

    @pytest.mark.parametrize("status", ["pending", "in_progress"])
    def test_unfinished_ticket_blocked(self, monkeypatch, status):
        """E2 正向對照：未完成的票被擋，阻擋訊息帶實際狀態。"""
        self._fake_cli(monkeypatch, stdout=_ticket_md(status))
        ok, msg = _merge_validate_ticket_status("0.1.1-W9-002")
        assert not ok and status in msg

    def test_completed_ticket_passes(self, monkeypatch):
        calls = self._fake_cli(monkeypatch, stdout=_ticket_md("completed"))
        assert _merge_validate_ticket_status("0.1.1-W9-002") == (True, "")
        assert calls == [["ticket", "show", "0.1.1-W9-002", "-r"]]

    def test_status_word_in_other_fields_not_misread(self, monkeypatch):
        """what／why／內文含 status 字樣時，只取 frontmatter 頂層 status 鍵。"""
        self._fake_cli(monkeypatch, stdout=_ticket_md("in_progress", what="修正 status: completed 的判讀"))
        ok, msg = _merge_validate_ticket_status("0.1.1-W9-002")
        assert not ok and "in_progress" in msg

    def test_ticket_not_found_blocked_with_reason(self, monkeypatch):
        """前段 INFO 行不得蓋過錯誤行（實機：worktree 內查詢會先印 linked worktree 的 INFO）。"""
        self._fake_cli(monkeypatch, rc=1, stderr="[INFO] 偵測到 linked worktree\n",
                       stdout="[Error] 找不到 Ticket 0.1.1-W9-002\n")
        ok, msg = _merge_validate_ticket_status("0.1.1-W9-002")
        assert not ok and "找不到 Ticket" in msg and "結束碼 1" in msg and "INFO" not in msg

    @pytest.mark.parametrize("exc,reason", [
        (FileNotFoundError(), "找不到 ticket CLI"),
        (__import__("subprocess").TimeoutExpired(["ticket"], 1), "逾時"),
    ])
    def test_cli_failure_blocked_with_reason(self, monkeypatch, exc, reason):
        self._fake_cli(monkeypatch, raise_exc=exc)
        ok, msg = _merge_validate_ticket_status("0.1.1-W9-002")
        assert not ok and reason in msg

    def test_missing_frontmatter_status_blocked(self, monkeypatch):
        self._fake_cli(monkeypatch, stdout="---\nid: x\n---\nstatus: completed\n")
        ok, msg = _merge_validate_ticket_status("0.1.1-W9-002")
        assert not ok and "沒有 status" in msg
