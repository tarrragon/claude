"""Tests for sync-claude-pull.py pin-aware pull（pinned_version + target ref + --bump）.

涵蓋 acceptance 案例：
  (b) pin 特定版 target 解析正確（pinned tag commit，非 HEAD）
  (c) --bump 更新 pin 並重跑
  (d) 預設 latest（或未設）= 現行 HEAD 行為，向後相容不破

設計：以本地 git repo 模擬上游 clone（含 v1.0.1 tag 與後續 HEAD commit），
驗證 resolve_target_ref 在 pin 特定版 / latest / 未設三種情境的解析。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull", _SCRIPT)
assert _spec and _spec.loader
pull_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull"] = pull_mod
_spec.loader.exec_module(pull_mod)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _make_upstream_with_tag(tmp_path: Path) -> tuple[Path, str, str]:
    """建立上游 clone：v1.0.1 tag 指向一個 commit，HEAD 在其後再多一個 commit。

    回傳 (upstream_dir, tagged_sha, head_sha)。
    """
    up = tmp_path / "upstream"
    up.mkdir()
    _git(["init"], up)
    _git(["config", "user.email", "t@example.com"], up)
    _git(["config", "user.name", "t"], up)
    (up / "VERSION").write_text("1.0.1\n", encoding="utf-8")
    (up / "a.md").write_text("v1.0.1 content\n", encoding="utf-8")
    _git(["add", "-A"], up)
    _git(["commit", "-m", "v1.0.1"], up)
    _git(["tag", "v1.0.1"], up)
    tagged_sha = _git(["rev-parse", "HEAD"], up).stdout.strip()

    (up / "a.md").write_text("newer HEAD content\n", encoding="utf-8")
    _git(["add", "-A"], up)
    _git(["commit", "-m", "post-tag change"], up)
    head_sha = _git(["rev-parse", "HEAD"], up).stdout.strip()
    return up, tagged_sha, head_sha


def _write_state(claude_dir: Path, **fields) -> None:
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / ".sync-state.json").write_text(
        json.dumps(fields, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------- read_pinned_version ----------

def test_read_pinned_version_absent_file(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    assert pull_mod.read_pinned_version(claude) is None


def test_read_pinned_version_no_field(tmp_path: Path):
    claude = tmp_path / ".claude"
    _write_state(claude, last_synced_base_sha="abc")
    assert pull_mod.read_pinned_version(claude) is None


def test_read_pinned_version_specific(tmp_path: Path):
    claude = tmp_path / ".claude"
    _write_state(claude, pinned_version="v1.0.1")
    assert pull_mod.read_pinned_version(claude) == "v1.0.1"


def test_read_pinned_version_latest(tmp_path: Path):
    claude = tmp_path / ".claude"
    _write_state(claude, pinned_version="latest")
    assert pull_mod.read_pinned_version(claude) == "latest"


# ---------- resolve_target_ref (b) + (d) ----------

def test_resolve_target_ref_pinned_specific(tmp_path: Path):
    """(b) pin 特定版 → 解析為 tag commit（非 HEAD）。"""
    up, tagged_sha, head_sha = _make_upstream_with_tag(tmp_path)
    assert tagged_sha != head_sha
    resolved = pull_mod.resolve_target_ref(up, "v1.0.1")
    assert resolved == tagged_sha


def test_resolve_target_ref_pin_without_v_prefix(tmp_path: Path):
    """pin 值無 v 前綴（如 1.0.1）仍能解析到 v1.0.1 tag。"""
    up, tagged_sha, _head = _make_upstream_with_tag(tmp_path)
    resolved = pull_mod.resolve_target_ref(up, "1.0.1")
    assert resolved == tagged_sha


def test_resolve_target_ref_latest_is_head(tmp_path: Path):
    """(d) latest → HEAD，與現行行為一致。"""
    up, _tagged, head_sha = _make_upstream_with_tag(tmp_path)
    assert pull_mod.resolve_target_ref(up, "latest") == head_sha


def test_resolve_target_ref_none_is_head(tmp_path: Path):
    """(d) 未設 pin（None）→ HEAD，向後相容。"""
    up, _tagged, head_sha = _make_upstream_with_tag(tmp_path)
    assert pull_mod.resolve_target_ref(up, None) == head_sha


def test_resolve_target_ref_missing_tag_fails_loud(tmp_path: Path):
    """pin 不存在的版本 → fail-loud（不靜默退回 HEAD）。"""
    up, _tagged, _head = _make_upstream_with_tag(tmp_path)
    import pytest

    with pytest.raises(SystemExit):
        pull_mod.resolve_target_ref(up, "v9.9.9")


# ---------- --bump (c) ----------

def test_bump_updates_pin_latest(tmp_path: Path):
    """(c) --bump 無參數 → pinned_version 設為 latest。"""
    claude = tmp_path / ".claude"
    _write_state(claude, pinned_version="v1.0.1", last_synced_base_sha="abc")
    pull_mod.update_pinned_version(claude, None)
    data = json.loads((claude / ".sync-state.json").read_text(encoding="utf-8"))
    assert data["pinned_version"] == "latest"
    # 保留既有欄位
    assert data["last_synced_base_sha"] == "abc"


def test_bump_updates_pin_specific(tmp_path: Path):
    """(c) --bump v1.2.0 → pinned_version 設為指定版。"""
    claude = tmp_path / ".claude"
    _write_state(claude, pinned_version="v1.0.1")
    pull_mod.update_pinned_version(claude, "v1.2.0")
    data = json.loads((claude / ".sync-state.json").read_text(encoding="utf-8"))
    assert data["pinned_version"] == "v1.2.0"


def test_bump_creates_state_when_absent(tmp_path: Path):
    """無 .sync-state.json 時 --bump 建立檔案並寫入 pin。"""
    claude = tmp_path / ".claude"
    claude.mkdir()
    pull_mod.update_pinned_version(claude, "latest")
    data = json.loads((claude / ".sync-state.json").read_text(encoding="utf-8"))
    assert data["pinned_version"] == "latest"
