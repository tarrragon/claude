"""get_next_seq 取號納入 remote-tracking ref（refs/remotes/*/main、master）。

兩個 clone 各自建票時，取號只看本地 main，fetch 後仍會配到 origin 上已有的
票號，合併時以 add/add 衝突顯現。fetch 之後，origin/main 上的票號應計入。
fetch 之前的撞號無法從本機得知，處置寫在 .claude/README.md。

測試採真實 tmp git repo（origin + clone），不 mock git。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ticket_system.lib import paths as paths_mod
from ticket_system.lib import ticket_builder
from ticket_system.lib.ticket_builder import (
    get_next_seq,
    list_ticket_files_from_remote_tracking,
)

VERSION = "0.19.0"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _tickets_dir(root: Path) -> Path:
    return root / "docs" / "work-logs" / "v0" / "v0.19" / f"v{VERSION}" / "tickets"


def _commit_tickets(root: Path, ticket_ids: list[str]) -> None:
    tickets_dir = _tickets_dir(root)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    for tid in ticket_ids:
        (tickets_dir / f"{tid}.md").write_text(f"---\nid: {tid}\n---\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"add {ticket_ids}")


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "checkout", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "init")


def _point_state_root(monkeypatch, root: Path) -> None:
    for module in (paths_mod, ticket_builder):
        for name in ("get_project_root", "get_ticket_state_root"):
            monkeypatch.setattr(module, name, lambda: root, raising=False)


@pytest.fixture
def fetched_clone(tmp_path, monkeypatch):
    """origin 有 W1-001..004；clone 的本地 main 只到 003，已 fetch 但未 merge。"""
    origin = tmp_path / "origin"
    _init_repo(origin)
    _commit_tickets(origin, [f"{VERSION}-W1-00{n}" for n in (1, 2, 3)])

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test")

    _commit_tickets(origin, [f"{VERSION}-W1-004"])
    _git(clone, "fetch", "-q", "origin")

    # 前置驗證：本地 main 沒有 004，origin/main 有
    local = _git(clone, "ls-tree", "-r", "--name-only", "main")
    remote = _git(clone, "ls-tree", "-r", "--name-only", "origin/main")
    assert "W1-004" not in local and "W1-004" in remote

    _point_state_root(monkeypatch, clone)
    return clone


def test_fetched_remote_ticket_counted(fetched_clone):
    assert get_next_seq(VERSION, 1) == 5


def test_without_remote_source_would_collide(fetched_clone, monkeypatch):
    """對照：拿掉 remote-tracking 來源時取號回到 4，正是 origin 上已有的號。"""
    monkeypatch.setattr(ticket_builder, "list_ticket_files_from_remote_tracking", lambda v: [])
    assert get_next_seq(VERSION, 1) == 4


def test_remote_tracking_listing_contains_remote_only_ticket(fetched_clone):
    files = list_ticket_files_from_remote_tracking(VERSION)
    assert any(Path(p).stem == f"{VERSION}-W1-004" for p in files)


def test_repo_without_remote_unchanged(tmp_path, monkeypatch):
    """E1 對照：沒有 remote 時沒有額外來源，取號與既有行為相同。"""
    root = tmp_path / "solo"
    _init_repo(root)
    _commit_tickets(root, [f"{VERSION}-W1-00{n}" for n in (1, 2, 3)])
    _point_state_root(monkeypatch, root)
    assert list_ticket_files_from_remote_tracking(VERSION) == []
    assert get_next_seq(VERSION, 1) == 4


def test_remote_head_symref_not_listed_twice(fetched_clone):
    """refs/remotes/origin/HEAD 是指向 origin/main 的符號 ref，不另外列一次。"""
    files = list_ticket_files_from_remote_tracking(VERSION)
    stems = [Path(p).stem for p in files]
    assert stems.count(f"{VERSION}-W1-004") == 1
