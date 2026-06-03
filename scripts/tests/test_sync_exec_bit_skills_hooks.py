"""Tests for exec-bit restoration covering skills/*/hooks/ (W1-020 缺陷 G).

背景：W10-092 將部分 hook 遷移至 skills/<name>/hooks/。原
restore_executable_bits 僅覆蓋頂層 .claude/hooks/（EXECUTABLE_PY_SUBDIRS=("hooks",)），
遷移後的 skills/*/hooks/ 下 .py 在 pull 後可能無 +x，造成 Permission denied。

本測試驗證 pull 與 push 兩端的 restore_executable_bits 皆遞迴覆蓋
.claude 下所有名為 hooks/ 的目錄（含 skills/*/hooks/）。
"""
from __future__ import annotations

import importlib.util
import os
import stat
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


# Windows NTFS 無 exec bit，filesystem chmod 對 mode 無作用，本測試跳過
pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX exec-bit semantics required"
)


def _is_executable(p: Path) -> bool:
    return bool(p.stat().st_mode & 0o111)


def _make_claude_tree(root: Path) -> dict[str, Path]:
    """建立含頂層 hooks/ 與 skills/<name>/hooks/ 的 .claude 樹，.py 均為 644。"""
    files: dict[str, Path] = {}

    top = root / "hooks" / "top_hook.py"
    top.parent.mkdir(parents=True, exist_ok=True)
    top.write_text("# top\n")
    files["top"] = top

    nested = root / "hooks" / "lib" / "nested_hook.py"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("# nested\n")
    files["nested"] = nested

    skill_hook = root / "skills" / "ticket" / "hooks" / "skill_hook.py"
    skill_hook.parent.mkdir(parents=True, exist_ok=True)
    skill_hook.write_text("# skill\n")
    files["skill"] = skill_hook

    skill_nested = root / "skills" / "doc-flow" / "hooks" / "sub" / "deep_hook.py"
    skill_nested.parent.mkdir(parents=True, exist_ok=True)
    skill_nested.write_text("# deep\n")
    files["skill_nested"] = skill_nested

    # 非 hooks/ 目錄下的 .py 不應被加 +x
    other = root / "skills" / "ticket" / "scripts" / "helper.py"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("# helper\n")
    files["other"] = other

    for p in files.values():
        p.chmod(0o644)
    return files


@pytest.mark.parametrize("mod", [pull_mod, push_mod], ids=["pull", "push"])
def test_restore_executable_bits_covers_skills_hooks(mod, tmp_path):
    files = _make_claude_tree(tmp_path)

    count = mod.restore_executable_bits(tmp_path)

    assert _is_executable(files["top"]), "頂層 hooks/ 仍應被覆蓋"
    assert _is_executable(files["nested"]), "頂層 hooks/ 子目錄應被覆蓋"
    assert _is_executable(files["skill"]), "skills/*/hooks/ 應被覆蓋（缺陷 G 修復）"
    assert _is_executable(files["skill_nested"]), "skills/*/hooks/ 深層子目錄應被覆蓋"
    assert not _is_executable(files["other"]), "非 hooks/ 目錄下 .py 不應加 +x"
    assert count == 4, f"應還原 4 個檔案，實際 {count}"


@pytest.mark.parametrize("mod", [pull_mod, push_mod], ids=["pull", "push"])
def test_restore_executable_bits_idempotent(mod, tmp_path):
    _make_claude_tree(tmp_path)
    first = mod.restore_executable_bits(tmp_path)
    second = mod.restore_executable_bits(tmp_path)
    assert first == 4
    assert second == 0, "已是 +x 的檔案不應重複計數"
