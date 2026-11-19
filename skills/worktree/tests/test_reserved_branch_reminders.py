"""worktree 兩支提醒 hook 的保留分支正反對照測試。

- merge-reminder：保留分支（票 pending）改列資訊、不附合併建議；非保留仍列合併提醒
- branch-check：保留分支不計入未合併進度；非保留仍列為未合併分支
"""

import importlib.util
import json
import logging
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parent.parent / "hooks"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _HOOKS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reminder = _load("wmr_reserved", "worktree-merge-reminder-hook.py")
check = _load("wbc_reserved", "worktree-branch-check-hook.py")

_BRANCH = "feat/3.3.0-W1-007"


def _run_reminder(monkeypatch, capsys, reservations):
    monkeypatch.setattr(reminder, "read_json_from_stdin", lambda logger: {"x": 1})
    monkeypatch.setattr(reminder, "is_subagent_environment", lambda d: False)
    monkeypatch.setattr(reminder, "is_ticket_complete_command", lambda d: True)
    monkeypatch.setattr(reminder, "parse_worktree_list", lambda logger: [("/wt/a", _BRANCH)])
    monkeypatch.setattr(
        reminder, "classify_worktrees",
        lambda wts, logger: ([("/wt/a", _BRANCH, ["abc1234 c"])], [], []),
    )
    monkeypatch.setattr(reminder, "find_reservation", lambda b, root, logger: reservations.get(b))
    assert reminder.main() == 0
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_merge_reminder_reserved_is_info_only(monkeypatch, capsys):
    msg = _run_reminder(monkeypatch, capsys, {_BRANCH: "3.4.0-W1-214"})
    assert "保留給票 3.4.0-W1-214" in msg
    assert "待合併 commit" not in msg
    assert "請在 ticket 完成前合併" not in msg


def test_merge_reminder_non_reserved_still_asks_merge(monkeypatch, capsys):
    msg = _run_reminder(monkeypatch, capsys, {})
    assert "待合併 commit: 1 個" in msg
    assert "請在 ticket 完成前合併" in msg


def _check_state(monkeypatch, reservations):
    monkeypatch.setattr(check, "get_worktree_list", lambda: [])
    monkeypatch.setattr(check, "get_unmerged_branches", lambda: [_BRANCH])
    import lib.reserved_branch as rb

    monkeypatch.setattr(rb, "find_reservation", lambda b, root, logger: reservations.get(b))
    return check.check_git_state()


def test_branch_check_reserved_not_counted_as_unmerged(monkeypatch):
    result = _check_state(monkeypatch, {_BRANCH: "3.4.0-W1-214"})
    assert result.unmerged_branches == []
    assert result.has_unmerged_branches is False
    assert result.reserved_branches == {_BRANCH: "3.4.0-W1-214"}


def test_branch_check_non_reserved_still_unmerged(monkeypatch):
    result = _check_state(monkeypatch, {})
    assert result.unmerged_branches == [_BRANCH]
    assert result.has_unmerged_branches is True
    assert _BRANCH in check.format_warning_output(result)
