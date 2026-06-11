"""
worktree-auto-commit-hook 測試套件（1.0.0-W1-062）

測試覆蓋三道修正：
1. 防 race：偵測活躍背景代理人時跳過代捕，stale entry 不阻斷兜底
2. 訊息富化：從變更檔案匹配 in_progress ticket where.files 推斷 ticket ID
3. 工作不遺失兜底：無活躍代理人時仍代捕 + index.lock 重試（不刪 lock）
"""

import importlib.util
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 動態導入 hook（檔案名含 dash）
_HOOK_FILE = (
    Path(__file__).resolve().parent.parent / "hooks" / "worktree-auto-commit-hook.py"
)
_spec = importlib.util.spec_from_file_location("worktree_auto_commit_hook", _HOOK_FILE)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


@pytest.fixture
def logger():
    return logging.getLogger("test-wac")


def _now_iso(hours_ago=0.0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


# ============================================================================
# 修正 1：防 race
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
        # 超過 MAX_AGE 的派發視為 stale，不阻止兜底（回傳 False）
        dispatches = [
            {"agent_description": "ghost", "dispatched_at": _now_iso(hours_ago=5)}
        ]
        with patch.object(hook, "get_active_dispatches", return_value=dispatches), patch.object(
            hook, "cleanup_expired", return_value=0
        ):
            assert hook.has_active_background_agents(Path("/repo"), logger) is False

    def test_project_root_none_degrades_to_fallback(self, logger):
        # 無法解析 project root 時降級為原始兜底行為（False）
        assert hook.has_active_background_agents(None, logger) is False

    def test_dispatch_tracker_unavailable_degrades(self, logger):
        with patch.object(hook, "get_active_dispatches", None):
            assert hook.has_active_background_agents(Path("/repo"), logger) is False

    def test_read_failure_degrades_to_fallback(self, logger):
        with patch.object(
            hook, "get_active_dispatches", side_effect=OSError("boom")
        ), patch.object(hook, "cleanup_expired", return_value=0):
            assert hook.has_active_background_agents(Path("/repo"), logger) is False

    def test_malformed_timestamp_treated_as_stale(self, logger):
        dispatches = [{"agent_description": "x", "dispatched_at": "not-a-date"}]
        with patch.object(hook, "get_active_dispatches", return_value=dispatches), patch.object(
            hook, "cleanup_expired", return_value=0
        ):
            # 解析失敗視為 stale → 不阻止兜底
            assert hook.has_active_background_agents(Path("/repo"), logger) is False


class TestIsDispatchStale:
    def test_fresh_dispatch_not_stale(self, logger):
        assert hook._is_dispatch_stale({"dispatched_at": _now_iso(0)}, logger) is False

    def test_old_dispatch_stale(self, logger):
        assert hook._is_dispatch_stale({"dispatched_at": _now_iso(5)}, logger) is True

    def test_naive_timestamp_handled(self, logger):
        naive = datetime.now().isoformat()  # 無 tz
        assert hook._is_dispatch_stale({"dispatched_at": naive}, logger) is False

    def test_missing_timestamp_stale(self, logger):
        assert hook._is_dispatch_stale({}, logger) is True


class TestFindProjectRoot:
    def test_prefers_cwd_dispatch_file(self, tmp_path, logger):
        # cwd 內有 .claude/dispatch-active.json → 優先採用 cwd（不查 git-common-dir）
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "dispatch-active.json").write_text("{}", encoding="utf-8")
        with patch.object(hook.Path, "cwd", return_value=tmp_path), patch.object(
            hook.subprocess, "run"
        ) as run:
            root = hook.find_project_root(logger)
        assert root == tmp_path
        run.assert_not_called()

    def test_fallback_to_common_dir(self, tmp_path, logger):
        # cwd 無 dispatch 檔 → fallback 至 git-common-dir 上一層
        common_dir = tmp_path / "mainrepo" / ".git"
        common_dir.mkdir(parents=True)
        proc = MagicMock(returncode=0, stdout=str(common_dir) + "\n", stderr="")
        empty_cwd = tmp_path / "wt"
        empty_cwd.mkdir()
        with patch.object(hook.Path, "cwd", return_value=empty_cwd), patch.object(
            hook.subprocess, "run", return_value=proc
        ):
            root = hook.find_project_root(logger)
        assert root == (tmp_path / "mainrepo")

    def test_returns_none_on_git_failure(self, tmp_path, logger):
        empty_cwd = tmp_path / "wt"
        empty_cwd.mkdir()
        proc = MagicMock(returncode=1, stdout="", stderr="err")
        with patch.object(hook.Path, "cwd", return_value=empty_cwd), patch.object(
            hook.subprocess, "run", return_value=proc
        ):
            assert hook.find_project_root(logger) is None


# ============================================================================
# 修正 2：訊息富化
# ============================================================================


class TestInferTicketIds:
    def _make_ticket(self, tmp_path, ticket_id, status, files):
        td = tmp_path / "docs" / "work-logs" / "v1" / "tickets"
        td.mkdir(parents=True, exist_ok=True)
        f = td / f"{ticket_id}.md"
        f.write_text("# stub", encoding="utf-8")
        return f

    def test_matches_in_progress_ticket(self, tmp_path, logger):
        tf = self._make_ticket(tmp_path, "1.0.0-W1-100", "in_progress", ["src/x.py"])
        with patch.object(hook, "find_ticket_files", return_value=[tf]), patch.object(
            hook,
            "parse_ticket_frontmatter",
            return_value={"id": "1.0.0-W1-100", "status": "in_progress"},
        ), patch.object(
            hook, "extract_where_files_from_frontmatter", return_value=["src/x.py"]
        ):
            ids = hook.infer_ticket_ids(tmp_path, ["src/x.py"], logger)
        assert ids == ["1.0.0-W1-100"]

    def test_ignores_non_in_progress_ticket(self, tmp_path, logger):
        tf = self._make_ticket(tmp_path, "1.0.0-W1-101", "pending", ["src/x.py"])
        with patch.object(hook, "find_ticket_files", return_value=[tf]), patch.object(
            hook,
            "parse_ticket_frontmatter",
            return_value={"id": "1.0.0-W1-101", "status": "pending"},
        ), patch.object(
            hook, "extract_where_files_from_frontmatter", return_value=["src/x.py"]
        ):
            ids = hook.infer_ticket_ids(tmp_path, ["src/x.py"], logger)
        assert ids == []

    def test_no_match_returns_empty(self, tmp_path, logger):
        tf = self._make_ticket(tmp_path, "1.0.0-W1-102", "in_progress", ["src/a.py"])
        with patch.object(hook, "find_ticket_files", return_value=[tf]), patch.object(
            hook,
            "parse_ticket_frontmatter",
            return_value={"id": "1.0.0-W1-102", "status": "in_progress"},
        ), patch.object(
            hook, "extract_where_files_from_frontmatter", return_value=["src/a.py"]
        ):
            ids = hook.infer_ticket_ids(tmp_path, ["src/b.py"], logger)
        assert ids == []

    def test_dependency_unavailable_returns_empty(self, tmp_path, logger):
        with patch.object(hook, "find_ticket_files", None):
            assert hook.infer_ticket_ids(tmp_path, ["src/x.py"], logger) == []

    def test_project_root_none_returns_empty(self, logger):
        assert hook.infer_ticket_ids(None, ["src/x.py"], logger) == []

    def test_normalizes_dot_slash_prefix(self, tmp_path, logger):
        tf = self._make_ticket(tmp_path, "1.0.0-W1-103", "in_progress", ["src/x.py"])
        with patch.object(hook, "find_ticket_files", return_value=[tf]), patch.object(
            hook,
            "parse_ticket_frontmatter",
            return_value={"id": "1.0.0-W1-103", "status": "in_progress"},
        ), patch.object(
            hook, "extract_where_files_from_frontmatter", return_value=["./src/x.py"]
        ):
            ids = hook.infer_ticket_ids(tmp_path, ["src/x.py"], logger)
        assert ids == ["1.0.0-W1-103"]


class TestBuildCommitMessage:
    def test_embeds_ticket_id(self, logger):
        with patch.object(hook, "infer_ticket_ids", return_value=["1.0.0-W1-100"]):
            msg = hook.build_commit_message(Path("/r"), ["src/x.py"], logger)
        assert "1.0.0-W1-100" in msg
        assert msg.startswith("auto(")

    def test_multiple_ticket_ids_joined(self, logger):
        with patch.object(
            hook, "infer_ticket_ids", return_value=["1.0.0-W1-100", "1.0.0-W1-101"]
        ):
            msg = hook.build_commit_message(Path("/r"), ["a.py"], logger)
        assert "1.0.0-W1-100, 1.0.0-W1-101" in msg

    def test_fallback_file_summary_when_no_ticket(self, logger):
        with patch.object(hook, "infer_ticket_ids", return_value=[]):
            msg = hook.build_commit_message(Path("/r"), ["a.py", "b.py"], logger)
        assert "2 files" in msg
        assert "a.py" in msg

    def test_fallback_truncates_long_file_list(self, logger):
        files = [f"f{i}.py" for i in range(10)]
        with patch.object(hook, "infer_ticket_ids", return_value=[]):
            msg = hook.build_commit_message(Path("/r"), files, logger)
        assert "+7 more" in msg


class TestGetChangedFiles:
    def test_parses_porcelain_output(self, logger):
        proc = MagicMock(returncode=0, stdout=" M src/a.py\n?? new.txt\n", stderr="")
        with patch.object(hook.subprocess, "run", return_value=proc):
            files = hook.get_changed_files(logger)
        assert files == ["src/a.py", "new.txt"]

    def test_parses_rename(self, logger):
        proc = MagicMock(returncode=0, stdout="R  old.py -> new.py\n", stderr="")
        with patch.object(hook.subprocess, "run", return_value=proc):
            files = hook.get_changed_files(logger)
        assert files == ["new.py"]

    def test_empty_when_clean(self, logger):
        proc = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(hook.subprocess, "run", return_value=proc):
            assert hook.get_changed_files(logger) == []


# ============================================================================
# 修正 3：兜底 + index.lock 重試
# ============================================================================


class TestLockRetry:
    def test_index_lock_retries_then_succeeds(self, logger):
        lock_fail = MagicMock(returncode=1, stderr="fatal: Unable to create index.lock")
        ok = MagicMock(returncode=0, stderr="")
        with patch.object(hook.subprocess, "run", side_effect=[lock_fail, ok]), patch(
            "time.sleep"
        ):
            success, rc, _ = hook._run_git_with_lock_retry(
                ["git", "add", "-A"], logger, "add", max_retries=3, wait_seconds=0
            )
        assert success is True
        assert rc == 0

    def test_non_lock_error_no_retry(self, logger):
        fail = MagicMock(returncode=1, stderr="fatal: some other error")
        with patch.object(hook.subprocess, "run", return_value=fail) as run, patch(
            "time.sleep"
        ):
            success, _, _ = hook._run_git_with_lock_retry(
                ["git", "add", "-A"], logger, "add", max_retries=3, wait_seconds=0
            )
        assert success is False
        # 非 lock 錯誤不重試，只呼叫一次
        assert run.call_count == 1

    def test_lock_persists_exhausts_retries(self, logger):
        lock_fail = MagicMock(returncode=1, stderr="Unable to create index.lock")
        with patch.object(
            hook.subprocess, "run", return_value=lock_fail
        ) as run, patch("time.sleep"):
            success, _, _ = hook._run_git_with_lock_retry(
                ["git", "commit"], logger, "commit", max_retries=3, wait_seconds=0
            )
        assert success is False
        assert run.call_count == 3

    def test_does_not_delete_lock_file(self, logger):
        # 確認重試路徑不觸碰 lock 檔刪除（無 os.remove / unlink 呼叫）
        lock_fail = MagicMock(returncode=1, stderr="Unable to create index.lock")
        ok = MagicMock(returncode=0, stderr="")
        with patch.object(
            hook.subprocess, "run", side_effect=[lock_fail, ok]
        ), patch("time.sleep"), patch("os.remove") as rm, patch(
            "pathlib.Path.unlink"
        ) as unlink:
            hook._run_git_with_lock_retry(
                ["git", "add", "-A"], logger, "add", wait_seconds=0
            )
        rm.assert_not_called()
        unlink.assert_not_called()


class TestAutoCommit:
    def test_success_path(self, logger):
        ok = MagicMock(returncode=0, stderr="")
        with patch.object(hook.subprocess, "run", return_value=ok):
            assert hook.auto_commit("msg", logger) is True

    def test_add_failure_aborts(self, logger):
        fail = MagicMock(returncode=1, stderr="add failed")
        with patch.object(hook.subprocess, "run", return_value=fail):
            assert hook.auto_commit("msg", logger) is False


# ============================================================================
# main 流程整合
# ============================================================================


class TestMainFlow:
    def test_skips_when_not_worktree(self):
        with patch.object(hook, "is_worktree_environment", return_value=False):
            assert hook.main() == 0

    def test_skips_when_clean(self):
        with patch.object(hook, "is_worktree_environment", return_value=True), patch.object(
            hook, "get_changed_files", return_value=[]
        ):
            assert hook.main() == 0

    def test_skips_capture_when_active_agents(self):
        with patch.object(hook, "is_worktree_environment", return_value=True), patch.object(
            hook, "get_changed_files", return_value=["a.py"]
        ), patch.object(hook, "find_project_root", return_value=Path("/r")), patch.object(
            hook, "has_active_background_agents", return_value=True
        ), patch.object(hook, "auto_commit") as ac:
            assert hook.main() == 0
            ac.assert_not_called()

    def test_captures_when_no_active_agents(self):
        with patch.object(hook, "is_worktree_environment", return_value=True), patch.object(
            hook, "get_changed_files", return_value=["a.py"]
        ), patch.object(hook, "find_project_root", return_value=Path("/r")), patch.object(
            hook, "has_active_background_agents", return_value=False
        ), patch.object(
            hook, "build_commit_message", return_value="auto: msg"
        ), patch.object(hook, "auto_commit", return_value=True) as ac:
            assert hook.main() == 0
            ac.assert_called_once()
