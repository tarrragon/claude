#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
External Query Guide Hook - PreToolUse Hook

功能: 檢測外部查詢工具（WebFetch、WebSearch）的使用，
     輸出工作流指導提示，建議派發 oregano-data-miner 執行外部資源研究。

觸發時機: 執行 WebFetch 或 WebSearch 工具時
行為: 輸出提示訊息到 stderr，允許命令繼續執行 (exit code 0)

設計原則:
- 提醒工作流，而非阻止操作
- 幫助主線程理解外部查詢的正確派發方式
- 記錄所有外部查詢調用，便於分析和監督
"""

import json
import sys
from typing import Dict, Any
from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import WorkflowMessages, format_message


# ============================================================================
# 檢測邏輯
# ============================================================================

def is_external_query_tool(tool_name: str) -> bool:
    """
    檢查是否為外部查詢工具

    Args:
        tool_name: 工具名稱

    Returns:
        bool - 是否為 WebFetch 或 WebSearch
    """
    external_query_tools = ["WebFetch", "WebSearch"]
    return tool_name in external_query_tools


def extract_tool_context(tool_input: Dict[str, Any]) -> str:
    """
    提取工具調用的上下文信息

    Args:
        tool_input: 工具輸入資料

    Returns:
        str - 上下文描述（用於日誌）
    """
    context_parts = []

    # 提取 URL（WebFetch）
    if "url" in tool_input:
        url = tool_input["url"]
        # 只記錄域名，不記錄完整 URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc or url[:50]
            context_parts.append(f"URL: {domain}")
        except Exception:
            context_parts.append(f"URL: {url[:50]}")

    # 提取查詢參數（WebSearch）
    if "query" in tool_input:
        query = tool_input["query"]
        context_parts.append(f"Query: {query[:50]}")

    return " | ".join(context_parts) if context_parts else "No context"


def _print_guide_message(tool_name: str, tool_input: Dict[str, Any]) -> None:
    """
    輸出工作流指導訊息到 stderr

    Args:
        tool_name: 工具名稱
        tool_input: 工具輸入
    """
    context = extract_tool_context(tool_input)
    guide_message = format_message(
        WorkflowMessages.EXTERNAL_QUERY_GUIDE,
        tool_name=tool_name
    )
    print(guide_message)


def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("external-query-guide")

    try:
        # 讀取 JSON 輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        logger.debug("接收工具: %s", tool_name)

        # 檢查是否為外部查詢工具
        if not is_external_query_tool(tool_name):
            # 非外部查詢工具：直接允許，不記錄
            return 0

        # 偵測到外部查詢工具：記錄並輸出指導訊息
        context = extract_tool_context(tool_input)
        logger.info("外部查詢工具檢測: %s | %s", tool_name, context)

        # 輸出友好的工作流提示
        _print_guide_message(tool_name, tool_input)

        # 輸出符合官方規範的 JSON 格式
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": format_message(
                    WorkflowMessages.EXTERNAL_QUERY_DETECTED,
                    tool_name=tool_name
                )
            }
        }
        print(json.dumps(result, ensure_ascii=False))

        return 0

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        # JSON 解析失敗：直接允許執行，不阻塊
        return 0
    except Exception as e:
        logger.error("執行錯誤: %s", e)
        # 任何錯誤都不阻塊
        return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "external-query-guide")
    sys.exit(exit_code)
