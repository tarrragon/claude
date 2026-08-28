"""
ticket-md-auto-commit-hook 測試套件

測試覆蓋:
1. 主 repo / worktree 環境判別（僅主 repo 生效）
2. 未提交檔案過濾為 ticket md 範圍（不觸及其他檔案）
3. 防 race：偵測活躍背景代理人時跳過代捕，stale entry 不阻斷兜底
4. 兜底提交（委派 ticket_system.lib.git_ops.commit_files_isolated，見
   TestAutoCommitTicketMdDelegation）

（原 TestAutoCommitTicketMd / TestAutoCommitTicketMdPathNormalization /
TestLockRetry 三個類別測試的是本 hook 自帶的隔離索引 CAS 實作，已改為委派
ticket_system.lib.git_ops.commit_files_isolated——與 lifecycle.complete()、
ticket_system.lib.git_utils._auto_commit_ticket_md 共用同一份實作，
GIT_INDEX_FILE 隔離、提交範圍自我驗證、index.lock 重試、絕對/相對路徑
正規化等底層行為已由 test_git_ops.py 完整涵蓋，故予以移除，改以
TestAutoCommitTicketMdDelegation 驗證本 hook 正確委派並轉譯回傳型別。）
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
    """路徑過濾邏輯測試——session 歸屬過濾以 patch `get_session_claimed_ticket_ids`
    隔離，聚焦本類別驗證路徑萃取/過濾本身（session 歸屬過濾的完整行為見
    `TestSessionAttributionFilter`）。"""

    def test_filters_to_ticket_md_only(self, logger):
        statuses = [
            hook.FileStatus(status=" M", file_path="docs/work-logs/v1/tickets/a.md"),
            hook.FileStatus(status=" M", file_path="lib/main.dart"),
            hook.FileStatus(status="??", file_path="docs/work-logs/v1/tickets/b.md"),
        ]
        with patch.object(hook, "get_uncommitted_files", return_value=statuses), \
                patch.object(hook, "get_session_claimed_ticket_ids", return_value={"a", "b"}):
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
        with patch.object(hook, "get_uncommitted_files", return_value=statuses), \
                patch.object(hook, "get_session_claimed_ticket_ids", return_value={"new"}):
            files = hook.get_changed_ticket_md_files(logger)
        assert files == ["docs/work-logs/v1/tickets/new.md"]

    def test_empty_when_no_ticket_md(self, logger):
        statuses = [hook.FileStatus(status=" M", file_path="lib/main.dart")]
        with patch.object(hook, "get_uncommitted_files", return_value=statuses):
            assert hook.get_changed_ticket_md_files(logger) == []

    def test_empty_when_clean(self, logger):
        with patch.object(hook, "get_uncommitted_files", return_value=[]):
            assert hook.get_changed_ticket_md_files(logger) == []


class TestSessionAttributionFilter:
    """session 歸屬過濾（0.2.1-W3-1075 核心）：僅納入本 session 現正認領中
    的 ticket md；歸屬無法判定時保守排除全部候選；排除須留痕於 hook log。"""

    _TWO_CANDIDATES = [
        hook.FileStatus(status=" M", file_path="docs/work-logs/v1/tickets/mine.md"),
        hook.FileStatus(status=" M", file_path="docs/work-logs/v1/tickets/theirs.md"),
    ]

    def test_only_session_claimed_ticket_included(self, logger):
        """工作區同時存在他 session 在途的 ticket md：僅本 session 認領的納入。"""
        with patch.object(
            hook, "get_uncommitted_files", return_value=self._TWO_CANDIDATES
        ), patch.object(
            hook, "get_session_claimed_ticket_ids", return_value={"mine"}
        ):
            files = hook.get_changed_ticket_md_files(logger)
        assert files == ["docs/work-logs/v1/tickets/mine.md"]

    def test_all_excluded_when_attribution_source_unavailable(self, logger):
        """歸屬判定來源不可用（回傳 None）時，保守排除全部候選（acceptance 第 2 項）。"""
        with patch.object(
            hook, "get_uncommitted_files", return_value=self._TWO_CANDIDATES
        ), patch.object(hook, "get_session_claimed_ticket_ids", return_value=None):
            files = hook.get_changed_ticket_md_files(logger)
        assert files == []

    def test_all_excluded_when_session_has_no_claims(self, logger):
        """本 session 合法地未認領任何票（空集合，非 None）：候選皆排除。"""
        with patch.object(
            hook, "get_uncommitted_files", return_value=self._TWO_CANDIDATES
        ), patch.object(hook, "get_session_claimed_ticket_ids", return_value=set()):
            files = hook.get_changed_ticket_md_files(logger)
        assert files == []

    def test_exclusion_logged_with_reason(self, logger, caplog):
        """排除須留痕（acceptance 第 2 項可觀測性）：被排除路徑出現於 log。"""
        import logging as _logging

        with caplog.at_level(_logging.INFO, logger=logger.name):
            with patch.object(
                hook, "get_uncommitted_files", return_value=self._TWO_CANDIDATES
            ), patch.object(
                hook, "get_session_claimed_ticket_ids", return_value={"mine"}
            ):
                hook.get_changed_ticket_md_files(logger)
        assert any(
            "theirs.md" in record.getMessage() for record in caplog.records
        ), "被排除的路徑應出現於 hook log（可觀測性，不可靜默丟失）"

    def test_get_session_claimed_ticket_ids_none_when_session_id_missing(
        self, logger, monkeypatch
    ):
        """CLAUDE_CODE_SESSION_ID 未設定時，歸屬判定來源視為不可用。"""
        monkeypatch.delenv(hook.ENV_SESSION_ID, raising=False)
        assert hook.get_session_claimed_ticket_ids(logger) is None

    def test_get_session_claimed_ticket_ids_none_when_registry_degraded(
        self, logger, monkeypatch, tmp_path
    ):
        """pm-registry 讀取降級（缺檔/損毀）時，歸屬判定來源視為不可用。"""
        monkeypatch.setenv(hook.ENV_SESSION_ID, "sess-abc")
        registry_file = tmp_path / "pm-registry.json"
        lock_file = tmp_path / "pm-registry.lock"
        with patch.object(
            hook, "get_registry_paths", return_value=(registry_file, lock_file)
        ):
            # registry_file 不存在 -> read_registry 回傳 degraded 骨架
            assert hook.get_session_claimed_ticket_ids(logger) is None

    def test_get_session_claimed_ticket_ids_returns_claimed_set(
        self, logger, monkeypatch, tmp_path
    ):
        """pm-registry 存在且本 session 有認領票時，回傳其 tickets 集合。"""
        import json

        monkeypatch.setenv(hook.ENV_SESSION_ID, "sess-abc")
        registry_file = tmp_path / "pm-registry.json"
        lock_file = tmp_path / "pm-registry.lock"
        registry_file.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "sessions": {
                        "sess-abc": {
                            "name": "n", "project": "p",
                            "registered_at": "t", "heartbeat_ts": "t",
                            "tickets": ["0.0.0-W0-X", "0.0.0-W0-Y"],
                            "files": [],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        with patch.object(
            hook, "get_registry_paths", return_value=(registry_file, lock_file)
        ):
            claimed = hook.get_session_claimed_ticket_ids(logger)
        assert claimed == {"0.0.0-W0-X", "0.0.0-W0-Y"}

    def test_get_session_claimed_ticket_ids_empty_set_when_session_unregistered(
        self, logger, monkeypatch, tmp_path
    ):
        """registry 有效但本 session 無 entry：合法空集合（非 None）。"""
        import json

        monkeypatch.setenv(hook.ENV_SESSION_ID, "sess-unknown")
        registry_file = tmp_path / "pm-registry.json"
        lock_file = tmp_path / "pm-registry.lock"
        registry_file.write_text(
            json.dumps({"schema_version": 2, "sessions": {}}), encoding="utf-8"
        )
        with patch.object(
            hook, "get_registry_paths", return_value=(registry_file, lock_file)
        ):
            claimed = hook.get_session_claimed_ticket_ids(logger)
        assert claimed == set()


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


class TestAutoCommitTicketMdDelegation:
    """驗證 hook.auto_commit_ticket_md 正確委派 git_ops.commit_files_isolated
    並轉譯回傳型別（dict -> bool）；GIT_INDEX_FILE 隔離、提交範圍自我驗證、
    index.lock 重試、絕對/相對路徑正規化等底層行為由 test_git_ops.py 涵蓋，
    不在此重複。"""

    _TARGET = "docs/work-logs/v1/tickets/a.md"

    def test_committed_delegates_to_git_ops_and_returns_true(self, logger):
        with patch.object(
            hook.git_ops, "commit_files_isolated",
            return_value={"status": "committed", "commit_sha": "deadbeef", "error": None},
        ) as commit_mock:
            assert hook.auto_commit_ticket_md([self._TARGET], "msg", logger) is True
        commit_mock.assert_called_once_with([self._TARGET], "msg")

    def test_empty_status_treated_as_success(self, logger):
        """paths 內容與 HEAD 相同（empty，graceful skip）視為成功，不視為失敗。"""
        with patch.object(
            hook.git_ops, "commit_files_isolated",
            return_value={"status": "empty", "commit_sha": None, "error": None},
        ):
            assert hook.auto_commit_ticket_md([self._TARGET], "msg", logger) is True

    def test_failed_status_returns_false(self, logger):
        with patch.object(
            hook.git_ops, "commit_files_isolated",
            return_value={"status": "failed", "commit_sha": None, "error": "add failed"},
        ):
            assert hook.auto_commit_ticket_md([self._TARGET], "msg", logger) is False


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
