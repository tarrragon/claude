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
import os
import sys
from datetime import datetime
from pathlib import Path


def setup_logging():
    """初始化日誌系統"""
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs" / "file-type-permission"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"file-type-permission-{datetime.now().strftime('%Y%m%d')}.log"
    return log_file


def log_message(log_file: Path, message: str):
    """記錄訊息到日誌檔案"""
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        # 日誌失敗不應該影響 Hook 執行
        pass


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


def print_permission_prompt(file_path: str, category: str):
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
    print(prompt, file=sys.stderr)


def main():
    """主入口點"""
    log_file = setup_logging()

    try:
        # 讀取 JSON 輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # 檢查是否為 Edit 工具
        if tool_name != "Edit":
            # 非 Edit 工具：直接允許
            log_message(log_file, f"跳過: 工具類型 {tool_name} 不是 Edit")
            sys.exit(0)

        # 取得檔案路徑
        file_path = tool_input.get("file_path", "")

        if not file_path:
            log_message(log_file, f"警告: 無法取得 file_path")
            sys.exit(0)

        # 判斷檔案類別
        category = get_file_category(file_path)

        # 根據檔案類別決定行為
        if category in ("ticket", "worklog"):
            # Ticket/Worklog 檔案：輸出提示訊息
            log_message(log_file, f"提示: {category.upper()} 檔案 - {file_path}")
            print_permission_prompt(file_path, category)

            # 允許執行（提示已發送）
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": f"{category.upper()} 檔案編輯提示已發送，請確認後繼續",
                }
            }
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0)

        # 程式碼檔案或其他檔案：靜默通過
        log_message(log_file, f"允許: {category} 檔案 - {file_path}")
        sys.exit(0)

    except json.JSONDecodeError as e:
        log_message(log_file, f"JSON 解析錯誤: {e}")
        # JSON 解析失敗：直接允許執行，不阻塊
        sys.exit(0)
    except Exception as e:
        log_message(log_file, f"執行錯誤: {e}")
        # 任何錯誤都不阻塊（非阻塞原則）
        sys.exit(0)


if __name__ == "__main__":
    main()
