"""
worktree-pre-dispatch-branch-drift-hook 測試套件（1.2.0-W1-030 Guard B）

防護目標：派發 worktree subagent 前，若主 repo HEAD 漂移離開 main/master 則阻擋。
來源事故：1.2.0-W1-028 事故二（cwd 污染致主 repo 漂到 feat 分支，merge 落錯處）。
"""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

_HOOK_FILE = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "worktree-pre-dispatch-branch-drift-hook.py"
)
_spec = importlib.util.spec_from_file_location(
    "worktree_pre_dispatch_branch_drift_hook", _HOOK_FILE
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


class TestMain:
    def test_non_worktree_isolation_passes(self):
        data = {"tool_input": {"isolation": "none"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data):
            assert hook.main() == 0

    def test_missing_isolation_passes(self):
        data = {"tool_input": {}}
        with patch.object(hook, "read_json_from_stdin", return_value=data):
            assert hook.main() == 0

    def test_empty_stdin_passes(self):
        with patch.object(hook, "read_json_from_stdin", return_value=None):
            assert hook.main() == 0

    def test_on_main_passes(self):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "run_git", return_value="main"
        ):
            assert hook.main() == 0

    def test_on_master_passes(self):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "run_git", return_value="master"
        ):
            assert hook.main() == 0

    def test_drifted_to_feat_blocks(self, capsys):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "run_git", return_value="feat/1.2.0-W1-025-terminal-frame"
        ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "Guard B" in captured.err
        assert "feat/1.2.0-W1-025-terminal-frame" in captured.err

    def test_detached_head_passes(self):
        # symbolic-ref 失敗回 None（detached / git 失敗）→ 放行不阻擋
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "run_git", return_value=None
        ):
            assert hook.main() == 0
