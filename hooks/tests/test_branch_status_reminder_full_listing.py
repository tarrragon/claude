"""
branch-status-reminder Hook 全量清單測試（W13-011 / PC-076 防護落地）

驗證 4 個 acceptance：
1. 列出全部 tracked-modified 與 untracked（分組 staged/modified/untracked）
2. 超過上限（50）時以「完整清單見 git status」提示替代截斷摘要
3. 雙通道輸出：stderr + 日誌（logger.warning）
4. 情況 1/2/3/4 皆呼叫 _report_uncommitted_changes（不再僅情況 1）
"""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


HOOK_PATH = Path(__file__).parent.parent / "branch-status-reminder.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location("branch_status_reminder", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_file_status(status: str, file_path: str):
    """建立 FileStatus 替身（僅含本 hook 用到的屬性）。"""
    fs = MagicMock()
    fs.status = status
    fs.file_path = file_path
    fs.__str__ = lambda self: f"{status} {file_path}"
    fs.is_staged = status[0] not in (' ', '?')
    fs.is_modified = 'M' in status
    fs.is_untracked = status == '??'
    return fs


def _capture_outputs(hook, files, branch_state):
    """以指定的 git 狀態執行 main()，回傳 stdout、stderr、logger 紀錄。"""
    logger_mock = MagicMock()

    with patch.object(hook, "get_uncommitted_files", return_value=files), \
         patch.object(hook, "get_current_branch", return_value=branch_state["branch"]), \
         patch.object(hook, "is_in_worktree", return_value=branch_state["in_worktree"]), \
         patch.object(hook, "is_allowed_branch", return_value=branch_state["allowed"]), \
         patch.object(hook, "is_protected_branch", return_value=branch_state["protected"]), \
         patch.object(hook, "setup_hook_logging", return_value=logger_mock):
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        with patch.object(sys, "stdout", captured_stdout), \
             patch.object(sys, "stderr", captured_stderr):
            rc = hook.main()
        return rc, captured_stdout.getvalue(), captured_stderr.getvalue(), logger_mock


# ---------------------------------------------------------------------------
# AC1：全量列出 + 分組顯示
# ---------------------------------------------------------------------------

def test_lists_all_modified_and_untracked_grouped():
    """情況 1 (主 repo + 保護分支)：staged / modified / untracked 三組皆列出。"""
    hook = load_hook_module()
    files = [
        _fake_file_status("M ", "src/a.py"),       # staged modified
        _fake_file_status(" M", "src/b.py"),       # modified (unstaged)
        _fake_file_status(" M", "src/c.py"),       # modified (unstaged)
        _fake_file_status("??", "new/d.txt"),      # untracked
    ]
    rc, stdout, _, _ = _capture_outputs(
        hook,
        files,
        {"branch": "main", "in_worktree": False, "allowed": False, "protected": True},
    )

    assert rc == 0
    # 所有檔案都被列出
    assert "src/a.py" in stdout
    assert "src/b.py" in stdout
    assert "src/c.py" in stdout
    assert "new/d.txt" in stdout
    # 含分組標題
    assert "staged" in stdout.lower()
    assert "modified" in stdout.lower()
    assert "untracked" in stdout.lower()


# ---------------------------------------------------------------------------
# AC1 / 情況 2-4：所有異常情況均呼叫 _report_uncommitted_changes
# ---------------------------------------------------------------------------

def test_case2_main_repo_allowed_branch_also_lists_changes():
    """情況 2：主 repo + 開發分支也必須列出未提交變更（修復前漏列）。"""
    hook = load_hook_module()
    files = [_fake_file_status(" M", "src/leftover.py")]
    rc, stdout, _, _ = _capture_outputs(
        hook,
        files,
        {"branch": "feat/x", "in_worktree": False, "allowed": True, "protected": False},
    )
    assert rc == 0
    assert "src/leftover.py" in stdout


def test_case3_worktree_anomaly_branch_also_lists_changes():
    """情況 3：worktree 分支異常時也列出未提交變更。"""
    hook = load_hook_module()
    files = [_fake_file_status(" M", "src/anomaly.py")]
    rc, stdout, _, _ = _capture_outputs(
        hook,
        files,
        {"branch": "weird-branch", "in_worktree": True, "allowed": False, "protected": False},
    )
    assert rc == 0
    assert "src/anomaly.py" in stdout


# ---------------------------------------------------------------------------
# AC1：上限 50 + 完整清單提示
# ---------------------------------------------------------------------------

def test_over_limit_shows_hint_to_run_git_status():
    """超過 50 個檔案時顯示「完整清單請執行 git status」提示。"""
    hook = load_hook_module()
    files = [_fake_file_status(" M", f"src/f{i}.py") for i in range(60)]
    rc, stdout, _, _ = _capture_outputs(
        hook,
        files,
        {"branch": "main", "in_worktree": False, "allowed": False, "protected": True},
    )
    assert rc == 0
    # 提示存在
    assert "git status" in stdout
    # 至少列了一部分（顯示上限至少 50）
    assert "src/f0.py" in stdout
    assert "src/f49.py" in stdout


def test_under_limit_lists_all_no_hint():
    """未超過上限時不顯示提示（避免噪訊）。"""
    hook = load_hook_module()
    files = [_fake_file_status(" M", f"src/f{i}.py") for i in range(5)]
    rc, stdout, _, _ = _capture_outputs(
        hook,
        files,
        {"branch": "main", "in_worktree": False, "allowed": False, "protected": True},
    )
    assert rc == 0
    # 5 個全部列出
    for i in range(5):
        assert f"src/f{i}.py" in stdout
    # 不應出現完整清單提示
    assert "完整清單" not in stdout


# ---------------------------------------------------------------------------
# AC2：雙通道（stderr + 日誌）
# ---------------------------------------------------------------------------

def test_dual_channel_stderr_and_logger():
    """未提交變更摘要必須同時輸出至 stderr 且寫入 logger。"""
    hook = load_hook_module()
    files = [
        _fake_file_status(" M", "src/a.py"),
        _fake_file_status("??", "new.txt"),
    ]
    rc, _, stderr, logger_mock = _capture_outputs(
        hook,
        files,
        {"branch": "main", "in_worktree": False, "allowed": False, "protected": True},
    )
    assert rc == 0
    # stderr 含未提交變更摘要（數量或檔案）
    assert "2" in stderr or "src/a.py" in stderr
    # logger 至少一次 warning 紀錄含 uncommitted 訊息
    warning_calls = [
        str(c) for c in logger_mock.warning.call_args_list
    ]
    assert any("uncommitted" in c.lower() or "未提交" in c for c in warning_calls), \
        f"logger.warning should record uncommitted summary; got: {warning_calls}"


# ---------------------------------------------------------------------------
# 邊界：無變更時靜默
# ---------------------------------------------------------------------------

def test_no_changes_silent():
    """無未提交變更時不應印出檔案清單或雙通道警告。"""
    hook = load_hook_module()
    rc, _, stderr, logger_mock = _capture_outputs(
        hook,
        [],
        {"branch": "main", "in_worktree": False, "allowed": False, "protected": True},
    )
    assert rc == 0
    assert "未提交變更" not in stderr
    # 無 warning 關於 uncommitted
    warning_calls = [str(c) for c in logger_mock.warning.call_args_list]
    assert not any("uncommitted" in c.lower() for c in warning_calls)
