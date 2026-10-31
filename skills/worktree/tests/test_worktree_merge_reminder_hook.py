import re
"""worktree-merge-reminder-hook 測試套件（0.2.1-W3-273）

防護目標（issue 46 症狀三）：`ticket track complete` 後的清理提醒，對「已合併
但仍有未追蹤檔案」的 worktree 明確列出「移除將永久遺失」的檔案清單，而非僅
標記 dirty——未追蹤檔案在 `git worktree remove --force` 下會隨 worktree 目錄
整個丟棄，且從未進入該分支任何 commit（與「已追蹤但未 commit」風險等級不同）。
"""

import importlib.util
import json
import logging
from pathlib import Path

import pytest

_HOOK_FILE = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "worktree-merge-reminder-hook.py"
)
_spec = importlib.util.spec_from_file_location(
    "worktree_merge_reminder_hook", _HOOK_FILE
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


@pytest.fixture
def logger():
    return logging.getLogger("test-wmr")


# ---------------------------------------------------------------------------
# get_dirty_files（0.2.1-W3-273 新增：布林 dirty 升級為檔案清單）
# ---------------------------------------------------------------------------


# 規則七禁形：commit 帶 `-- <path>` pathspec（亦涵蓋 --only / -o）
RULE7_PATHSPEC_COMMIT = re.compile(r"commit\b[^\n]*(\s--\s+\S|\s--only\b|\s-o\b)")

_OLD_SUGGESTION = (
    'git -C /path/to/wt add <paths> && '
    'git -C /path/to/wt commit -m "<message>" -- <paths>'
)


def test_rule7_checker_flags_pre_fix_literal():
    """正向對照：修正前的訊息字面必須被判為違規，否則斷言無鑑別力。"""
    assert RULE7_PATHSPEC_COMMIT.search(_OLD_SUGGESTION)


class TestGetDirtyFiles:
    def test_parses_untracked_and_modified(self, logger, monkeypatch):
        """0.2.1-W3-286：get_dirty_files 改呼叫共用層
        lib.git_utils.get_uncommitted_files，直接 mock 該函式回傳
        FileStatus 列表（不再 patch hook 自身的 subprocess）。"""
        monkeypatch.setattr(
            hook, "get_uncommitted_files",
            lambda cwd: [
                hook.FileStatus(status="??", file_path="tickets/0.0.0-W1-001.md"),
                hook.FileStatus(status=" M", file_path="tickets/0.0.0-W1-002.md"),
            ],
        )

        files = hook.get_dirty_files("/path/to/wt", logger)
        assert files == [
            ("??", "tickets/0.0.0-W1-001.md"),
            (" M", "tickets/0.0.0-W1-002.md"),
        ]

    def test_empty_status_returns_empty_list(self, logger, monkeypatch):
        monkeypatch.setattr(hook, "get_uncommitted_files", lambda cwd: [])
        assert hook.get_dirty_files("/path/to/wt", logger) == []

    def test_git_command_failure_returns_empty_list(self, logger, monkeypatch):
        """0.2.1-W3-286：共用層不區分 git 失敗與無變更，皆回傳空清單。"""
        monkeypatch.setattr(hook, "get_uncommitted_files", lambda cwd: [])
        assert hook.get_dirty_files("/path/to/wt", logger) == []


class TestIsWorktreeDirty:
    def test_dirty_when_files_present(self, logger, monkeypatch):
        monkeypatch.setattr(
            hook, "get_dirty_files", lambda path, lg: [("??", "a.md")]
        )
        assert hook.is_worktree_dirty("/path/to/wt", logger) is True

    def test_clean_when_no_files(self, logger, monkeypatch):
        monkeypatch.setattr(hook, "get_dirty_files", lambda path, lg: [])
        assert hook.is_worktree_dirty("/path/to/wt", logger) is False


# ---------------------------------------------------------------------------
# main() 端到端：清理提醒訊息內容
# ---------------------------------------------------------------------------


def _install_main_mocks(
    monkeypatch,
    *,
    worktrees=None,
    unmerged_commits_by_branch=None,
    dirty_files_by_path=None,
    locked_paths=(),
    zero_commit_branches=(),
):
    # 0.5.0-W1-300：0.5.0-W1-290 新增 locked／零提交判準；預設前提為
    # 「未 locked、分支有自己的提交」，使原清理提醒分支可達。
    monkeypatch.setattr(hook, "get_locked_paths", lambda logger: set(locked_paths))
    monkeypatch.setattr(
        hook,
        "has_no_own_commits",
        lambda branch, logger: branch in zero_commit_branches,
    )
    input_data = {
        "tool_input": {"command": "ticket track complete 0.0.0-W1-001"},
    }
    monkeypatch.setattr(hook, "read_json_from_stdin", lambda logger: input_data)
    monkeypatch.setattr(hook, "is_subagent_environment", lambda data: False)
    monkeypatch.setattr(hook, "parse_worktree_list", lambda logger: worktrees or [])

    unmerged_commits_by_branch = unmerged_commits_by_branch or {}
    monkeypatch.setattr(
        hook,
        "get_unmerged_commits",
        lambda branch, logger: unmerged_commits_by_branch.get(branch, []),
    )

    dirty_files_by_path = dirty_files_by_path or {}
    monkeypatch.setattr(
        hook,
        "get_dirty_files",
        lambda path, logger: dirty_files_by_path.get(path, []),
    )


def _run_main_and_get_message(capsys) -> str:
    rc = hook.main()
    assert rc == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out.strip())
    return output["hookSpecificOutput"]["additionalContext"]


class TestInProgressClassification:
    """E2 正向對照（0.5.0-W1-300）：locked／零提交 worktree 歸進行中，
    不列入清理建議。斷言看結構化結果（classify_worktrees 回傳值）。"""

    def _classify(self, monkeypatch, **kwargs):
        _install_main_mocks(monkeypatch, **kwargs)
        wts = [("/path/to/wt", "feat/0.0.0-W1-010")]
        return hook.classify_worktrees(wts, logging.getLogger("test-wmr"))

    def test_locked_worktree_is_in_progress(self, monkeypatch):
        unmerged, merged, in_progress = self._classify(
            monkeypatch, locked_paths=["/path/to/wt"]
        )
        assert unmerged == []
        assert merged == []
        assert in_progress == [
            ("/path/to/wt", "feat/0.0.0-W1-010", "worktree 已 locked")
        ]

    def test_zero_commit_worktree_is_in_progress(self, monkeypatch):
        unmerged, merged, in_progress = self._classify(
            monkeypatch, zero_commit_branches=["feat/0.0.0-W1-010"]
        )
        assert unmerged == []
        assert merged == []
        assert in_progress == [
            ("/path/to/wt", "feat/0.0.0-W1-010", "分支尚無自己的提交")
        ]

    def test_unlocked_with_commits_is_merged_control(self, monkeypatch):
        """對照組：未 locked 且有自己的提交 → merged（確認上兩筆差異來自判準）。"""
        unmerged, merged, in_progress = self._classify(monkeypatch)
        assert in_progress == []
        assert [(p, b) for p, b, _ in merged] == [
            ("/path/to/wt", "feat/0.0.0-W1-010")
        ]


class TestMergedCleanupReminderMessage:
    def test_untracked_file_shows_loss_warning_with_filename(
        self, monkeypatch, capsys
    ):
        """核心驗證：merged + 未追蹤檔案 → 明確列出檔名與遺失警告（非僅標 dirty）。"""
        _install_main_mocks(
            monkeypatch,
            worktrees=[("/path/to/wt", "feat/0.0.0-W1-001")],
            unmerged_commits_by_branch={},  # 空 → 視為已合併
            dirty_files_by_path={
                "/path/to/wt": [("??", "tickets/0.0.0-W1-001.md")]
            },
        )

        message = _run_main_and_get_message(capsys)
        assert "[遺失警告]" in message
        assert "tickets/0.0.0-W1-001.md" in message
        assert "未提交變更（dirty）" in message

    def test_tracked_modified_only_shows_loss_warning(self, monkeypatch, capsys):
        """已追蹤但未 commit（無 ?? 項）：0.2.1-W3-280 翻轉——代理人寫入的修改
        內容本身從未進入任何 commit，強制移除仍會遺失，故仍需觸發遺失警告
        （訊息用詞區分「修改內容」而非「整檔」）。"""
        _install_main_mocks(
            monkeypatch,
            worktrees=[("/path/to/wt", "feat/0.0.0-W1-002")],
            unmerged_commits_by_branch={},
            dirty_files_by_path={
                "/path/to/wt": [(" M", "tickets/0.0.0-W1-002.md")]
            },
        )

        message = _run_main_and_get_message(capsys)
        assert "未提交變更（dirty）" in message
        assert "[遺失警告]" in message
        assert "遺失修改內容" in message
        assert "tickets/0.0.0-W1-002.md" in message

    def test_cleanup_suggestion_uses_git_dash_c_not_bare_cd(self, monkeypatch, capsys):
        """0.2.1-W3-282：清理建議行不得用裸 cd（PC-166 觸發鏈第一環），改用 git -C。"""
        _install_main_mocks(
            monkeypatch,
            worktrees=[("/path/to/wt", "feat/0.0.0-W1-006")],
            unmerged_commits_by_branch={},
            dirty_files_by_path={
                "/path/to/wt": [(" M", "tickets/0.0.0-W1-006.md")]
            },
        )

        message = _run_main_and_get_message(capsys)
        assert "cd /path/to/wt &&" not in message
        assert "git -C /path/to/wt status --porcelain" in message

    def test_dirty_suggestion_not_mutually_exclusive_with_guard_c(
        self, monkeypatch, capsys
    ):
        """0.2.1-W3-285：dirty 分支建議不再直接指向會被 Guard C 阻擋的
        `remove --force`，改為 commit 後 merge 再 remove 的導向，且明示
        --force 對 dirty 狀態會被 Guard C 阻擋。"""
        _install_main_mocks(
            monkeypatch,
            worktrees=[("/path/to/wt", "feat/0.0.0-W1-007")],
            unmerged_commits_by_branch={},
            dirty_files_by_path={
                "/path/to/wt": [(" M", "tickets/0.0.0-W1-007.md")]
            },
        )

        message = _run_main_and_get_message(capsys)
        assert 'git -C /path/to/wt commit -m "<message>"' in message
        assert "git -C /path/to/wt add <exact-path>" in message
        assert "git -C /path/to/wt diff --cached --name-only" in message
        assert not RULE7_PATHSPEC_COMMIT.search(message)
        assert "/worktree merge 0.0.0-W1-007" in message
        assert "git -C /path/to/wt restore ." in message
        assert "git -C /path/to/wt clean -fd ." in message
        assert "會被 Guard C 阻擋" in message
        # 移除建議本身不得再帶 --force（僅在文字說明中提及會被擋）
        assert "/worktree cleanup 0.0.0-W1-007   #" in message
        assert "--force" not in message.split("/worktree cleanup", 1)[1].split("#")[0]

    def test_mixed_untracked_and_tracked_modified_both_shown_separately(
        self, monkeypatch, capsys
    ):
        """0.2.1-W3-285（bay-quality-auditor 發現的覆蓋缺口）：get_dirty_files
        新 tuple 格式下，未追蹤與已追蹤但未提交同時存在時，兩組須各自標題
        分列且互不混雜（非合併成單一清單）。"""
        _install_main_mocks(
            monkeypatch,
            worktrees=[("/path/to/wt", "feat/0.0.0-W1-008")],
            unmerged_commits_by_branch={},
            dirty_files_by_path={
                "/path/to/wt": [
                    ("??", "tickets/new.md"),
                    (" M", "tickets/modified.md"),
                ]
            },
        )

        message = _run_main_and_get_message(capsys)
        assert "以下檔案為未追蹤，強制移除將永久遺失" in message
        assert "以下檔案已追蹤但未提交，強制移除將遺失修改內容" in message
        untracked_idx = message.index("tickets/new.md")
        tracked_idx = message.index("tickets/modified.md")
        untracked_header_idx = message.index("以下檔案為未追蹤")
        tracked_header_idx = message.index("以下檔案已追蹤但未提交")
        # 未追蹤檔名須落在未追蹤標題之後、已追蹤標題之前（分組不交錯）
        assert untracked_header_idx < untracked_idx < tracked_header_idx
        assert tracked_header_idx < tracked_idx

    def test_clean_worktree_no_dirty_section(self, monkeypatch, capsys):
        _install_main_mocks(
            monkeypatch,
            worktrees=[("/path/to/wt", "feat/0.0.0-W1-003")],
            unmerged_commits_by_branch={},
            dirty_files_by_path={"/path/to/wt": []},
        )

        message = _run_main_and_get_message(capsys)
        assert "狀態: clean" in message
        assert "[遺失警告]" not in message

    def test_untracked_list_truncated_beyond_ten(self, monkeypatch, capsys):
        """超過 10 個未追蹤檔案時截斷並提示剩餘數量（與既有 commit 清單截斷慣例一致）。"""
        many_files = [("??", f"tickets/0.0.0-W1-{i:03d}.md") for i in range(15)]
        _install_main_mocks(
            monkeypatch,
            worktrees=[("/path/to/wt", "feat/0.0.0-W1-004")],
            unmerged_commits_by_branch={},
            dirty_files_by_path={"/path/to/wt": many_files},
        )

        message = _run_main_and_get_message(capsys)
        assert "還有 5 個" in message

    def test_unmerged_worktree_unaffected_by_dirty_file_change(
        self, monkeypatch, capsys
    ):
        """既有「未合併」區塊不受本次改動影響（歸屬 Section 1，非 Section 2）。"""
        _install_main_mocks(
            monkeypatch,
            worktrees=[("/path/to/wt", "feat/0.0.0-W1-005")],
            unmerged_commits_by_branch={
                "feat/0.0.0-W1-005": ["abc1234 some commit"]
            },
        )

        message = _run_main_and_get_message(capsys)
        assert "[Worktree 合併提醒]" in message
        assert "[遺失警告]" not in message


# ---------------------------------------------------------------------------
# 0.5.0-W1-371：落地 main 建議改走合併閘門（/worktree merge），不得印裸 git merge
# ---------------------------------------------------------------------------

import shlex
import sys

_BARE_MERGE = re.compile(r"\bgit\s+merge\b")


def _messages_for(monkeypatch, capsys, branch, *, unmerged, dirty):
    _install_main_mocks(
        monkeypatch,
        worktrees=[("/path/to/wt", branch)],
        unmerged_commits_by_branch={branch: ["abc1234 msg"]} if unmerged else {},
        dirty_files_by_path={"/path/to/wt": [(" M", "a.md")]} if dirty else {},
    )
    return _run_main_and_get_message(capsys)


def test_bare_merge_checker_flags_old_literal():
    """正向對照：舊字面必須被判為違規。"""
    assert _BARE_MERGE.search("建議: git merge feat/0.0.0-W1-001 --no-edit")


@pytest.mark.parametrize("unmerged,dirty", [(True, False), (False, True), (True, True)])
def test_suggestions_have_no_bare_merge_nor_checkout_main(
    monkeypatch, capsys, unmerged, dirty
):
    msg = _messages_for(
        monkeypatch, capsys, "feat/0.0.0-W1-001", unmerged=unmerged, dirty=dirty
    )
    assert not _BARE_MERGE.search(msg)
    assert "git checkout main" not in msg
    assert "/worktree merge 0.0.0-W1-001" in msg


def test_ticket_branch_prints_ticket_form(monkeypatch, capsys):
    msg = _messages_for(
        monkeypatch, capsys, "feat/0.0.0-W1-001", unmerged=True, dirty=False
    )
    assert "建議: /worktree merge 0.0.0-W1-001" in msg
    assert "--branch" not in msg


def test_other_branch_prints_quoted_branch_form(monkeypatch, capsys):
    for branch in ("worktree-agent-a1b2c3d4", "fix/it's here"):
        msg = _messages_for(monkeypatch, capsys, branch, unmerged=True, dirty=False)
        assert f"/worktree merge --branch {shlex.quote(branch)}" in msg


def test_printed_forms_parse_with_worktree_argparse(monkeypatch, capsys):
    """PC-GPD-034：印出的建議必須能被 worktree 的 argparse 解析並導向 cmd_merge。"""
    sys.path.insert(0, str(_HOOK_FILE.parent.parent / "scripts"))
    import worktree_manager

    for branch, expect in (
        ("worktree-agent-a1b2c3d4", (None, "worktree-agent-a1b2c3d4")),
        ("fix/it's here", (None, "fix/it's here")),
        ("feat/0.0.0-W1-001", ("0.0.0-W1-001", None)),
    ):
        msg = _messages_for(monkeypatch, capsys, branch, unmerged=True, dirty=False)
        line = next(l.strip() for l in msg.splitlines() if "/worktree merge" in l)
        argv = shlex.split(line.split("建議:", 1)[-1])
        assert argv[0] == "/worktree"
        seen = {}
        monkeypatch.setattr(
            worktree_manager, "cmd_merge",
            lambda ticket_id, **kw: seen.update(t=ticket_id, b=kw.get("branch")) or 0,
        )
        monkeypatch.setattr(sys, "argv", ["worktree_manager.py"] + argv[1:])
        assert worktree_manager.main() == 0
        assert (seen["t"], seen["b"]) == expect


def test_reminder_falls_back_when_worktree_manager_import_fails(monkeypatch, capsys):
    from unittest.mock import patch

    branch = "fix/it's here"
    with patch.dict(sys.modules, {"worktree_manager": None}):
        msg = _messages_for(monkeypatch, capsys, branch, unmerged=True, dirty=False)
    assert f"建議: /worktree merge --branch {shlex.quote(branch)}" in msg
    assert not _BARE_MERGE.search(msg)


# ---------------------------------------------------------------------------
# 0.5.0-W1-384：已合併區塊的清理建議改走 /worktree cleanup，不得印裸 git worktree remove
# ---------------------------------------------------------------------------

_BARE_REMOVE = re.compile(r"\bgit\s+worktree\s+remove\b")


def _clean_suggestion_line(msg: str) -> str:
    return next(l.strip() for l in msg.splitlines() if "/worktree cleanup" in l)


def test_bare_remove_checker_flags_old_literal():
    """E2 正向對照：修正前的字面必須被判為違規。"""
    assert _BARE_REMOVE.search("  建議: git worktree remove /path/to/wt")


def test_clean_merged_suggestion_has_no_bare_remove(monkeypatch, capsys):
    msg = _messages_for(
        monkeypatch, capsys, "feat/0.0.0-W1-001", unmerged=False, dirty=False
    )
    assert not _BARE_REMOVE.search(msg)
    assert "建議: /worktree cleanup 0.0.0-W1-001" in msg


@pytest.mark.parametrize("dirty", [False, True])
def test_whole_reminder_has_no_bare_remove(monkeypatch, capsys, dirty):
    """clean 與 dirty 兩種情況，整段提醒都不得含裸 git worktree remove。"""
    msg = _messages_for(
        monkeypatch, capsys, "feat/0.0.0-W1-001", unmerged=False, dirty=dirty
    )
    assert not _BARE_REMOVE.search(msg)


def test_cleanup_other_branch_prints_quoted_branch_form(monkeypatch, capsys):
    for branch in ("worktree-agent-a1b2c3d4", "fix/it's here", "fix/a b"):
        msg = _messages_for(monkeypatch, capsys, branch, unmerged=False, dirty=False)
        assert f"建議: /worktree cleanup --branch {shlex.quote(branch)}" in msg


def test_cleanup_forms_parse_with_worktree_argparse(monkeypatch, capsys):
    """PC-GPD-034：印出的清理建議必須能被 argparse 解析並導向 cmd_cleanup。"""
    sys.path.insert(0, str(_HOOK_FILE.parent.parent / "scripts"))
    import cleanup_command
    import worktree_manager

    for branch, expect in (
        ("worktree-agent-a1b2c3d4", (None, "worktree-agent-a1b2c3d4")),
        ("fix/it's here", (None, "fix/it's here")),
        ("fix/a b", (None, "fix/a b")),
        ("feat/0.0.0-W1-001", ("0.0.0-W1-001", None)),
    ):
        msg = _messages_for(monkeypatch, capsys, branch, unmerged=False, dirty=False)
        argv = shlex.split(_clean_suggestion_line(msg).split("建議:", 1)[-1])
        assert argv[0] == "/worktree"
        seen = {}
        monkeypatch.setattr(
            cleanup_command, "cmd_cleanup",
            lambda ticket_id, **kw: seen.update(t=ticket_id, b=kw.get("branch")) or 0,
        )
        monkeypatch.setattr(sys, "argv", ["worktree_manager.py"] + argv[1:])
        assert worktree_manager.main() == 0
        assert (seen["t"], seen["b"]) == expect


def test_cleanup_falls_back_when_worktree_manager_import_fails(monkeypatch, capsys):
    from unittest.mock import patch

    branch = "fix/it's here"
    with patch.dict(sys.modules, {"worktree_manager": None}):
        msg = _messages_for(monkeypatch, capsys, branch, unmerged=False, dirty=False)
    assert f"建議: /worktree cleanup --branch {shlex.quote(branch)}" in msg
    assert not _BARE_REMOVE.search(msg)
