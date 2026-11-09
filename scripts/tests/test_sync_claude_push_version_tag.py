"""Tests for sync-claude-push.py tagged-release（push 每版打 git tag）.

涵蓋 acceptance 案例 (a)：push 對每版打 git tag，remote 可見 tag。

設計：create_and_push_version_tag 對指定 commit 打 annotated tag v<version>
並 push 到 origin。以本地 bare repo 模擬 remote，驗證 tag 在 remote 可見。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _setup_clone_with_remote(tmp_path: Path) -> tuple[Path, Path]:
    """建立 bare remote + 一個 clone，回傳 (clone_dir, bare_remote_dir)。"""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _git(["init", "--bare"], bare)

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(["init"], seed)
    _git(["config", "user.email", "t@example.com"], seed)
    _git(["config", "user.name", "t"], seed)
    (seed / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    _git(["add", "-A"], seed)
    _git(["commit", "-m", "seed"], seed)
    _git(["branch", "-M", "main"], seed)
    _git(["remote", "add", "origin", str(bare)], seed)
    _git(["push", "origin", "main"], seed)

    clone = tmp_path / "clone"
    _git(["clone", str(bare), str(clone)], tmp_path)
    _git(["config", "user.email", "t@example.com"], clone)
    _git(["config", "user.name", "t"], clone)
    return clone, bare


def test_create_and_push_version_tag_visible_on_remote(tmp_path: Path):
    clone, bare = _setup_clone_with_remote(tmp_path)

    # 在 clone 上產生一個新 commit（模擬 push 流程的版本提交）
    (clone / "VERSION").write_text("1.0.1\n", encoding="utf-8")
    _git(["add", "-A"], clone)
    _git(["commit", "-m", "v1.0.1"], clone)
    _git(["push", "origin", "main"], clone)

    sync_mod.create_and_push_version_tag(clone, "1.0.1")

    # tag 在 remote（bare）可見
    result = subprocess.run(
        ["git", "tag", "--list"], cwd=str(bare), capture_output=True, text=True
    )
    assert "v1.0.1" in result.stdout.split()


def test_version_tag_points_to_head_commit(tmp_path: Path):
    clone, bare = _setup_clone_with_remote(tmp_path)
    (clone / "VERSION").write_text("1.0.1\n", encoding="utf-8")
    _git(["add", "-A"], clone)
    _git(["commit", "-m", "v1.0.1"], clone)
    _git(["push", "origin", "main"], clone)

    head = _git(["rev-parse", "HEAD"], clone).stdout.strip()
    sync_mod.create_and_push_version_tag(clone, "1.0.1")

    tag_commit = subprocess.run(
        ["git", "rev-list", "-n", "1", "v1.0.1"],
        cwd=str(bare), capture_output=True, text=True,
    ).stdout.strip()
    assert tag_commit == head


def test_ensure_tag_absent_passes_when_tag_missing(tmp_path: Path):
    clone, _bare = _setup_clone_with_remote(tmp_path)
    sync_mod.ensure_tag_absent_on_remote(clone, "1.0.1")


def test_ensure_tag_absent_rejects_when_remote_has_tag(tmp_path: Path):
    clone, bare = _setup_clone_with_remote(tmp_path)
    _git(["tag", "-a", "v1.0.1", "-m", "x"], bare)
    with pytest.raises(SystemExit) as exc:
        sync_mod.ensure_tag_absent_on_remote(clone, "1.0.1")
    assert exc.value.code != 0


def test_tag_push_failure_exits_nonzero(tmp_path: Path):
    """tag 建立/推送失敗必須 exit 非 0（原只印警告）。"""
    clone, _bare = _setup_clone_with_remote(tmp_path)
    _git(["remote", "set-url", "origin", str(tmp_path / "nonexistent.git")], clone)
    with pytest.raises(SystemExit) as exc:
        sync_mod.create_and_push_version_tag(clone, "1.0.1")
    assert exc.value.code != 0
