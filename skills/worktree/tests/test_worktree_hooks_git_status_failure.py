"""
worktree-merge-reminder / worktree-auto-commit：git status 失敗須有可見訊號（3.4.0-W1-331）

- merge-reminder：失敗保守視為 dirty（不列為可清理）並留痕
- auto-commit：失敗時跳過代捕並留痕；成功路徑輸出不變
"""

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import patch

_HOOKS_DIR = Path(__file__).parent.parent / "hooks"
_CLAUDE_DIR = Path(__file__).resolve().parents[3]
for _p in (str(_CLAUDE_DIR), str(_CLAUDE_DIR / "hooks")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GIT_ERROR = "fatal: not a git repository"
_logger = logging.getLogger("test-worktree-git-status-failure")


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge_hook = _load("worktree_merge_reminder_gsf", "worktree-merge-reminder-hook.py")
commit_hook = _load("worktree_auto_commit_gsf", "worktree-auto-commit-hook.py")


def _fail_git():
    from lib import git_utils
    return patch.object(git_utils, "run_git_command", return_value=(False, GIT_ERROR))


def _ok_git(porcelain_z: str):
    from lib import git_utils
    return patch.object(git_utils, "run_git_command", return_value=(True, porcelain_z))


class TestMergeReminder:
    def test_failure_treated_as_dirty_with_trace(self, capsys, caplog):
        with caplog.at_level(logging.WARNING), _fail_git():
            files = merge_hook.get_dirty_files("/wt", _logger)
            dirty = merge_hook.is_worktree_dirty("/wt", _logger)
        assert files and files[0][0] == "??"
        assert dirty is True
        err = capsys.readouterr().err
        assert "[worktree-merge-reminder] git status 失敗" in err
        assert "/wt" in err and GIT_ERROR in err

    def test_success_output_unchanged(self, capsys):
        with _ok_git(" M a.md\0"):
            assert merge_hook.get_dirty_files("/wt", _logger) == [(" M", "a.md")]
        with _ok_git(""):
            assert merge_hook.get_dirty_files("/wt", _logger) == []
        assert capsys.readouterr().err == ""


class TestAutoCommit:
    def test_failure_skips_and_traces(self, capsys, caplog):
        with caplog.at_level(logging.WARNING), _fail_git():
            files = commit_hook.get_changed_files(_logger)
        assert files == []
        err = capsys.readouterr().err
        assert "[worktree-auto-commit] git status 失敗" in err
        assert GIT_ERROR in err
        assert "git status 失敗" in caplog.text

    def test_success_output_unchanged(self, capsys):
        with _ok_git(" M src/a.py\0?? new.txt\0"):
            files = commit_hook.get_changed_files(_logger)
        assert files == ["src/a.py", "new.txt"]
        assert capsys.readouterr().err == ""
