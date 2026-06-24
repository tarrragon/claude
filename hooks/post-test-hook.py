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
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    is_subagent_environment,
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

# 測試命令偵測 regex（W3-066 修正）
#
# 舊版 TEST_COMMAND_KEYWORDS substring `in` 比對 ["npm test", ...] 會誤觸發
# echo "npm test" 等回顯關鍵字的非測試命令。改用 statement 邊界 + word
# boundary regex：要求 test 命令位於命令序列起頭（^/&&/||/;/|/(/換行）後，
# 可選環境變數前綴，最後接 flutter test / dart test / npm test / npm run test。
#
# 同時補強 npm run test:hooks 等 substring 比對漏觸發的情境。
TEST_COMMAND_PATTERN = re.compile(
    r"(?:^|[;|&(\n]|&&|\|\|)\s*"                # statement 邊界
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"       # 可選環境變數前綴
    r"(?:flutter\s+test|dart\s+test|npm\s+(?:test|run\s+test))\b"
)

# Ticket body 寫入操作關鍵字（W3-041 豁免；W3-066 補齊）
# 這些 CLI 命令會把含「FAILED / N tests failed」字面的 ticket body 內容
# 回顯到 tool_response，與真實測試失敗輸出無關，應跳過失敗評估。
#
# W3-066 修正：
# - 移除不存在的命令 `ticket track create`、`ticket track update`
#   （ticket CLI 真實命令為 top-level `ticket create`，無 track 前綴）
# - 補齊 top-level 寫入 / 回顯命令：ticket create / batch-create / show
TICKET_WRITE_COMMAND_KEYWORDS = [
    # Top-level commands that create or echo ticket body content
    "ticket create",
    "ticket batch-create",
    "ticket show",
    # track sub-commands (write / echo back body or state)
    "ticket track append-log",
    "ticket track set-acceptance",
    "ticket track check-acceptance",
    "ticket track complete",
    "ticket track claim",
]

# Ticket md 檔案路徑樣式（W3-041 豁免，防御性檢查 Edit/Write 觸發場景）
TICKET_MD_PATH_PATTERNS = [
    re.compile(r"docs/work-logs/v[^/]+/.+/tickets/.+\.md$"),
    re.compile(r"\.claude/skills/[^/]+/tickets/.+\.md$"),
]

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
    # W1-055: 排除「0 tests failed」/「0 failed」綠燈 summary
    # 用 negative lookbehind 確保前面數字不是 0
    (r"(?<![\d])([1-9]\d*)\s+tests?\s+failed\b", "{0} 個測試失敗"),
    # W1-055: 縮窄 FAILED pattern
    # 舊版 r"FAILED" 會誤命中：
    #   - 「0 failed」「零 failed」綠燈 summary
    #   - 「not failed」「FAILED-CASES」等識別符
    #   - 「Tests: 0 failed」等 jest/vitest 綠燈摘要
    # 縮窄為：行首或非識別符前綴 + FAILED + word boundary，且前後不能是
    # 「0 」「not 」或 hyphen/底線連字符
    (r"(?<![\w-])FAILED(?![\w-])(?!\s*[:=]\s*0\b)", "測試失敗"),
    (r"AssertionError", "斷言錯誤"),
]

ANALYZER_WARNING_PATTERNS = [
    (r"info\s*-.*?unused", "未使用的警告"),
    # eslint stylish formatter 格式：縮排 + row:col + warning + 訊息 + rule-name
    # 例：「  12:34  warning  Unused variable  no-unused-vars」
    # 縮窄理由：W1-059 / W1-048.8 實證舊 regex r"warning\s*-" 誤報 jest console.warn
    # 與含 "warning - ..." 的訊息字串。要求 row:col 起頭 + 結尾 rule name 才屬 lint warning。
    (r"^\s*\d+:\d+\s+warning\s+.+?\s+@?[a-z][a-z0-9-]*(?:/[a-z0-9-]+)*\s*$", "lint 警告"),
    (r"deprecated\s+(?:function|class|method)", "已棄用 API"),
]

TRUNCATED_OUTPUT_PATTERN = re.compile(
    r"Output too large.*?Full output saved to:\s*(\S+)"
)


# ============================================================================
# 輔助函式：判斷是否為測試命令
# ============================================================================

def _is_test_command(input_data: dict) -> bool:
    """判斷是否為測試命令。

    W3-066: 改用 statement 邊界 + word boundary regex，避免 echo "npm test"
    等回顯關鍵字的非測試命令誤觸發。
    """
    tool_name = input_data.get("tool_name", "")

    if tool_name == "Bash":
        command = (input_data.get("tool_input") or {}).get("command", "")
        return bool(TEST_COMMAND_PATTERN.search(command))
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


def _is_ticket_body_write(input_data: dict, tool_input: dict) -> bool:
    """判斷此 PostToolUse 是否為 ticket body 寫入操作（W3-041 豁免）。

    觸發場景：thyme 透過 ticket CLI append-log 或 Edit/Write 將含「FAILED」
    字面的修復描述寫入 ticket md。tool_response 會回顯該內容，被 regex
    誤判為真實測試失敗。

    判定條件（任一成立即視為 ticket body 寫入）：
    1. Bash command 含 ticket CLI 寫入子命令
    2. tool_input.file_path 匹配 ticket md 路徑樣式（防御性，目前 hook
       僅註冊於 Bash/mcp__dart__run_tests，但保留以避免未來重註冊出錯）
    """
    tool_name = input_data.get("tool_name", "")

    if tool_name == "Bash":
        command = (tool_input or {}).get("command", "")
        if any(kw in command for kw in TICKET_WRITE_COMMAND_KEYWORDS):
            return True

    file_path = (tool_input or {}).get("file_path", "")
    if file_path:
        for pattern in TICKET_MD_PATH_PATTERNS:
            if pattern.search(file_path):
                return True

    return False


# W1-055: 綠燈 summary 識別 patterns
# 涵蓋 Jest / Vitest / Mocha / pytest / npm 標準綠燈摘要
GREEN_SUMMARY_PATTERNS = [
    # Jest / Vitest: "Tests: 4994 passed, 0 failed" 或 "Tests: 4994 passed"
    re.compile(r"Tests?:\s+\d+\s+passed(?:,\s+0\s+failed)?", re.IGNORECASE),
    # Jest summary 變體: "Tests:       N passed, N total"
    re.compile(r"Tests?:\s+\d+\s+passed,\s+\d+\s+total", re.IGNORECASE),
    # pytest: "===== N passed in X.XXs =====" 或 "N passed, 0 failed"
    re.compile(r"=+\s*\d+\s+passed(?:,\s+\d+\s+\w+)*\s+in\s+[\d.]+s", re.IGNORECASE),
    # Mocha: "N passing" without "N failing"
    re.compile(r"^\s*\d+\s+passing\b", re.MULTILINE | re.IGNORECASE),
    # 通用「0 failed」字面（與 passed 同段出現）
    re.compile(r"\b0\s+failed\b", re.IGNORECASE),
    # Go test: "PASS\nok ..." 或 "ok\t<pkg>"
    re.compile(r"^ok\s+\S+\s+[\d.]+s", re.MULTILINE),
]


def _is_green_summary(output: str) -> bool:
    """判斷輸出是否含綠燈測試摘要（W1-055）。

    若 output 同時含「N passed」且明示「0 failed」（或無 failed 字面），
    視為綠燈，跳過 TEST_FAILURE_PATTERNS 命中（防 FAILED 字面誤判）。

    判定條件（任一成立）：
    - 含明確「0 failed」字面
    - 含 Jest/Vitest/pytest/Mocha 標準綠燈 summary
    - 含「all tests passed」「no issues found」（既有判定，保留相容）
    """
    lower = output.lower()
    if "all tests passed" in lower or "no issues found" in lower:
        return True

    for pattern in GREEN_SUMMARY_PATTERNS:
        if pattern.search(output):
            return True

    return False


def evaluate_test_failure(input_data: dict, tool_input: dict, logger):
    """子邏輯 2: 測試失敗評估。回傳評估訊息或 None。"""
    # W3-041: ticket body 寫入豁免（避免 thyme 寫修復描述含「FAILED」字面被誤判）
    if _is_ticket_body_write(input_data, tool_input):
        logger.debug("evaluation: ticket body 寫入操作，跳過失敗評估（W3-041）")
        return None

    tool_response = input_data.get("tool_response", "")
    if not tool_response:
        logger.debug("evaluation: 無 tool_response，跳過")
        return None

    output_str = str(tool_response) if not isinstance(tool_response, str) else tool_response
    output_str = _resolve_truncated_output(output_str, logger)

    # W1-055: 強化綠燈識別（Jest/Vitest/pytest/Mocha summary + 0 failed 字面）
    if _is_green_summary(output_str):
        logger.debug("evaluation: 偵測到綠燈 summary，跳過（W1-055）")
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

    # 偵測 subagent 環境：agent_id 僅在 subagent 中出現（W1-071 / PC-V1-004 入口污染防護）
    # 開 Ticket / 派發代理人等動作性提示屬 PM 決策，注入 subagent context 會誘導越界
    if is_subagent_environment(input_data):
        logger.debug(
            "偵測到 subagent 環境（agent_id=%s），跳過測試後置提醒",
            input_data.get("agent_id"),
        )
        return EXIT_SUCCESS

    if not _is_test_command(input_data):
        return EXIT_SUCCESS

    tool_input = (input_data.get("tool_input") or {})

    # W3-066: ticket body 寫入豁免提升為 main() 早期 gate（原僅在 evaluate_test_failure
    # 內部豁免），避免 timeout monitor 在 ticket CLI 命令上誤觸發。
    # 觸發場景：ticket track append-log / ticket create 等 ticket body 寫入命令的
    # 內容含 `cd && npm test`、`flutter test` 等字面，被新 word-boundary regex
    # 正確匹配為「statement boundary 後 test command」，但實際非真實測試執行。
    if _is_ticket_body_write(input_data, tool_input):
        logger.debug("ticket body 寫入操作，跳過所有後續子邏輯（W3-066 補強）")
        return EXIT_SUCCESS

    logger.info("偵測到測試命令，開始執行子邏輯")

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
