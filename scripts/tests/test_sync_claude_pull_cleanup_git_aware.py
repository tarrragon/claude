"""Tests for sync-claude-pull.py cleanup git-tracking awareness.

full overlay fallback 下 cleanup_stale_files 不再靜默刪除本地獨有 git 追蹤檔
（本地累積、上游 repo 無），改移至 .sync-conflicts/；並提供 full overlay 前的
will-delete / will-overwrite dry-run 預覽。

背景：full overlay 曾誤刪上游 repo 不存在但本地累積的防護檔（未列 sync-preserve.yaml）。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# sync-claude-pull.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_git_aware", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_git_aware"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _init_git_repo(root: Path) -> None:
    """在 root 初始化 git repo 並設定最小 identity。"""
    subprocess.run(["git", "init"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root, capture_output=True)


def _git_add_commit(root: Path, *rel_paths: str) -> None:
    """git add + commit 指定相對路徑。"""
    subprocess.run(["git", "add", *rel_paths], cwd=root, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, capture_output=True)


def _make_claude(root: Path) -> Path:
    """建立 root/.claude 並回傳。"""
    claude = root / ".claude"
    claude.mkdir()
    return claude


def test_git_tracked_local_only_not_deleted(tmp_path: Path) -> None:
    """本地 git 追蹤但遠端無的檔（本地累積、上游無）不刪，移至 .sync-conflicts，計入 preserved。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    evolved = claude / "error-patterns" / "PC-999-local.md"
    evolved.parent.mkdir(parents=True)
    evolved.write_text("local evolution", encoding="utf-8")
    _git_add_commit(root, ".claude/error-patterns/PC-999-local.md")

    remote_files: set[Path] = set()  # 遠端無此檔
    removed, preserved = sync_mod.cleanup_stale_files(
        claude, remote_files, preserve=set(), project_root=root
    )

    assert not evolved.exists(), "git 追蹤檔不應留在原位（已移走）"
    assert any("PC-999-local.md" in p for p in preserved), "應計入 preserved_as_conflict"
    assert not any("PC-999-local.md" in r for r in removed), "不應計入真刪 removed"
    conflicts = list((claude / sync_mod.SYNC_CONFLICTS_DIR).rglob("*PC-999-local*"))
    assert conflicts, "應移至 .sync-conflicts/ 暫存"


def test_untracked_stale_still_deleted(tmp_path: Path) -> None:
    """本地非 git 追蹤且遠端無的檔（runtime / 真 stale）維持原刪除行為。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    stale = claude / "runtime" / "temp.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("runtime garbage", encoding="utf-8")
    # 不 git add → untracked

    remote_files: set[Path] = set()
    removed, preserved = sync_mod.cleanup_stale_files(
        claude, remote_files, preserve=set(), project_root=root
    )

    assert not stale.exists(), "非追蹤 stale 檔應被刪除（維持原行為）"
    assert any("temp.txt" in r for r in removed), "應計入 removed"
    assert not any("temp.txt" in p for p in preserved), "不應計入 preserved"


def test_preserve_still_honored(tmp_path: Path) -> None:
    """preserve 清單中的檔案不刪也不移（回歸保護不破壞）。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    special = claude / "special.txt"
    special.write_text("keep me", encoding="utf-8")
    _git_add_commit(root, ".claude/special.txt")

    remote_files: set[Path] = set()
    removed, preserved = sync_mod.cleanup_stale_files(
        claude, remote_files, preserve={"special.txt"}, project_root=root
    )

    assert special.exists(), "preserve 清單檔應原地保留"
    assert not any("special.txt" in r for r in removed)
    assert not any("special.txt" in p for p in preserved)


def test_overlay_dryrun_lists_deletions(tmp_path: Path) -> None:
    """full overlay dry-run 預覽列出 will-delete，並標示 git 追蹤者轉 conflict。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    tracked = claude / "tracked.md"
    tracked.write_text("evolution", encoding="utf-8")
    _git_add_commit(root, ".claude/tracked.md")
    untracked = claude / "junk.txt"
    untracked.write_text("junk", encoding="utf-8")

    temp_dir = tmp_path / "fake_upstream"  # 空遠端 → 兩檔皆 will-delete
    temp_dir.mkdir()
    will_overwrite, will_delete, _will_skip = sync_mod.preview_overlay_changes(
        temp_dir, claude, remote_files=set(), preserve=set(), project_root=root
    )

    delete_map = {rel: is_tracked for rel, is_tracked in will_delete}
    assert delete_map.get("tracked.md") is True, "git 追蹤檔應標 is_tracked True（轉 conflict）"
    assert delete_map.get("junk.txt") is False, "非追蹤檔應標 is_tracked False（真刪）"
