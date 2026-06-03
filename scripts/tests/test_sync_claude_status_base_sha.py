"""Tests for sync-claude-status.py base SHA schema 讀取與顯示。

涵蓋 0.19.1-W1-025 acceptance：
  - load_sync_state 正確讀取含 last_synced_base_sha 的 schema
  - load_sync_state 對缺欄位 / 不存在檔案的容錯（回傳空字典）
  - 單一 base SHA 欄位（非雙欄位；schema 不對 SHA 做 max）

多視角 H1：禁雙欄位 max(SHA)。commit SHA 為字典序字串，max() 會選錯共同祖先，
故 schema 僅保留單一 last_synced_base_sha，push/pull 成功皆覆寫同一欄位。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# sync-claude-status.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-status.py"
_spec = importlib.util.spec_from_file_location("sync_claude_status", _SCRIPT)
assert _spec and _spec.loader
status_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_status"] = status_mod
_spec.loader.exec_module(status_mod)  # type: ignore[union-attr]


def _write_state(claude_dir: Path, payload: dict) -> None:
    (claude_dir / status_mod.SYNC_STATE_FILENAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ---------- load_sync_state schema 讀取 ----------

def test_load_sync_state_reads_base_sha(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    _write_state(
        claude_dir,
        {
            "last_push_hash": "abc123",
            "last_synced_base_sha": "deadbeefcafe1234567890",
        },
    )
    state = status_mod.load_sync_state(claude_dir)
    assert state["last_synced_base_sha"] == "deadbeefcafe1234567890"
    assert state["last_push_hash"] == "abc123"


def test_load_sync_state_missing_base_sha_field(tmp_path):
    """schema 缺 base SHA 欄位時不應拋例外，state.get 回退由呼叫端處理。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    _write_state(claude_dir, {"last_push_hash": "abc123"})
    state = status_mod.load_sync_state(claude_dir)
    assert "last_synced_base_sha" not in state
    assert state.get("last_synced_base_sha", "（無記錄）") == "（無記錄）"


def test_load_sync_state_missing_file(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    assert status_mod.load_sync_state(claude_dir) == {}


# ---------- 單一 base SHA 顯示輔助 ----------

def test_resolve_base_sha_display_present(tmp_path):
    state = {"last_synced_base_sha": "ff00aa11"}
    assert status_mod.resolve_base_sha_display(state) == "ff00aa11"


def test_resolve_base_sha_display_absent():
    assert status_mod.resolve_base_sha_display({}) == "（無記錄）"


def test_schema_has_single_base_sha_field_not_dual():
    """H1 防護：schema 不得使用 push/pull 雙欄位（會誘發對 SHA 做 max）。"""
    # resolve_base_sha_display 只認單一鍵；雙欄位 schema 不被支援
    dual = {
        "last_synced_base_sha_push": "aaa",
        "last_synced_base_sha_pull": "bbb",
    }
    # 雙欄位下單一鍵不存在 → 回退無記錄，證明系統不依賴雙欄位
    assert status_mod.resolve_base_sha_display(dual) == "（無記錄）"
