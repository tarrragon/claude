#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
MCP run_tests 使用規範驗證 Hook (PreToolUse)

功能: 防止 mcp__dart__run_tests 在無 paths 參數情況下執行全量測試
規範: 必須指定 paths 參數限制測試範圍，防止卡住超過 20 分鐘

觸發時機: 執行 mcp__dart__run_tests 工具前
檢查位置: roots 參數中的每個 root 物件

執行結果:
  - 有效用法 (包含 paths): 允許執行
  - 無效用法 (缺少 paths): 阻止執行並提示正確用法
"""

import json
import sys
from pathlib import Path
from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import ValidationMessages


def validate_roots_parameter(roots: list) -> tuple[bool, list]:
    """
    驗證 roots 參數

    Args:
        roots: mcp__dart__run_tests 的 roots 參數列表

    Returns:
        (is_valid, invalid_roots) - 是否有效，無效的 root 清單
    """
    if not isinstance(roots, list):
        return False, ["roots 參數必須是陣列"]

    invalid_roots = []

    for idx, root in enumerate(roots):
        if not isinstance(root, dict):
            invalid_roots.append(f"root[{idx}]: 必須是物件，收到 {type(root).__name__}")
            continue

        # 檢查是否有 paths 參數
        has_paths = "paths" in root
        paths_value = root.get("paths", [])

        # 驗證邏輯: paths 必須存在且非空
        if not has_paths or not paths_value:
            root_str = root.get("root", f"root[{idx}]")
            invalid_roots.append(
                f"{root_str}: 缺少 paths 參數或 paths 為空陣列"
            )

    return len(invalid_roots) == 0, invalid_roots


def format_error_message(invalid_roots: list) -> str:
    """格式化錯誤訊息"""
    message_parts = [
        ValidationMessages.MCP_TESTS_ERROR_TITLE,
        "",
        ValidationMessages.MCP_TESTS_PROBLEM_HEADER,
        ValidationMessages.MCP_TESTS_PROBLEM_DESC,
        "",
        ValidationMessages.MCP_TESTS_VIOLATION_HEADER,
    ]

    for invalid in invalid_roots:
        message_parts.append(f"  • {invalid}")

    message_parts.extend([
        "",
        ValidationMessages.MCP_TESTS_CORRECT_HEADER,
        "",
        ValidationMessages.MCP_TESTS_EXAMPLE_1,
        ValidationMessages.MCP_TESTS_EXAMPLE_1_CODE,
        "",
        ValidationMessages.MCP_TESTS_EXAMPLE_2,
        ValidationMessages.MCP_TESTS_EXAMPLE_2_CODE,
        "",
        ValidationMessages.MCP_TESTS_EXAMPLE_3,
        ValidationMessages.MCP_TESTS_EXAMPLE_3_CODE,
        "",
        ValidationMessages.MCP_TESTS_RECOMMENDED_HEADER,
        ValidationMessages.MCP_TESTS_RECOMMENDED_1,
        ValidationMessages.MCP_TESTS_RECOMMENDED_2,
        "",
        ValidationMessages.MCP_TESTS_REFERENCE_HEADER,
    ])

    return "\n".join(message_parts)


def main() -> int:
    """主程式邏輯"""
    logger = setup_hook_logging("mcp-run-tests-validator")

    try:
        # 讀取 stdin 輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # 只處理 mcp__dart__run_tests 工具
        if tool_name != "mcp__dart__run_tests":
            # 其他工具直接允許
            logger.debug("非 mcp__dart__run_tests 工具，直接允許: %s", tool_name)
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow"
                }
            }
            print(json.dumps(result, ensure_ascii=False))
            return 0

        # 提取 roots 參數
        roots = tool_input.get("roots", [])

        # 驗證 roots 參數
        is_valid, invalid_roots = validate_roots_parameter(roots)

        if is_valid:
            # 有效用法，允許執行
            logger.info("mcp__dart__run_tests 使用規範檢查通過")
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": ValidationMessages.MCP_TESTS_VALIDATION_PASSED
                }
            }
            print(json.dumps(result, ensure_ascii=False))
            return 0

        # 無效用法，阻止執行
        logger.error("mcp_run_tests_no_paths: roots=%s, invalid_roots=%s", roots, invalid_roots)

        error_message = format_error_message(invalid_roots)

        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": error_message
            }
        }

        # 輸出錯誤訊息到 stderr 供調試
        print(error_message)
        print(json.dumps(result, ensure_ascii=False))
        return 2

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        error_msg = f"Hook 錯誤: 無效的 JSON 輸入: {e}"
        print(error_msg)
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": error_msg
            }
        }
        print(json.dumps(result, ensure_ascii=False))
        return 2

    except Exception as e:
        logger.error("執行錯誤: %s: %s", type(e).__name__, str(e))
        error_msg = f"Hook 執行失敗: {type(e).__name__}: {str(e)}"
        print(error_msg)
        # 發生未預期的錯誤時，允許工具執行以防 Hook 故障
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"Hook 檢查失敗，允許執行: {str(e)}"
            }
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "mcp-run-tests-validator")
    sys.exit(exit_code)
