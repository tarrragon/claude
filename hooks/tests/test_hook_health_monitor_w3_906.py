"""Tests for hook-health-monitor.py _extract_filename_from_command (0.2.1-W3-906).

889（e404bb416）將 settings.json SessionStart hooks 全數改為顯式解譯器形式
（'uv run --quiet <path>' / 'python3 <path>'）後，_extract_filename_from_command
仍假設 command_parts[0] 即為 hook 路徑，對新形式一律回傳 None。

本檔覆蓋三種 command 形式的解析，並以 settings.json 現況做回歸驗證。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOK_DIR))


def _load_monitor_module():
    path = HOOK_DIR / "hook-health-monitor.py"
    spec = importlib.util.spec_from_file_location("hook_health_monitor_w3_906", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


monitor = _load_monitor_module()


@pytest.mark.parametrize(
    "command,expected",
    [
        (
            "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/foo.py",
            "foo.py",
        ),
        (
            "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/bar.py",
            "bar.py",
        ),
        (
            "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/baz.py",
            "baz.py",
        ),
        (
            "$CLAUDE_PROJECT_DIR/.claude/hooks/qux.py",
            "qux.py",
        ),
        (
            ".claude/hooks/quux.py",
            "quux.py",
        ),
        (
            "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/with-args.py --flag value",
            "with-args.py",
        ),
    ],
)
def test_extract_filename_supports_all_forms(command, expected):
    assert monitor._extract_filename_from_command(command) == expected


@pytest.mark.parametrize(
    "command",
    [
        "",
        "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/skills/foo/bar.py",
        "python3 /some/other/path/not_a_hook.py",
        "echo hello",
    ],
)
def test_extract_filename_returns_none_for_non_hook_commands(command):
    assert monitor._extract_filename_from_command(command) is None


def test_load_sessionstart_hooks_from_real_settings_nonempty():
    """迴歸驗證：settings.json 現況應能解析出全部 SessionStart hook（非 0）。"""
    settings_path = HOOK_DIR.parent / "settings.json"
    hooks = monitor.load_sessionstart_hooks_from_settings(settings_path)
    assert len(hooks) > 0

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)
    session_start_groups = settings.get("hooks", {}).get("SessionStart", [])
    total_registered = sum(
        len(group.get("hooks", [])) for group in session_start_groups
    )
    assert total_registered > 0
    # 每個實際註冊的 command 皆能被解析（去重後 hooks 數 <= 註冊筆數，但須 > 0
    # 且不得因新形式而全數漏解析）。
    assert len(hooks) <= total_registered
