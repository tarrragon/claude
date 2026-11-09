"""Tests for sync-claude-push.py 發版版號來源（3.0.0-W1-001）。

推送版號取自本地 .claude/VERSION，不經遞增；本地版號須高於遠端；
推送後不回寫本地 VERSION（write_local_version 已移除）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def test_read_local_release_version_returns_file_value(tmp_path: Path):
    (tmp_path / "VERSION").write_text("3.0.0\n", encoding="utf-8")
    assert sync_mod.read_local_release_version(tmp_path) == "3.0.0"


def test_read_local_release_version_missing_file_exits(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        sync_mod.read_local_release_version(tmp_path)
    assert exc.value.code != 0


def test_check_release_version_accepts_higher_local():
    sync_mod.check_release_version("3.0.0", "2.90.0")
    sync_mod.check_release_version("2.90.1", "2.90.0")


def test_check_release_version_accepts_missing_remote():
    sync_mod.check_release_version("3.0.0", None)


@pytest.mark.parametrize("local", ["2.90.0", "2.89.9", "1.99.99"])
def test_check_release_version_rejects_not_higher(local: str, capsys):
    with pytest.raises(SystemExit) as exc:
        sync_mod.check_release_version(local, "2.90.0")
    assert exc.value.code != 0
    out = capsys.readouterr()
    text = out.out + out.err
    assert ".claude/VERSION" in text and ".claude/CHANGELOG.md" in text


def test_check_release_version_compares_numerically():
    # 字串比較會誤判 2.9.0 > 2.10.0
    with pytest.raises(SystemExit):
        sync_mod.check_release_version("2.9.0", "2.10.0")


def test_check_release_version_rejects_unparseable():
    with pytest.raises(SystemExit) as exc:
        sync_mod.check_release_version("abc", "2.90.0")
    assert exc.value.code != 0


def test_write_local_version_and_bump_removed():
    assert not hasattr(sync_mod, "write_local_version")
    assert not hasattr(sync_mod, "bump_version")
