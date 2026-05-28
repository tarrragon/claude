"""Tests for sync-claude-pull.py backup_dir cleanup (W3-076).

涵蓋 cleanup_old_backups 四個情境：
  - 超期目錄被刪除
  - 保留期內目錄保留
  - 空 temp / 無匹配前綴
  - 非 claude-backup-* 前綴不影響
  - retention_days 參數影響範圍
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

import pytest

# sync-claude-pull.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_cleanup", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_cleanup"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _make_dir_with_mtime(parent: Path, name: str, age_days: float) -> Path:
    """建立目錄並設定 mtime 為 age_days 天前。"""
    target = parent / name
    target.mkdir()
    (target / "marker.txt").write_text("x", encoding="utf-8")
    past = time.time() - age_days * 86400
    os.utime(target, (past, past))
    return target


def test_cleanup_old_backups_removes_expired(tmp_path: Path) -> None:
    """超過 retention_days 的 claude-backup-* 目錄應被刪除。"""
    old1 = _make_dir_with_mtime(tmp_path, "claude-backup-aaa", age_days=10)
    old2 = _make_dir_with_mtime(tmp_path, "claude-backup-bbb", age_days=30)
    fresh = _make_dir_with_mtime(tmp_path, "claude-backup-ccc", age_days=1)

    removed = sync_mod.cleanup_old_backups(retention_days=7, temp_root=tmp_path)

    assert removed == 2
    assert not old1.exists()
    assert not old2.exists()
    assert fresh.exists()


def test_cleanup_no_match_prefix(tmp_path: Path) -> None:
    """非 claude-backup-* 前綴的目錄不應被刪除（即使含 claude 字串）。"""
    other1 = _make_dir_with_mtime(tmp_path, "other-temp-xxx", age_days=30)
    other2 = _make_dir_with_mtime(tmp_path, "claude-other-yyy", age_days=30)
    other3 = _make_dir_with_mtime(tmp_path, "backup-claude-zzz", age_days=30)

    removed = sync_mod.cleanup_old_backups(retention_days=7, temp_root=tmp_path)

    assert removed == 0
    assert other1.exists()
    assert other2.exists()
    assert other3.exists()


def test_cleanup_empty_temp(tmp_path: Path) -> None:
    """temp 目錄為空時應 return 0 不出錯。"""
    removed = sync_mod.cleanup_old_backups(retention_days=7, temp_root=tmp_path)
    assert removed == 0


def test_cleanup_respects_retention_days_param(tmp_path: Path) -> None:
    """不同 retention_days 應影響刪除範圍。"""
    d3 = _make_dir_with_mtime(tmp_path, "claude-backup-d3", age_days=3)
    d10 = _make_dir_with_mtime(tmp_path, "claude-backup-d10", age_days=10)

    # retention=1：兩個都超期
    removed = sync_mod.cleanup_old_backups(retention_days=1, temp_root=tmp_path)
    assert removed == 2
    assert not d3.exists()
    assert not d10.exists()


def test_cleanup_skips_symlinks(tmp_path: Path) -> None:
    """符號連結即使前綴匹配也不刪。"""
    real = _make_dir_with_mtime(tmp_path, "real-dir", age_days=30)
    link = tmp_path / "claude-backup-link"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("Platform does not support symlinks")

    removed = sync_mod.cleanup_old_backups(retention_days=7, temp_root=tmp_path)
    assert removed == 0
    assert link.exists()


def test_cleanup_nonexistent_temp_root(tmp_path: Path) -> None:
    """temp_root 不存在時 return 0 不 raise。"""
    missing = tmp_path / "nonexistent"
    removed = sync_mod.cleanup_old_backups(retention_days=7, temp_root=missing)
    assert removed == 0
