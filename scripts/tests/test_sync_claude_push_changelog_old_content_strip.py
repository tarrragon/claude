"""Tests for copy_release_files()（3.0.0-W1-001）。

CHANGELOG 不再由腳本產生條目：遠端 CHANGELOG.md 與 VERSION 逐位元等於本地
.claude/ 對應檔。原 update_changelog 與其剝除測試隨自動產生一併移除。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_changelog_copy", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_changelog_copy"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _local(tmp_path: Path, changelog: str | None) -> Path:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "VERSION").write_text("3.0.0\n", encoding="utf-8")
    if changelog is not None:
        (claude / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return claude


def test_changelog_copied_byte_for_byte_and_not_rewritten(tmp_path: Path) -> None:
    text = "## [3.0.0] - 2026-11-09\n\n手寫條目 W3-1226 保留原樣\n\n---\n\n## [2.90.0]\n"
    claude = _local(tmp_path, text)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CHANGELOG.md").write_text("## [2.90.0] 舊遠端內容\n", encoding="utf-8")

    sync_mod.copy_release_files(repo, claude)

    assert (repo / "CHANGELOG.md").read_text(encoding="utf-8") == text
    assert (repo / "VERSION").read_text(encoding="utf-8") == "3.0.0\n"


def test_missing_local_changelog_exits(tmp_path: Path) -> None:
    claude = _local(tmp_path, None)
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(SystemExit) as exc:
        sync_mod.copy_release_files(repo, claude)
    assert exc.value.code != 0


def test_update_changelog_removed() -> None:
    assert not hasattr(sync_mod, "update_changelog")
