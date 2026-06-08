"""Tests for exec-bit restoration covering settings.json-registered skill root scripts (W9-007).

背景：exec-bit 還原邏輯以「目錄名 hooks」為涵蓋邊界（W1-020 缺陷 G），
未涵蓋「skill 根目錄被 settings.json 註冊為直接執行的腳本」。

`skills/continuous-learning/evaluate-session.py`、`skills/strategic-compact/suggest-compact.py`
位於 skill 根目錄（非 hooks/ 子目錄），透過 settings.json hook command 直接執行，
sync 後失去 exec bit → Permission denied。

本測試驗證 pull 與 push 兩端對 settings.json 註冊的 skill 根目錄 .py 還原 exec bit，
且不影響未註冊的 skill .py（避免純 shebang 策略的 false positive）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, _SCRIPTS_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


pull_mod = _load("sync_claude_pull", "sync-claude-pull.py")
push_mod = _load("sync_claude_push", "sync-claude-push.py")


pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX exec-bit semantics required"
)


def _is_executable(p: Path) -> bool:
    return bool(p.stat().st_mode & 0o111)


def _make_claude_tree_with_settings(root: Path) -> dict[str, Path]:
    """建立含 skill 根目錄執行檔 + settings.json 的 .claude 樹，.py 均為 644。"""
    files: dict[str, Path] = {}

    # 已註冊的 skill 根目錄執行檔（應被加 +x）
    registered_a = root / "skills" / "continuous-learning" / "evaluate-session.py"
    registered_a.parent.mkdir(parents=True, exist_ok=True)
    registered_a.write_text("#!/usr/bin/env -S uv run\n# eval\n")
    files["registered_a"] = registered_a

    registered_b = root / "skills" / "strategic-compact" / "suggest-compact.py"
    registered_b.parent.mkdir(parents=True, exist_ok=True)
    registered_b.write_text("#!/usr/bin/env python3\n# compact\n")
    files["registered_b"] = registered_b

    # 未註冊的 skill 根目錄 .py（有 shebang 但 settings 未註冊，不應加 +x）
    unregistered = root / "skills" / "ticket" / "test_migration_dryrun.py"
    unregistered.parent.mkdir(parents=True, exist_ok=True)
    unregistered.write_text("#!/usr/bin/env python3\n# dryrun, 未註冊\n")
    files["unregistered"] = unregistered

    settings = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "$CLAUDE_PROJECT_DIR/.claude/skills/"
                            "continuous-learning/evaluate-session.py",
                        }
                    ]
                }
            ],
            "PreCompact": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "$CLAUDE_PROJECT_DIR/.claude/skills/"
                            "strategic-compact/suggest-compact.py",
                        }
                    ]
                }
            ],
        }
    }
    (root / "settings.json").write_text(json.dumps(settings, indent=2))

    for p in files.values():
        p.chmod(0o644)
    return files


@pytest.mark.parametrize("mod", [pull_mod, push_mod], ids=["pull", "push"])
def test_restore_covers_settings_registered_skill_root(mod, tmp_path):
    files = _make_claude_tree_with_settings(tmp_path)

    mod.restore_executable_bits(tmp_path)

    assert _is_executable(files["registered_a"]), (
        "settings.json 註冊的 skill 根目錄執行檔應被加 +x"
    )
    assert _is_executable(files["registered_b"]), (
        "第二個註冊的 skill 根目錄執行檔應被加 +x"
    )
    assert not _is_executable(files["unregistered"]), (
        "未在 settings.json 註冊的 skill 根目錄 .py 不應加 +x（避免 false positive）"
    )


def test_collect_registered_skill_scripts(tmp_path):
    """直接驗證 settings.json 反查 helper（pull 端）。"""
    _make_claude_tree_with_settings(tmp_path)

    registered = pull_mod.collect_registered_skill_scripts(tmp_path)
    rel = {p.relative_to(tmp_path).as_posix() for p in registered}

    assert "skills/continuous-learning/evaluate-session.py" in rel
    assert "skills/strategic-compact/suggest-compact.py" in rel
    assert "skills/ticket/test_migration_dryrun.py" not in rel
