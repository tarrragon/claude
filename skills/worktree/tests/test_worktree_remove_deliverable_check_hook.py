import re
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


RULE7_PATHSPEC_COMMIT = re.compile(r"commit\b[^\n]*(\s--\s+\S|\s--only\b|\s-o\b)")


def test_rule7_checker_flags_pre_fix_literal():
    """正向對照：修正前的訊息字面必須被判為違規。"""
    old = 'git -C p add <paths> && git -C p commit -m "<message>" -- <paths>'
    assert RULE7_PATHSPEC_COMMIT.search(old)


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


class _RecLogger:
    def __init__(self):
        self.records = []

    def _rec(self, level):
        return lambda msg, *a, **k: self.records.append((level, msg % a if a else msg))

    def __getattr__(self, name):
        if name in ("debug", "info", "warning", "error"):
            return self._rec(name)
        raise AttributeError(name)


class TestMainEmptyTargetLogging:
    def _run(self, command):
        rec = _RecLogger()
        data = {"tool_input": {"command": command}}
        with patch.object(hook, "setup_hook_logging", return_value=rec), patch.object(
            hook, "read_json_from_stdin", return_value=data
        ):
            rc = hook.main()
        return rc, rec.records

    def test_log_reader_command_logged_as_non_remove(self):
        cmd = "grep x .claude/hook-logs/worktree-remove-deliverable-check/a.log"
        rc, records = self._run(cmd)
        assert rc == 0
        assert any(lv == "debug" and "非 remove" in m for lv, m in records)
        assert not any("無法靜態解析" in m for _, m in records)

    def test_real_remove_without_path_keeps_info(self):
        rc, records = self._run("git worktree remove --force")
        assert rc == 0
        assert any(lv == "info" and "無法靜態解析" in m for lv, m in records)

    def test_unparseable_and_regex_miss_logs_warning(self):
        with patch.object(hook, "find_git_invocations", return_value=None):
            rc, records = self._run("echo worktree remove")
        assert rc == 0
        assert any(lv == "warning" for lv, _ in records)
        assert not any("無法靜態解析" in m for _, m in records)


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
        assert "/worktree merge --branch <branch>" in captured.err

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
        assert "/worktree merge 1.2.0-W1-030" in captured.err

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

    def test_dirty_block_message_no_bare_cd_and_exact_add_bare_commit(self, capsys):
        """0.2.1-W3-282：BLOCK_MESSAGE_DIRTY 不得含裸 cd，commit 建議須為
        精確 add、diff --cached 核對、裸 commit（規則七；pathspec 提交會被
        bare-commit-guard 擋下，故不得出現）。"""
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
        assert 'git -C .claude/worktrees/agent-abc commit -m "<message>"' in captured.err
        assert "git -C .claude/worktrees/agent-abc add <exact-path>" in captured.err
        assert "diff --cached --name-only" in captured.err
        assert not RULE7_PATHSPEC_COMMIT.search(captured.err)

    def test_pass_when_dirty_status_query_fails(self):
        """git status 查詢失敗（None）不阻擋，避免誤擋。"""
        data = {"tool_input": {"command": "git worktree remove some-path"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_branch_of_worktree", return_value="feat/x"
        ), patch.object(hook, "_unmerged_files", return_value=[]), patch.object(
            hook, "_dirty_status", return_value=None
        ):
            assert hook.main() == 0


# ---------------------------------------------------------------------------
# Guard A 內容等價出口（真實 tmp git repo；E2 三案）
# ---------------------------------------------------------------------------

import subprocess


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """main 上有 base.txt；chdir 到 repo 使 hook 內 run_git 作用於此 repo。"""
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "base.txt").write_text("base\n")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _commit_on_branch(repo, branch, filename, content):
    _git(repo, "checkout", "-q", "-b", branch, "main")
    (repo / filename).write_text(content)
    _git(repo, "add", filename)
    _git(repo, "commit", "-q", "-m", "on " + branch)


class TestGuardAContentEquivalence:
    def test_patch_equivalent_branch_passes(self, repo, logger):
        """案 1：分支 commit 的 patch 已在 main（cherry 全為 -）→ 放行。"""
        _commit_on_branch(repo, "feat/dup", "a.txt", "same\n")
        _git(repo, "checkout", "-q", "main")
        # main 先前進一個 commit，cherry-pick 才會產生不同 hash 的等價 patch
        (repo / "other.txt").write_text("x\n")
        _git(repo, "add", "other.txt")
        _git(repo, "commit", "-q", "-m", "other")
        _git(repo, "cherry-pick", "feat/dup")
        assert hook._guard_a(str(repo), "feat/dup", logger) is None

    def test_superseded_content_blocks_with_explicit_exit(self, repo, logger):
        """案 2：cherry 含 +（內容被不同寫法取代）→ 阻擋，訊息含顯式出口。"""
        _commit_on_branch(repo, "feat/old", "a.txt", "old version\n")
        _git(repo, "checkout", "-q", "main")
        (repo / "a.txt").write_text("new version\n")
        _git(repo, "add", "a.txt")
        _git(repo, "commit", "-q", "-m", "supersede")
        message = hook._guard_a(str(repo), "feat/old", logger)
        assert message is not None
        assert "branch -D feat/old" in message
        assert "checkout --detach" in message
        assert "merge -s ours" not in message

    def test_truly_unmerged_branch_blocks(self, repo, logger):
        """案 3：真正未合併 → 阻擋（與修前一致）。"""
        _commit_on_branch(repo, "feat/new", "b.txt", "only on branch\n")
        _git(repo, "checkout", "-q", "main")
        message = hook._guard_a(str(repo), "feat/new", logger)
        assert message is not None
        assert "b.txt" in message


# ---------------------------------------------------------------------------
# 0.5.0-W1-371：落地 main 建議改走合併閘門，不得印裸 git merge / git checkout main
# ---------------------------------------------------------------------------

import shlex
import sys

_BARE_MERGE = re.compile(r"\bgit\s+merge\b")


def _block_stderr(capsys, branch, *, guard):
    data = {"tool_input": {"command": "git worktree remove --force .claude/worktrees/agent-abc"}}
    unmerged = ["app/lib/foo.dart"] if guard == "A" else []
    dirty = [] if guard == "A" else [" M tickets/a.md"]
    with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
        hook, "_branch_of_worktree", return_value=branch
    ), patch.object(hook, "_unmerged_files", return_value=unmerged), patch.object(
        hook, "_dirty_status", return_value=dirty
    ):
        assert hook.main() == 2
    return capsys.readouterr().err


def _merge_command_line(err):
    line = next(l for l in err.splitlines() if "/worktree merge" in l)
    return line[line.index("/worktree merge"):].split("  #", 1)[0].strip()


def test_bare_merge_checker_flags_old_literal():
    assert _BARE_MERGE.search("git checkout main && git merge feat/x --no-edit")


@pytest.mark.parametrize(
    "guard,branch",
    [("A", "feat/1.2.0-W1-030"), ("A", "feat/x"), ("C", "feat/1.2.0-W1-030"),
     ("C", "feat/x"), ("C", None)],
)
def test_block_messages_have_no_bare_merge_nor_checkout_main(capsys, guard, branch):
    err = _block_stderr(capsys, branch, guard=guard)
    assert not _BARE_MERGE.search(err)
    assert "git checkout main" not in err
    assert "/worktree merge" in err


def test_ticket_branch_prints_ticket_form(capsys):
    for guard in ("A", "C"):
        err = _block_stderr(capsys, "feat/1.2.0-W1-030", guard=guard)
        assert _merge_command_line(err) == "/worktree merge 1.2.0-W1-030"


def test_other_branch_prints_quoted_branch_form(capsys):
    for branch in ("worktree-agent-a1b2c3d4", "fix/it's here"):
        err = _block_stderr(capsys, branch, guard="A")
        assert _merge_command_line(err) == f"/worktree merge --branch {shlex.quote(branch)}"


def test_printed_forms_parse_with_worktree_argparse(capsys, monkeypatch):
    """PC-GPD-034：印出的建議必須能被 worktree 的 argparse 解析並導向 cmd_merge。"""
    sys.path.insert(0, str(_HOOK_FILE.parent.parent / "scripts"))
    import worktree_manager

    for branch, expect in (
        ("worktree-agent-a1b2c3d4", (None, "worktree-agent-a1b2c3d4")),
        ("fix/it's here", (None, "fix/it's here")),
        ("feat/1.2.0-W1-030", ("1.2.0-W1-030", None)),
    ):
        for guard in ("A", "C"):
            argv = shlex.split(_merge_command_line(_block_stderr(capsys, branch, guard=guard)))
            seen = {}
            monkeypatch.setattr(
                worktree_manager, "cmd_merge",
                lambda ticket_id, **kw: seen.update(t=ticket_id, b=kw.get("branch")) or 0,
            )
            monkeypatch.setattr(sys, "argv", ["worktree_manager.py"] + argv[1:])
            assert worktree_manager.main() == 0
            assert (seen["t"], seen["b"]) == expect


def test_guard_a_still_blocks_when_worktree_manager_import_fails(capsys):
    """lazy import 失敗時阻擋型守衛仍須阻擋，建議退回通用字面（分支名 shlex.quote）。"""
    branch = "fix/it's here"
    with patch.dict(sys.modules, {"worktree_manager": None}):
        err = _block_stderr(capsys, branch, guard="A")
    assert "Guard A" in err
    assert f"/worktree merge --branch {shlex.quote(branch)}" in err
    assert not _BARE_MERGE.search(err)


def test_guard_c_unknown_branch_fallback_when_import_fails(capsys):
    with patch.dict(sys.modules, {"worktree_manager": None}):
        err = _block_stderr(capsys, None, guard="C")
    assert "Guard C" in err
    assert "/worktree merge --branch <branch>" in err


# ---------------------------------------------------------------------------
# 0.5.0-W1-378：git -C 形式的 worktree remove 也受 Guard A / C 檢查（真實 git）
# ---------------------------------------------------------------------------


def _add_worktree(repo, name, branch):
    wt = repo.parent / (repo.name + "-" + name)
    _git(repo, "worktree", "add", "-q", "-b", branch, str(wt), "main")
    return wt


def _run_main(command):
    data = {"tool_input": {"command": command}}
    with patch.object(hook, "read_json_from_stdin", return_value=data):
        return hook.main()


class TestGitDashCRemove:
    def test_dash_c_dirty_worktree_blocked_by_guard_c(self, repo, capsys):
        wt = _add_worktree(repo, "dirty", "feat/dirty")
        (wt / "scratch.txt").write_text("unsaved\n")
        rc = _run_main("git -C {} worktree remove --force {}".format(repo, wt))
        assert rc == 2
        assert "Guard C" in capsys.readouterr().err

    def test_dash_c_unmerged_deliverable_blocked_by_guard_a(self, repo, capsys):
        wt = _add_worktree(repo, "unmerged", "feat/unmerged")
        (wt / "deliv.txt").write_text("work\n")
        _git(wt, "add", "deliv.txt")
        _git(wt, "commit", "-q", "-m", "deliverable")
        rc = _run_main("git -C {} worktree remove --force {}".format(repo, wt))
        assert rc == 2
        err = capsys.readouterr().err
        assert "Guard A" in err
        assert "deliv.txt" in err

    def test_dash_c_merged_clean_worktree_passes(self, repo):
        """主控條件（正向對照）：已合併且乾淨仍放行。"""
        wt = _add_worktree(repo, "clean", "feat/clean")
        assert _run_main("git -C {} worktree remove {}".format(repo, wt)) == 0

    def test_dash_c_relative_path_resolved_against_dash_c_dir(self, repo, capsys):
        wt = _add_worktree(repo, "rel", "feat/rel")
        (wt / "scratch.txt").write_text("unsaved\n")
        rc = _run_main("git -C {} worktree remove ../{}".format(repo, wt.name))
        assert rc == 2
        assert "Guard C" in capsys.readouterr().err

    def test_quoted_or_echoed_remove_text_does_not_trigger(self, repo):
        """E2：引號／echo 內的字樣不是呼叫。"""
        wt = _add_worktree(repo, "e2", "feat/e2")
        (wt / "scratch.txt").write_text("unsaved\n")
        for cmd in (
            'echo "git -C {} worktree remove {}"'.format(repo, wt),
            'git -C {} commit -m "git worktree remove {}"'.format(repo, wt),
        ):
            assert _run_main(cmd) == 0

    def test_unresolvable_dash_c_fails_open(self, logger):
        cmd = 'git -C "$REPO" worktree remove rel-path'
        assert hook._extract_remove_paths(cmd, logger) == []

    def test_unparseable_pipe_to_shell_falls_back_to_regex_and_blocks(self, repo, capsys):
        """無法解析（管線接 shell）時退回正則擷取，路徑仍送 Guard A/C。"""
        wt = _add_worktree(repo, "pipesh", "feat/pipesh")
        (wt / "scratch.txt").write_text("unsaved\n")
        rc = _run_main('echo "git worktree remove {}" | sh'.format(wt))
        assert rc == 2
        assert "Guard C" in capsys.readouterr().err

    def test_unparseable_and_regex_miss_fails_open(self, logger):
        assert hook._extract_remove_paths('echo "unclosed', logger) == []


# ---------------------------------------------------------------------------
# 0.5.0-W1-386：Guard A 以 -C 指向的 repo 為基準查詢（真實 git，cwd 在另一個 repo）
# ---------------------------------------------------------------------------


@pytest.fixture
def two_repos(tmp_path, monkeypatch):
    """repo A（cwd）與 repo B（被 -C 指向），各自有 main 與 base 提交。"""
    repos = []
    for name in ("repo_a", "repo_b"):
        r = tmp_path / name
        r.mkdir()
        _git(r, "init", "-q", "-b", "main")
        (r / "base.txt").write_text("base\n")
        _git(r, "add", "base.txt")
        _git(r, "commit", "-q", "-m", "base")
        repos.append(r)
    monkeypatch.chdir(repos[0])
    return repos


class TestGuardABaseRepo:
    def test_cross_repo_unmerged_worktree_blocked(self, two_repos, capsys):
        repo_a, repo_b = two_repos
        wt = _add_worktree(repo_b, "unmerged", "feat/unmerged")
        (wt / "deliv.txt").write_text("work\n")
        _git(wt, "add", "deliv.txt")
        _git(wt, "commit", "-q", "-m", "deliverable")
        rc = _run_main("git -C {} worktree remove --force {}".format(repo_b, wt))
        assert rc == 2
        err = capsys.readouterr().err
        assert "Guard A" in err
        assert "deliv.txt" in err

    def test_cross_repo_merged_clean_worktree_passes(self, two_repos):
        """正向對照：同一跨 repo 設定下，已合併且乾淨仍放行。"""
        _, repo_b = two_repos
        wt = _add_worktree(repo_b, "clean", "feat/clean")
        assert _run_main("git -C {} worktree remove {}".format(repo_b, wt)) == 0

    def test_extract_targets_carries_repo_base(self, logger):
        cmd = "git -C /x/y worktree remove /x/y-wt && git worktree remove wt-b"
        assert hook._extract_remove_targets(cmd, logger) == [
            ("/x/y-wt", "/x/y"),
            ("wt-b", None),
        ]
