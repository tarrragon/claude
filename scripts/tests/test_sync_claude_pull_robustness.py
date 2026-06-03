"""Tests for sync-claude-pull.py robustness fixes (0.19.1-W1-021).

涵蓋兩項 robustness 修復：
  - H: load_preserve_list 解析失敗時 fail-loud（stderr 警告 + raise），
       不再靜默回空集合關閉全部 preserve（違反 quality-baseline 規則 4）。
  - Q: 備份 .claude 時排除 .venv/__pycache__/.pytest_cache，避免備份 bloat。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# sync-claude-pull.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_robustness", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_robustness"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


# --- H: load_preserve_list fail-loud ---

def test_load_preserve_list_missing_file_returns_empty(tmp_path: Path) -> None:
    """檔案不存在時回傳空集合（合法情境，非失敗）。"""
    assert sync_mod.load_preserve_list(tmp_path) == set()


def test_load_preserve_list_valid_parses(tmp_path: Path) -> None:
    """正常 YAML 正確解析出 preserve 清單。"""
    (tmp_path / "sync-preserve.yaml").write_text(
        "preserve:\n  - settings.local.json\n  - VERSION\n", encoding="utf-8"
    )
    assert sync_mod.load_preserve_list(tmp_path) == {
        "settings.local.json",
        "VERSION",
    }


def test_load_preserve_list_malformed_yaml_fails_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """malformed YAML 必須 fail-loud（raise），不可靜默回空集合（H）。

    靜默回空集合會關閉全部 preserve 保護，導致本地特化檔案被遠端覆蓋。
    """
    # 故意製造 YAML 解析錯誤（未閉合括號 + tab 縮排衝突）
    (tmp_path / "sync-preserve.yaml").write_text(
        "preserve: [unclosed\n\t- bad indent: : :\n", encoding="utf-8"
    )
    with pytest.raises(Exception):
        sync_mod.load_preserve_list(tmp_path)
    # 必須有 stderr 警告（quality-baseline 規則 4 雙通道可觀測性）
    captured = capsys.readouterr()
    assert "preserve" in captured.err.lower()


# --- Q: backup excludes tool artifacts ---

def test_backup_claude_dir_excludes_artifacts(tmp_path: Path) -> None:
    """備份 .claude 時排除 .venv/__pycache__/.pytest_cache（Q）。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "VERSION").write_text("1.0.0", encoding="utf-8")

    # 工具產物目錄
    (claude_dir / ".venv").mkdir()
    (claude_dir / ".venv" / "lib.txt").write_text("x", encoding="utf-8")
    (claude_dir / "hooks").mkdir()
    (claude_dir / "hooks" / "__pycache__").mkdir()
    (claude_dir / "hooks" / "__pycache__" / "a.pyc").write_text("x", encoding="utf-8")
    (claude_dir / "hooks" / "real.py").write_text("y", encoding="utf-8")
    (claude_dir / ".pytest_cache").mkdir()
    (claude_dir / ".pytest_cache" / "v.txt").write_text("x", encoding="utf-8")

    dest = tmp_path / "backup" / ".claude"
    sync_mod.backup_claude_dir(claude_dir, dest)

    assert (dest / "VERSION").exists()
    assert (dest / "hooks" / "real.py").exists()
    assert not (dest / ".venv").exists()
    assert not (dest / "hooks" / "__pycache__").exists()
    assert not (dest / ".pytest_cache").exists()
