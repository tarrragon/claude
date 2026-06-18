"""
worktree-remove-deliverable-check-hook 測試套件（1.2.0-W1-030 Guard A）

防護目標：`git worktree remove` 前，若分支有未 merge 進 main 的交付物則阻擋。
來源事故：1.2.0-W1-028 事故一（未提交產品碼遭 force-remove 永久遺失）。
"""

import importlib.util
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

_HOOK_FILE = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "worktree-remove-deliverable-check-hook.py"
)
_spec = importlib.util.spec_from_file_location(
    "worktree_remove_deliverable_check_hook", _HOOK_FILE
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


@pytest.fixture
def logger():
    return logging.getLogger("test-wrd")


# ---------------------------------------------------------------------------
# _extract_remove_paths
# ---------------------------------------------------------------------------


class TestExtractRemovePaths:
    def test_simple_remove(self, logger):
        cmd = "git worktree remove .claude/worktrees/agent-abc"
        assert hook._extract_remove_paths(cmd, logger) == [".claude/worktrees/agent-abc"]

    def test_remove_with_force_flag(self, logger):
        cmd = "git worktree remove --force .claude/worktrees/agent-abc"
        assert hook._extract_remove_paths(cmd, logger) == [".claude/worktrees/agent-abc"]

    def test_remove_short_force_flag(self, logger):
        cmd = "git worktree remove -f .claude/worktrees/agent-xyz"
        assert hook._extract_remove_paths(cmd, logger) == [".claude/worktrees/agent-xyz"]

    def test_quoted_path(self, logger):
        cmd = "git worktree remove '.claude/worktrees/agent-q'"
        assert hook._extract_remove_paths(cmd, logger) == [".claude/worktrees/agent-q"]

    def test_chained_removes(self, logger):
        cmd = "git worktree remove wt-a && git worktree remove wt-b"
        assert hook._extract_remove_paths(cmd, logger) == ["wt-a", "wt-b"]

    def test_batch_script_no_static_path(self, logger):
        # while-read 批量腳本：path token 解析不出具體路徑（含 shell 變數）
        cmd = 'git worktree list | while read wt; do git worktree remove "$wt"; done'
        # "$wt" 不以 - 開頭，會被當 path token；確保不誤判為無路徑時仍安全（見 main 略過邏輯）
        paths = hook._extract_remove_paths(cmd, logger)
        assert paths == ['$wt']


# ---------------------------------------------------------------------------
# _branch_of_worktree
# ---------------------------------------------------------------------------


class TestBranchOfWorktree:
    def test_matches_by_path_basename(self, logger):
        porcelain = (
            "worktree /repo\n"
            "HEAD aaa\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /repo/.claude/worktrees/agent-abc\n"
            "HEAD bbb\n"
            "branch refs/heads/feat/1.2.0-W1-030\n"
        )
        with patch.object(hook, "run_git", return_value=porcelain):
            result = hook._branch_of_worktree(".claude/worktrees/agent-abc", logger)
        assert result == "feat/1.2.0-W1-030"

    def test_detached_returns_none(self, logger):
        porcelain = (
            "worktree /repo/.claude/worktrees/agent-abc\n"
            "HEAD bbb\n"
            "detached\n"
        )
        with patch.object(hook, "run_git", return_value=porcelain):
            assert hook._branch_of_worktree(".claude/worktrees/agent-abc", logger) is None

    def test_git_failure_returns_none(self, logger):
        with patch.object(hook, "run_git", return_value=None):
            assert hook._branch_of_worktree("anything", logger) is None


# ---------------------------------------------------------------------------
# _unmerged_files
# ---------------------------------------------------------------------------


class TestUnmergedFiles:
    def test_unmerged_commits_with_files(self, logger):
        def fake_run_git(args, **kwargs):
            if "log" in args:
                return "bbb feat commit"
            if "diff" in args:
                return "app/lib/foo.dart\napp/lib/bar.dart"
            return None

        with patch.object(hook, "run_git", side_effect=fake_run_git):
            files = hook._unmerged_files("feat/x", logger)
        assert files == ["app/lib/foo.dart", "app/lib/bar.dart"]

    def test_no_unmerged_commits(self, logger):
        def fake_run_git(args, **kwargs):
            if "log" in args:
                return ""  # 無未合併 commit
            return None

        with patch.object(hook, "run_git", side_effect=fake_run_git):
            assert hook._unmerged_files("feat/x", logger) == []

    def test_git_log_failure_returns_none(self, logger):
        with patch.object(hook, "run_git", return_value=None):
            assert hook._unmerged_files("feat/x", logger) is None


# ---------------------------------------------------------------------------
# main 整合
# ---------------------------------------------------------------------------


class TestMain:
    def test_non_remove_command_passes(self):
        with patch.object(
            hook, "read_json_from_stdin", return_value={"tool_input": {"command": "git status"}}
        ):
            assert hook.main() == 0

    def test_empty_stdin_passes(self):
        with patch.object(hook, "read_json_from_stdin", return_value=None):
            assert hook.main() == 0

    def test_block_when_unmerged_deliverable(self, capsys):
        data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/1.2.0-W1-030"
        ), patch.object(hook, "_unmerged_files", return_value=["app/lib/foo.dart"]):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "Guard A" in captured.err
        assert "app/lib/foo.dart" in captured.err

    def test_pass_when_no_unmerged_deliverable(self, capsys):
        data = {"tool_input": {"command": "git worktree remove .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]):
            assert hook.main() == 0

    def test_pass_when_branch_not_found(self):
        data = {"tool_input": {"command": "git worktree remove some-path"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value=None
        ):
            assert hook.main() == 0

    def test_pass_when_git_query_fails(self):
        data = {"tool_input": {"command": "git worktree remove some-path"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=None):
            assert hook.main() == 0
