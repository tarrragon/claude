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
    def test_matches_by_absolute_path(self, logger):
        """0.2.1-W3-286：路徑比對鍵改採絕對路徑（原末段名稱比對已移除）。"""
        target_abs = "/repo/.claude/worktrees/agent-abc"
        worktrees = [
            {"path": "/repo", "branch": "main"},
            {"path": target_abs, "branch": "feat/1.2.0-W1-030"},
        ]
        with patch.object(hook, "get_worktree_list", return_value=worktrees):
            result = hook._branch_of_worktree(target_abs, logger)
        assert result == "feat/1.2.0-W1-030"

    def test_same_basename_different_layer_not_misattributed(self, logger):
        """絕對路徑比對可正確區分同名不同層的 worktree（原末段比對會誤配）。"""
        worktrees = [
            {"path": "/other/repo/.claude/worktrees/agent-abc", "branch": "feat/wrong"},
        ]
        with patch.object(hook, "get_worktree_list", return_value=worktrees):
            result = hook._branch_of_worktree("/repo/.claude/worktrees/agent-abc", logger)
        assert result is None

    def test_detached_returns_none(self, logger):
        target_abs = "/repo/.claude/worktrees/agent-abc"
        worktrees = [{"path": target_abs, "detached": True}]
        with patch.object(hook, "get_worktree_list", return_value=worktrees):
            assert hook._branch_of_worktree(target_abs, logger) is None

    def test_git_failure_returns_none(self, logger):
        with patch.object(hook, "get_worktree_list", return_value=[]):
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
# _dirty_status（0.2.1-W3-280）
# ---------------------------------------------------------------------------


class TestDirtyStatus:
    def test_parses_nonempty_lines(self, logger):
        with patch.object(
            hook, "get_uncommitted_files",
            return_value=[
                hook.FileStatus(status=" M", file_path="tickets/a.md"),
                hook.FileStatus(status="??", file_path="tickets/b.md"),
            ],
        ):
            assert hook._dirty_status("/path/wt", logger) == [
                " M tickets/a.md",
                "?? tickets/b.md",
            ]

    def test_clean_returns_empty_list(self, logger):
        with patch.object(hook, "get_uncommitted_files", return_value=[]):
            assert hook._dirty_status("/path/wt", logger) == []

    def test_git_failure_returns_empty_list(self, logger):
        """0.2.1-W3-286：共用層不區分「git 失敗」與「無變更」，兩者皆回傳
        空清單；main() 兩種情形皆落在同一放行分支，行為結果一致（見
        _dirty_status docstring 的行為變更說明）。"""
        with patch.object(hook, "get_uncommitted_files", return_value=[]):
            assert hook._dirty_status("/path/wt", logger) == []


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

    def test_pass_when_no_unmerged_deliverable_and_clean(self, capsys):
        data = {"tool_input": {"command": "git worktree remove .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=[]
        ):
            assert hook.main() == 0

    def test_pass_when_branch_not_found_and_clean(self):
        data = {"tool_input": {"command": "git worktree remove some-path"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value=None
        ), patch.object(hook, "_dirty_status", return_value=[]):
            assert hook.main() == 0

    def test_pass_when_git_query_fails(self):
        data = {"tool_input": {"command": "git worktree remove some-path"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=None), patch.object(
            hook, "_dirty_status", return_value=[]
        ):
            assert hook.main() == 0

    # -----------------------------------------------------------------------
    # Guard C（0.2.1-W3-280；0.2.1-W3-285 由 Guard B 改名避免與
    # worktree-pre-dispatch-branch-drift-hook 的 Guard B 撞號）：
    # target worktree 未提交變更檢查
    # -----------------------------------------------------------------------

    def test_block_when_dirty_working_tree(self, capsys):
        """merge 已完成（Guard A 放行），但 working tree 有未提交修改 → 阻擋。"""
        data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=[" M tickets/0.0.0-W1-001.md"]
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "Guard C" in captured.err
        assert "Guard B" not in captured.err
        assert "tickets/0.0.0-W1-001.md" in captured.err

    def test_block_when_dirty_and_branch_not_found(self, capsys):
        """detached/找不到分支（Guard A 略過），但 working tree 有未提交變更 → 仍阻擋。"""
        data = {"tool_input": {"command": "git worktree remove some-path"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value=None
        ), patch.object(
            hook, "_dirty_status", return_value=["?? tickets/new.md"]
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "Guard C" in captured.err
        # 分支未知時，merge 步驟改用 <branch> 佔位並附說明，而非留空或報錯
        assert "git merge <branch> --no-edit" in captured.err

    def test_dirty_block_message_groups_untracked_and_tracked(self, capsys):
        """0.2.1-W3-285：分組呈現比照 worktree-merge-reminder-hook，未追蹤與
        已追蹤但未提交分別列出標題，不混雜成單一清單。"""
        data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook,
            "_dirty_status",
            return_value=["?? tickets/new.md", " M tickets/modified.md"],
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "未追蹤（1 項" in captured.err
        assert "已追蹤但未提交（1 項" in captured.err
        untracked_idx = captured.err.index("tickets/new.md")
        tracked_idx = captured.err.index("tickets/modified.md")
        untracked_header_idx = captured.err.index("未追蹤（1 項")
        tracked_header_idx = captured.err.index("已追蹤但未提交（1 項")
        assert untracked_header_idx < untracked_idx < tracked_header_idx
        assert tracked_header_idx < tracked_idx

    def test_dirty_block_message_commit_option_includes_merge_followup(self, capsys):
        """0.2.1-W3-285：commit 建議須補 merge 續步，否則 commit 後分支仍未
        合併，remove 會接著被 Guard A 擋下（互斥指示的另一種形式）。"""
        data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/1.2.0-W1-030"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=[" M tickets/a.md"]
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "commit -m" in captured.err
        assert "git merge feat/1.2.0-W1-030 --no-edit" in captured.err

    def test_dirty_block_message_restore_clean_are_literal_commands(self, capsys):
        """0.2.1-W3-285：restore 與 clean 拆為逐字可執行命令並標明作用對象，
        原「git -C {path} restore/clean 清除」非合法命令語法。"""
        data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=[" M tickets/a.md"]
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "restore/clean" not in captured.err
        assert "git -C .claude/worktrees/agent-abc restore ." in captured.err
        assert "git -C .claude/worktrees/agent-abc clean -fd ." in captured.err

    def test_dirty_block_message_status_moved_to_verification_not_fix_option(self, capsys):
        """0.2.1-W3-285：唯讀的 status 命令不得列在「修復方式擇一」之下（選它
        等於未處理仍會被擋），須獨立為處理後的「驗證」步驟。"""
        data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=[" M tickets/a.md"]
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        fix_section_idx = captured.err.index("修復方式（擇一")
        verify_section_idx = captured.err.index("驗證（處理後執行")
        status_cmd_idx = captured.err.index("status --porcelain")
        # status 命令須出現在「驗證」標題之後（不在修復方式擇一的兩個選項內）
        assert fix_section_idx < verify_section_idx < status_cmd_idx

    def test_dirty_block_message_doc_reference_uses_guard_c(self, capsys):
        """0.2.1-W3-285：文件指引須指向 worktree-operations.md 階段 3 的
        Guard C 章節（而非已被 branch-drift-hook 佔用的 Guard B）。"""
        data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=[" M tickets/a.md"]
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "階段 3：清理後 / Guard C" in captured.err

    def test_pass_when_clean_working_tree(self):
        data = {"tool_input": {"command": "git worktree remove .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=[]
        ):
            assert hook.main() == 0

    def test_dirty_block_message_no_bare_cd_and_path_limited_commit(self, capsys):
        """0.2.1-W3-282：BLOCK_MESSAGE_DIRTY 不得含裸 cd，commit 建議須 path-limited
        （與 bare-commit-guard 並行期無 pathspec 即 DENY 對齊，不互斥）。"""
        data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=[" M tickets/a.md"]
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "cd .claude/worktrees/agent-abc &&" not in captured.err
        assert "git -C .claude/worktrees/agent-abc" in captured.err
        assert "git add -A" not in captured.err
        assert "commit -m" in captured.err
        assert "-- <paths>" in captured.err

    def test_pass_when_dirty_status_query_fails(self):
        """git status 查詢失敗（None）不阻擋，避免誤擋。"""
        data = {"tool_input": {"command": "git worktree remove some-path"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=None
        ):
            assert hook.main() == 0
