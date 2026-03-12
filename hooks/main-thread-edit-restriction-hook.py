#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

r"""
Main Thread Edit Restriction Hook - PreToolUse Hook

功能: 限制主線程的 Edit/Write 工具使用，防止直接編輯程式碼（預設拒絕安全策略）
- 允許編輯：.claude/plans/*, .claude/rules/*, .claude/methodologies/*,
           .claude/hooks/*, .claude/skills/*, .claude/agents/*,
           .claude/references/*, .claude/error-patterns/*, .claude/handoff/*,
           docs/work-logs/**（含 tickets/）, docs/todolist.yaml, CLAUDE.md
- 拒絕編輯：lib/*, test/*, *.dart（除 .claude/ 中的）, backend/*, *.go, go.mod, go.sum
- 拒絕時返回 exit code 2 和錯誤訊息，提示允許的路徑範圍

觸發時機: 執行 Edit/Write 工具時

許可的檔案路徑（具體白名單）:
  ^\.claude/plans/.*              # plan 檔案
  ^\.claude/rules/.*              # 規則檔案
  ^\.claude/methodologies/.*      # 方法論
  ^\.claude/hooks/.*              # Hook 檔案
  ^\.claude/skills/.*             # Skill 檔案
  ^\.claude/agents/.*             # 代理人定義
  ^\.claude/references/.*         # 參考檔案
  ^\.claude/error-patterns/.*     # 錯誤模式
  ^\.claude/handoff/.*            # 交接檔案
  ^docs/work-logs/.*              # worklog 資料夾（含 tickets/）
  ^docs/todolist\.yaml$           # todolist 檔案
  ^CLAUDE\.md$                    # 專案入口文件

禁止的檔案路徑:
  ^lib/.*                         # 應用程式碼
  ^test/.*                        # 測試程式碼
  .*\.dart$                       # Dart 檔案（除 .claude/ 中的）
  ^backend/.*                     # Go backend 程式碼
  .*\.go$                         # Go 檔案
  ^go\.mod$                       # Go 依賴管理
  ^go\.sum$                       # Go 依賴鎖檔

安全策略（預設拒絕）:
  - 白名單中的檔案 → 允許編輯
  - 禁止清單中的檔案 → 拒絕編輯
  - .claude/ 內非白名單路徑 → 拒絕編輯（防止建立未預定義的子目錄）
  - 其他所有檔案 → 拒絕編輯（預設拒絕）

行為:
  - 允許的檔案: 允許編輯，返回 exit code 0
  - 禁止的檔案: 拒絕編輯，返回 exit code 2，輸出錯誤訊息
  - .claude/ 非白名單: 拒絕編輯，返回 exit code 2，輸出錯誤訊息
  - 其他檔案: 拒絕編輯，返回 exit code 2，輸出錯誤訊息
"""

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# 設置 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, get_project_root, save_check_log, read_json_from_stdin
from lib.hook_messages import GateMessages, CoreMessages, format_message


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
    r"^\.claude/rules/.*",              # 規則檔案
    r"^\.claude/methodologies/.*",      # 方法論
    r"^\.claude/hooks/.*",              # Hook 檔案
    r"^\.claude/skills/.*",             # Skill 檔案
    r"^\.claude/agents/.*",             # 代理人定義
    r"^\.claude/references/.*",         # 參考檔案
    r"^\.claude/error-patterns/.*",     # 錯誤模式
    r"^\.claude/handoff/.*",            # 交接檔案
    r"^docs/work-logs/.*",              # worklog 資料夾（含 tickets/）
    r"^docs/todolist\.yaml$",           # todolist 檔案
    r"^CLAUDE\.md$",                    # 專案入口文件
]

# 禁止的檔案路徑模式（正則）
BLOCKED_PATTERNS = [
    r"^lib/.*",                         # 應用程式碼
    r"^test/.*",                        # 測試程式碼
    r".*\.dart$",                       # Dart 檔案（除 .claude/ 中的）
    r"^\.claude/skills/.*\.py$",        # Skills 中的 Python 檔案
    r"^\.claude/lib/.*\.py$",           # lib 中的 Python 檔案
    r"^backend/.*",                     # Go backend 程式碼
    r".*\.go$",                         # Go 檔案
    r"^go\.mod$",                       # Go 依賴管理
    r"^go\.sum$",                       # Go 依賴鎖檔
]

# 例外：允許編輯的特定檔案路徑（優先於禁止清單）
EXCEPTION_PATTERNS = [
    r"^\.claude/hooks/.*\.py$",         # Hook 檔案可以編輯
    r"^\.claude/skills/.*\.py$",        # Skills 中的 Python 檔案（派發給代理人時允許）
]


# ============================================================================
# 檔案路徑檢查
# ============================================================================

def normalize_path(file_path: str) -> str:
    """
    正規化檔案路徑為相對於專案根目錄的路徑

    Args:
        file_path: 原始檔案路徑（可能是絕對或相對路徑）

    Returns:
        str - 正規化後的相對路徑（使用正斜杠）
    """
    # 統一使用正斜杠
    normalized = file_path.replace("\\", "/")

    # 取得專案根目錄（絕對路徑）
    project_dir = os.getenv("CLAUDE_PROJECT_DIR", str(Path.cwd()))
    project_dir = project_dir.replace("\\", "/")

    # 如果是絕對路徑且在專案目錄內，轉換為相對路徑
    if normalized.startswith(project_dir):
        normalized = normalized[len(project_dir):]
        # 移除開頭的斜杠
        if normalized.startswith("/"):
            normalized = normalized[1:]

    # 移除開頭的 ./ 如果有的話
    if normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized


def is_allowed_path(file_path: str, logger) -> bool:
    """
    檢查檔案路徑是否在允許清單中

    Args:
        file_path: 要檢查的檔案路徑
        logger: 日誌物件

    Returns:
        bool - 是否為允許的路徑
    """
    normalized_path = normalize_path(file_path)

    for pattern in ALLOWED_PATTERNS:
        if re.match(pattern, normalized_path):
            logger.debug(f"檔案匹配允許模式 {pattern}: {normalized_path}")
            return True

    return False


def is_blocked_path(file_path: str, logger) -> bool:
    """
    檢查檔案路徑是否在禁止清單中

    Args:
        file_path: 要檢查的檔案路徑
        logger: 日誌物件

    Returns:
        bool - 是否為禁止的路徑
    """
    normalized_path = normalize_path(file_path)

    for pattern in BLOCKED_PATTERNS:
        if re.match(pattern, normalized_path):
            logger.debug(f"檔案匹配禁止模式 {pattern}: {normalized_path}")
            return True

    return False


def is_exception_path(file_path: str, logger) -> bool:
    """
    檢查檔案路徑是否在例外清單中（允許編輯的特定檔案）

    Args:
        file_path: 要檢查的檔案路徑
        logger: 日誌物件

    Returns:
        bool - 是否為例外的路徑
    """
    normalized_path = normalize_path(file_path)

    for pattern in EXCEPTION_PATTERNS:
        if re.match(pattern, normalized_path):
            logger.debug(f"檔案匹配例外模式 {pattern}: {normalized_path}")
            return True

    return False


def check_file_permission(file_path: str, logger) -> Tuple[bool, str]:
    """
    檢查檔案編輯權限

    Args:
        file_path: 要編輯的檔案路徑
        logger: 日誌物件

    Returns:
        tuple - (is_allowed, reason)
            - is_allowed: 是否允許編輯
            - reason: 原因說明
    """
    if not file_path:
        logger.warning("警告: 檔案路徑為空")
        return True, "檔案路徑為空，允許編輯"

    normalized_path = normalize_path(file_path)
    logger.debug(f"檢查檔案路徑: {normalized_path}")

    # 優先檢查例外清單（允許編輯的特定檔案）
    if is_exception_path(normalized_path, logger):
        logger.info(f"允許編輯例外檔案: {normalized_path}")
        return True, "檔案在例外清單中，允許編輯"

    # 檢查禁止清單（在檢查允許清單之前）
    if is_blocked_path(normalized_path, logger):
        reason = GateMessages.EDIT_BLOCKED_PROGRAM_FILES
        logger.warning(f"拒絕編輯禁止的檔案: {normalized_path}")
        return False, reason

    # 檢查允許清單
    if is_allowed_path(normalized_path, logger):
        logger.info(f"允許編輯檔案: {normalized_path}")
        return True, "檔案在允許清單中"

    # 對 .claude/ 路徑，非白名單 = 攔截
    # （防止主線程在 .claude/ 建立未預定義的子目錄）
    if normalized_path.startswith(".claude/"):
        reason = GateMessages.EDIT_BLOCKED_CLAUDE_INVALID_PATH
        logger.warning(f"拒絕編輯非白名單 .claude/ 路徑: {normalized_path}")
        return False, reason

    # 預設拒絕所有其他檔案（安全策略）
    reason = GateMessages.EDIT_BLOCKED_DEFAULT_DENY
    logger.warning(f"拒絕編輯非白名單路徑（預設拒絕）: {normalized_path}")
    return False, reason


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
    permission = GateMessages.EDIT_ALLOWED if is_allowed else GateMessages.EDIT_RESTRICTED
    decision = "allow" if is_allowed else "deny"

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }




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
    # 步驟 1: 初始化日誌
    logger = setup_hook_logging("main-thread-edit-restriction")

    try:
        logger.info("Main Thread Edit Restriction Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)
        if input_data:
            logger.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False)[:200]}...")
        else:
            logger.debug("輸入為空或解析失敗，返回預設允許")
            result = generate_hook_output(True, "輸入為空，預設允許")
            print(json.dumps(result, ensure_ascii=False))
            return EXIT_ALLOW

        # 步驟 3: 取得工具資訊和檔案路徑
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        # 只檢查 Edit 和 Write 工具
        if tool_name not in ["Edit", "Write"]:
            logger.debug(f"跳過: 工具類型 {tool_name} 不在檢查範圍內")
            result = generate_hook_output(True, f"工具 {tool_name} 不在檢查範圍")
            print(json.dumps(result, ensure_ascii=False))
            return EXIT_ALLOW

        file_path = tool_input.get("file_path", "")
        logger.info(f"檢查工具: {tool_name}, 檔案: {file_path}")

        # 步驟 4: 檢查編輯權限
        is_allowed, reason = check_file_permission(file_path, logger)

        # 步驟 5: 生成 Hook 輸出
        hook_output = generate_hook_output(is_allowed, reason)
        print(json.dumps(hook_output, ensure_ascii=False))

        # 步驟 6: 儲存日誌
        log_entry = f"""[{datetime.now().isoformat()}]
  FilePath: {file_path}
  Permission: {"ALLOWED" if is_allowed else "BLOCKED"}
  Reason: {reason}

"""
        save_check_log("main-thread-edit-restriction", log_entry, logger)

        # 步驟 7: 返回適當的 exit code
        exit_code = EXIT_ALLOW if is_allowed else EXIT_BLOCK
        logger.info(f"Hook 檢查完成，exit code: {exit_code}")
        return exit_code

    except Exception as e:
        logger.error(f"Hook 執行錯誤: {e}")
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
    sys.exit(run_hook_safely(main, "main-thread-edit-restriction"))
