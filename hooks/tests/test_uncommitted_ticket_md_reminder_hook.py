"""
uncommitted-ticket-md-reminder-hook 測試套件（W8-005，W8-002 ANA 方案 4）

驗證輕量「未 commit ticket md 偵測」hook：
1. is_git_commit_command 判斷邏輯（含排除變體）
2. is_ticket_md_path 路徑判斷（docs/work-logs/**/tickets/*.md）
3. find_uncommitted_ticket_md 過濾 git status 結果
4. 偵測到 modified/staged ticket md → stderr 警告 + exit 0（不阻擋）
5. 無 modified ticket md → 靜默 exit 0
6. 非 git commit 命令 → 靜默 exit 0
"""

from pathlib import Path
from unittest.mock import patch
import importlib.util

hooks_path = Path(__file__).parent.parent

# 動態導入（檔名含 dash）
hook_file = hooks_path / "uncommitted-ticket-md-reminder-hook.py"
spec = importlib.util.spec_from_file_location(
    "uncommitted_ticket_md_reminder_hook", hook_file
)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


# --- is_git_commit_command ---

def test_is_git_commit_command_true():
    assert hook.is_git_commit_command('git commit -m "feat: x"') is True


def test_is_git_commit_command_heredoc():
    assert hook.is_git_commit_command(
        'git commit -m "$(cat <<\'EOF\'\nfeat: x\nEOF\n)"'
    ) is True


def test_is_git_commit_command_excludes_log():
    assert hook.is_git_commit_command("git log --oneline") is False


def test_is_git_commit_command_excludes_show():
    assert hook.is_git_commit_command("git show HEAD") is False


def test_is_git_commit_command_excludes_diff():
    assert hook.is_git_commit_command("git diff --cached") is False


def test_is_git_commit_command_excludes_status():
    assert hook.is_git_commit_command("git status") is False


def test_is_git_commit_command_non_git():
    assert hook.is_git_commit_command("npm test") is False


# --- is_ticket_md_path ---

def test_is_ticket_md_path_true():
    assert hook.is_ticket_md_path(
        "docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W8-005.md"
    ) is True


def test_is_ticket_md_path_flat_structure():
    assert hook.is_ticket_md_path(
        "docs/work-logs/v0.29.0/tickets/0.29.0-W1-001.md"
    ) is True


def test_is_ticket_md_path_non_ticket_md():
    assert hook.is_ticket_md_path("src/popup/popup.js") is False


def test_is_ticket_md_path_worklog_non_ticket():
    # work-logs 下但非 tickets/ 子目錄
    assert hook.is_ticket_md_path(
        "docs/work-logs/v1/v1.0/v1.0.0/summary.md"
    ) is False


def test_is_ticket_md_path_tickets_non_md():
    assert hook.is_ticket_md_path(
        "docs/work-logs/v1/v1.0/v1.0.0/tickets/notes.txt"
    ) is False


# --- find_uncommitted_ticket_md ---

class _FakeFileStatus:
    def __init__(self, status, file_path):
        self.status = status
        self.file_path = file_path

    @property
    def is_modified(self):
        return "M" in self.status

    @property
    def is_staged(self):
        return self.status[0] not in (" ", "?")

    @property
    def is_untracked(self):
        return self.status == "??"


def test_find_uncommitted_ticket_md_detects_modified():
    files = [
        _FakeFileStatus(" M", "docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W8-005.md"),
        _FakeFileStatus(" M", "src/popup/popup.js"),
    ]
    with patch.object(hook, "get_uncommitted_files", return_value=files):
        result = hook.find_uncommitted_ticket_md()
    assert result == [
        "docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W8-005.md"
    ]


def test_find_uncommitted_ticket_md_detects_staged():
    files = [
        _FakeFileStatus("M ", "docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W8-005.md"),
    ]
    with patch.object(hook, "get_uncommitted_files", return_value=files):
        result = hook.find_uncommitted_ticket_md()
    assert len(result) == 1


def test_find_uncommitted_ticket_md_detects_untracked():
    files = [
        _FakeFileStatus("??", "docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W8-099.md"),
    ]
    with patch.object(hook, "get_uncommitted_files", return_value=files):
        result = hook.find_uncommitted_ticket_md()
    assert len(result) == 1


def test_find_uncommitted_ticket_md_empty_when_no_ticket():
    files = [
        _FakeFileStatus(" M", "src/popup/popup.js"),
    ]
    with patch.object(hook, "get_uncommitted_files", return_value=files):
        result = hook.find_uncommitted_ticket_md()
    assert result == []


def test_find_uncommitted_ticket_md_empty_when_clean():
    with patch.object(hook, "get_uncommitted_files", return_value=[]):
        result = hook.find_uncommitted_ticket_md()
    assert result == []


# --- main / run_hook 整合（exit 0 + stderr 行為）---

def _run_main_with(input_data, uncommitted):
    """以 mock stdin 與 git status 執行 main，回傳 (exit_code, stderr_text)。"""
    import io
    import json
    import sys

    files = [_FakeFileStatus(s, p) for s, p in uncommitted]
    with patch.object(hook, "read_json_from_stdin", return_value=input_data), \
         patch.object(hook, "get_uncommitted_files", return_value=files):
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            exit_code = hook.main()
        finally:
            sys.stderr = old_stderr
    return exit_code, captured.getvalue()


def test_main_warns_when_ticket_md_uncommitted():
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": 'git commit -m "feat: x"'},
    }
    exit_code, stderr_text = _run_main_with(
        input_data,
        [(" M", "docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W8-005.md")],
    )
    assert exit_code == 0
    assert "1.0.0-W8-005.md" in stderr_text


def test_main_silent_when_no_ticket_md():
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": 'git commit -m "feat: x"'},
    }
    exit_code, stderr_text = _run_main_with(
        input_data,
        [(" M", "src/popup/popup.js")],
    )
    assert exit_code == 0
    assert stderr_text.strip() == ""


def test_main_silent_when_not_commit():
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "npm test"},
    }
    exit_code, stderr_text = _run_main_with(
        input_data,
        [(" M", "docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W8-005.md")],
    )
    assert exit_code == 0
    assert stderr_text.strip() == ""


def test_main_silent_when_non_bash():
    input_data = {
        "tool_name": "Edit",
        "tool_input": {},
    }
    exit_code, stderr_text = _run_main_with(input_data, [])
    assert exit_code == 0
    assert stderr_text.strip() == ""
