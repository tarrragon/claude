"""
Agent Commit Verification Hook - porcelain 路徑首字元截斷修復測試

對應 Ticket 1.0.0-W1-055.2 AC：
- AC1: porcelain 第一行前導空白不再被剝除，路徑無首字元截斷
- AC2: EXCLUDED_PATH_PREFIXES 豁免對第一行檔案正確生效

根因（1.0.0-W1-055 Problem Analysis）：
  get_uncommitted_files 原以 result.stdout.strip() 整體 strip，剝除
  porcelain 第一行的前導空白（worktree-modified 格式為「空格M空格filename」），
  隨後 line[3:] 多切一個字元 → `.claude/` 變 `claude/`、`docs/` 變 `ocs/`，
  豁免前綴比對失效（豁免繞過），乾淨範圍內檔案被誤報為未 commit。
"""

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


# 動態載入 hook module（檔名含連字號，無法直接 import）
_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "agent_commit_verification_hook_porcelain",
    _HOOKS_DIR / "agent-commit-verification-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

get_uncommitted_files = _hook.get_uncommitted_files

_logger = logging.getLogger("test-porcelain")


def _mock_git_status(stdout: str) -> MagicMock:
    """建構 git status --porcelain 的 subprocess.run 回傳值。"""
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = ""
    return result


def _patch_git(stdout: str):
    """Patch hook 模組的 subprocess.run（動態載入的模組不在 sys.modules，
    無法用字串路徑 patch，改以 patch.object 直接替換模組屬性）。"""
    return patch.object(_hook.subprocess, "run", return_value=_mock_git_status(stdout))


# ----------------------------------------------------------------------------
# AC1：第一行為 worktree-modified（前導空白）時路徑不被截斷
# ----------------------------------------------------------------------------

def test_first_line_worktree_modified_path_not_truncated():
    """porcelain 第一行為「空格M空格path」時，回傳路徑須保留首字元。"""
    stdout = (
        " M src/core/errors/ErrorHelper.js\n"
        "?? src/utils/new-helper.js\n"
    )
    with _patch_git(stdout):
        files = get_uncommitted_files("/fake/project", _logger)

    # 修復前：整體 strip 剝除第一行前導空白 → line[3:] 切出 "c/core/..."
    assert files == [
        "src/core/errors/ErrorHelper.js",
        "src/utils/new-helper.js",
    ]


def test_first_line_staged_modified_unaffected():
    """第一行無前導空白（staged，如「M 空格空格path」）時行為不變（回歸保護）。"""
    stdout = (
        "M  src/popup/popup.js\n"
        " M src/background/service-worker.js\n"
    )
    with _patch_git(stdout):
        files = get_uncommitted_files("/fake/project", _logger)

    assert files == [
        "src/popup/popup.js",
        "src/background/service-worker.js",
    ]


# ----------------------------------------------------------------------------
# AC2：.claude/ 與 docs/ 豁免前綴在第一行仍正確豁免
# ----------------------------------------------------------------------------

def test_claude_prefix_exempt_on_first_line():
    """`.claude/` 檔案落在 porcelain 第一行（前導空白）仍須被豁免。"""
    stdout = (
        " M .claude/hooks/tests/test_ticket_quality_gate_tool_aware.py\n"
        " M src/core/messages/MessageDictionary.js\n"
    )
    with _patch_git(stdout):
        files = get_uncommitted_files("/fake/project", _logger)

    # 修復前：第一行被截為 "claude/..."，不匹配 ".claude/" 前綴 → 豁免繞過
    assert files == ["src/core/messages/MessageDictionary.js"]


def test_docs_prefix_exempt_on_first_line():
    """`docs/` 檔案落在 porcelain 第一行（前導空白）仍須被豁免。"""
    stdout = (
        " M docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W1-054.md\n"
    )
    with _patch_git(stdout):
        files = get_uncommitted_files("/fake/project", _logger)

    # 修復前：第一行被截為 "ocs/work-logs/..."，不匹配 "docs/" 前綴 → 誤報
    assert files == []


def test_exempt_prefixes_on_non_first_lines_still_work():
    """非第一行的豁免路徑（保有前導空白）維持正確豁免（回歸保護）。"""
    stdout = (
        " M src/ui/search.js\n"
        " M .claude/hooks/some-hook.py\n"
        " M docs/struct.md\n"
    )
    with _patch_git(stdout):
        files = get_uncommitted_files("/fake/project", _logger)

    assert files == ["src/ui/search.js"]


# ----------------------------------------------------------------------------
# 邊界案例
# ----------------------------------------------------------------------------

def test_empty_stdout_returns_empty():
    """工作區乾淨（stdout 為空）回傳空清單。"""
    with _patch_git(""):
        files = get_uncommitted_files("/fake/project", _logger)

    assert files == []


def test_blank_lines_skipped():
    """stdout 含空行時跳過，不產生垃圾項目。"""
    stdout = " M src/handlers/event-handler.js\n\n"
    with _patch_git(stdout):
        files = get_uncommitted_files("/fake/project", _logger)

    assert files == ["src/handlers/event-handler.js"]
