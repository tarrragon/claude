"""
ticket-md-auto-commit-hook 測試套件

測試覆蓋:
1. 主 repo / worktree 環境判別（僅主 repo 生效）
2. 未提交檔案過濾為 ticket md 範圍（不觸及其他檔案）
3. 防 race：偵測活躍背景代理人時跳過代捕，stale entry 不阻斷兜底
4. 兜底提交 + index.lock 重試
"""

import importlib.util
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_HOOK_FILE = (
    Path(__file__).resolve().parent.parent / "hooks" / "ticket-md-auto-commit-hook.py"
)
_spec = importlib.util.spec_from_file_location("ticket_md_auto_commit_hook", _HOOK_FILE)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


@pytest.fixture
def logger():
    return logging.getLogger("test-tmac")


def _now_iso(hours_ago=0.0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


# ============================================================================
# ticket md 路徑判別
# ============================================================================


class TestIsTicketMdPath:
    def test_matches_flat_structure(self):
        assert hook.is_ticket_md_path("docs/work-logs/v0.29.0/tickets/foo.md") is True

    def test_matches_hierarchical_structure(self):
        assert (
            hook.is_ticket_md_path(
                "docs/work-logs/v0/v0.2/v0.2.1/tickets/0.2.1-W3-757.md"
            )
            is True
        )

    def test_non_ticket_md_rejected(self):
        assert hook.is_ticket_md_path("lib/main.dart") is False
        assert hook.is_ticket_md_path("docs/spec/foo.md") is False

    def test_empty_path_rejected(self):
        assert hook.is_ticket_md_path("") is False
        assert hook.is_ticket_md_path(None) is False


class TestGetChangedTicketMdFiles:
    def test_filters_to_ticket_md_only(self, logger):
        statuses = [
            hook.FileStatus(status=" M", file_path="docs/work-logs/v1/tickets/a.md"),
            hook.FileStatus(status=" M", file_path="lib/main.dart"),
            hook.FileStatus(status="??", file_path="docs/work-logs/v1/tickets/b.md"),
        ]
        with patch.object(hook, "get_uncommitted_files", return_value=statuses):
            files = hook.get_changed_ticket_md_files(logger)
        assert files == [
            "docs/work-logs/v1/tickets/a.md",
            "docs/work-logs/v1/tickets/b.md",
        ]

    def test_parses_rename_to_new_path(self, logger):
        statuses = [
            hook.FileStatus(
                status="R ",
                file_path="docs/work-logs/v1/tickets/old.md -> docs/work-logs/v1/tickets/new.md",
            )
        ]
        with patch.object(hook, "get_uncommitted_files", return_value=statuses):
            files = hook.get_changed_ticket_md_files(logger)
        assert files == ["docs/work-logs/v1/tickets/new.md"]

    def test_empty_when_no_ticket_md(self, logger):
        statuses = [hook.FileStatus(status=" M", file_path="lib/main.dart")]
        with patch.object(hook, "get_uncommitted_files", return_value=statuses):
            assert hook.get_changed_ticket_md_files(logger) == []

    def test_empty_when_clean(self, logger):
        with patch.object(hook, "get_uncommitted_files", return_value=[]):
            assert hook.get_changed_ticket_md_files(logger) == []


# ============================================================================
# 環境判別：僅主 repo 生效
# ============================================================================


class TestIsWorktreeEnvironment:
    def test_git_file_detected_as_worktree(self, tmp_path, logger):
        (tmp_path / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
        with patch.object(hook.Path, "cwd", return_value=tmp_path):
            assert hook.is_worktree_environment(logger) is True

    def test_git_dir_detected_as_main_repo(self, tmp_path, logger):
        (tmp_path / ".git").mkdir()
        common_dir = str(tmp_path / ".git")
        proc = MagicMock(returncode=0, stdout=common_dir + "\n", stderr="")
        with patch.object(hook.Path, "cwd", return_value=tmp_path), patch.object(
            hook.subprocess, "run", return_value=proc
        ):
            assert hook.is_worktree_environment(logger) is False


# ============================================================================
# 防 race（比照 worktree-auto-commit-hook 設計）
# ============================================================================


class TestHasActiveBackgroundAgents:
    def test_active_dispatch_present_returns_true(self, logger):
        dispatches = [{"agent_description": "agent A", "dispatched_at": _now_iso(0)}]
        with patch.object(hook, "get_active_dispatches", return_value=dispatches), patch.object(
            hook, "cleanup_expired", return_value=0
        ):
            assert hook.has_active_background_agents(Path("/repo"), logger) is True

    def test_no_dispatch_returns_false(self, logger):
        with patch.object(hook, "get_active_dispatches", return_value=[]), patch.object(
            hook, "cleanup_expired", return_value=0
        ):
            assert hook.has_active_background_agents(Path("/repo"), logger) is False

    def test_stale_dispatch_does_not_block_fallback(self, logger):
        dispatches = [
            {"agent_description": "ghost", "dispatched_at": _now_iso(hours_ago=5)}
        ]
        with patch.object(hook, "get_active_dispatches", return_value=dispatches), patch.object(
            hook, "cleanup_expired", return_value=0
        ):
            assert hook.has_active_background_agents(Path("/repo"), logger) is False

    def test_project_root_none_degrades_to_fallback(self, logger):
        assert hook.has_active_background_agents(None, logger) is False

    def test_dispatch_tracker_unavailable_degrades(self, logger):
        with patch.object(hook, "get_active_dispatches", None):
            assert hook.has_active_background_agents(Path("/repo"), logger) is False

    def test_read_failure_degrades_to_fallback(self, logger):
        with patch.object(
            hook, "get_active_dispatches", side_effect=OSError("boom")
        ), patch.object(hook, "cleanup_expired", return_value=0):
            assert hook.has_active_background_agents(Path("/repo"), logger) is False


class TestIsDispatchStale:
    def test_fresh_dispatch_not_stale(self, logger):
        assert hook._is_dispatch_stale({"dispatched_at": _now_iso(0)}, logger) is False

    def test_old_dispatch_stale(self, logger):
        assert hook._is_dispatch_stale({"dispatched_at": _now_iso(5)}, logger) is True

    def test_missing_timestamp_stale(self, logger):
        assert hook._is_dispatch_stale({}, logger) is True


# ============================================================================
# commit message + 提交範圍
# ============================================================================


class TestBuildCommitMessage:
    def test_embeds_file_count_and_preview(self):
        msg = hook.build_commit_message(["docs/work-logs/v1/tickets/a.md"])
        assert "1 files" in msg
        assert "a" in msg
        assert msg.startswith("auto(ticket-md):")

    def test_truncates_long_file_list(self):
        files = [f"docs/work-logs/v1/tickets/t{i}.md" for i in range(5)]
        msg = hook.build_commit_message(files)
        assert "+2 more" in msg


class TestAutoCommitTicketMd:
    def test_add_scope_limited_to_ticket_md(self, logger):
        """驗證 git add 呼叫的參數僅含指定的 ticket md 路徑，無 -A。"""
        ok = MagicMock(returncode=0, stderr="")
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return ok

        with patch.object(hook.subprocess, "run", side_effect=fake_run):
            assert hook.auto_commit_ticket_md(
                ["docs/work-logs/v1/tickets/a.md"], "msg", logger
            ) is True
        add_call = calls[0]
        assert add_call == ["git", "add", "--", "docs/work-logs/v1/tickets/a.md"]
        assert "-A" not in add_call

    def test_add_failure_aborts(self, logger):
        fail = MagicMock(returncode=1, stderr="add failed")
        with patch.object(hook.subprocess, "run", return_value=fail):
            assert (
                hook.auto_commit_ticket_md(
                    ["docs/work-logs/v1/tickets/a.md"], "msg", logger
                )
                is False
            )


class TestLockRetry:
    def test_index_lock_retries_then_succeeds(self, logger):
        lock_fail = MagicMock(returncode=1, stderr="fatal: Unable to create index.lock")
        ok = MagicMock(returncode=0, stderr="")
        with patch.object(hook.subprocess, "run", side_effect=[lock_fail, ok]), patch(
            "time.sleep"
        ):
            success, rc, _ = hook._run_git_with_lock_retry(
                ["git", "add", "--", "a.md"], logger, "add", max_retries=3, wait_seconds=0
            )
        assert success is True
        assert rc == 0

    def test_does_not_delete_lock_file(self, logger):
        lock_fail = MagicMock(returncode=1, stderr="Unable to create index.lock")
        ok = MagicMock(returncode=0, stderr="")
        with patch.object(
            hook.subprocess, "run", side_effect=[lock_fail, ok]
        ), patch("time.sleep"), patch("os.remove") as rm, patch(
            "pathlib.Path.unlink"
        ) as unlink:
            hook._run_git_with_lock_retry(
                ["git", "add", "--", "a.md"], logger, "add", wait_seconds=0
            )
        rm.assert_not_called()
        unlink.assert_not_called()


# ============================================================================
# main 流程整合
# ============================================================================


class TestMainFlow:
    def test_skips_when_worktree(self):
        with patch.object(hook, "is_worktree_environment", return_value=True), patch.object(
            hook, "get_changed_ticket_md_files"
        ) as gcf:
            assert hook.main() == 0
            gcf.assert_not_called()

    def test_skips_when_no_ticket_md_changes(self):
        with patch.object(hook, "is_worktree_environment", return_value=False), patch.object(
            hook, "get_changed_ticket_md_files", return_value=[]
        ):
            assert hook.main() == 0

    def test_skips_capture_when_active_agents(self):
        with patch.object(hook, "is_worktree_environment", return_value=False), patch.object(
            hook, "get_changed_ticket_md_files", return_value=["docs/work-logs/v1/tickets/a.md"]
        ), patch.object(hook, "find_project_root", return_value=Path("/r")), patch.object(
            hook, "has_active_background_agents", return_value=True
        ), patch.object(hook, "auto_commit_ticket_md") as ac:
            assert hook.main() == 0
            ac.assert_not_called()

    def test_captures_when_no_active_agents(self):
        with patch.object(hook, "is_worktree_environment", return_value=False), patch.object(
            hook, "get_changed_ticket_md_files", return_value=["docs/work-logs/v1/tickets/a.md"]
        ), patch.object(hook, "find_project_root", return_value=Path("/r")), patch.object(
            hook, "has_active_background_agents", return_value=False
        ), patch.object(
            hook, "build_commit_message", return_value="auto(ticket-md): msg"
        ), patch.object(hook, "auto_commit_ticket_md", return_value=True) as ac:
            assert hook.main() == 0
            ac.assert_called_once()
