"""Tests for sync-claude-pull.py 收尾依專案 hook 清冊重建 settings.local.json（3.4.0-W1-009）。

pull 與 SessionStart 共用 lib.project_hook_registry.sync；本檔驗證 pull 收尾當下
settings.local.json 即與清冊一致（不等下個 session），含正向對照（清冊移除的條目被移除）。
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_registry_rebuild", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_registry_rebuild"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

import lib.project_hook_registry as registry  # noqa: E402

USER_COMMAND = "echo user-owned"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """紀錄狀態檔改放 tmp（須 patch lib，sync 在 lib 內解析 state_path）。"""
    state = tmp_path / "state" / "generated.json"
    monkeypatch.setattr(registry, "state_path", lambda root: state)
    return state


def _write_manifest(root: Path, scripts: list) -> None:
    lines = ["version: 1", "hooks:"]
    for name in scripts:
        lines += [f"  {name}:", f"    script: .claude/hooks/{name}.py", "    event: Stop"]
    path = root / registry.MANIFEST_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for name in scripts:
        (root / ".claude" / "hooks" / f"{name}.py").write_text("", encoding="utf-8")


def _local_commands(root: Path) -> set:
    data = json.loads((root / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    return {h["command"] for g in data.get("hooks", {}).get("Stop", []) for h in g["hooks"]}


def test_new_manifest_entry_appears_immediately(tmp_path):
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    _write_manifest(tmp_path, ["proj-a"])
    pull.rebuild_local_hooks_from_registry(tmp_path)
    assert registry.build_command(".claude/hooks/proj-a.py") in _local_commands(tmp_path)


def test_removed_manifest_entry_is_removed_user_entry_kept(tmp_path, capsys):
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    _write_manifest(tmp_path, ["proj-a", "proj-b"])
    pull.rebuild_local_hooks_from_registry(tmp_path)
    local = tmp_path / ".claude" / "settings.local.json"
    data = json.loads(local.read_text(encoding="utf-8"))
    data["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": USER_COMMAND}]})
    local.write_text(json.dumps(data), encoding="utf-8")

    _write_manifest(tmp_path, ["proj-a"])  # proj-b 從清冊移除
    pull.rebuild_local_hooks_from_registry(tmp_path)

    commands = _local_commands(tmp_path)
    assert registry.build_command(".claude/hooks/proj-a.py") in commands
    assert registry.build_command(".claude/hooks/proj-b.py") not in commands
    assert USER_COMMAND in commands
    assert USER_COMMAND in capsys.readouterr().err  # 使用者自加者示警


def test_pull_and_session_start_share_one_function():
    hook_spec = importlib.util.spec_from_file_location(
        "registry_sync_hook_for_pull_test",
        Path(__file__).resolve().parents[2] / "hooks" / "project-hook-registry-sync-hook.py",
    )
    hook = importlib.util.module_from_spec(hook_spec)
    hook_spec.loader.exec_module(hook)  # type: ignore[union-attr]
    assert hook.sync is registry.sync
    assert pull.project_hook_registry_sync is registry.sync


def test_manifest_error_reports_stderr_and_does_not_raise(tmp_path, capsys):
    path = tmp_path / registry.MANIFEST_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text("version: 99\nhooks: {}\n", encoding="utf-8")
    report = pull.rebuild_local_hooks_from_registry(tmp_path)
    assert report
    assert "project-hook-registry-sync" in capsys.readouterr().err
    assert not logging.getLogger("project-hook-registry-sync").disabled
