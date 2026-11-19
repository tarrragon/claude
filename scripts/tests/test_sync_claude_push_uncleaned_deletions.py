"""Tests for sync-claude-push.py detect_uncleaned_deletions（缺口 3，W8-037.2）.

情境：本地 git rm 了 tracked .claude/ 檔，但本次 push 未帶 --clean。此時
clean_stale_files 不會執行，遠端（clone）殘留該檔成孤兒。detect_uncleaned_deletions
偵測「遠端 clone 有、本地 tracked 樹（staging）無」的檔，供 main 結尾輸出 soft
警告（R2：不阻擋、不改 --clean 預設）。

判定須與 clean_stale_files 一致（警告集合 == --clean 實際刪除集合）：
  - 遠端獨有檔（CHANGELOG/VERSION/README/LICENSE/.gitignore/.git）不算孤兒
  - 遠端已追蹤、推送方 tracked 樹無的 local-only 名稱算孤兒（--clean 會刪）
  - 帶 base_sha 時，base 之後他方新增的檔不算孤兒
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


# ---------- 對齊 clean_stale_files：遠端已追蹤的 local-only 名稱會被 --clean 刪除 ----------

def test_remote_tracked_local_only_file_is_reported(tmp_path: Path):
    """正向對照：local-only 名稱遠端有、推送方 tracked 樹無時，--clean 會刪，警告須列出。"""
    temp_dir, staging = _make_dirs(tmp_path)
    assert sync_mod.should_exclude(Path("settings.local.json")) is True
    _write(temp_dir, "settings.local.json", "{}\n")
    _write(temp_dir, "keep.md")
    _write(staging, "keep.md")

    assert sync_mod.detect_uncleaned_deletions(temp_dir, staging) == ["settings.local.json"]


# ---------- 契約：警告集合 == --clean 實際刪除集合 ----------

def _run_git(args: list[str], cwd: Path) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def _files(root: Path) -> set[str]:
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def test_warning_set_equals_clean_deletion_set(tmp_path: Path):
    """同一份輸入下，警告列出的檔與 clean_stale_files 實際刪除的檔相同。

    遠端含：本地已刪的檔（刪）、遠端已追蹤的 local-only 名稱（刪）、base 之後
    他方新增的檔（保留）、雙方都有的檔（保留）、遠端獨有 metadata（保留）。
    """
    temp_dir, staging = _make_dirs(tmp_path)
    _run_git(["init", "-q"], temp_dir)
    _run_git(["config", "user.email", "t@example.com"], temp_dir)
    _run_git(["config", "user.name", "t"], temp_dir)
    _write(temp_dir, "keep.md")
    _write(temp_dir, "hooks/obsolete.py")
    _write(temp_dir, "settings.local.json", "{}\n")
    _write(temp_dir, "CHANGELOG.md")
    _run_git(["add", "-A"], temp_dir)
    _run_git(["commit", "-q", "-m", "base"], temp_dir)
    base_sha = _run_git(["rev-parse", "HEAD"], temp_dir)
    _write(temp_dir, "rules/other-consumer.md")
    _run_git(["add", "-A"], temp_dir)
    _run_git(["commit", "-q", "-m", "other consumer"], temp_dir)
    _write(staging, "keep.md")

    warned = sync_mod.detect_uncleaned_deletions(temp_dir, staging, base_sha=base_sha)
    before = _files(temp_dir)
    sync_mod.clean_stale_files(temp_dir, staging, base_sha=base_sha)
    deleted = sorted(before - _files(temp_dir))

    assert warned == deleted == ["hooks/obsolete.py", "settings.local.json"]


# ---------- 多孤兒：排序輸出 ----------

def test_multiple_orphans_sorted(tmp_path: Path):
    temp_dir, staging = _make_dirs(tmp_path)
    _write(temp_dir, "z/last.md")
    _write(temp_dir, "a/first.md")
    _write(temp_dir, "m/mid.md")
    # staging 全空（皆為孤兒）

    orphans = sync_mod.detect_uncleaned_deletions(temp_dir, staging)

    assert orphans == ["a/first.md", "m/mid.md", "z/last.md"]
