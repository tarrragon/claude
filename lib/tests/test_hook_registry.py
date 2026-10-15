#!/usr/bin/env python3
"""
hook_registry 共用 helper 測試

涵蓋：registry 讀取、併入 settings 的事件與 matcher、讀取失敗的可見性，
以及以 registry 為唯一讀取點的消費端（涵蓋率檢查、依賴隔離檢查、
健康監控）不再把被併入分派程序的 hook 判為未註冊，並含正向對照
（settings 與 registry 皆無的 hook 仍被判為未註冊）。
"""

import importlib.util
import json
import logging
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(CLAUDE_DIR.parent))
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))

from lib import hook_registry  # noqa: E402

_LOGGER = logging.getLogger("test_hook_registry")
DISPATCHER_CMD = "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/hook-dispatcher.py --group PreToolUse:Bash"


def _load_hook(filename):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), CLAUDE_DIR / "hooks" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_registry(root, paths, timeout=None):
    d = root / ".claude" / "hooks"
    d.mkdir(parents=True, exist_ok=True)
    hooks = []
    for p in paths:
        e = {"path": p}
        if timeout:
            e["timeout"] = timeout
        hooks.append(e)
    (d / "hook-dispatch-registry.json").write_text(
        json.dumps({"groups": {"PreToolUse:Bash": {"hooks": hooks}}}), encoding="utf-8")


def _settings():
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": DISPATCHER_CMD}]}]}}


class TestHookRegistry:
    def test_missing_registry_returns_no_groups(self, tmp_path):
        assert hook_registry.load_registry_groups(tmp_path) == {}

    def test_merge_adds_hooks_under_real_event_and_matcher(self, tmp_path):
        _write_registry(tmp_path, [".claude/hooks/merged-a-hook.py"], timeout=30)
        settings = hook_registry.merge_dispatch_registry(_settings(), tmp_path)
        groups = settings["hooks"]["PreToolUse"]
        merged = [g for g in groups if g["matcher"] == "Bash"][-1]
        assert merged["hooks"][0]["command"] == "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/merged-a-hook.py"
        assert merged["hooks"][0]["timeout"] == 30
        assert "_DispatchRegistry" not in settings["hooks"]

    def test_unreadable_registry_is_logged_and_settings_unchanged(self, tmp_path, caplog):
        d = tmp_path / ".claude" / "hooks"
        d.mkdir(parents=True)
        (d / "hook-dispatch-registry.json").write_text("{bad", encoding="utf-8")
        with caplog.at_level(logging.INFO, logger="test_hook_registry"):
            settings = hook_registry.merge_dispatch_registry(_settings(), tmp_path, _LOGGER)
        assert settings == _settings()
        assert "讀取分派 registry 失敗" in caplog.text

    def test_corrupt_registry_warns_on_both_channels_and_returns_original(self, tmp_path, caplog, capsys):
        d = tmp_path / ".claude" / "hooks"
        d.mkdir(parents=True)
        (d / "hook-dispatch-registry.json").write_text("{bad", encoding="utf-8")
        with caplog.at_level(logging.DEBUG, logger="test_hook_registry"):
            settings = hook_registry.merge_dispatch_registry(_settings(), tmp_path, _LOGGER)
        assert settings == _settings()
        records = [r for r in caplog.records if r.name == "test_hook_registry"]
        assert records and all(r.levelno == logging.WARNING for r in records)
        err = capsys.readouterr().err
        assert "hook-dispatch-registry.json" in err and "讀取分派 registry 失敗" in err

    def test_registry_commands_equivalent_to_original_registration(self, tmp_path):
        _write_registry(tmp_path, [".claude/hooks/a-hook.py", ".claude/skills/s/hooks/b-hook.py"])
        assert hook_registry.registry_commands(tmp_path) == [
            "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/a-hook.py",
            "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/skills/s/hooks/b-hook.py"]


class TestCoverageCheckConsumer:
    """涵蓋率檢查：E1 對照（有 registry / 無 registry）與正向對照（兩處皆無）"""

    def _registered(self, settings):
        mod = _load_hook("hook-registration-coverage-check.py")
        return mod.extract_registered_hooks(settings)

    def test_hook_only_in_registry_counts_as_registered_but_not_without_it(self, tmp_path):
        _write_registry(tmp_path, [".claude/hooks/merged-a-hook.py"])
        without = self._registered(_settings())
        with_registry = self._registered(hook_registry.merge_dispatch_registry(_settings(), tmp_path))
        assert "merged-a-hook.py" not in without
        assert "merged-a-hook.py" in with_registry

    def test_hook_in_neither_is_still_unregistered(self, tmp_path):
        _write_registry(tmp_path, [".claude/hooks/merged-a-hook.py"])
        registered = self._registered(hook_registry.merge_dispatch_registry(_settings(), tmp_path))
        assert "orphan-hook.py" not in registered

    def test_skill_hook_in_registry_counts_as_registered(self, tmp_path):
        _write_registry(tmp_path, [".claude/skills/ticket/hooks/merged-s-hook.py"])
        mod = _load_hook("hook-registration-coverage-check.py")
        merged = hook_registry.merge_dispatch_registry(_settings(), tmp_path)
        assert mod.extract_registered_skill_hooks(merged)
        assert not mod.extract_registered_skill_hooks(_settings())


class TestDependencyIsolationConsumer:
    def test_registry_hooks_are_extracted_with_uv_prefix(self, tmp_path):
        _write_registry(tmp_path, [".claude/hooks/merged-a-hook.py"])
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.write_text(json.dumps(_settings()), encoding="utf-8")
        mod = _load_hook("hook-dependency-isolation-check-hook.py")
        assert ".claude/hooks/merged-a-hook.py" in mod.extract_registered_hook_paths(settings_path)
        prefixes = mod.extract_hook_command_prefixes(settings_path)
        assert prefixes[".claude/hooks/merged-a-hook.py"] == {"uv run --quiet"}

    def test_hook_in_neither_is_not_extracted(self, tmp_path):
        _write_registry(tmp_path, [".claude/hooks/merged-a-hook.py"])
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.write_text(json.dumps(_settings()), encoding="utf-8")
        mod = _load_hook("hook-dependency-isolation-check-hook.py")
        assert ".claude/hooks/orphan-hook.py" not in mod.extract_registered_hook_paths(settings_path)


class TestHealthMonitorConsumer:
    def test_load_settings_merges_registry(self, tmp_path):
        _write_registry(tmp_path, [".claude/hooks/merged-a-hook.py"])
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.write_text(json.dumps(_settings()), encoding="utf-8")
        mod = _load_hook("hook-health-monitor.py")
        loaded = mod._load_settings(settings_path)
        commands = [h["command"] for g in loaded["hooks"]["PreToolUse"] for h in g["hooks"]]
        assert any(c.endswith("merged-a-hook.py") for c in commands)

    def test_missing_settings_still_returns_empty(self, tmp_path):
        mod = _load_hook("hook-health-monitor.py")
        assert mod._load_settings(tmp_path / "nope.json") == {}


class TestSingleReaderInvariant:
    def test_only_hook_registry_module_parses_registry_file(self):
        offenders = []
        for base in (CLAUDE_DIR / "hooks", CLAUDE_DIR / "lib"):
            for p in base.glob("*.py"):
                if p.name == "hook_registry.py":
                    continue
                text = p.read_text(encoding="utf-8")
                if "hook-dispatch-registry.json" in text and "json.load(" in text:
                    offenders.append(p.name)
        assert offenders == []


def test_hook_output_validator_target_hooks_include_registry_entries():
    """validator 經 merge_dispatch_registry 取清單：被併入分派 registry 的 hook 不得缺席"""
    p = CLAUDE_DIR / "lib" / "hook_output_validator.py"
    spec = importlib.util.spec_from_file_location("hook_output_validator_under_test", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    commands = [c for _, _, c in mod.load_target_hooks()]
    assert any("workspace-wipe-guard-hook.py" in c for c in commands)
