"""Tests for sync-claude-pull.py --bump 寫入時點（3.4.0-W1-304）。

--bump 的 pin 只在環境檢查與 tag 解析都成功後才寫入；任一步失敗時
.sync-state.json 的內容與存在與否都不變。對照組（tag 存在）確認 pin 確實寫入。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_bump_order", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_bump_order"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

STATE_BYTES = b'{"last_synced_base_sha": "abc"}\n'


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init"], path)
    _git(["config", "user.email", "t@example.com"], path)
    _git(["config", "user.name", "t"], path)


def _make_upstream(tmp_path: Path) -> Path:
    up = tmp_path / "upstream"
    _init_repo(up)
    (up / "VERSION").write_text("1.0.1\n", encoding="utf-8")
    _git(["add", "-A"], up)
    _git(["commit", "-m", "v1.0.1"], up)
    _git(["tag", "v1.0.1"], up)
    return up


def _make_project(tmp_path: Path, with_state: bool) -> Path:
    root = tmp_path / "project"
    _init_repo(root)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "keep.md").write_text("x\n", encoding="utf-8")
    _git(["add", "-A"], root)
    _git(["commit", "-m", "init"], root)
    if with_state:
        (claude / ".sync-state.json").write_bytes(STATE_BYTES)
    return root


def _run_sync(root: Path, up: Path, bump) -> None:
    pull._sync_with_backup(root, up, False, bump)


def test_bump_missing_tag_keeps_existing_state_bytes(tmp_path: Path):
    up = _make_upstream(tmp_path)
    root = _make_project(tmp_path, with_state=True)
    with pytest.raises(SystemExit) as exc:
        _run_sync(root, up, "v9.9.9")
    assert exc.value.code != 0
    assert (root / ".claude" / ".sync-state.json").read_bytes() == STATE_BYTES


def test_bump_missing_tag_does_not_create_state_file(tmp_path: Path):
    up = _make_upstream(tmp_path)
    root = _make_project(tmp_path, with_state=False)
    with pytest.raises(SystemExit) as exc:
        _run_sync(root, up, "v9.9.9")
    assert exc.value.code != 0
    assert not (root / ".claude" / ".sync-state.json").exists()
    assert not (root / ".claude" / "sync-base.json").exists()


def test_bump_dirty_worktree_keeps_state_unchanged(tmp_path: Path, monkeypatch):
    root = _make_project(tmp_path, with_state=True)
    (root / ".claude" / "keep.md").write_text("dirty\n", encoding="utf-8")
    called = {"clone": False}

    def _no_clone(*_a, **_k):
        called["clone"] = True
        raise AssertionError("環境檢查失敗後不應進入 clone")

    monkeypatch.setattr(pull, "find_project_root", lambda: root)
    monkeypatch.setattr(pull, "_clone_and_backup", _no_clone)
    monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py", "--bump", "v1.0.1"])
    with pytest.raises(SystemExit) as exc:
        pull.main()
    assert exc.value.code != 0
    assert called["clone"] is False
    assert (root / ".claude" / ".sync-state.json").read_bytes() == STATE_BYTES


def test_bump_existing_tag_writes_pin_and_message_after_write(
    tmp_path: Path, monkeypatch, capsys
):
    """對照組（E1）：tag 存在時 pin 確實寫入，訊息在寫入之後。"""
    up = _make_upstream(tmp_path)
    root = _make_project(tmp_path, with_state=False)
    order: list[str] = []
    real_update = pull.update_pinned_version

    def _spy(claude_dir, version):
        order.append("write")
        real_update(claude_dir, version)

    monkeypatch.setattr(pull, "update_pinned_version", _spy)
    real_print = pull.print_color

    def _print(msg, *a, **k):
        if "已更新 pinned_version" in msg:
            order.append("message")
        real_print(msg, *a, **k)

    monkeypatch.setattr(pull, "print_color", _print)
    # 只驗 pin 寫入時點，後續同步流程在 tag 解析後以 sentinel 例外中止
    _stop_after_pin_message(monkeypatch)
    with pytest.raises(_Stop):
        _run_sync(root, up, "v1.0.1")
    assert pull.read_pinned_version(root / ".claude") == "v1.0.1"
    assert order == ["write", "message"]


def test_bump_none_writes_latest(tmp_path: Path, monkeypatch):
    up = _make_upstream(tmp_path)
    root = _make_project(tmp_path, with_state=False)
    _stop_after_pin_message(monkeypatch)
    with pytest.raises(_Stop):
        _run_sync(root, up, None)
    assert pull.read_pinned_version(root / ".claude") == pull.PIN_LATEST


def test_no_bump_does_not_write_pin(tmp_path: Path, monkeypatch):
    up = _make_upstream(tmp_path)
    root = _make_project(tmp_path, with_state=False)
    def _stop(*_a, **_k):
        raise _Stop()

    monkeypatch.setattr(pull, "_decide_script_upgrade", _stop)
    with pytest.raises(_Stop):
        _run_sync(root, up, pull._BUMP_NOT_SET)
    assert not (root / ".claude" / ".sync-state.json").exists()


class _Stop(Exception):
    """pin 寫入時點之後中止後續同步流程。"""


def _stop_after_pin_message(monkeypatch) -> None:
    """pin 寫入並輸出訊息之後即中止，避免跑完整同步。"""
    real_print = pull.print_color

    def _print(msg, *a, **k):
        real_print(msg, *a, **k)
        if "已更新 pinned_version" in msg:
            raise _Stop()

    monkeypatch.setattr(pull, "print_color", _print)


# ---------- 3.5.1-W1-002：自我升級判定先於 pin 寫入（#144）----------

def _make_upgrade_upstream(tmp_path: Path) -> Path:
    """上游含較新版本（2.0.0）與內容不同的腳本，必觸發自我升級交棒。"""
    up = tmp_path / "upstream"
    (up / "scripts").mkdir(parents=True)
    _init_repo(up)
    (up / "VERSION").write_text("2.0.0\n", encoding="utf-8")
    (up / pull.UPSTREAM_SCRIPT_REL).write_text("# newer upstream\n", encoding="utf-8")
    _git(["add", "-A"], up)
    _git(["commit", "-m", "v2.0.0"], up)
    _git(["tag", "v2.0.0"], up)
    return up


def _make_tracked_project(tmp_path: Path) -> Path:
    """pin 所在的 sync-base.json 已被追蹤（與下游實況一致），VERSION 較舊。"""
    root = tmp_path / "project"
    _init_repo(root)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (claude / "sync-base.json").write_bytes(STATE_BYTES)
    _git(["add", "-A"], root)
    _git(["commit", "-m", "init"], root)
    return root


def test_bump_with_upstream_script_upgrade_hands_off_without_writing_pin(tmp_path: Path):
    """修正後：交棒時 pin 尚未寫入，交棒後的上游腳本看到乾淨的 .claude。"""
    up = _make_upgrade_upstream(tmp_path)
    root = _make_tracked_project(tmp_path)
    with pytest.raises(pull.ScriptUpgradeRerun):
        _run_sync(root, up, "v2.0.0")
    assert (root / ".claude" / "sync-base.json").read_bytes() == STATE_BYTES
    pull.check_uncommitted_changes(root)  # 不得 SystemExit


def test_pin_written_before_handoff_aborts_upstream_check(tmp_path: Path):
    """對照（E1）：修正前的順序（先寫 pin 再交棒）會讓上游腳本的檢查中止。"""
    root = _make_tracked_project(tmp_path)
    pull.update_pinned_version(root / ".claude", "v2.0.0")
    with pytest.raises(SystemExit) as exc:
        pull.check_uncommitted_changes(root)
    assert exc.value.code != 0
