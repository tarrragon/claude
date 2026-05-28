"""Tests for sync-claude-push.py no-change early-exit (W3-075).

涵蓋 check_no_change_early_exit 的五種狀態：
  - 首次推送（.sync-state.json 不存在）
  - state 檔損壞（JSON 解析失敗）
  - state 檔缺欄位
  - hash 相同且無新 commit（應 abort）
  - hash 相同但有新 commit（不 abort）
  - hash 不同（不 abort）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# sync-claude-push.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_ee", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_ee"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


@pytest.fixture
def claude_dir(tmp_path: Path) -> Path:
    """建立含一個檔案的 fake .claude/ 目錄。"""
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "dummy.txt").write_text("content\n", encoding="utf-8")
    return d


def _write_state(claude_dir: Path, hash_value: str, time_value: str = "2026-05-28T11:00:00") -> None:
    state = {
        "last_push_hash": hash_value,
        "last_push_version": "1.0.0",
        "last_push_time": time_value,
    }
    (claude_dir / ".sync-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_first_push_no_state_file(claude_dir: Path, tmp_path: Path) -> None:
    """無 .sync-state.json 時不應 abort。"""
    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "首次推送" in reason


def test_corrupted_state_file(claude_dir: Path, tmp_path: Path) -> None:
    """JSON 解析失敗時不應 abort（fail-safe）。"""
    (claude_dir / ".sync-state.json").write_text("{ not valid json", encoding="utf-8")
    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "解析失敗" in reason


def test_state_missing_fields(claude_dir: Path, tmp_path: Path) -> None:
    """state 缺欄位時不應 abort。"""
    (claude_dir / ".sync-state.json").write_text(
        json.dumps({"last_push_version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "缺欄位" in reason


def test_hash_match_no_new_commit_aborts(
    claude_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash 相同且無新 commit 時應 abort。"""
    current_hash = sync_mod._compute_content_hash(claude_dir)
    _write_state(claude_dir, current_hash)

    # mock collect_claude_commits 回傳空 list（無新 commit）
    monkeypatch.setattr(sync_mod, "collect_claude_commits", lambda root, since: [])

    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is True
    assert "無實質變更" in reason


def test_hash_match_but_has_new_commit_continues(
    claude_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash 相同但有新 commit（罕見：commit 後 revert）時不應 abort。"""
    current_hash = sync_mod._compute_content_hash(claude_dir)
    _write_state(claude_dir, current_hash)

    monkeypatch.setattr(
        sync_mod, "collect_claude_commits", lambda root, since: ["feat: x", "revert: x"]
    )

    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "2 個新 commit" in reason


def test_hash_mismatch_continues(
    claude_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash 不同時不應 abort。"""
    _write_state(claude_dir, "deadbeef00000000")

    monkeypatch.setattr(sync_mod, "collect_claude_commits", lambda root, since: [])

    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "hash 不同" in reason
