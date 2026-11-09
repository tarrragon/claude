"""sync-push --clean：遠端已追蹤的 LOCAL_ONLY 名稱、推送方不追蹤時應被刪除."""
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

LOCAL_ONLY = "settings.local.json"


def _write(root: Path, rel: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x")


def test_clean_deletes_tracked_local_only_not_in_pusher(tmp_path):
    remote, staging = tmp_path / "r", tmp_path / "s"
    staging.mkdir()
    _write(remote, LOCAL_ONLY)
    _write(remote, "analyses/a.md")
    sync_mod.clean_stale_files(remote, staging)
    assert not (remote / LOCAL_ONLY).exists()
    assert not (remote / "analyses/a.md").exists()


def test_without_clean_remote_keeps_file(tmp_path):
    """不帶 --clean 只跑 copy 階段：遠端副本仍在（與帶 --clean 結果不同）。"""
    remote, staging = tmp_path / "r", tmp_path / "s"
    staging.mkdir()
    _write(remote, LOCAL_ONLY)
    _write(staging, "agents/a.md")
    sync_mod.copy_filtered_from_staging(staging, remote, set(), None)
    assert (remote / LOCAL_ONLY).exists()
    assert (remote / "agents/a.md").exists()


def test_preserve_and_lineage_still_kept(tmp_path):
    remote, staging = tmp_path / "r", tmp_path / "s"
    staging.mkdir()
    _write(remote, LOCAL_ONLY)
    _write(remote, "analyses/b.md")
    sync_mod.clean_stale_files(
        remote, staging, preserve={LOCAL_ONLY}, lineage_claimed={"analyses/b.md"}
    )
    assert (remote / LOCAL_ONLY).exists()
    assert (remote / "analyses/b.md").exists()


def test_pusher_tracked_local_only_not_copied(tmp_path):
    remote, staging = tmp_path / "r", tmp_path / "s"
    remote.mkdir()
    _write(staging, LOCAL_ONLY)
    sync_mod.copy_filtered_from_staging(staging, remote, set(), None)
    assert not (remote / LOCAL_ONLY).exists()
