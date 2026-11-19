"""Tests for .claude/lib/sync_base_store.py 與 pull／push／status 的接線（3.4.0-W1-300.2）。

涵蓋：
  - base、pin 寫入入版控的 sync-base.json；last_push_* 等本機欄位留在 .sync-state.json
  - 只有舊位置有值時讀得到；寫入時兩欄位一起遷移並自舊檔移除
  - 讀取不寫檔（唯讀命令與中止的 pull 不留副作用）
  - sync-base.json 屬類型 E：不同步、不要求 gitignore
  - pull／push／status 的讀寫點改走新檔
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent.parent.parent / "lib"
sys.path.insert(0, str(_LIB))
import sync_base_store as store  # noqa: E402
import sync_exclude_manifest as manifest  # noqa: E402

_SCRIPTS = Path(__file__).resolve().parent.parent


def _load_script(name: str, mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, _SCRIPTS / name)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


pull = _load_script("sync-claude-pull.py", "sync_claude_pull_base_store")
push = _load_script("sync-claude-push.py", "sync_claude_push_base_store")
status = _load_script("sync-claude-status.py", "sync_claude_status_base_store")


def _claude(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    claude.mkdir()
    return claude


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


# ---------- store 本身 ----------


def test_write_goes_to_tracked_file_and_keeps_local_fields(tmp_path: Path):
    claude = _claude(tmp_path)
    _write(claude / ".sync-state.json", {"last_push_hash": "h1", "last_push_time": "t"})

    store.write_sync_base_field(claude, store.BASE_SHA_FIELD, "a" * 40)
    store.write_sync_base_field(claude, store.PINNED_VERSION_FIELD, "v1.2.0")

    assert _json(claude / "sync-base.json") == {
        "last_synced_base_sha": "a" * 40,
        "pinned_version": "v1.2.0",
    }
    assert _json(claude / ".sync-state.json") == {"last_push_hash": "h1", "last_push_time": "t"}


def test_read_falls_back_to_legacy_without_writing(tmp_path: Path):
    claude = _claude(tmp_path)
    legacy = claude / ".sync-state.json"
    _write(legacy, {"last_synced_base_sha": "old", "pinned_version": "v1.0.0"})
    before = legacy.read_bytes()

    assert store.read_sync_base_field(claude, store.BASE_SHA_FIELD) == "old"
    assert store.read_sync_base_field(claude, store.PINNED_VERSION_FIELD) == "v1.0.0"
    assert not (claude / "sync-base.json").exists()
    assert legacy.read_bytes() == before


def test_new_file_wins_over_legacy(tmp_path: Path):
    claude = _claude(tmp_path)
    _write(claude / ".sync-state.json", {"last_synced_base_sha": "old"})
    _write(claude / "sync-base.json", {"last_synced_base_sha": "new"})
    assert store.read_sync_base_field(claude, store.BASE_SHA_FIELD) == "new"


def test_write_one_field_migrates_both_and_strips_legacy(tmp_path: Path, capsys):
    claude = _claude(tmp_path)
    _write(
        claude / ".sync-state.json",
        {"last_synced_base_sha": "old", "pinned_version": "v1.0.0", "last_push_hash": "h"},
    )

    store.write_sync_base_field(claude, store.BASE_SHA_FIELD, "new")

    # pin 隨 base 一起搬，新 clone 才讀得到 pin
    assert _json(claude / "sync-base.json") == {
        "last_synced_base_sha": "new",
        "pinned_version": "v1.0.0",
    }
    assert _json(claude / ".sync-state.json") == {"last_push_hash": "h"}
    err = capsys.readouterr().err
    assert "pinned_version" in err and "sync-base.json" in err


def test_migrate_keeps_new_value_and_drops_stale_legacy(tmp_path: Path):
    claude = _claude(tmp_path)
    _write(claude / ".sync-state.json", {"last_synced_base_sha": "stale"})
    _write(claude / "sync-base.json", {"last_synced_base_sha": "current"})

    assert store.migrate_legacy_fields(claude) == []
    assert _json(claude / "sync-base.json") == {"last_synced_base_sha": "current"}
    assert _json(claude / ".sync-state.json") == {}


def test_migrate_noop_when_legacy_has_no_tracked_fields(tmp_path: Path):
    claude = _claude(tmp_path)
    legacy = claude / ".sync-state.json"
    _write(legacy, {"last_push_hash": "h"})
    before = legacy.read_bytes()

    assert store.migrate_legacy_fields(claude) == []
    assert not (claude / "sync-base.json").exists()
    assert legacy.read_bytes() == before


def test_sync_base_file_is_type_e(tmp_path: Path):
    assert "sync-base.json" in manifest.PER_PROJECT_PATTERNS
    assert manifest.should_exclude(Path("sync-base.json"))
    assert "sync-base.json" not in manifest.GITIGNORE_EXPECTED


# ---------- pull／push／status 接線 ----------


def test_pull_reads_and_writes_new_file(tmp_path: Path):
    claude = _claude(tmp_path)
    _write(claude / ".sync-state.json", {"last_synced_base_sha": "old", "pending_base_sha": "p"})
    assert pull.read_base_sha(claude) == "old"

    pull.write_base_sha(claude, "new")
    pull.update_pinned_version(claude, "v2.0.0")

    assert _json(claude / "sync-base.json") == {
        "last_synced_base_sha": "new",
        "pinned_version": "v2.0.0",
    }
    # 衝突輪的 pending base 屬本機狀態，留在舊檔
    assert _json(claude / ".sync-state.json") == {"pending_base_sha": "p"}
    assert pull.read_pinned_version(claude) == "v2.0.0"


def test_pull_resolve_done_promotes_into_new_file(tmp_path: Path, monkeypatch):
    claude = _claude(tmp_path)
    _write(claude / ".sync-state.json", {"last_synced_base_sha": "old"})
    pull.write_pending_base_sha(claude, "pend", [])
    monkeypatch.setattr(pull, "scan_conflict_marker_residue", lambda _d: [])

    assert pull.resolve_done(claude) == 0
    assert _json(claude / "sync-base.json") == {"last_synced_base_sha": "pend"}
    assert _json(claude / ".sync-state.json") == {}


def test_push_reads_and_writes_new_file(tmp_path: Path):
    claude = _claude(tmp_path)
    _write(claude / ".sync-state.json", {"last_synced_base_sha": "old", "last_push_hash": "h"})
    assert push.read_base_sha(claude) == "old"

    push.write_base_sha(claude, "new")

    assert _json(claude / "sync-base.json") == {"last_synced_base_sha": "new"}
    assert _json(claude / ".sync-state.json") == {"last_push_hash": "h"}


def test_status_displays_base_from_new_file_then_legacy(tmp_path: Path):
    claude = _claude(tmp_path)
    assert status.read_base_sha_display(claude) == status.NO_RECORD
    _write(claude / ".sync-state.json", {"last_synced_base_sha": "old"})
    assert status.read_base_sha_display(claude) == "old"
    _write(claude / "sync-base.json", {"last_synced_base_sha": "new"})
    assert status.read_base_sha_display(claude) == "new"
    # status 唯讀，不遷移
    assert _json(claude / ".sync-state.json") == {"last_synced_base_sha": "old"}
