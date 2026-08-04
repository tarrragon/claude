"""
Agent Commit Verification Hook - 逐 worktree 未提交變更檢查測試（0.2.1-W3-283）

防護目標（issue 46 症狀四驗收側）：代理人在 worktree 完成實作但產品碼從未
commit，分支上只有 ticket CLI 的 append-log commit。既有 get_uncommitted_files
以主 repo 為 cwd 跑 git status，看不見 worktree 的獨立 working tree；
get_unmerged_worktrees 只查 commit 歷史，該情境下反而判定「有未合併 commit
請 merge」的綠燈式提醒。本測試驗證 get_worktree_uncommitted_files 逐 worktree
執行 `git -C <path> status --porcelain`，於代理人回報當下即可見未落地內容。
"""

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "agent_commit_verification_hook_worktree_uncommitted",
    _HOOKS_DIR / "agent-commit-verification-hook.py",
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_logger = logging.getLogger("test-wt-uncommitted")


def _mock_result(stdout: str, returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = ""
    return result


def _patch_git_utils_subprocess(stdout: str, returncode: int = 0, side_effect=None):
    """0.2.1-W3-286：list_worktrees / get_worktree_uncommitted_files 改呼叫
    lib.git_utils 共用實作，patch 對象隨之從 hook.subprocess 改為
    git_utils.subprocess（hook 自身不再直接呼叫 subprocess 執行這兩類查詢）。
    """
    from lib import git_utils as _git_utils_mod
    if side_effect is not None:
        return patch.object(_git_utils_mod.subprocess, "run", side_effect=side_effect)
    return patch.object(
        _git_utils_mod.subprocess, "run",
        return_value=_mock_result(stdout, returncode),
    )


# ---------------------------------------------------------------------------
# get_worktree_uncommitted_files
# ---------------------------------------------------------------------------


class TestGetWorktreeUncommittedFiles:
    def test_dirty_worktree_reports_files(self):
        """worktree 有未提交產品碼 → 回傳該 worktree 的檔案清單。"""
        with _patch_git_utils_subprocess(" M lib/screen_clock.dart\n?? lib/new_widget.dart\n"):
            result = hook.get_worktree_uncommitted_files(
                [("/repo/.claude/worktrees/agent-abc", "feat/1.4.0-W3-027")], _logger
            )

        assert result == [
            (
                "/repo/.claude/worktrees/agent-abc",
                "feat/1.4.0-W3-027",
                ["lib/screen_clock.dart", "lib/new_widget.dart"],
            )
        ]

    def test_clean_worktree_not_reported(self):
        """worktree 乾淨（無未提交變更）→ 不出現在結果中，不誤報。"""
        with _patch_git_utils_subprocess(""):
            result = hook.get_worktree_uncommitted_files(
                [("/repo/.claude/worktrees/agent-clean", "feat/x")], _logger
            )

        assert result == []

    def test_multiple_worktrees_mixed_dirty_and_clean(self):
        """多 worktree 混合：只回傳 dirty 的那些，clean 的略過。

        0.2.1-W3-286 收斂後改呼叫 git_utils.run_git_command，該函式以
        `cwd=` kwarg（非 `-C` flag）指定 worktree 路徑，fake_run 依此判斷。
        """
        def fake_run(cmd, **kwargs):
            path = kwargs.get("cwd")
            if path == "/repo/.claude/worktrees/agent-dirty":
                return _mock_result(" M lib/foo.dart\n")
            return _mock_result("")

        with _patch_git_utils_subprocess(None, side_effect=fake_run):
            result = hook.get_worktree_uncommitted_files(
                [
                    ("/repo/.claude/worktrees/agent-dirty", "feat/a"),
                    ("/repo/.claude/worktrees/agent-clean", "feat/b"),
                ],
                _logger,
            )

        assert len(result) == 1
        assert result[0][0] == "/repo/.claude/worktrees/agent-dirty"
        assert result[0][2] == ["lib/foo.dart"]

    def test_excluded_prefixes_filtered_same_as_main_repo(self):
        """`.claude/` 與 `docs/` 前綴沿用主 repo 同一份豁免清單。"""
        with _patch_git_utils_subprocess(
            " M .claude/hooks/some-hook.py\n"
            " M docs/work-logs/v0/ticket.md\n"
            " M lib/real_feature.dart\n"
        ):
            result = hook.get_worktree_uncommitted_files(
                [("/repo/.claude/worktrees/agent-abc", "feat/x")], _logger
            )

        assert result == [
            ("/repo/.claude/worktrees/agent-abc", "feat/x", ["lib/real_feature.dart"])
        ]

    def test_all_files_excluded_worktree_not_reported(self):
        """過濾豁免路徑後檔案清單為空時，該 worktree 不出現在結果中。"""
        with _patch_git_utils_subprocess(" M docs/work-logs/v0/ticket.md\n"):
            result = hook.get_worktree_uncommitted_files(
                [("/repo/.claude/worktrees/agent-abc", "feat/x")], _logger
            )

        assert result == []

    def test_git_status_failure_skips_worktree_gracefully(self):
        """git status 查詢失敗（非零 returncode）時略過，不崩潰、不誤報。"""
        with _patch_git_utils_subprocess("", returncode=128):
            result = hook.get_worktree_uncommitted_files(
                [("/repo/.claude/worktrees/agent-abc", "feat/x")], _logger
            )

        assert result == []

    def test_git_status_timeout_skips_worktree_gracefully(self):
        """git status 逾時時略過，不崩潰。"""
        import subprocess as _subprocess

        def _raise(*a, **kw):
            raise _subprocess.TimeoutExpired(cmd="git", timeout=5)

        with _patch_git_utils_subprocess(None, side_effect=_raise):
            result = hook.get_worktree_uncommitted_files(
                [("/repo/.claude/worktrees/agent-abc", "feat/x")], _logger
            )

        assert result == []

    def test_empty_worktree_list_returns_empty(self):
        assert hook.get_worktree_uncommitted_files([], _logger) == []


# ---------------------------------------------------------------------------
# build_worktree_uncommitted_message
# ---------------------------------------------------------------------------


class TestBuildWorktreeUncommittedMessage:
    def test_message_contains_path_branch_and_files(self):
        message = hook.build_worktree_uncommitted_message(
            [hook.WorktreeItems("/repo/.claude/worktrees/agent-abc", "feat/1.4.0-W3-027", ["lib/screen_clock.dart"])]
        )
        assert "feat/1.4.0-W3-027" in message
        assert "/repo/.claude/worktrees/agent-abc" in message
        assert "lib/screen_clock.dart" in message
        assert hook.MSG_WORKTREE_UNCOMMITTED_TITLE in message

    def test_message_distinguishable_from_main_repo_warning(self):
        """訊息標題須與主 repo 未 commit 警告區分來源。"""
        message = hook.build_worktree_uncommitted_message(
            [hook.WorktreeItems("/repo/.claude/worktrees/agent-abc", "feat/x", ["lib/a.dart"])]
        )
        assert message != hook.build_warning_message("desc", ["lib/a.dart"])
        assert hook.MSG_TITLE not in message


# ---------------------------------------------------------------------------
# list_worktrees（既有 get_unmerged_worktrees 解析邏輯抽出後的共用函式）
# ---------------------------------------------------------------------------


class TestListWorktrees:
    def test_parses_non_main_worktrees(self):
        porcelain = (
            "worktree /repo\n"
            "HEAD aaa\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /repo/.claude/worktrees/agent-abc\n"
            "HEAD bbb\n"
            "branch refs/heads/feat/x\n"
        )
        with _patch_git_utils_subprocess(porcelain):
            result = hook.list_worktrees("/repo", _logger)

        assert result == [("/repo/.claude/worktrees/agent-abc", "feat/x")]

    def test_git_failure_returns_empty(self):
        with _patch_git_utils_subprocess("", returncode=1):
            assert hook.list_worktrees("/repo", _logger) == []


# ---------------------------------------------------------------------------
# main() 整合：worktree 未提交變更觸發 PM 立即動作摘要
# ---------------------------------------------------------------------------


class TestMainIntegration:
    def _base_input(self):
        return {"agent_id": "agent-1", "stop_hook_active": False}

    def test_main_includes_worktree_uncommitted_warning(self, monkeypatch, capsys):
        monkeypatch.setattr(hook, "read_json_from_stdin", lambda logger: self._base_input())
        monkeypatch.setattr(hook, "get_project_root", lambda: Path("/repo"))
        monkeypatch.setattr(hook, "_lookup_agent_info", lambda root, aid, lg: ("desc", True))
        monkeypatch.setattr(hook, "get_uncommitted_files", lambda root, lg: [])
        monkeypatch.setattr(hook, "list_worktrees", lambda root, lg: [("/repo/.claude/worktrees/agent-abc", "feat/x")])
        monkeypatch.setattr(
            hook, "get_worktree_uncommitted_files",
            lambda worktrees, lg: [
                hook.WorktreeItems("/repo/.claude/worktrees/agent-abc", "feat/x", ["lib/foo.dart"])
            ],
        )
        monkeypatch.setattr(hook, "get_unmerged_worktrees", lambda root, lg, worktrees=None: [])
        monkeypatch.setattr(hook, "get_unmerged_feature_branches", lambda root, lg, names: [])
        monkeypatch.setattr(hook, "scan_hook_errors", lambda root, minutes, lg: [])

        with pytest.raises(SystemExit) as exc_info:
            hook.main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "lib/foo.dart" in captured.out
        assert hook.MSG_WORKTREE_UNCOMMITTED_TITLE in captured.out
        assert hook.MSG_PM_ACTION_TITLE in captured.out

    def test_main_clean_worktree_no_warning(self, monkeypatch, capsys):
        monkeypatch.setattr(hook, "read_json_from_stdin", lambda logger: self._base_input())
        monkeypatch.setattr(hook, "get_project_root", lambda: Path("/repo"))
        monkeypatch.setattr(hook, "_lookup_agent_info", lambda root, aid, lg: ("desc", False))
        monkeypatch.setattr(hook, "get_uncommitted_files", lambda root, lg: [])
        monkeypatch.setattr(hook, "list_worktrees", lambda root, lg: [("/repo/.claude/worktrees/agent-clean", "feat/x")])
        monkeypatch.setattr(hook, "get_worktree_uncommitted_files", lambda worktrees, lg: [])
        monkeypatch.setattr(hook, "get_unmerged_worktrees", lambda root, lg, worktrees=None: [])
        monkeypatch.setattr(hook, "get_unmerged_feature_branches", lambda root, lg, names: [])
        monkeypatch.setattr(hook, "scan_hook_errors", lambda root, minutes, lg: [])

        with pytest.raises(SystemExit) as exc_info:
            hook.main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert captured.out.strip() == ""
