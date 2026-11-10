"""named-agent-delivery-channel-hint-hook 測試（tarrragon/claude#54）。

以子程序實跑 hook（PreToolUse, tool_name=Agent），斷言 stdout 的 additionalContext。
正向對照：帶 name、背景、prompt 無交付通道句 -> 提醒。
反向對照：含交付通道句、不帶 name、明確前景 -> 不輸出。
提醒不阻擋：exit 0，且輸出不帶 permissionDecision。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
HOOK_PATH = HOOKS_DIR / "named-agent-delivery-channel-hint-hook.py"
SETTINGS_PATH = HOOKS_DIR.parent / "settings.json"

_spec = importlib.util.spec_from_file_location("named_agent_hint_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

NO_CHANNEL = "審查 W1-001 的 Solution，列出問題。"
WITH_CHANNEL = "審查後以 SendMessage({to: \"main\"}) 送出報告本體。"


def _run(tool_input: dict, tmp_path: Path, tool_name: str = "Agent") -> subprocess.CompletedProcess:
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)},
    )


def test_named_background_without_channel_gets_hint(tmp_path):
    result = _run({"name": "reviewer", "prompt": NO_CHANNEL}, tmp_path)

    assert result.returncode == 0
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert "SendMessage" in output["additionalContext"]
    assert "permissionDecision" not in output


@pytest.mark.parametrize(
    "tool_input",
    [
        {"name": "reviewer", "prompt": WITH_CHANNEL},
        {"prompt": NO_CHANNEL},
        {"name": "", "prompt": NO_CHANNEL},
        {"name": "reviewer", "prompt": NO_CHANNEL, "run_in_background": False},
    ],
    ids=["has-channel", "no-name", "empty-name", "foreground"],
)
def test_no_hint_cases(tool_input, tmp_path):
    result = _run(tool_input, tmp_path)

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_explicit_background_true_gets_hint(tmp_path):
    result = _run({"name": "r", "prompt": NO_CHANNEL, "run_in_background": True}, tmp_path)
    assert "additionalContext" in json.loads(result.stdout)["hookSpecificOutput"]


def test_non_agent_tool_ignored(tmp_path):
    result = _run({"name": "r", "prompt": NO_CHANNEL}, tmp_path, tool_name="Bash")
    assert result.stdout.strip() == ""


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("完成後以 SendMessage 送到main", True),          # 中文緊鄰仍算獨立的 main
        ("用 SendMessage 回報給 domain owner", False),     # domain 不算
        ("寫入 main 分支即可", False),                      # 缺 SendMessage
        ("SendMessage to main", True),
    ],
)
def test_delivery_channel_criterion(prompt, expected):
    assert hook.has_delivery_channel(prompt) is expected


def test_registered_in_settings_pretooluse_agent():
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    commands = [
        h["command"]
        for group in settings["hooks"]["PreToolUse"]
        if group.get("matcher") == "Agent"
        for h in group["hooks"]
    ]
    assert any(c.endswith("/named-agent-delivery-channel-hint-hook.py") for c in commands)
