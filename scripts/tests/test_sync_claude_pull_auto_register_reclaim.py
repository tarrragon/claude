"""Tests for auto_register_hooks 收回自己寫入的註冊（3.3.0-W1-214.1，tarrragon/claude#68）。

背景：上游只靠 config/hook-registry.yaml 登記的 hook，被 auto_register_hooks 寫進
consumer settings.json 後屬本地新增，三方合併不會動它；auto_register 原本只增不刪，
上游改名後舊註冊永遠留著，新舊兩支每次事件都執行。

修法：auto_register 把寫入的 command 記在 .sync-state.json；後續執行時，紀錄中的
command 若腳本已不在清冊、或已改由其他來源（settings.json 其他項目、dispatch
registry）註冊，就從 settings.json 收回。沒有紀錄的項目一律不移除（3.3.0-W1-036
用戶裁定：只移除可證明是本工具產生的項目），其中與 dispatch registry 重複者只警告，
警告寫出要刪哪一筆、在哪個檔的哪個區段。

對照組（主控裁定 2026-11-12）：
  - 有紀錄、清冊已不列：收回
  - 沒有紀錄的既有項目：只警告（或不動）
  - 清冊仍列：保留
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_auto_register_reclaim", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_auto_register_reclaim"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

if pull.yaml is None:
    pytest.skip(
        "pyyaml 未安裝；改用 `uv run --project .claude/scripts --group dev pytest`",
        allow_module_level=True,
    )

PREFIX = "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/"


def _cmd(rel: str) -> str:
    return PREFIX + rel


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _settings(commands: list[str]) -> dict:
    return {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": c} for c in commands],
                }
            ]
        }
    }


def _setup(tmp_path: Path, yaml_text: str, settings_cmds: list[str],
           recorded: list[str] | None = None, dispatch_paths: list[str] | None = None,
           files: tuple[str, ...] = ()) -> Path:
    claude_dir = tmp_path / ".claude"
    for rel in files:
        _write(claude_dir / rel, "# hook\n")
    _write(claude_dir / "config" / "hook-registry.yaml", yaml_text)
    _write(claude_dir / "settings.json", json.dumps(_settings(settings_cmds), indent=2))
    if recorded is not None:
        _write(
            claude_dir / pull.SYNC_STATE_FILENAME,
            json.dumps({pull.AUTO_REGISTERED_FIELD: recorded}),
        )
    if dispatch_paths:
        _write(
            claude_dir / "hooks" / "hook-dispatch-registry.json",
            json.dumps({"groups": {"PostToolUse:Bash": {
                "hooks": [{"path": p} for p in dispatch_paths]}}}),
        )
    return claude_dir


def _commands(claude_dir: Path) -> list[str]:
    data = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    return [
        h["command"]
        for group in data.get("hooks", {}).get("PostToolUse", [])
        for h in group.get("hooks", [])
    ]


def _recorded(claude_dir: Path) -> set[str]:
    state = json.loads((claude_dir / pull.SYNC_STATE_FILENAME).read_text(encoding="utf-8"))
    return set(state.get(pull.AUTO_REGISTERED_FIELD, []))


NEW_ONLY_YAML = "hooks:\n  new-hook.py: {event: PostToolUse, matcher: Bash}\n"
OLD_ONLY_YAML = "hooks: {}\nskill_hooks:\n  s/old-hook.py: {event: PostToolUse, matcher: Bash}\n"


def test_recorded_entry_no_longer_listed_is_reclaimed(tmp_path, capsys):
    """對照一：有紀錄、清冊已不列（上游改名）→ 收回舊註冊，新註冊補上，stdout 列出。"""
    old = _cmd("skills/s/hooks/old-hook.py")
    claude_dir = _setup(
        tmp_path, NEW_ONLY_YAML, [old], recorded=[old],
        files=("skills/s/hooks/old-hook.py", "hooks/new-hook.py"),
    )

    pull.auto_register_hooks(tmp_path)

    cmds = _commands(claude_dir)
    assert old not in cmds
    assert _cmd("hooks/new-hook.py") in cmds
    assert "old-hook.py" in capsys.readouterr().out
    assert _recorded(claude_dir) == {_cmd("hooks/new-hook.py")}


def test_unrecorded_entry_not_listed_is_kept(tmp_path):
    """對照二：沒有紀錄的既有項目（含使用者手寫項目）不移除。"""
    old = _cmd("skills/s/hooks/old-hook.py")
    manual = "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/manual-hook.py"
    claude_dir = _setup(
        tmp_path, NEW_ONLY_YAML, [old, manual], recorded=[],
        files=("skills/s/hooks/old-hook.py", "hooks/new-hook.py", "hooks/manual-hook.py"),
    )

    pull.auto_register_hooks(tmp_path)

    cmds = _commands(claude_dir)
    assert old in cmds
    assert manual in cmds


def test_recorded_entry_still_listed_is_kept(tmp_path):
    """對照三：清冊仍列 → 保留，且不重複登記。"""
    old = _cmd("skills/s/hooks/old-hook.py")
    claude_dir = _setup(
        tmp_path, OLD_ONLY_YAML, [old], recorded=[old],
        files=("skills/s/hooks/old-hook.py",),
    )

    pull.auto_register_hooks(tmp_path)

    assert _commands(claude_dir).count(old) == 1
    assert _recorded(claude_dir) == {old}


def test_recorded_entry_now_in_dispatch_registry_is_reclaimed(tmp_path):
    """有紀錄、清冊仍列但已改由 dispatch registry 執行 → 收回（避免同事件跑兩次）。"""
    old = _cmd("skills/s/hooks/old-hook.py")
    claude_dir = _setup(
        tmp_path, OLD_ONLY_YAML, [old], recorded=[old],
        dispatch_paths=[".claude/skills/s/hooks/old-hook.py"],
        files=("skills/s/hooks/old-hook.py",),
    )

    pull.auto_register_hooks(tmp_path)

    assert old not in _commands(claude_dir)
    assert _recorded(claude_dir) == set()


def test_unrecorded_dispatch_duplicate_warns_with_removal_steps(tmp_path, capsys):
    """沒有紀錄、但與 dispatch registry 重複 → 不移除，警告寫出檔名、區段與 command。"""
    dup = _cmd("hooks/in-dispatcher.py")
    claude_dir = _setup(
        tmp_path, "hooks: {}\n", [dup], recorded=None,
        dispatch_paths=[".claude/hooks/in-dispatcher.py"],
        files=("hooks/in-dispatcher.py",),
    )

    pull.auto_register_hooks(tmp_path)

    assert dup in _commands(claude_dir)
    out = capsys.readouterr().out
    assert "settings.json" in out
    assert "PostToolUse" in out
    assert dup in out


def test_newly_added_command_is_recorded(tmp_path):
    """新登記的 command 寫進紀錄，下一輪才有依據收回。"""
    claude_dir = _setup(
        tmp_path, NEW_ONLY_YAML, [], recorded=None, files=("hooks/new-hook.py",),
    )

    pull.auto_register_hooks(tmp_path)

    assert _recorded(claude_dir) == {_cmd("hooks/new-hook.py")}


def test_corrupt_sync_state_reclaims_nothing_and_is_not_overwritten(tmp_path, capsys):
    """狀態檔損毀：視為沒有紀錄（不收回），且不覆寫損毀檔，stderr 說明。"""
    old = _cmd("skills/s/hooks/old-hook.py")
    claude_dir = _setup(
        tmp_path, NEW_ONLY_YAML, [old], recorded=None,
        files=("skills/s/hooks/old-hook.py", "hooks/new-hook.py"),
    )
    corrupt = '{"last_synced_base_sha": "abc", "auto_registered_hook_commands": ['
    _write(claude_dir / pull.SYNC_STATE_FILENAME, corrupt)

    pull.auto_register_hooks(tmp_path)

    assert old in _commands(claude_dir)
    assert (claude_dir / pull.SYNC_STATE_FILENAME).read_text(encoding="utf-8") == corrupt
    assert "無法解析" in capsys.readouterr().err


def test_reclaim_preserves_other_sync_state_fields(tmp_path):
    """寫紀錄不得覆蓋 .sync-state.json 其他欄位（基準點等）。"""
    claude_dir = _setup(
        tmp_path, NEW_ONLY_YAML, [], recorded=None, files=("hooks/new-hook.py",),
    )
    _write(
        claude_dir / pull.SYNC_STATE_FILENAME,
        json.dumps({pull.BASE_SHA_FIELD: "abc123"}),
    )

    pull.auto_register_hooks(tmp_path)

    state = json.loads((claude_dir / pull.SYNC_STATE_FILENAME).read_text(encoding="utf-8"))
    assert state[pull.BASE_SHA_FIELD] == "abc123"
