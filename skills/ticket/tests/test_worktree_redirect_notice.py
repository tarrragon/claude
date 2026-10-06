"""linked worktree 導回主倉庫時的 stderr [INFO] 提示測試。

get_ticket_state_root() 在 linked worktree 內刻意回推主倉庫，worktree 對票務
寫入不構成隔離。本測試驗證導向發生時 stderr 輸出一行 [INFO] 並標明主倉庫路徑，
主 checkout 與獨立 clone 不輸出，同一程序只輸出一次，stdout 不受影響。

fixture 一律以 tmp_path 建立 repo，不碰真實票庫。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.paths import (
    get_ticket_state_root,
    reset_project_root_cache,
    reset_ticket_state_root_cache,
)

NOTICE_MARKER = "[INFO]"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "checkout", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "init")


@pytest.fixture
def repos(tmp_path, monkeypatch):
    """main repo、其 linked worktree、獨立 clone；關閉測試隔離逃生艙走真實解析鏈。"""
    main_root = (tmp_path / "main").resolve()
    _init_repo(main_root)
    wt_root = (tmp_path / "wt").resolve()
    _git(main_root, "worktree", "add", "-q", "-b", "feat/x", str(wt_root), "HEAD")
    clone_root = (tmp_path / "clone").resolve()
    _git(tmp_path, "clone", "-q", "--no-hardlinks", str(main_root), str(clone_root))

    monkeypatch.delenv("TICKET_SYSTEM_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    reset_project_root_cache()
    reset_ticket_state_root_cache()
    yield main_root, wt_root, clone_root
    reset_project_root_cache()
    reset_ticket_state_root_cache()


def _resolve_in(monkeypatch, cwd: Path) -> Path:
    monkeypatch.chdir(cwd)
    reset_project_root_cache()
    reset_ticket_state_root_cache()
    return get_ticket_state_root()


def test_linked_worktree_emits_info_with_main_repo_path(repos, monkeypatch, capsys):
    main_root, wt_root, _ = repos
    root = _resolve_in(monkeypatch, wt_root)
    captured = capsys.readouterr()

    assert root == main_root
    assert NOTICE_MARKER in captured.err
    assert str(main_root) in captured.err
    assert NOTICE_MARKER not in captured.out


@pytest.mark.parametrize("which", ["main", "clone"])
def test_non_worktree_emits_no_info(repos, monkeypatch, capsys, which):
    main_root, _, clone_root = repos
    cwd = main_root if which == "main" else clone_root
    _resolve_in(monkeypatch, cwd)
    captured = capsys.readouterr()

    assert NOTICE_MARKER not in captured.err
    assert captured.out == ""


def test_repeated_resolution_emits_once(repos, monkeypatch, capsys):
    _, wt_root, _ = repos
    _resolve_in(monkeypatch, wt_root)
    get_ticket_state_root()
    get_ticket_state_root()
    captured = capsys.readouterr()

    assert captured.err.count(NOTICE_MARKER) == 1
    assert captured.out == ""

