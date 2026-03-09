#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
File Type Permission Hook - PreToolUse Hook

功能: 根據編輯的檔案類型決定是否需要人工確認
- Ticket 和 Worklog 檔案需要人工確認
- 程式碼檔案 (lib/, test/, integration_test/) 自動通過
- 其他檔案依據預設行為

觸發時機: 執行 Edit 工具時
檔案路徑判斷:
  - Ticket 檔案: .claude/tickets/*
  - Worklog 檔案: docs/work-logs/*
  需要人工確認，輸出提示訊息到 stderr

  - 程式碼檔案: lib/*, test/*, integration_test/*
  自動通過，靜默執行（無任何輸出）

行為:
  - Ticket/Worklog: 輸出提示訊息到 stderr，返回 exit code 0（允許執行）
  - 程式碼檔案: 靜默通過，無任何輸出
  - 其他檔案: 靜默通過
"""

import json
import sys
from pathlib import Path
from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import QualityMessages, format_message


def get_file_category(file_path: str) -> str:
    """
    根據檔案路徑判斷檔案類別

    Args:
        file_path: 編輯的檔案路徑

    Returns:
        str - 'ticket' | 'worklog' | 'code' | 'other'
    """
    path = Path(file_path)
    path_str = str(path).replace("\\", "/")

    # 檢查 Ticket 檔案
    if "/.claude/tickets/" in path_str or ".claude/tickets/" in path_str:
        return "ticket"

    # 檢查 Worklog 檔案
    if "/docs/work-logs/" in path_str or "docs/work-logs/" in path_str:
        return "worklog"

    # 檢查程式碼檔案
    if any(
        pattern in path_str
        for pattern in ["/lib/", "/test/", "/integration_test/"]
    ):
        return "code"

    return "other"


def _print_permission_prompt(file_path: str, category: str) -> None:
    """
    輸出人工確認提示訊息到 stderr

    Args:
        file_path: 編輯的檔案路徑
        category: 檔案類別 ('ticket' 或 'worklog')
    """
    category_name = "Ticket" if category == "ticket" else "Worklog"
    prompt = f"""[File Permission Guard] 提示: 正在編輯 {category_name} 檔案

檔案: {file_path}
說明: 此類檔案的修改需要人工審查確認

"""
    print(prompt)


def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("file-type-permission")

    try:
        # 讀取 JSON 輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        # 檢查是否為 Edit 工具
        if tool_name != "Edit":
            # 非 Edit 工具：直接允許
            logger.info("跳過: 工具類型 %s 不是 Edit", tool_name)
            return 0

        # 取得檔案路徑
        file_path = tool_input.get("file_path", "")

        if not file_path:
            logger.warning("警告: 無法取得 file_path")
            return 0

        # 判斷檔案類別
        category = get_file_category(file_path)

        # 根據檔案類別決定行為
        if category in ("ticket", "worklog"):
            # Ticket/Worklog 檔案：輸出提示訊息
            logger.info("提示: %s 檔案 - %s", category.upper(), file_path)
            _print_permission_prompt(file_path, category)

            # 允許執行（提示已發送）
            category_name = "Ticket" if category == "ticket" else "Worklog"
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": format_message(QualityMessages.FILE_EDIT_WARNING, category=category_name),
                }
            }
            print(json.dumps(result, ensure_ascii=False))
            return 0

        # 程式碼檔案或其他檔案：靜默通過
        logger.info("允許: %s 檔案 - %s", category, file_path)
        return 0

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        # JSON 解析失敗：直接允許執行，不阻塊
        return 0
    except Exception as e:
        logger.error("執行錯誤: %s", e)
        # 任何錯誤都不阻塊（非阻塊原則）
        return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "file-type-permission")
    sys.exit(exit_code)
