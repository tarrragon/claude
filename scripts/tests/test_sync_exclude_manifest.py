"""Tests for sync_exclude_manifest SSOT module + push/status hash 一致性回歸。

涵蓋：
  - 原始分類 frozenset 對外暴露且為 frozenset
  - 組合集合 PUSH_EXCLUDE = LOCAL_ONLY | CREDENTIAL
  - should_exclude 對相對路徑契約（assert not is_absolute）
  - should_exclude 對各分類維度（名稱 / 副檔名 / 前綴 / 目錄段）
  - 缺陷 N 回歸：push.compute_content_hash 與 status.compute_content_hash
    對同一 .claude fixture 產生相同指紋
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# manifest 位於 .claude/hooks/lib/
_LIB = Path(__file__).resolve().parent.parent.parent / "hooks" / "lib"
sys.path.insert(0, str(_LIB))
import sync_exclude_manifest as manifest  # noqa: E402

_SCRIPTS = Path(__file__).resolve().parent.parent


def _load_script(name: str, mod_name: str):
    """以 importlib 載入含連字符的 uv-script 腳本。"""
    spec = importlib.util.spec_from_file_location(mod_name, _SCRIPTS / name)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


push_mod = _load_script("sync-claude-push.py", "sync_claude_push")
status_mod = _load_script("sync-claude-status.py", "sync_claude_status")


# ---------- manifest 結構 ----------

def test_raw_classifications_are_frozensets():
    assert isinstance(manifest.LOCAL_ONLY_PATTERNS, frozenset)
    assert isinstance(manifest.CREDENTIAL_PATTERNS, frozenset)
    assert isinstance(manifest.EXCLUDE_SUFFIXES, frozenset)
    assert isinstance(manifest.EXCLUDE_NAME_PREFIXES, frozenset)


def test_push_exclude_is_union():
    assert manifest.PUSH_EXCLUDE == (
        manifest.LOCAL_ONLY_PATTERNS | manifest.CREDENTIAL_PATTERNS
    )


def test_credential_dimensions_present():
    # H2：憑證 .pem/.key/secret 前綴漏搬為最高風險，驗證仍存在
    assert ".pem" in manifest.EXCLUDE_SUFFIXES
    assert ".key" in manifest.EXCLUDE_SUFFIXES
    assert "secret" in manifest.EXCLUDE_NAME_PREFIXES
    assert ".secrets" in manifest.CREDENTIAL_PATTERNS


# ---------- should_exclude 契約與分類 ----------

def test_should_exclude_rejects_absolute_path():
    with pytest.raises(AssertionError):
        manifest.should_exclude(Path("/abs/path/file.json"))


def test_should_exclude_by_name():
    assert manifest.should_exclude(Path("dispatch-active.json"))
    assert manifest.should_exclude(Path(".sync-state.json"))


def test_should_exclude_by_suffix():
    assert manifest.should_exclude(Path("server.pem"))
    assert manifest.should_exclude(Path("cache.pyc"))


def test_should_exclude_by_prefix():
    assert manifest.should_exclude(Path(".env.staging"))
    assert manifest.should_exclude(Path("secret_key.txt"))


def test_should_exclude_by_dir_segment():
    assert manifest.should_exclude(Path("hook-state/x.json"))
    assert manifest.should_exclude(Path("secrets/api.txt"))


def test_should_not_exclude_normal_file():
    assert not manifest.should_exclude(Path("rules/core/quality-baseline.md"))


# ---------- 缺陷 N 回歸：push / status hash 一致 ----------

def _build_fixture(claude_dir: Path) -> None:
    """建立含「正常檔 + 各類排除檔」的臨時 .claude fixture。"""
    (claude_dir / "rules" / "core").mkdir(parents=True)
    (claude_dir / "rules" / "core" / "a.md").write_text("alpha", encoding="utf-8")
    (claude_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    # 各類應排除檔（status 舊版漏列這些 → 缺陷 N）
    (claude_dir / "dispatch-active.json").write_text("{}", encoding="utf-8")
    (claude_dir / "settings.local.json").write_text("{}", encoding="utf-8")
    (claude_dir / ".zhtw-mcp-skip").write_text("", encoding="utf-8")
    (claude_dir / "hook-state").mkdir()
    (claude_dir / "hook-state" / "s.json").write_text("{}", encoding="utf-8")
    (claude_dir / ".sync-state.json").write_text("{}", encoding="utf-8")
    (claude_dir / "server.pem").write_text("KEY", encoding="utf-8")


def test_push_and_status_hash_equal(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    _build_fixture(claude_dir)

    push_hash = push_mod._compute_content_hash(claude_dir)
    status_hash = status_mod.compute_content_hash(claude_dir)
    assert push_hash == status_hash, (
        f"push hash {push_hash} != status hash {status_hash}（缺陷 N：排除清單漂移）"
    )


def test_hash_matches_manifest(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    _build_fixture(claude_dir)
    assert push_mod._compute_content_hash(claude_dir) == manifest.compute_content_hash(
        claude_dir
    )
