"""
Agent Commit Verification Hook - scan_hook_errors 誤報修復測試

對應 Ticket 0.18.0-W11-004.9 AC：
- AC1: scan_hook_errors 只對 log level 為 ERROR/CRITICAL/FATAL 的行或 Traceback 標記匹配
- AC2: 使用者命令字串中夾帶 ERROR/FAIL/Exception 等關鍵字不觸發誤報
- AC3: 真實 Hook ERROR（例如派發被拒）仍能被偵測
- AC4: 涵蓋三個場景：命令字串含關鍵字不誤報 / 真 ERROR log 行偵測 / Traceback 標記偵測

取代 IMP-060 舊設計（純字串匹配 HOOK_ERROR_KEYWORDS 造成循環誤報）。
"""

import importlib.util
import sys
from pathlib import Path


# 動態載入 hook module（檔名含連字號，無法直接 import）
_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "agent_commit_verification_hook",
    _HOOKS_DIR / "agent-commit-verification-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

_has_hook_error = _hook._has_hook_error


# ----------------------------------------------------------------------------
# AC2：使用者命令字串中夾帶關鍵字不觸發誤報
# ----------------------------------------------------------------------------

def test_user_command_with_error_keyword_does_not_false_positive():
    """INFO log 中回放使用者命令含 'ERROR' 字樣不應被視為錯誤。"""
    content = (
        "[2026-04-19 02:22:44] INFO - 執行命令: grep -rn 'ERROR' src/\n"
        "[2026-04-19 02:22:45] DEBUG - Hook execution time: 0.02s\n"
    )
    assert _has_hook_error(content) is False


def test_user_command_with_fail_keyword_does_not_false_positive():
    """INFO log 中命令含 'FAIL' 不應誤報。"""
    content = "[2026-04-19 02:22:44] INFO - npm test -- --testNamePattern='should FAIL gracefully'\n"
    assert _has_hook_error(content) is False


def test_user_command_with_exception_keyword_does_not_false_positive():
    """INFO log 中命令含 'Exception' 不應誤報。"""
    content = "[2026-04-19 02:22:44] INFO - 新增 class NetworkException(BaseException)\n"
    assert _has_hook_error(content) is False


def test_warning_level_with_keyword_does_not_false_positive():
    """WARNING 等級即使訊息含 ERROR 關鍵字也不應觸發（只 ERROR/CRITICAL/FATAL 採計）。"""
    content = "[2026-04-19 02:22:44] WARNING - 偵測到 ERROR 字樣於使用者輸入，略過\n"
    assert _has_hook_error(content) is False


def test_debug_level_with_keyword_does_not_false_positive():
    """DEBUG 等級含 Traceback 字詞（非行首標記）不應觸發。"""
    content = "[2026-04-19 02:22:44] DEBUG - 參考 Traceback 文件 https://example.com\n"
    assert _has_hook_error(content) is False


# ----------------------------------------------------------------------------
# AC3：真實 Hook ERROR log 行能被偵測
# ----------------------------------------------------------------------------

def test_real_error_log_line_detected():
    """真實 ERROR 等級 log 行應被偵測。"""
    content = "[2026-04-19 02:22:44] ERROR - Hook 派發被拒：target path 超出 exempt_prefixes\n"
    assert _has_hook_error(content) is True


def test_real_critical_log_line_detected():
    """CRITICAL 等級 log 行應被偵測。"""
    content = "[2026-04-19 02:22:44] CRITICAL - 致命錯誤：dispatch-active.json 損毀\n"
    assert _has_hook_error(content) is True


def test_real_fatal_log_line_detected():
    """FATAL 等級 log 行應被偵測。"""
    content = "[2026-04-19 02:22:44] FATAL - 無法啟動 Hook\n"
    assert _has_hook_error(content) is True


def test_mixed_log_with_single_error_detected():
    """混合 log 中即使只有一行 ERROR 也應被偵測。"""
    content = (
        "[2026-04-19 02:22:44] INFO - 啟動 Hook\n"
        "[2026-04-19 02:22:45] DEBUG - 載入設定\n"
        "[2026-04-19 02:22:46] ERROR - 派發驗證失敗\n"
        "[2026-04-19 02:22:47] INFO - Hook 結束\n"
    )
    assert _has_hook_error(content) is True


# ----------------------------------------------------------------------------
# AC4：Traceback 標記偵測
# ----------------------------------------------------------------------------

def test_python_traceback_marker_detected():
    """行首 Python Traceback 標記應被偵測。"""
    content = (
        "[2026-04-19 02:22:44] INFO - 執行中\n"
        "Traceback (most recent call last):\n"
        '  File "hook.py", line 10, in main\n'
        "    raise ValueError('bad input')\n"
        "ValueError: bad input\n"
    )
    assert _has_hook_error(content) is True


def test_traceback_in_middle_of_line_not_detected():
    """Traceback 字樣在行中（非行首）不應被誤判為真實錯誤標記。"""
    content = "[2026-04-19 02:22:44] INFO - 參考 Traceback (most recent call last): 格式範例\n"
    # 此行既非 ERROR log level 也非行首 Traceback，不應被視為錯誤
    assert _has_hook_error(content) is False


# ----------------------------------------------------------------------------
# 邊界案例
# ----------------------------------------------------------------------------

def test_empty_content_returns_false():
    """空內容不應觸發。"""
    assert _has_hook_error("") is False


def test_only_info_and_debug_returns_false():
    """僅 INFO/DEBUG log 不應觸發。"""
    content = (
        "[2026-04-19 02:22:44] INFO - 啟動\n"
        "[2026-04-19 02:22:45] DEBUG - 處理中\n"
        "[2026-04-19 02:22:46] INFO - 結束\n"
    )
    assert _has_hook_error(content) is False
