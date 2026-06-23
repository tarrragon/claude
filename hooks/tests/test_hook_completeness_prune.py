"""Tests for hook-completeness-check prune --fix（1.4.0-W2-013.4）.

驗證 prune_phantom_local_registrations：opt-in 只刪 settings.local.json 中
command 指向不存在 .py 檔的幽靈 hook entry，不誤刪 working hook 與 inline 指令，
dry-run 不寫檔，全刪後清理空的 hooks 結構。

設計依據：1.4.0-W2-013.2 reality-test（CC hooks 累積合併、local 不可自癒），
PC-148 固化原則（settings.local.json 不放 hook），ARCH-TUNL-001（幽靈無自癒機制）。
"""
from __future__ import annotations

import importlib.util
import json
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


def _local_settings(*entries) -> dict:
    """entries: (event, matcher, command) tuples → settings.local.json dict."""
    hooks: dict = {}
    for event, matcher, command in entries:
        hooks.setdefault(event, []).append(
            {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
        )
    return {"permissions": {"allow": ["Edit"]}, "hooks": hooks}


def _write_local(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / ".claude" / "settings.local.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


class TestPrunePhantomLocalRegistrations:
    def test_returns_phantom_entry(self, hook_module, tmp_path):
        data = _local_settings(
            ("Stop", "", "$CLAUDE_PROJECT_DIR/.claude/hooks/ghost.py")
        )
        local_path = _write_local(tmp_path, data)
        removed = hook_module.prune_phantom_local_registrations(
            local_path, tmp_path, apply=False
        )
        assert len(removed) == 1
        assert removed[0][0] == "Stop"
        assert removed[0][1].endswith("ghost.py")

    def test_dry_run_does_not_write(self, hook_module, tmp_path):
        data = _local_settings(
            ("Stop", "", "$CLAUDE_PROJECT_DIR/.claude/hooks/ghost.py")
        )
        local_path = _write_local(tmp_path, data)
        before = local_path.read_text(encoding="utf-8")
        hook_module.prune_phantom_local_registrations(local_path, tmp_path, apply=False)
        assert local_path.read_text(encoding="utf-8") == before

    def test_apply_removes_phantom_from_file(self, hook_module, tmp_path):
        data = _local_settings(
            ("Stop", "", "$CLAUDE_PROJECT_DIR/.claude/hooks/ghost.py")
        )
        local_path = _write_local(tmp_path, data)
        hook_module.prune_phantom_local_registrations(local_path, tmp_path, apply=True)
        reloaded = json.loads(local_path.read_text(encoding="utf-8"))
        # 幽靈刪除後 hooks 結構被清空
        assert reloaded.get("hooks", {}) == {}
        # 非 hook 設定保留
        assert reloaded["permissions"] == {"allow": ["Edit"]}

    def test_preserves_working_hook(self, hook_module, tmp_path):
        real = tmp_path / ".claude" / "hooks" / "real.py"
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_text("# real", encoding="utf-8")
        data = _local_settings(
            ("Stop", "", "$CLAUDE_PROJECT_DIR/.claude/hooks/real.py")
        )
        local_path = _write_local(tmp_path, data)
        removed = hook_module.prune_phantom_local_registrations(
            local_path, tmp_path, apply=True
        )
        assert removed == []
        reloaded = json.loads(local_path.read_text(encoding="utf-8"))
        assert reloaded["hooks"]["Stop"][0]["hooks"][0]["command"].endswith("real.py")

    def test_preserves_inline_non_py_command(self, hook_module, tmp_path):
        data = _local_settings(("Stop", "", "echo done"))
        local_path = _write_local(tmp_path, data)
        removed = hook_module.prune_phantom_local_registrations(
            local_path, tmp_path, apply=True
        )
        assert removed == []
        reloaded = json.loads(local_path.read_text(encoding="utf-8"))
        assert reloaded["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo done"

    def test_mixed_prunes_only_phantom(self, hook_module, tmp_path):
        real = tmp_path / ".claude" / "hooks" / "real.py"
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_text("# real", encoding="utf-8")
        data = _local_settings(
            ("Stop", "", "$CLAUDE_PROJECT_DIR/.claude/hooks/real.py"),
            ("PreToolUse", "Bash", "$CLAUDE_PROJECT_DIR/.claude/hooks/ghost.py"),
        )
        local_path = _write_local(tmp_path, data)
        removed = hook_module.prune_phantom_local_registrations(
            local_path, tmp_path, apply=True
        )
        assert len(removed) == 1
        assert removed[0][0] == "PreToolUse"
        reloaded = json.loads(local_path.read_text(encoding="utf-8"))
        assert "Stop" in reloaded["hooks"]
        assert "PreToolUse" not in reloaded["hooks"]

    def test_missing_local_file_returns_empty(self, hook_module, tmp_path):
        removed = hook_module.prune_phantom_local_registrations(
            tmp_path / ".claude" / "settings.local.json", tmp_path, apply=True
        )
        assert removed == []

    def test_no_hooks_key_returns_empty(self, hook_module, tmp_path):
        local_path = _write_local(tmp_path, {"permissions": {"allow": ["Edit"]}})
        removed = hook_module.prune_phantom_local_registrations(
            local_path, tmp_path, apply=True
        )
        assert removed == []
