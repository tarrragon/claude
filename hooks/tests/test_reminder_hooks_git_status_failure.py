"""
uncommitted-ticket-md-reminder / branch-status-reminder：git status 失敗須有可見訊號（3.4.0-W1-331）

根因（3.4.0-W1-058）：舊 API 失敗回空清單，失敗與「無變更」同形。遷移至
get_uncommitted_files_strict 後，失敗時 stderr + 日誌留痕、不阻擋；成功路徑輸出不變。
"""

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

GIT_ERROR = "fatal: not a git repository"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ticket_hook = _load("ticket_md_reminder_gsf", "uncommitted-ticket-md-reminder-hook.py")
branch_hook = _load("branch_status_reminder_gsf", "branch-status-reminder.py")


def _fail_git():
    from lib import git_utils
    return patch.object(git_utils, "run_git_command", return_value=(False, GIT_ERROR))


def _ok_git(porcelain_z: str):
    from lib import git_utils
    return patch.object(git_utils, "run_git_command", return_value=(True, porcelain_z))


class TestUncommittedTicketMdReminder:
    def test_failure_writes_stderr_and_log(self, capsys, caplog):
        with caplog.at_level(logging.WARNING), _fail_git():
            result = ticket_hook.find_uncommitted_ticket_md()
        assert result == []
        err = capsys.readouterr().err
        assert "[uncommitted-ticket-md-reminder] git status 失敗" in err
        assert GIT_ERROR in err
        assert "git status 失敗" in caplog.text

    def test_failure_reaches_additional_context(self, capsys):
        """跳過訊息須走平常的提醒管道（additionalContext），模型才看得到"""
        import json
        with _fail_git():
            ticket_hook.find_uncommitted_ticket_md()
        out = capsys.readouterr().out.strip()
        hso = json.loads(out)["hookSpecificOutput"]
        assert hso["hookEventName"] == "PreToolUse"
        assert "git status 失敗" in hso["additionalContext"]
        assert GIT_ERROR in hso["additionalContext"]

    def test_success_output_unchanged(self, capsys):
        path = "docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W8-005.md"
        with _ok_git(f"?? {path}\0"):
            result = ticket_hook.find_uncommitted_ticket_md()
        assert result == [path]
        assert capsys.readouterr().err == ""


class TestBranchStatusReminder:
    def test_failure_writes_stderr_and_log(self, capsys):
        logger = MagicMock()
        with _fail_git():
            branch_hook._report_uncommitted_changes(logger)
        err = capsys.readouterr().err
        assert "[branch-status-reminder] git status 失敗" in err
        assert GIT_ERROR in err
        assert logger.warning.called

    def test_success_output_unchanged(self, capsys):
        logger = MagicMock()
        with _ok_git("?? a.txt\0"):
            branch_hook._report_uncommitted_changes(logger)
        err = capsys.readouterr().err
        assert "git status 失敗" not in err
        assert "偵測到 1 個未提交變更" in err
