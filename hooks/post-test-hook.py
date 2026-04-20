#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
測試後置 Hook (PostToolUse) - 合併版

合併以下 2 個 Hook：
1. test-timeout-post.py — 測試超時監控
2. pre-fix-evaluation-hook.py — 測試失敗評估

觸發時機: PostToolUse (Bash: flutter test / dart test / npm test, 或 mcp__dart__run_tests)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)

try:
    from lib.common_functions import hook_output, read_hook_input
    from lib.hook_messages import WorkflowMessages, format_message
except ImportError as _import_err:
    # lib 函式僅 pre-fix-evaluation 子邏輯使用，缺失時該子邏輯會被 try-except 捕獲
    import logging as _fallback_logging
    _fallback_logging.getLogger("post-test-hook").warning("lib import 失敗: %s", _import_err)

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# 測試命令關鍵字
TEST_COMMAND_KEYWORDS = ["flutter test", "dart test", "npm test"]

# --- timeout 子邏輯常數 ---
WARNING_THRESHOLD = 300     # 5 分鐘
CRITICAL_THRESHOLD = 900    # 15 分鐘
AUTO_KILL_THRESHOLD = 1800  # 30 分鐘

# --- pre-fix-evaluation 子邏輯常數 ---


class ErrorType(Enum):
    """錯誤類型列舉"""
    SYNTAX_ERROR = "syntax_error"
    COMPILATION_ERROR = "compilation_error"
    TEST_FAILURE = "test_failure"
    ANALYZER_WARNING = "analyzer_warning"
    UNKNOWN = "unknown"


SYNTAX_PATTERNS = [
    (r"Expected.*?['\"]([;})\]])['\"]", "缺少括號或分號: {0}"),
    (r"Unexpected\s+(?:end of|token)\b", "意外 token"),
    (r"unterminated string literal", "字串未結束"),
    (r"unexpected end of(?:\s+\w+)*\s*file", "檔案不完整"),
    (r"missing comma", "缺少逗號"),
    (r"invalid number format", "無效數字格式"),
]

COMPILATION_PATTERNS = [
    (r"(?:type|variable).*?can't be assigned", "類型不匹配"),
    (r"is not a subtype of", "類型不匹配"),
    (r"Undefined\s+(?:name|class|function)\s+['\"]?(\w+)['\"]?", "未定義名稱: {0}"),
    (r"Target of URI\s+.*?\s+doesn't exist", "導入檔案不存在"),
    (r"(?:Class|Function|Method)\s+['\"]?(\w+)['\"]?\s+not found", "引用不存在: {0}"),
    (r"cannot find symbol", "符號未定義"),
    (r"incompatible types", "類型不相容"),
]

TEST_FAILURE_PATTERNS = [
    (r"Expected:\s*(.+?)\s*Actual:", "斷言失敗: Expected {0}"),
    (r"(\d+)\s+tests?\s+failed", "{0} 個測試失敗"),
    (r"FAILED", "測試失敗"),
    (r"AssertionError", "斷言錯誤"),
]

ANALYZER_WARNING_PATTERNS = [
    (r"info\s*-.*?unused", "未使用的警告"),
    (r"warning\s*-", "lint 警告"),
    (r"deprecated\s+(?:function|class|method)", "已棄用 API"),
]

TRUNCATED_OUTPUT_PATTERN = re.compile(
    r"Output too large.*?Full output saved to:\s*(\S+)"
)


# ============================================================================
# 輔助函式：判斷是否為測試命令
# ============================================================================

def _is_test_command(input_data: dict) -> bool:
    """判斷是否為測試命令。"""
    tool_name = input_data.get("tool_name", "")

    if tool_name == "Bash":
        command = (input_data.get("tool_input") or {}).get("command", "")
        return any(kw in command for kw in TEST_COMMAND_KEYWORDS)
    elif tool_name == "mcp__dart__run_tests":
        return True

    return False


# ============================================================================
# 子邏輯 1: 測試超時監控（來自 test-timeout-post.py）
# ============================================================================

def check_test_timeout(input_data: dict, tool_input: dict, logger):
    """子邏輯 1: 測試超時監控。回傳訊息或 None。"""
    project_dir = get_project_root()
    monitor_file = project_dir / ".claude" / "hook-logs" / "test-monitor.json"

    if not monitor_file.exists():
        logger.debug("timeout: 監控檔案不存在，跳過")
        return None

    try:
        with open(monitor_file) as f:
            monitor_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.debug("timeout: 監控檔案無法讀取，跳過")
        return None

    start_timestamp = monitor_data.get("start_timestamp", 0)
    if start_timestamp == 0:
        return None

    duration = datetime.now().timestamp() - start_timestamp
    duration_minutes = duration / 60

    monitor_data["end_time"] = datetime.now().isoformat()
    monitor_data["duration_seconds"] = duration
    monitor_data["status"] = "completed"

    message = ""
    if duration >= AUTO_KILL_THRESHOLD:
        subprocess.run(["pkill", "-f", "flutter_tester"], capture_output=True,
        encoding="utf-8",
        errors="replace")
        message = f"測試執行 {duration_minutes:.1f} 分鐘，已自動終止 flutter_tester"
        monitor_data["action"] = "auto_killed"
    elif duration >= CRITICAL_THRESHOLD:
        message = f"嚴重警告：測試執行 {duration_minutes:.1f} 分鐘，建議手動終止"
        monitor_data["action"] = "critical_warning"
    elif duration >= WARNING_THRESHOLD:
        message = f"警告：測試執行 {duration_minutes:.1f} 分鐘，可能有卡住問題"
        monitor_data["action"] = "warning"
    else:
        message = f"測試完成：{duration_minutes:.1f} 分鐘"
        monitor_data["action"] = "normal"

    try:
        with open(monitor_file, "w") as f:
            json.dump(monitor_data, f, indent=2, ensure_ascii=False)
        history_file = project_dir / ".claude" / "hook-logs" / "test-duration-history.jsonl"
        with open(history_file, "a") as f:
            f.write(json.dumps(monitor_data, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[WARNING] 無法寫入測試監控記錄: {e}", file=sys.stderr)
        logger.warning(f"timeout: 寫入監控檔案失敗: {e}")

    logger.info(f"timeout: {message}")
    return message


# ============================================================================
# 子邏輯 2: 測試失敗評估（來自 pre-fix-evaluation-hook.py）
# ============================================================================

def _classify_errors(output: str, logger) -> Tuple[ErrorType, List[Dict[str, str]]]:
    """分類錯誤類型。"""
    all_pattern_groups = [
        (ErrorType.SYNTAX_ERROR, SYNTAX_PATTERNS),
        (ErrorType.COMPILATION_ERROR, COMPILATION_PATTERNS),
        (ErrorType.TEST_FAILURE, TEST_FAILURE_PATTERNS),
        (ErrorType.ANALYZER_WARNING, ANALYZER_WARNING_PATTERNS),
    ]

    for error_type, patterns in all_pattern_groups:
        errors: List[Dict[str, str]] = []
        for pattern, description in patterns:
            matches = re.finditer(pattern, output, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                desc = description.format(*match.groups()) if "{" in description else description
                errors.append({
                    "type": error_type.value,
                    "description": desc,
                    "pattern": pattern,
                })
        if errors:
            return error_type, errors

    return ErrorType.UNKNOWN, []


def _resolve_truncated_output(output_str: str, logger) -> str:
    """偵測截斷輸出並讀取完整檔案內容。"""
    match = TRUNCATED_OUTPUT_PATTERN.search(output_str)
    if not match:
        return output_str

    saved_file_path = match.group(1)
    logger.info(f"偵測到截斷輸出，嘗試讀取: {saved_file_path}")

    try:
        full_content = Path(saved_file_path).read_text(encoding="utf-8")
        logger.info(f"成功讀取完整輸出，大小: {len(full_content)} 字元")
        return full_content
    except (OSError, ValueError) as e:
        logger.warning(f"無法讀取截斷輸出檔案: {e}")
        return output_str


def _log_evaluation(error_type: ErrorType, errors: List[Dict[str, str]], logger) -> None:
    """記錄評估結果到日誌。"""
    project_root = get_project_root()
    log_dir = project_root / ".claude" / "hook-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    report_file = log_dir / f"pre-fix-evaluation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error_type.value,
        "error_count": len(errors),
        "errors": errors,
        "requires_ticket": "pm_decision",
    }

    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"評估結果已記錄到 {report_file}")
    except OSError as e:
        # 寫入失敗不應阻塞提醒輸出（quality-baseline 規則 4）
        logger.warning(f"_log_evaluation 寫入失敗: {e}")
        sys.stderr.write(f"[post-test-hook] _log_evaluation 寫入失敗: {e}\n")


def evaluate_test_failure(input_data: dict, tool_input: dict, logger):
    """子邏輯 2: 測試失敗評估。回傳評估訊息或 None。"""
    tool_response = input_data.get("tool_response", "")
    if not tool_response:
        logger.debug("evaluation: 無 tool_response，跳過")
        return None

    output_str = str(tool_response) if not isinstance(tool_response, str) else tool_response
    output_str = _resolve_truncated_output(output_str, logger)

    if "all tests passed" in output_str.lower() or "no issues found" in output_str.lower():
        logger.debug("evaluation: 測試全部通過，跳過")
        return None

    error_type, errors = _classify_errors(output_str, logger)

    if not errors:
        logger.debug("evaluation: 未偵測到錯誤")
        return None

    logger.info(f"evaluation: 偵測到 {len(errors)} 個 {error_type.value} 錯誤")
    _log_evaluation(error_type, errors, logger)

    if error_type == ErrorType.SYNTAX_ERROR:
        message = f"\n語法錯誤 - 簡化修復流程\n\n錯誤數量: {len(errors)}\n推薦代理人: mint-format-specialist\n\n識別的語法錯誤：\n"
        for i, error in enumerate(errors, 1):
            message += f"{i}. {error['description']}\n"
        message += "\n[WARN] 建議直接修復語法錯誤（無需開 Ticket）。\n"
    else:
        message = f"\n[WARNING] 修復前強制評估 - {error_type.value.upper().replace('_', ' ')}\n\n"
        message += "[WARNING] 此錯誤類型 **必須開 Ticket** 追蹤，禁止直接分派修復！\n\n識別的錯誤：\n"
        for i, error in enumerate(errors, 1):
            message += f"{i}. {error['description']}\n"
        message += "\n[WARN] 建議流程：\n1. 使用 /pre-fix-eval Skill 進行六階段評估\n2. 使用 /ticket create 建立修復 Ticket\n3. 分派給專業代理人執行\n"

    return message


# ============================================================================
# 主程式
# ============================================================================

def main() -> int:
    """主入口點：測試命令後依序執行 2 個子邏輯。"""
    logger = setup_hook_logging("post-test-hook")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return EXIT_SUCCESS

    if not _is_test_command(input_data):
        return EXIT_SUCCESS

    logger.info("偵測到測試命令，開始執行子邏輯")

    tool_input = (input_data.get("tool_input") or {})
    messages = []

    # 子邏輯 1: 超時監控（優先執行）
    try:
        msg = check_test_timeout(input_data, tool_input, logger)
        if msg:
            messages.append(msg)
    except Exception as e:
        logger.error("timeout 子邏輯失敗: %s", e, exc_info=True)

    # 子邏輯 2: 失敗評估
    try:
        msg = evaluate_test_failure(input_data, tool_input, logger)
        if msg:
            messages.append(msg)
    except Exception as e:
        logger.error("evaluation 子邏輯失敗: %s", e, exc_info=True)

    # 統一輸出
    if messages:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n\n".join(messages)
            }
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "post-test-hook"))
