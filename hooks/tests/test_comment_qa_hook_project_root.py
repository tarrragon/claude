#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for comment-qa-hook.py 的 PROJECT_ROOT 解析（0.2.1-W3-1198）。

修復前：PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))，
未設環境變數時退回 cwd，與 cwd 相對——與 0.2.1-W3-1189 修復的
skill-sync/ticket 同源缺陷（已實測產生 .claude/hooks/.claude/hook-logs/
錯置目錄）。修復後：lib 可用時改呼叫 get_project_root()（worktree 感知、
git toplevel 等多層 fallback，不受 cwd 影響）；lib 不可用（消費端缺
.claude/lib/）時維持既有 CLAUDE_PROJECT_DIR-or-cwd 降級路徑不變。
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = (
    REPO_ROOT / ".claude" / "skills" / "compositional-writing"
    / "hooks" / "comment-qa-hook.py"
)


def _load_hook_module():
    """動態載入 Hook 模組（檔名含 `-` 不能用一般 import）。"""
    spec = importlib.util.spec_from_file_location(
        "comment_qa_hook_module_w3_1198", HOOK_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_project_root_uses_get_project_root_when_lib_available(tmp_path, monkeypatch):
    """lib 可用時，PROJECT_ROOT 應等於 get_project_root() 的回傳值，不受
    呼叫端 cwd 影響。"""
    fake_root = tmp_path / "fake-repo"
    fake_root.mkdir()
    nested_cwd = fake_root / ".claude" / "hooks"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    hooks_dir = REPO_ROOT / ".claude" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    if str(REPO_ROOT / ".claude") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / ".claude"))
    import lib as _lib_pkg

    with patch.object(_lib_pkg, "get_project_root", return_value=fake_root):
        mod = _load_hook_module()

    assert mod.PROJECT_ROOT == fake_root
    assert mod.LOG_DIR == fake_root / ".claude" / "hook-logs"
    assert mod.REPORT_DIR == fake_root / ".claude" / "hook-logs" / "comment-qa-reports"


def test_project_root_independent_of_caller_cwd(tmp_path, monkeypatch):
    """模擬呼叫端 cwd 落在 .claude/hooks/ 這種曾實測產生錯置的情境，
    PROJECT_ROOT 仍應解析到真正的專案根，不落在呼叫端 cwd 底下。"""
    fake_root = tmp_path / "fake-repo"
    fake_root.mkdir()
    nested_cwd = fake_root / ".claude" / "hooks"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    hooks_dir = REPO_ROOT / ".claude" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    if str(REPO_ROOT / ".claude") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / ".claude"))
    import lib as _lib_pkg

    with patch.object(_lib_pkg, "get_project_root", return_value=fake_root):
        mod = _load_hook_module()

    resolved = mod.LOG_DIR
    assert resolved == fake_root / ".claude" / "hook-logs"
    # 巢狀錯置路徑斷言：絕不應落在 .claude/hooks/.claude 這種呼叫端 cwd 底下
    assert str(resolved).count(".claude") == 1
