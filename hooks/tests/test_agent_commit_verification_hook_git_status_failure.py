"""
agent-commit-verification-hook：git status 失敗須有可見訊號（3.4.0-W1-329）

根因（3.4.0-W1-058）：共用層舊 API 失敗時回空清單，失敗與「無變更」同形，
提醒漏報且不留痕。遷移至 get_uncommitted_files_strict 後：
- 主 checkout 與各 worktree 兩處，失敗時 stderr + 日誌留痕
- 失敗不阻擋 hook 其餘檢查（提醒類 fail-open，但不再靜默）
- 反向對照：git status 成功時行為與遷移前相同
"""

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import patch

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "agent_commit_verification_hook_git_status_failure",
    _HOOKS_DIR / "agent-commit-verification-hook.py",
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_logger = logging.getLogger("test-git-status-failure")

GIT_ERROR = "fatal: not a git repository"


def _fail_git():
    from lib import git_utils
    return patch.object(git_utils, "run_git_command", return_value=(False, GIT_ERROR))


def _ok_git(porcelain_z: str):
    from lib import git_utils
    return patch.object(git_utils, "run_git_command", return_value=(True, porcelain_z))


class TestMainCheckoutFailure:
    def test_failure_writes_stderr_and_log(self, capsys, caplog):
        with caplog.at_level(logging.WARNING, logger=_logger.name), _fail_git():
            result = hook.get_uncommitted_files("/repo", _logger)
        assert result == []
        err = capsys.readouterr().err
        assert "[agent-commit-verification-hook] git status 失敗" in err
        assert "/repo" in err and GIT_ERROR in err
        assert any(GIT_ERROR in r.getMessage() for r in caplog.records)

    def test_success_unchanged_and_silent(self, capsys):
        with _ok_git(" M lib/a.dart\0?? lib/b.dart\0"):
            result = hook.get_uncommitted_files("/repo", _logger)
        assert result == ["lib/a.dart", "lib/b.dart"]
        assert capsys.readouterr().err == ""


class TestWorktreeFailure:
    def test_failure_writes_stderr_and_log_and_skips_that_worktree(self, capsys, caplog):
        with caplog.at_level(logging.WARNING, logger=_logger.name), _fail_git():
            result = hook.get_worktree_uncommitted_files(
                [("/repo/.claude/worktrees/agent-x", "feat/x")], _logger
            )
        assert result == []
        err = capsys.readouterr().err
        assert "[agent-commit-verification-hook] git status 失敗" in err
        assert "/repo/.claude/worktrees/agent-x" in err
        assert any("agent-x" in r.getMessage() for r in caplog.records)

    def test_success_unchanged_and_silent(self, capsys):
        with _ok_git(" M lib/a.dart\0"):
            result = hook.get_worktree_uncommitted_files(
                [("/repo/.claude/worktrees/agent-x", "feat/x")], _logger
            )
        assert result == [("/repo/.claude/worktrees/agent-x", "feat/x", ["lib/a.dart"])]
        assert capsys.readouterr().err == ""
