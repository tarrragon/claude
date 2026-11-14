#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
File Type Permission Hook - PreToolUse Hook

功能: 依編輯的檔案類型記錄審計日誌（不做權限決策）
- Ticket 和 Worklog 檔案：寫審計日誌
- 其他檔案：只寫一般日誌

觸發時機: 執行 Edit 工具時
檔案路徑判斷:
  - Ticket 檔案: .claude/tickets/*
  - Worklog 檔案: docs/work-logs/*

行為:
  - 所有路徑 exit 0 且不輸出 permissionDecision；是否提示權限交回平台
    權限流程與 settings 規則（hook 輸出 allow 會略過提示，等於代用戶核可）
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin


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


def _log_permission_prompt(logger, file_path: str, category: str) -> None:
    """
    記錄人工確認提示訊息到 debug log（低頻 Hook 降級：stderr 提示改為 debug log）

    依據：Hook 觸發後 0% 產生 Action 的比例實測
    原行為：寫入 stderr 觸發 UI 顯示。降級後改 debug log，可在 hook-logs 追溯。

    Args:
        file_path: 編輯的檔案路徑
        category: 檔案類別 ('ticket' 或 'worklog')
    """
    category_name = "Ticket" if category == "ticket" else "Worklog"
    logger.debug(
        "[File Permission Guard] 編輯 %s 檔案: %s（此類檔案的修改建議人工審查）",
        category_name, file_path,
    )


def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("file-type-permission")

    try:
        # 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)
        if input_data is None:
            return 0
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
            # 低頻 Hook 降級：原 stderr 提示改為 debug log
            # 仍輸出 allow 決策，保留審計鏈但不干擾 PM/agent UI
            # 只記審計日誌，不輸出 permissionDecision：allow 會略過平台的權限
            # 提示，等於代用戶核可；是否提示交回平台權限流程與 settings 規則
            logger.info("允許: %s 檔案 - %s", category.upper(), file_path)
            _log_permission_prompt(logger, file_path, category)
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
