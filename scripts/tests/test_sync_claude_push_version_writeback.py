"""Tests for sync-claude-push.py 本地 VERSION 回寫（0.2.1-W3-342）。

背景：W3-050 收尾實測發現 sync-push 成功推送後，本地 .claude/VERSION 未回寫，
fix_version.py 省略 --version 時依 docstring 契約讀取本地 VERSION 視為
「已同步版本」，因此註記過期版本。write_local_version 於 push 成功後將本次
推送版本寫回本地 .claude/VERSION，失敗路徑（push 未成功）不呼叫此函式。

單元層級驗證：直接呼叫 write_local_version，不觸發真實 git push（PC-162 / 規則
6 對應約束：測試不得為驗證而實際推送遠端）。
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


def test_write_local_version_writes_new_version(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "VERSION").write_text("2.24.1\n", encoding="utf-8")

    success, error = sync_mod.write_local_version(claude, "2.24.12")

    assert success is True
    assert error == ""
    assert (claude / "VERSION").read_text(encoding="utf-8") == "2.24.12\n"


def test_write_local_version_creates_file_if_missing(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()

    success, error = sync_mod.write_local_version(claude, "1.0.1")

    assert success is True
    assert error == ""
    assert (claude / "VERSION").read_text(encoding="utf-8") == "1.0.1\n"


def test_write_local_version_matches_fix_version_contract(tmp_path: Path):
    """回歸防護：fix_version.py 省略 --version 時讀本地 VERSION 應等於推送版本。

    不 import fix_version.py（避免耦合其 CLI 依賴），直接複製其
    extract_version_string 讀取邏輯的等價斷言：VERSION 檔首個有效行去除
    v 前綴後應與推送版本一致。
    """
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "VERSION").write_text("2.24.1\n", encoding="utf-8")

    sync_mod.write_local_version(claude, "2.24.12")

    written = (claude / "VERSION").read_text(encoding="utf-8").strip()
    assert written.lstrip("v") == "2.24.12"


def test_write_local_version_returns_false_when_path_not_writable(tmp_path: Path):
    """寫入失敗（VERSION 路徑實為目錄，無法 write_text）時回傳 False 而非拋例外。"""
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "VERSION").mkdir()  # 讓目標路徑成為目錄，write_text 必失敗

    success, error = sync_mod.write_local_version(claude, "1.0.1")

    assert success is False


def test_write_local_version_returns_original_oserror_message(tmp_path: Path):
    """0.2.1-W3-343：失敗時回傳值需含原始 OSError 訊息，供呼叫端組成含細節的警告。"""
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "VERSION").mkdir()  # 讓目標路徑成為目錄，write_text 必觸發 IsADirectoryError

    _success, error = sync_mod.write_local_version(claude, "1.0.1")

    assert error != ""
    assert isinstance(error, str)
