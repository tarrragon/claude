#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
修復前強制評估 Hook (PostToolUse) — WARN 模式

功能:
  自動偵測測試失敗、編譯錯誤、lint 警告
  根據錯誤類型分類並提供建議（僅警告，不自動決策）：
  - SYNTAX_ERROR: 建議直接修復
  - 其他錯誤: 建議開 Ticket 追蹤

觸發時機:
  - mcp__dart__run_tests 執行完成且有失敗
  - Bash(flutter test) 執行完成且有失敗
  - Bash(dart analyze) 執行完成且有錯誤

輸出:
  所有路徑: exitCode=0, stdout 包含 [WARN] 建議（不阻塞）

環境變數:
  HOOK_DEBUG: 啟用詳細日誌 (true/false)

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Bash",
  "timeout": 10000,
  "description": "修復前評估 WARN 模式 — 偵測錯誤並提供分類建議，不自動決策",
  "dependencies": [],
  "version": "2.0.0"
}
"""

import json
import sys
import os
import re
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Dict, List, Tuple, Optional

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

try:
    from hook_utils import setup_hook_logging, run_hook_safely
    from lib.common_functions import hook_output, read_hook_input
    from lib.hook_messages import WorkflowMessages, format_message
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# 錯誤類型定義
# ============================================================================

class ErrorType(Enum):
    """錯誤類型列舉"""
    SYNTAX_ERROR = "syntax_error"
    COMPILATION_ERROR = "compilation_error"
    TEST_FAILURE = "test_failure"
    ANALYZER_WARNING = "analyzer_warning"
    UNKNOWN = "unknown"


# ============================================================================
# 正則表達式模式
# ============================================================================

# 語法錯誤 - 優先檢查 (最簡單，可直接修復)
SYNTAX_PATTERNS = [
    (r"Expected.*?['\"]([;})\]])['\"]", "缺少括號或分號: {0}"),
    (r"Unexpected\s+(?:end of|token)\b", "意外 token"),
    (r"unterminated string literal", "字串未結束"),
    (r"unexpected end of(?:\s+\w+)*\s*file", "檔案不完整"),
    (r"missing comma", "缺少逗號"),
    (r"invalid number format", "無效數字格式"),
]

# 編譯錯誤 - 需要開 Ticket
COMPILATION_PATTERNS = [
    (r"(?:type|variable).*?can't be assigned", "類型不匹配"),
    (r"is not a subtype of", "類型不匹配"),
    (r"Undefined\s+(?:name|class|function)\s+['\"]?(\w+)['\"]?", "未定義名稱: {0}"),
    (r"Target of URI\s+.*?\s+doesn't exist", "導入檔案不存在"),
    (r"(?:Class|Function|Method)\s+['\"]?(\w+)['\"]?\s+not found", "引用不存在: {0}"),
    (r"cannot find symbol", "符號未定義"),
    (r"incompatible types", "類型不相容"),
]

# 測試失敗 - 需要開 Ticket
TEST_FAILURE_PATTERNS = [
    (r"Expected:\s*(.+?)\s*Actual:", "斷言失敗: Expected {0}"),
    (r"(\d+)\s+tests?\s+failed", "{0} 個測試失敗"),
    (r"FAILED", "測試失敗"),
    (r"AssertionError", "斷言錯誤"),
]

# Analyzer 警告 - 需要開 Ticket
ANALYZER_WARNING_PATTERNS = [
    (r"info\s*-.*?unused", "未使用的警告"),
    (r"warning\s*-", "lint 警告"),
    (r"deprecated\s+(?:function|class|method)", "已棄用 API"),
]

# 截斷輸出偵測
TRUNCATED_OUTPUT_PATTERN = re.compile(
    r"Output too large.*?Full output saved to:\s*(\S+)"
)

# 截斷輸出相關訊息
TRUNCATED_OUTPUT_READ_FAILED_MESSAGE = (
    "[WARNING] 工具輸出被截斷，但無法讀取完整輸出檔案: {path}\n"
    "錯誤: {error}\n"
    "請手動檢查該檔案以確認是否有測試失敗或錯誤。"
)
TRUNCATED_OUTPUT_BLOCK_MESSAGE = (
    "[WARNING] 工具輸出被截斷且無法讀取完整內容。\n"
    "為避免遺漏錯誤，已阻塞後續操作。\n"
    "請使用 Read 工具讀取完整輸出檔案後再繼續。"
)


# ============================================================================
# 錯誤分類函式
# ============================================================================

def classify_errors(output: str, logger) -> Tuple[ErrorType, List[Dict[str, str]]]:
    """
    分類錯誤類型

    Args:
        output: 工具輸出文本
        logger: 日誌物件

    Returns:
        (錯誤類型, 錯誤詳情列表)

    優先級: SYNTAX_ERROR > COMPILATION_ERROR > TEST_FAILURE > ANALYZER_WARNING
    """
    errors: List[Dict[str, str]] = []
    error_type = ErrorType.UNKNOWN

    # 優先檢查：語法錯誤 (最簡單)
    for pattern, description in SYNTAX_PATTERNS:
        matches = re.finditer(pattern, output, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            desc = description.format(*match.groups()) if "{" in description else description
            errors.append({
                "type": ErrorType.SYNTAX_ERROR.value,
                "description": desc,
                "pattern": pattern
            })
            error_type = ErrorType.SYNTAX_ERROR

    if error_type == ErrorType.SYNTAX_ERROR:
        return error_type, errors

    # 第二優先：編譯錯誤
    for pattern, description in COMPILATION_PATTERNS:
        matches = re.finditer(pattern, output, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            desc = description.format(*match.groups()) if "{" in description else description
            errors.append({
                "type": ErrorType.COMPILATION_ERROR.value,
                "description": desc,
                "pattern": pattern
            })
            if error_type != ErrorType.COMPILATION_ERROR:
                error_type = ErrorType.COMPILATION_ERROR

    if error_type == ErrorType.COMPILATION_ERROR:
        return error_type, errors

    # 第三優先：測試失敗
    for pattern, description in TEST_FAILURE_PATTERNS:
        matches = re.finditer(pattern, output, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            desc = description.format(*match.groups()) if "{" in description else description
            errors.append({
                "type": ErrorType.TEST_FAILURE.value,
                "description": desc,
                "pattern": pattern
            })
            if error_type != ErrorType.TEST_FAILURE:
                error_type = ErrorType.TEST_FAILURE

    if error_type == ErrorType.TEST_FAILURE:
        return error_type, errors

    # 第四優先：Analyzer 警告
    for pattern, description in ANALYZER_WARNING_PATTERNS:
        matches = re.finditer(pattern, output, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            desc = description.format(*match.groups()) if "{" in description else description
            errors.append({
                "type": ErrorType.ANALYZER_WARNING.value,
                "description": desc,
                "pattern": pattern
            })
            if error_type != ErrorType.ANALYZER_WARNING:
                error_type = ErrorType.ANALYZER_WARNING

    return error_type, errors


def _get_project_root_internal(logger) -> Path:
    """取得專案根目錄（來自 hook_utils）"""
    # 使用 hook_utils 的標準函式
    from hook_utils import get_project_root as hook_get_project_root
    return hook_get_project_root()


def log_evaluation(error_type: ErrorType, errors: List[Dict[str, str]], logger) -> None:
    """記錄評估結果到日誌"""
    project_root = _get_project_root_internal(logger)
    log_dir = project_root / ".claude" / "hook-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    report_file = log_dir / f"pre-fix-evaluation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error_type.value,
        "error_count": len(errors),
        "errors": errors,
        "requires_ticket": "pm_decision"
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"評估結果已記錄到 {report_file}")


# ============================================================================
# 輸出生成函式
# ============================================================================

def generate_syntax_error_output(errors: List[Dict[str, str]], logger) -> Dict:
    """生成語法錯誤輸出 (簡化流程)"""
    message = f"""
語法錯誤 - 簡化修復流程

錯誤數量: {len(errors)}
推薦代理人: mint-format-specialist

識別的語法錯誤：
"""
    for i, error in enumerate(errors, 1):
        message += f"{i}. {error['description']}\n"

    message += """
[WARN] 建議直接修復語法錯誤（無需開 Ticket）。
PM 可決定是否直接分派修復或開 Ticket 追蹤。
"""

    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "decision": "allow"
        },
        "systemMessage": message,
        "suppressOutput": False
    }


def generate_non_syntax_error_output(error_type: ErrorType, errors: List[Dict[str, str]], logger) -> Dict:
    """生成非語法錯誤輸出 (必須開 Ticket)"""
    message = format_message(
        WorkflowMessages.PRE_FIX_EVAL_REQUIRED
    )

    message = f"""
[WARNING] 修復前強制評估 - {error_type.value.upper().replace('_', ' ')}

[WARNING] 此錯誤類型 **必須開 Ticket** 追蹤，禁止直接分派修復！

識別的錯誤：
"""
    for i, error in enumerate(errors, 1):
        message += f"{i}. {error['description']}\n"

    message += f"""

[WARN] 建議流程：
1. 使用 /pre-fix-eval Skill 進行六階段評估
2. 使用 /ticket create 建立修復 Ticket
3. 分派給專業代理人執行

PM 可根據情況決定是否開 Ticket 或直接修復。
"""

    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "decision": "allow"
        },
        "systemMessage": message,
        "suppressOutput": False
    }


# ============================================================================
# 截斷輸出處理
# ============================================================================

def _resolve_truncated_output(output_str: str, logger) -> str:
    """
    偵測截斷輸出並讀取完整檔案內容。

    當 Claude Code 將超過 2KB 的工具輸出替換為截斷訊息時，
    從指定的完整輸出檔案讀取原始內容，確保正則匹配正常運作。

    Args:
        output_str: 原始工具輸出（可能是截斷訊息）
        logger: 日誌物件

    Returns:
        完整輸出內容（成功讀取時）或原始字串（無截斷時）。
        讀取失敗時透過 hook_output 輸出阻塞訊息並終止程式。
    """
    match = TRUNCATED_OUTPUT_PATTERN.search(output_str)
    if not match:
        return output_str

    saved_file_path = match.group(1)
    logger.info(f"偵測到截斷輸出，嘗試讀取完整檔案: {saved_file_path}")

    try:
        full_content = Path(saved_file_path).read_text(encoding="utf-8")
        logger.info(f"成功讀取完整輸出，大小: {len(full_content)} 字元")
        return full_content
    except (OSError, ValueError) as e:
        error_msg = TRUNCATED_OUTPUT_READ_FAILED_MESSAGE.format(
            path=saved_file_path, error=e
        )
        logger.error(error_msg)
        print(error_msg, file=sys.stderr)

        # 保守處理：阻塞後續操作
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "decision": "block"
            },
            "systemMessage": TRUNCATED_OUTPUT_BLOCK_MESSAGE,
            "suppressOutput": False
        }))
        sys.exit(2)


# ============================================================================
# 主程式
# ============================================================================

def main() -> int:
    """主程式進入點"""
    logger = setup_hook_logging("pre-fix-evaluation-hook")
    logger.info("=== pre-fix-evaluation hook start ===")

    try:
        # 從 stdin 讀取 JSON 輸入
        input_data = read_hook_input()
        if not input_data:
            logger.info("No input data, skipping evaluation")
            return 0
        logger.debug("Input data: {}".format(json.dumps(input_data, ensure_ascii=False, indent=2)))

        # 提取工具回應
        tool_response = input_data.get("tool_response", "")
        if not tool_response:
            logger.info("No tool response, skipping evaluation")
            return 0

        # 檢查是否有錯誤或失敗
        output_str = str(tool_response) if not isinstance(tool_response, str) else tool_response

        # 截斷輸出偵測：讀取完整輸出檔案替換截斷內容
        output_str = _resolve_truncated_output(output_str, logger)

        # 檢查成功標誌 (Dart 測試成功輸出中會有這些標誌)
        if "all tests passed" in output_str.lower() or "no issues found" in output_str.lower():
            logger.info("All tests passed, no evaluation needed")
            return 0

        # 分類錯誤
        error_type, errors = classify_errors(output_str, logger)

        if not errors:
            logger.info("No errors detected")
            return 0

        logger.info("Detected {} {} errors".format(len(errors), error_type.value))

        # 記錄評估結果
        log_evaluation(error_type, errors, logger)

        # 生成輸出
        if error_type == ErrorType.SYNTAX_ERROR:
            output = generate_syntax_error_output(errors, logger)
            exit_code = 0
        else:
            output = generate_non_syntax_error_output(error_type, errors, logger)
            exit_code = 0  # WARN 模式：不阻塞

        # 輸出結果
        print(json.dumps(output, ensure_ascii=False, indent=2))
        logger.info("=== pre-fix-evaluation hook complete ===")
        return exit_code

    except Exception as e:
        logger.exception("Unexpected error: {}".format(e))
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "decision": "allow"
            },
            "systemMessage": "Hook internal error: {}".format(e),
            "suppressOutput": False
        }))
        return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "pre-fix-evaluation-hook"))
