"""Tests for sync-claude-push.py detect_uncleaned_deletions（缺口 3，W8-037.2）.

情境：本地 git rm 了 tracked .claude/ 檔，但本次 push 未帶 --clean。此時
clean_stale_files 不會執行，遠端（clone）殘留該檔成孤兒。detect_uncleaned_deletions
偵測「遠端 clone 有、本地 tracked 樹（staging）無」的檔，供 main 結尾輸出 soft
警告（R2：不阻擋、不改 --clean 預設）。

判定須與 clean_stale_files 對齊：
  - 遠端獨有檔（CHANGELOG/VERSION/README/LICENSE/.gitignore/.git）不算孤兒
  - should_exclude 命中者（local-only / 憑證，可能屬他專案）不算孤兒
  - 遠端與本地都有的檔不算孤兒
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _make_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """建立模擬遠端 clone（temp_dir）與本地 tracked 樹（staging）。"""
    temp_dir = tmp_path / "remote_clone"
    staging = tmp_path / "staging"
    temp_dir.mkdir()
    staging.mkdir()
    return temp_dir, staging


def _write(base: Path, rel: str, content: str = "x\n") -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ---------- 核心：本地已刪、遠端殘留 → 偵測為孤兒 ----------

def test_detects_locally_deleted_file_present_on_remote(tmp_path: Path):
    temp_dir, staging = _make_dirs(tmp_path)
    # 遠端與本地都有 keep.md
    _write(temp_dir, "rules/keep.md")
    _write(staging, "rules/keep.md")
    # 遠端有但本地已 git rm（不在 staging）→ 孤兒
    _write(temp_dir, "hooks/obsolete.py")

    orphans = sync_mod.detect_uncleaned_deletions(temp_dir, staging)

    assert orphans == ["hooks/obsolete.py"]


def test_no_orphans_when_trees_aligned(tmp_path: Path):
    temp_dir, staging = _make_dirs(tmp_path)
    _write(temp_dir, "a.md")
    _write(staging, "a.md")
    _write(temp_dir, "sub/b.py")
    _write(staging, "sub/b.py")

    assert sync_mod.detect_uncleaned_deletions(temp_dir, staging) == []


# ---------- 對齊 clean_stale_files：遠端獨有檔不算孤兒 ----------

def test_remote_only_metadata_files_not_reported(tmp_path: Path):
    temp_dir, staging = _make_dirs(tmp_path)
    # 這些遠端獨有檔本就不該被刪，不算孤兒
    for name in ("CHANGELOG.md", "VERSION", "README.md", "LICENSE", ".gitignore"):
        _write(temp_dir, name)
    _write(temp_dir, "keep.md")
    _write(staging, "keep.md")

    assert sync_mod.detect_uncleaned_deletions(temp_dir, staging) == []


def test_git_dir_files_not_reported(tmp_path: Path):
    temp_dir, staging = _make_dirs(tmp_path)
    _write(temp_dir, ".git/config")
    _write(temp_dir, ".git/HEAD")
    _write(temp_dir, "keep.md")
    _write(staging, "keep.md")

    assert sync_mod.detect_uncleaned_deletions(temp_dir, staging) == []


# ---------- 對齊 clean_stale_files：should_exclude 命中者不算孤兒 ----------

def test_should_exclude_files_not_reported(tmp_path: Path):
    temp_dir, staging = _make_dirs(tmp_path)
    # settings.local.json 為 local-only（should_exclude 命中），可能屬他專案，不算孤兒
    assert sync_mod.should_exclude(Path("settings.local.json")) is True
    _write(temp_dir, "settings.local.json", "{}\n")
    _write(temp_dir, "keep.md")
    _write(staging, "keep.md")

    assert sync_mod.detect_uncleaned_deletions(temp_dir, staging) == []


# ---------- 多孤兒：排序輸出 ----------

def test_multiple_orphans_sorted(tmp_path: Path):
    temp_dir, staging = _make_dirs(tmp_path)
    _write(temp_dir, "z/last.md")
    _write(temp_dir, "a/first.md")
    _write(temp_dir, "m/mid.md")
    # staging 全空（皆為孤兒）

    orphans = sync_mod.detect_uncleaned_deletions(temp_dir, staging)

    assert orphans == ["a/first.md", "m/mid.md", "z/last.md"]
