"""Tests for sync-claude-push.py clean-check (缺陷 T 根因修復，0.19.1-W1-030).

缺陷 T：push step 2 的乾淨檢查若把未進 .gitignore 的 local-only untracked 檔
（如 .zhtw-mcp-skip / .sync-conflicts）也視為「未提交變更」而 abort，使 push
無法進行。

M1 根因解：clean-check 改用 git status --porcelain 取工作區狀態，再以
sync_exclude_manifest.should_exclude 過濾掉 local-only / 憑證後判定。
過濾後仍有變更 → 真的需要先 commit（abort）；過濾後乾淨 → 放行。

回歸保證：
  - untracked local-only 檔（should_exclude 命中）不再造成 abort
  - 真正未 commit 的 tracked 程式碼變更仍被攔截
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=str(cwd), check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "t@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "CLAUDE.md").write_text("base\n", encoding="utf-8")
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "init"], root)


def test_clean_check_passes_with_untracked_local_only(tmp_path):
    """untracked local-only 檔（.zhtw-mcp-skip）不應使 clean-check 失敗（缺陷 T 根因）。"""
    _init_repo(tmp_path)
    # 新增一個 should_exclude 命中的 untracked 檔
    (tmp_path / ".claude" / ".zhtw-mcp-skip").write_text("", encoding="utf-8")
    (tmp_path / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")

    assert sync_mod.ensure_committed(tmp_path) is True


def test_clean_check_fails_with_uncommitted_tracked_change(tmp_path):
    """真正未 commit 的 tracked 程式碼變更仍應使 clean-check 失敗。"""
    _init_repo(tmp_path)
    # 修改既有 tracked 檔但不 commit
    (tmp_path / ".claude" / "CLAUDE.md").write_text("modified\n", encoding="utf-8")

    assert sync_mod.ensure_committed(tmp_path) is False


def test_clean_check_fails_with_untracked_real_file(tmp_path):
    """非 local-only 的 untracked 檔（真正的新框架檔）仍應使 clean-check 失敗。"""
    _init_repo(tmp_path)
    (tmp_path / ".claude" / "new_rule.md").write_text("content\n", encoding="utf-8")

    assert sync_mod.ensure_committed(tmp_path) is False


def test_clean_check_passes_when_fully_committed(tmp_path):
    """全數 commit 時 clean-check 通過。"""
    _init_repo(tmp_path)
    assert sync_mod.ensure_committed(tmp_path) is True
