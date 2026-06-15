"""Tests for hook-completeness-check 反向檢查（W9-004 / framework issue #2）.

驗證：
- _resolve_command_path 解析 $CLAUDE_PROJECT_DIR / interpreter 前綴 / 非 .py 回 None
- find_phantom_registrations 偵測「已註冊但檔不存在」幽靈註冊（runtime 崩潰類型）
- find_duplicate_registrations 偵測跨檔重複（Stop matcher=""），且不誤判不同 matcher
  的多工具覆蓋（false-positive 回歸防護）
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

HOOK_FILE = _HOOKS_DIR / "hook-completeness-check.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "hook_completeness_check", HOOK_FILE
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["hook_completeness_check"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_module():
    return _load_hook_module()


def _settings_with_command(event: str, matcher: str, command: str) -> dict:
    return {
        "hooks": {
            event: [
                {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
            ]
        }
    }


class TestResolveCommandPath:
    def test_resolves_claude_project_dir(self, hook_module, tmp_path):
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/foo.py"
        assert hook_module._resolve_command_path(cmd, tmp_path) == (
            tmp_path / ".claude" / "hooks" / "foo.py"
        )

    def test_resolves_braced_form(self, hook_module, tmp_path):
        cmd = "${CLAUDE_PROJECT_DIR}/.claude/hooks/foo.py"
        assert hook_module._resolve_command_path(cmd, tmp_path) == (
            tmp_path / ".claude" / "hooks" / "foo.py"
        )

    def test_handles_interpreter_prefix(self, hook_module, tmp_path):
        cmd = "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/foo.py --flag"
        assert hook_module._resolve_command_path(cmd, tmp_path) == (
            tmp_path / ".claude" / "hooks" / "foo.py"
        )

    def test_returns_none_for_non_py_command(self, hook_module, tmp_path):
        assert hook_module._resolve_command_path("echo hello", tmp_path) is None

    def test_returns_none_for_empty(self, hook_module, tmp_path):
        assert hook_module._resolve_command_path("", tmp_path) is None


class TestFindPhantomRegistrations:
    def test_detects_registered_but_missing_file(self, hook_module, tmp_path):
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/ghost.py"
        settings = _settings_with_command("Stop", "", cmd)
        phantoms = hook_module.find_phantom_registrations(
            [("settings.local.json", settings)], tmp_path
        )
        assert len(phantoms) == 1
        label, event, path = phantoms[0]
        assert label == "settings.local.json"
        assert event == "Stop"
        assert path.endswith("ghost.py")

    def test_no_phantom_when_file_exists(self, hook_module, tmp_path):
        hook_path = tmp_path / ".claude" / "hooks" / "real.py"
        hook_path.parent.mkdir(parents=True)
        hook_path.write_text("# real", encoding="utf-8")
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/real.py"
        settings = _settings_with_command("Stop", "", cmd)
        phantoms = hook_module.find_phantom_registrations(
            [("settings.json", settings)], tmp_path
        )
        assert phantoms == []

    def test_skips_none_settings(self, hook_module, tmp_path):
        phantoms = hook_module.find_phantom_registrations(
            [("settings.local.json", None)], tmp_path
        )
        assert phantoms == []

    def test_ignores_non_py_inline_command(self, hook_module, tmp_path):
        settings = _settings_with_command("Stop", "", "echo done")
        phantoms = hook_module.find_phantom_registrations(
            [("settings.json", settings)], tmp_path
        )
        assert phantoms == []


class TestFindDuplicateRegistrations:
    def test_detects_cross_file_duplicate(self, hook_module, tmp_path):
        """同一 Stop hook（matcher=""）在 settings.json + settings.local.json → 重複."""
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/stop.py"
        s1 = _settings_with_command("Stop", "", cmd)
        s2 = _settings_with_command("Stop", "", cmd)
        dups = hook_module.find_duplicate_registrations(
            [("settings.json", s1), ("settings.local.json", s2)], tmp_path
        )
        assert len(dups) == 1
        event, path, labels = dups[0]
        assert event == "Stop"
        assert "settings.json" in labels and "settings.local.json" in labels

    def test_different_matchers_not_flagged(self, hook_module, tmp_path):
        """同一 hook 在 PreToolUse 下用不同 matcher（Edit/Write）屬合法多工具覆蓋，不報重複."""
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py"
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Edit", "hooks": [{"type": "command", "command": cmd}]},
                    {"matcher": "Write", "hooks": [{"type": "command", "command": cmd}]},
                ]
            }
        }
        dups = hook_module.find_duplicate_registrations(
            [("settings.json", settings)], tmp_path
        )
        assert dups == []

    def test_single_registration_not_flagged(self, hook_module, tmp_path):
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/solo.py"
        settings = _settings_with_command("Stop", "", cmd)
        dups = hook_module.find_duplicate_registrations(
            [("settings.json", settings), ("settings.local.json", None)], tmp_path
        )
        assert dups == []
