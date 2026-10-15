"""
PreToolUse 提醒類 hook 經 hook-dispatcher 合併後 additionalContext 仍存在

分派器群組 PreToolUse:Bash 內的提醒 hook（version-release-guard、
worktree-branch-check、uncommitted-ticket-md-reminder）以 additionalContext
輸出；本測試用分派器的 run_inprocess + merge_results 驗證合併輸出保留提醒，
且提醒不落入 stderr（stderr 對模型不可見）。
"""

import importlib.util
import json
import os
from pathlib import Path

_CLAUDE_DIR = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "hook_dispatcher_for_reminder_test", _CLAUDE_DIR / "hooks" / "hook-dispatcher.py"
)
dispatcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dispatcher)

_VERSION_GUARD = (
    _CLAUDE_DIR / "skills" / "version-release" / "hooks" / "version-release-guard-hook.py"
)
_GROUP = "PreToolUse:Bash"


def _payload(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def test_registry_group_contains_the_three_reminder_hooks():
    group = dispatcher.load_group(_GROUP)
    paths = " ".join(h["path"] for h in group["hooks"])
    for name in (
        "version-release-guard-hook.py",
        "worktree-branch-check-hook.py",
        "uncommitted-ticket-md-reminder-hook.py",
    ):
        assert name in paths


def test_version_guard_reminder_survives_merge(monkeypatch):
    monkeypatch.delenv("VERSION_RELEASE_SCRIPT", raising=False)
    result = dispatcher.run_inprocess(
        _VERSION_GUARD, _payload('git commit -m "feat(v1.2.3): x"'), 30
    )
    code, stdout, stderr = dispatcher.merge_results([result], event="PreToolUse")
    assert code == 0
    assert stderr.strip() == ""
    hso = json.loads(stdout)["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert "Version Release Guard" in hso["additionalContext"]


def test_reminder_merges_with_other_hook_context():
    a = dispatcher.HookResult(
        "a-hook", 0,
        json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": "提醒甲"}}),
    )
    b = dispatcher.HookResult(
        "b-hook", 0,
        json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": "提醒乙"}}),
    )
    code, stdout, stderr = dispatcher.merge_results([a, b], event="PreToolUse")
    ctx = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
    assert code == 0 and stderr == ""
    assert "提醒甲" in ctx and "提醒乙" in ctx
