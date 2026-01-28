#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

r"""
Main Thread Edit Restriction Hook - PreToolUse Hook

功能: 限制主線程的 Edit/Write 工具使用，防止直接編輯程式碼
- 允許編輯：.claude/*, docs/work-logs/*, docs/todolist.md
- 拒絕編輯：lib/*, test/*, *.dart（除 .claude/ 中的）
- 拒絕時返回 exit code 2 和錯誤訊息

觸發時機: 執行 Edit/Write 工具時

許可的檔案路徑（正則）:
  ^\.claude/plans/.*              # plan 檔案
  ^\.claude/tickets/.*            # Ticket 檔案（.claude 中）
  ^\.claude/.*                    # .claude 資料夾
  ^docs/work-logs/.*/tickets/.*   # Ticket 檔案（worklog 中）
  ^docs/work-logs/.*              # worklog 資料夾
  ^docs/todolist\.md$             # todolist 檔案

禁止的檔案路徑:
  ^lib/.*                         # 應用程式碼
  ^test/.*                        # 測試程式碼
  .*\.dart$                       # Dart 檔案（除 .claude/ 中的）

行為:
  - 允許的檔案: 允許編輯，返回 exit code 0
  - 禁止的檔案: 拒絕編輯，返回 exit code 2，輸出錯誤訊息
  - 其他檔案: 允許編輯，返回 exit code 0
"""

import json
import os
import sys
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


# ============================================================================
# 常數定義
# ============================================================================

# Exit Code
EXIT_SUCCESS = 0
EXIT_ALLOW = 0
EXIT_BLOCK = 2

# 允許的檔案路徑模式（正則）
# 注意：Ticket 檔案由 ticket-file-access-guard-hook.py 專責處理
ALLOWED_PATTERNS = [
    r"^\.claude/plans/.*",              # plan 檔案
    r"^\.claude/(?!tickets/).*",        # .claude 資料夾（排除 tickets）
    r"^docs/work-logs/(?!.*/tickets/).*",  # worklog 資料夾（排除 tickets）
    r"^docs/todolist\.md$",             # todolist 檔案
]

# 禁止的檔案路徑模式（正則）
BLOCKED_PATTERNS = [
    r"^lib/.*",                         # 應用程式碼
    r"^test/.*",                        # 測試程式碼
    r".*\.dart$",                       # Dart 檔案（除 .claude/ 中的）
]


# ============================================================================
# 日誌設置
# ============================================================================

def setup_logging() -> Path:
    """
    初始化日誌系統

    Returns:
        Path - 日誌檔案路徑
    """
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs" / "main-thread-edit-restriction"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"main-thread-edit-restriction-{datetime.now().strftime('%Y%m%d')}.log"

    # 配置基本日誌記錄
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
        ]
    )

    return log_file


def log_message(message: str, level: str = "INFO") -> None:
    """
    記錄訊息

    Args:
        message: 訊息內容
        level: 日誌級別 (DEBUG, INFO, WARNING, ERROR)
    """
    if level == "DEBUG":
        logging.debug(message)
    elif level == "INFO":
        logging.info(message)
    elif level == "WARNING":
        logging.warning(message)
    elif level == "ERROR":
        logging.error(message)


# ============================================================================
# 檔案路徑檢查
# ============================================================================

def normalize_path(file_path: str) -> str:
    """
    正規化檔案路徑

    Args:
        file_path: 原始檔案路徑

    Returns:
        str - 正規化後的路徑（使用正斜杠）
    """
    # 統一使用正斜杠
    normalized = file_path.replace("\\", "/")
    # 移除開頭的 ./ 如果有的話
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_allowed_path(file_path: str) -> bool:
    """
    檢查檔案路徑是否在允許清單中

    Args:
        file_path: 要檢查的檔案路徑

    Returns:
        bool - 是否為允許的路徑
    """
    normalized_path = normalize_path(file_path)

    for pattern in ALLOWED_PATTERNS:
        if re.match(pattern, normalized_path):
            log_message(f"檔案匹配允許模式 {pattern}: {normalized_path}", "DEBUG")
            return True

    return False


def is_blocked_path(file_path: str) -> bool:
    """
    檢查檔案路徑是否在禁止清單中

    Args:
        file_path: 要檢查的檔案路徑

    Returns:
        bool - 是否為禁止的路徑
    """
    normalized_path = normalize_path(file_path)

    for pattern in BLOCKED_PATTERNS:
        if re.match(pattern, normalized_path):
            log_message(f"檔案匹配禁止模式 {pattern}: {normalized_path}", "DEBUG")
            return True

    return False


def check_file_permission(file_path: str) -> Tuple[bool, str]:
    """
    檢查檔案編輯權限

    Args:
        file_path: 要編輯的檔案路徑

    Returns:
        tuple - (is_allowed, reason)
            - is_allowed: 是否允許編輯
            - reason: 原因說明
    """
    if not file_path:
        log_message("警告: 檔案路徑為空", "WARNING")
        return True, "檔案路徑為空，允許編輯"

    normalized_path = normalize_path(file_path)
    log_message(f"檢查檔案路徑: {normalized_path}", "DEBUG")

    # 優先檢查禁止清單（更具體的規則）
    if is_blocked_path(normalized_path):
        reason = "主線程禁止直接編輯程式碼。請建立 Ticket 並派發給對應代理人執行。"
        log_message(f"拒絕編輯禁止的檔案: {normalized_path}", "WARNING")
        return False, reason

    # 檢查允許清單
    if is_allowed_path(normalized_path):
        log_message(f"允許編輯檔案: {normalized_path}", "INFO")
        return True, "檔案在允許清單中"

    # 預設允許其他檔案
    log_message(f"預設允許編輯檔案: {normalized_path}", "DEBUG")
    return True, "檔案不在禁止清單中，預設允許"


# ============================================================================
# Hook 輸出生成
# ============================================================================

def generate_hook_output(is_allowed: bool, reason: str) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        is_allowed: 是否允許編輯
        reason: 原因說明

    Returns:
        dict - Hook 輸出 JSON
    """
    if is_allowed:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": reason,
            }
        }
    else:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }


def save_check_log(
    file_path: str,
    is_allowed: bool,
    reason: str
) -> None:
    """
    儲存檢查日誌

    Args:
        file_path: 檔案路徑
        is_allowed: 是否允許編輯
        reason: 原因說明
    """
    try:
        project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
        log_dir = project_dir / ".claude" / "hook-logs" / "main-thread-edit-restriction"
        log_dir.mkdir(parents=True, exist_ok=True)

        report_file = log_dir / f"checks-{datetime.now().strftime('%Y%m%d')}.log"

        log_entry = f"""[{datetime.now().isoformat()}]
  FilePath: {file_path}
  Permission: {"ALLOWED" if is_allowed else "BLOCKED"}
  Reason: {reason}

"""
        with open(report_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        log_message(f"檢查日誌已儲存: {report_file}", "DEBUG")
    except Exception as e:
        log_message(f"儲存檢查日誌失敗: {e}", "ERROR")


# ============================================================================
# 主入口點
# ============================================================================

def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化日誌
    2. 讀取 JSON 輸入
    3. 取得檔案路徑
    4. 檢查編輯權限
    5. 生成 Hook 輸出
    6. 儲存日誌
    7. 返回適當的 exit code

    Returns:
        int - Exit code (0 for allow, 2 for deny)
    """
    try:
        # 步驟 1: 初始化日誌
        setup_logging()
        log_message("Main Thread Edit Restriction Hook 啟動", "INFO")

        # 步驟 2: 讀取 JSON 輸入
        input_data = json.load(sys.stdin)
        log_message(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False)[:200]}...", "DEBUG")

        # 步驟 3: 取得工具資訊和檔案路徑
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # 只檢查 Edit 和 Write 工具
        if tool_name not in ["Edit", "Write"]:
            log_message(f"跳過: 工具類型 {tool_name} 不在檢查範圍內", "DEBUG")
            result = generate_hook_output(True, f"工具 {tool_name} 不在檢查範圍")
            print(json.dumps(result, ensure_ascii=False))
            return EXIT_ALLOW

        file_path = tool_input.get("file_path", "")
        log_message(f"檢查工具: {tool_name}, 檔案: {file_path}", "INFO")

        # 步驟 4: 檢查編輯權限
        is_allowed, reason = check_file_permission(file_path)

        # 步驟 5: 生成 Hook 輸出
        hook_output = generate_hook_output(is_allowed, reason)
        print(json.dumps(hook_output, ensure_ascii=False))

        # 步驟 6: 儲存日誌
        save_check_log(file_path, is_allowed, reason)

        # 步驟 7: 返回適當的 exit code
        exit_code = EXIT_ALLOW if is_allowed else EXIT_BLOCK
        log_message(f"Hook 檢查完成，exit code: {exit_code}", "INFO")
        return exit_code

    except json.JSONDecodeError as e:
        log_message(f"JSON 解析錯誤: {e}", "ERROR")
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "JSON 解析錯誤，預設允許"
            }
        }
        print(json.dumps(error_output, ensure_ascii=False))
        return EXIT_ALLOW

    except Exception as e:
        log_message(f"Hook 執行錯誤: {e}", "ERROR")
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"Hook 執行錯誤：{str(e)}"
            }
        }
        print(json.dumps(error_output, ensure_ascii=False))
        return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(main())
