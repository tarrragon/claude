"""
Test: main-thread-edit-restriction-hook 開發分支放行只在 linked worktree 內成立

驗證：
1. 主 checkout 切到 feat 分支，編輯 lib/ 仍被擋（正向對照：修前此輸入被放行）
2. linked worktree（feat 分支）內編輯 lib/ 照常放行；session 以該 worktree
   為專案根，排除跨專案放行遮蔽分支放行
3. 目標檔案上層目錄尚未建立（Write 新目錄）：worktree 內放行、主 checkout 仍擋
4. _linked_worktree_root：主 checkout、無 commondir 的 gitlink（submodule 形態）、
   相對路徑皆為 None

隔離：每個測試自建 tmp git repo；git 子行程明確傳入去除 GIT_* 的 env；
CLAUDE_PROJECT_DIR 以 monkeypatch 設定（function scope）。
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))


def _load_hook():
    spec = importlib.util.spec_from_file_location(
        "main_thread_edit_restriction_branch", HOOKS_DIR / "main-thread-edit-restriction-hook.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


def _git_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
    )
    return env


def _git(cwd: Path, *args):
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True, env=_git_env(),
    )


@pytest.fixture
def repo(tmp_path):
    """主 checkout 在 feat/x 分支，另有 linked worktree 在 feat/y 分支。"""
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "lib").mkdir()
    (main / "lib" / "a.dart").write_text("")
    _git(main, "add", "lib/a.dart")
    _git(main, "commit", "-q", "-m", "init")
    _git(main, "checkout", "-q", "-b", "feat/x")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat/y", str(wt))
    return main, wt


def _run(file_path: str, session_root: Path, monkeypatch) -> int:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(session_root))
    payload = {"tool_name": "Edit", "tool_input": {"file_path": file_path}}
    with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
            patch.object(hook, "is_subagent_environment", return_value=False), \
            patch.object(hook, "get_project_root", return_value=str(session_root)), \
            patch.object(hook, "_check_dispatch_warning", return_value=""):
        return hook.main()


def test_main_checkout_feat_branch_lib_blocked(repo, monkeypatch):
    # E2 正向對照：主 checkout 開 feat 分支不再放行
    main, _ = repo
    assert _run(str(main / "lib" / "a.dart"), main, monkeypatch) == hook.EXIT_BLOCK


def test_linked_worktree_feat_branch_lib_allowed(repo, monkeypatch):
    _, wt = repo
    assert _run(str(wt / "lib" / "a.dart"), wt, monkeypatch) == hook.EXIT_ALLOW


def test_linked_worktree_new_dir_allowed(repo, monkeypatch):
    # Write 到 worktree 內尚未建立的目錄：分支須以 worktree 根查詢
    _, wt = repo
    assert _run(str(wt / "newdir" / "sub" / "b.dart"), wt, monkeypatch) == hook.EXIT_ALLOW


def test_main_checkout_new_dir_blocked(repo, monkeypatch):
    # E2 正向對照：主 checkout 尚未建立的目錄仍擋
    main, _ = repo
    assert _run(str(main / "newdir" / "b.dart"), main, monkeypatch) == hook.EXIT_BLOCK


def test_linked_worktree_detection(repo, tmp_path):
    main, wt = repo
    assert hook._linked_worktree_root(str(wt / "lib" / "a.dart")) == str(wt)
    assert hook._linked_worktree_root(str(wt / "no" / "such" / "a.dart")) == str(wt)
    assert hook._linked_worktree_root(str(main / "lib" / "a.dart")) is None
    assert hook._linked_worktree_root("lib/a.dart") is None
    assert hook._linked_worktree_root("") is None


def test_gitlink_without_commondir_is_not_linked_worktree(tmp_path):
    # submodule 形態：.git 為 gitlink 檔，指向的目錄沒有 commondir
    sub = (tmp_path / "sub").resolve()
    (sub / "lib").mkdir(parents=True)
    moddir = tmp_path / "modules" / "sub"
    moddir.mkdir(parents=True)
    (sub / ".git").write_text(f"gitdir: {moddir}\n")
    assert hook._linked_worktree_root(str(sub / "lib" / "a.dart")) is None
