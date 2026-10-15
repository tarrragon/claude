"""
worktree-branch-check-hook 提醒輸出管道測試

提醒（目標分支不符、未合併 worktree/分支）必須走 PreToolUse
additionalContext（模型可見）；stderr 不得有提醒；非觸發分支無任何輸出（E2 對照）。
"""

import contextlib
import importlib.util
import io
import json
from pathlib import Path

_HOOK_FILE = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "worktree-branch-check-hook.py"
)
_spec = importlib.util.spec_from_file_location(
    "worktree_branch_check_hook_emit", _HOOK_FILE
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _run(monkeypatch, command, result, target_warning=None):
    """執行 main()，回傳 (exit_code, stdout, stderr)。"""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(hook.sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(hook, "check_git_state", lambda: result)
    monkeypatch.setattr(hook, "check_target_branch", lambda: target_warning)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hook.main()
    return code, out.getvalue(), err.getvalue()


def _dirty_result():
    wt = hook.WorktreeInfo(
        path="/tmp/wt-a", branch="feat-a", is_main=False, uncommitted_count=3
    )
    return hook.CheckResult(True, True, [wt], ["feat-b"])


def test_unmerged_progress_emits_additional_context(monkeypatch):
    code, out, err = _run(monkeypatch, "git push origin main", _dirty_result())
    assert code == 0
    assert err == ""
    hso = json.loads(out)["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert "wt-a" in hso["additionalContext"]
    assert "feat-b" in hso["additionalContext"]


def test_target_branch_and_unmerged_merge_into_single_output(monkeypatch):
    code, out, err = _run(
        monkeypatch, "git merge feat-a", _dirty_result(), "[WARNING] 目標分支不符"
    )
    assert code == 0
    assert err == ""
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "目標分支不符" in ctx
    assert "feat-b" in ctx


def test_target_branch_only_emits_additional_context(monkeypatch):
    clean = hook.CheckResult(False, False, [], [])
    code, out, err = _run(monkeypatch, "git cherry-pick abc", clean, "[WARNING] 目標分支不符")
    assert code == 0
    assert err == ""
    assert "目標分支不符" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_clean_state_is_silent(monkeypatch):
    clean = hook.CheckResult(False, False, [], [])
    assert _run(monkeypatch, "git push origin main", clean) == (0, "", "")


def test_non_git_command_is_silent(monkeypatch):
    assert _run(monkeypatch, "ls -la", _dirty_result()) == (0, "", "")
