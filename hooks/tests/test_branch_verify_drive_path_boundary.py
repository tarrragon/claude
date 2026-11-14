"""
Test: branch-verify 與 main-thread-edit-restriction 的磁碟機絕對路徑辨識與目錄邊界

驗證：
1. is_absolute_path：POSIX 與磁碟機路徑（含反斜線）為絕對，相對路徑不是
2. branch-verify _resolve_cwd_for_branch_detection：磁碟機路徑取檔案所在目錄查分支（修前退回環境變數）
3. 同字首兄弟路徑不被 _strip_root 當成專案根之下（POSIX 與磁碟機路徑各一）
4. 正向對照（E2）：保護分支上專案內非豁免路徑仍不豁免
5. main-thread-edit-restriction：磁碟機路徑會偵測目標 repo（修前略過）

磁碟機路徑在 POSIX 上以「cwd 下名為 C: 的目錄」模擬為真實存在的路徑；
cwd 以 monkeypatch.chdir 設定（function scope）。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

from lib.checkout_identity import is_absolute_path  # noqa: E402


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bv = _load("branch_verify_drive", "branch-verify-hook.py")
mt = _load("main_thread_drive", "main-thread-edit-restriction-hook.py")


@pytest.mark.parametrize("path,expected", [
    ("/a/b.py", True),
    ("C:/u/proj/a.py", True),
    ("c:\\u\\proj\\a.py", True),
    ("src/a.py", False),
    ("C:", False),
    ("", False),
])
def test_is_absolute_path(path, expected):
    assert is_absolute_path(path) is expected


def test_branch_cwd_uses_drive_path_directory(tmp_path, monkeypatch):
    (tmp_path / "C:" / "u" / "proj" / "src").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert bv._resolve_cwd_for_branch_detection("C:/u/proj/src/a.py") == "C:/u/proj/src"


@pytest.mark.parametrize("path,root", [
    ("/a/proj-wt/src/a.py", "/a/proj"),
    ("C:/u/proj-wt/src/a.py", "C:/u/proj"),
])
def test_strip_root_rejects_sibling_prefix(path, root):
    assert bv._strip_root(path, root) is None


@pytest.mark.parametrize("path,root", [
    ("/a/proj-wt/src/a.py", "/a/proj"),
    ("C:/u/proj-wt/src/a.py", "C:/u/proj"),
])
def test_sibling_worktree_file_is_outside_project(path, root):
    # 主 session 編輯同字首兄弟 worktree 的檔案：不在專案根之下 → 豁免（修前誤擋）
    assert bv.is_exempt_path_on_protected_branch(path, host_root=root) is True


@pytest.mark.parametrize("path,root", [
    ("/a/proj/src/a.py", "/a/proj"),
    ("C:/u/proj/src/a.py", "C:/u/proj"),
    ("c:/u/proj/src/a.py", "C:/u/proj"),
])
def test_project_src_on_protected_branch_still_not_exempt(path, root):
    # E2 正向對照：專案內 src/ 在保護分支上仍擋
    assert bv.is_exempt_path_on_protected_branch(path, host_root=root) is False


def test_main_thread_detects_target_repo_for_drive_path(monkeypatch):
    calls = []

    def _spy(path):
        calls.append(path)
        return None

    payload = {"tool_name": "Edit", "tool_input": {"file_path": "C:/u/other/src/a.py"}}
    with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
            patch.object(mt, "is_subagent_environment", return_value=False), \
            patch.object(mt, "find_target_repo", side_effect=_spy), \
            patch.object(mt, "_check_dispatch_warning", return_value=""):
        mt.main()
    assert calls == ["C:/u/other/src/a.py"]
