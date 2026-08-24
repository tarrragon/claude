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
    _TARGET = "docs/work-logs/v1/tickets/a.md"

    def _fake_run_factory(self, calls, extra_changed=None):
        """建立模擬 git plumbing 各步驟輸出的 fake subprocess.run。"""
        extra_changed = extra_changed or []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["git", "rev-parse"]:
                return MagicMock(returncode=0, stdout="old_head_sha\n", stderr="")
            if args[:2] == ["git", "read-tree"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "add"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "write-tree"]:
                return MagicMock(returncode=0, stdout="tree_sha\n", stderr="")
            if args[:2] == ["git", "commit-tree"]:
                return MagicMock(returncode=0, stdout="new_commit_sha\n", stderr="")
            if args[:2] == ["git", "diff"]:
                changed = [self._TARGET] + extra_changed
                return MagicMock(returncode=0, stdout="\n".join(changed) + "\n", stderr="")
            if args[:2] == ["git", "update-ref"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            raise AssertionError(f"未預期的 git 呼叫: {args}")

        return fake_run

    def test_add_scope_limited_to_ticket_md(self, logger):
        """驗證 git add 呼叫的參數僅含指定的 ticket md 路徑，無 -A。"""
        calls = []
        with patch.object(
            hook.subprocess, "run", side_effect=self._fake_run_factory(calls)
        ):
            assert hook.auto_commit_ticket_md([self._TARGET], "msg", logger) is True
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 1
        assert add_calls[0] == ["git", "add", "--", self._TARGET]
        assert "-A" not in add_calls[0]

    def test_never_invokes_bare_commit(self, logger):
        """驗證提交路徑不經過 `git commit`（改用 plumbing，天然不觸發
        pre-commit/commit-msg hook，含 bare-commit-guard-hook）。"""
        calls = []
        with patch.object(
            hook.subprocess, "run", side_effect=self._fake_run_factory(calls)
        ):
            assert hook.auto_commit_ticket_md([self._TARGET], "msg", logger) is True
        assert all(c[:2] != ["git", "commit"] for c in calls)
        assert any(c[:2] == ["git", "commit-tree"] for c in calls)
        assert any(c[:2] == ["git", "update-ref"] for c in calls)

    def test_add_failure_aborts(self, logger):
        def fake_run(args, **kwargs):
            if args[:2] == ["git", "rev-parse"]:
                return MagicMock(returncode=0, stdout="old_head_sha\n", stderr="")
            if args[:2] == ["git", "read-tree"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "add"]:
                return MagicMock(returncode=1, stdout="", stderr="add failed")
            raise AssertionError(f"未預期的 git 呼叫: {args}")

        with patch.object(hook.subprocess, "run", side_effect=fake_run):
            assert (
                hook.auto_commit_ticket_md([self._TARGET], "msg", logger) is False
            )

    def test_scope_self_check_rejects_unexpected_extra_file(self, logger):
        """diff 範圍自我驗證：新 commit 若含指定範圍以外的檔案，放棄 update-ref。"""
        calls = []
        with patch.object(
            hook.subprocess,
            "run",
            side_effect=self._fake_run_factory(
                calls, extra_changed=["lib/main.dart"]
            ),
        ):
            assert hook.auto_commit_ticket_md([self._TARGET], "msg", logger) is False
        assert all(c[:2] != ["git", "update-ref"] for c in calls)

    def test_update_ref_cas_failure_returns_false(self, logger):
        """update-ref 帶舊值失敗（HEAD 於期間被並行移動）時回傳 False，不覆蓋。"""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["git", "rev-parse"]:
                return MagicMock(returncode=0, stdout="old_head_sha\n", stderr="")
            if args[:2] == ["git", "read-tree"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "add"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "write-tree"]:
                return MagicMock(returncode=0, stdout="tree_sha\n", stderr="")
            if args[:2] == ["git", "commit-tree"]:
                return MagicMock(returncode=0, stdout="new_commit_sha\n", stderr="")
            if args[:2] == ["git", "diff"]:
                return MagicMock(returncode=0, stdout=self._TARGET + "\n", stderr="")
            if args[:2] == ["git", "update-ref"]:
                return MagicMock(returncode=1, stdout="", stderr="fatal: HEAD 已改變")
            raise AssertionError(f"未預期的 git 呼叫: {args}")

        with patch.object(hook.subprocess, "run", side_effect=fake_run):
            assert hook.auto_commit_ticket_md([self._TARGET], "msg", logger) is False


class TestAutoCommitTicketMdPathNormalization:
    """實地觸發：真實 git repo 驗證絕對/相對路徑輸入自我驗證皆通過（W3-918）。

    `git diff --name-only` 一律輸出相對 repo root 的路徑；ticket_md_files
    若夾帶絕對路徑（cwd 不等於 repo root 時的實際觀察案例），逐字比較曾誤判
    為範圍不符而放棄提交。此處以真實 git 命令（非 mock）重現並驗證修復。
    """

    def _init_repo(self, tmp_path):
        """建立最小可用的真實 git repo，回傳 (repo_root, ticket_md_path)。"""
        import subprocess as sp

        repo = tmp_path / "repo"
        repo.mkdir()
        run = lambda args: sp.run(  # noqa: E731
            args, cwd=repo, check=True, capture_output=True, text=True
        )
        run(["git", "init", "-q"])
        run(["git", "config", "user.email", "t@example.com"])
        run(["git", "config", "user.name", "t"])
        ticket_dir = repo / "docs" / "work-logs" / "v1" / "tickets"
        ticket_dir.mkdir(parents=True)
        ticket_md = ticket_dir / "a.md"
        ticket_md.write_text("initial\n", encoding="utf-8")
        run(["git", "add", "-A"])
        run(["git", "commit", "-q", "-m", "init"])
        ticket_md.write_text("changed\n", encoding="utf-8")
        return repo, ticket_md

    def test_relative_path_input_passes_self_check(self, tmp_path, logger):
        """相對路徑輸入（既有主路徑）自我驗證通過，liveness 落 commit-tree。"""
        repo, ticket_md = self._init_repo(tmp_path)
        rel_path = "docs/work-logs/v1/tickets/a.md"
        real_run = hook.subprocess.run

        def spy(args, **kwargs):
            kwargs.setdefault("cwd", repo)
            return real_run(args, **kwargs)

        with patch.object(hook.Path, "cwd", return_value=repo):
            with patch.object(hook.subprocess, "run", side_effect=spy):
                result = hook.auto_commit_ticket_md(
                    [rel_path], "auto(ticket-md): test", logger
                )
        assert result is True
        log = __import__("subprocess").run(
            ["git", "log", "-1", "--pretty=%s"], cwd=repo, capture_output=True, text=True
        ).stdout.strip()
        assert log == "auto(ticket-md): test"

    def test_absolute_path_input_passes_self_check(self, tmp_path, logger):
        """絕對路徑輸入（W3-913 觀察到的誤判分支）自我驗證通過，非放棄提交。"""
        repo, ticket_md = self._init_repo(tmp_path)
        abs_path = str(ticket_md)
        real_run = hook.subprocess.run

        def spy(args, **kwargs):
            kwargs.setdefault("cwd", repo)
            return real_run(args, **kwargs)

        with patch.object(hook.Path, "cwd", return_value=repo):
            with patch.object(hook.subprocess, "run", side_effect=spy):
                result = hook.auto_commit_ticket_md(
                    [abs_path], "auto(ticket-md): test-abs", logger
                )
        assert result is True, "絕對路徑輸入不應觸發提交範圍自我驗證失敗"
        log = __import__("subprocess").run(
            ["git", "log", "-1", "--pretty=%s"], cwd=repo, capture_output=True, text=True
        ).stdout.strip()
        assert log == "auto(ticket-md): test-abs"

    def test_mismatched_absolute_path_still_rejected(self, tmp_path, logger):
        """正規化不掩蓋真實範圍不符：絕對路徑指向未變更檔案仍應放棄提交。"""
        repo, ticket_md = self._init_repo(tmp_path)
        other = repo / "docs" / "work-logs" / "v1" / "tickets" / "other.md"
        # other.md 未實際變更，僅用來構造「範圍不符」的輸入
        wrong_abs_path = str(other)
        real_run = hook.subprocess.run

        def spy(args, **kwargs):
            kwargs.setdefault("cwd", repo)
            return real_run(args, **kwargs)

        with patch.object(hook.Path, "cwd", return_value=repo):
            with patch.object(hook.subprocess, "run", side_effect=spy):
                result = hook.auto_commit_ticket_md(
                    [wrong_abs_path], "auto(ticket-md): test-mismatch", logger
                )
        assert result is False
        log = __import__("subprocess").run(
            ["git", "log", "-1", "--pretty=%s"], cwd=repo, capture_output=True, text=True
        ).stdout.strip()
        assert log == "init", "範圍不符時不應提交，HEAD 應維持 init"


class TestLockRetry:
    def test_index_lock_retries_then_succeeds(self, logger):
        lock_fail = MagicMock(returncode=1, stdout="", stderr="fatal: Unable to create index.lock")
        ok = MagicMock(returncode=0, stdout="done", stderr="")
        with patch.object(hook.subprocess, "run", side_effect=[lock_fail, ok]), patch(
            "time.sleep"
        ):
            success, stdout, _ = hook._run_git_with_lock_retry(
                ["git", "add", "--", "a.md"], logger, "add", max_retries=3, wait_seconds=0
            )
        assert success is True
        assert stdout == "done"

    def test_does_not_delete_lock_file(self, logger):
        lock_fail = MagicMock(returncode=1, stdout="", stderr="Unable to create index.lock")
        ok = MagicMock(returncode=0, stdout="", stderr="")
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
