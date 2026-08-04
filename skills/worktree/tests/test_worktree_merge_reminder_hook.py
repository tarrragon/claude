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
):
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
        assert "commit -m" in message
        assert "-- <paths>" in message
        assert "git merge feat/0.0.0-W1-007 --no-edit" in message
        assert "git -C /path/to/wt restore ." in message
        assert "git -C /path/to/wt clean -fd ." in message
        assert "會被 Guard C 阻擋" in message
        # 移除建議本身不得再帶 --force（僅在文字說明中提及會被擋）
        assert "git worktree remove /path/to/wt   #" in message
        assert "git worktree remove /path/to/wt --force" not in message

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
