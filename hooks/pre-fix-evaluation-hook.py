#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
修復前強制評估 Hook (PostToolUse)

功能:
  自動偵測測試失敗、編譯錯誤、lint 警告
  根據錯誤類型分類：
  - SYNTAX_ERROR: 直接分派修復，無需開 Ticket
  - 其他錯誤: 強制開 Ticket，禁止直接分派

觸發時機:
  - mcp__dart__run_tests 執行完成且有失敗
  - Bash(flutter test) 執行完成且有失敗
  - Bash(dart analyze) 執行完成且有錯誤

輸出:
  成功: exitCode=0, stdout 包含評估提示
  阻塊: exitCode=2, stderr 包含強制開 Ticket 提示

環境變數:
  HOOK_DEBUG: 啟用詳細日誌 (true/false)

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Bash",
  "timeout": 10000,
  "description": "修復前強制評估 - 自動偵測錯誤並進行分類",
  "dependencies": [],
  "version": "1.0.0"
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
        "requires_ticket": error_type != ErrorType.SYNTAX_ERROR
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
直接執行精確修復，無需開 Ticket。
執行步驟：
1. 識別每個語法錯誤的確切位置
2. 最小化修改（只改必要字元）
3. 修改後立即執行測試驗證
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

執行以下步驟：
1. 完成六階段評估 (使用 /pre-fix-eval Skill)
   - Stage 1: 錯誤分類 (已自動完成)
   - Stage 2: BDD 意圖分析
   - Stage 3: 設計文件查詢
   - Stage 4: 根因定位
   - Stage 5: 開 Ticket 記錄
   - Stage 6: 分派執行

2. 使用 /ticket create 建立修復 Ticket
   - 標題: Fix {error_type.value}: [簡短描述]
   - 描述: 包含以上六階段分析結果
   - Agent: 根據錯誤類型分派

3. Ticket 建立後分派給專業代理人執行

禁止直接分派或跳過評估流程！
"""

    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "decision": "block"
        },
        "systemMessage": message,
        "suppressOutput": False
    }


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
            exit_code = 2  # 阻塊錯誤

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
