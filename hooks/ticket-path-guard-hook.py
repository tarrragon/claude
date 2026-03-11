#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Ticket Path Guard Hook - PreToolUse Hook

功能: 阻止在 .claude/tickets/ 路徑下建立或編輯檔案，引導使用 /ticket 指令

背景:
  代理人曾繞過 ticket 系統，直接使用 Write 工具在 .claude/tickets/ 路徑下建立檔案。
  正確的 Ticket 存放位置是 docs/work-logs/v{version}/tickets/

行為:
  - 在 .claude/tickets/ 路徑建立檔案: 阻止，返回 exit code 2
  - 在 .claude/tickets/ 路徑編輯檔案: 阻止，返回 exit code 2
  - 正確路徑 (docs/work-logs/*/tickets/): 允許，返回 exit code 0
  - 其他操作: 允許，返回 exit code 0

觸發時機: 執行 Write/Edit 工具時

設計理由:
  - 確保所有 Ticket 都透過 /ticket create 指令建立，編號正確
  - 統一 Ticket 存放位置為 docs/work-logs/v{version}/tickets/
  - 防止代理人繞過 ticket 系統

Hook 類型: PreToolUse
觸發工具: Write, Edit
"""

import json
import os
import sys
import re
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, get_project_root, save_check_log, read_json_from_stdin
from lib.hook_messages import GateMessages, CoreMessages, format_message

from datetime import datetime
from typing import Dict, Any, Tuple

# ============================================================================
# 常數定義
# ============================================================================

EXIT_ALLOW = 0
EXIT_BLOCK = 2

# 禁止路徑：.claude/tickets/
# 正確路徑：docs/work-logs/v{version}/tickets/
FORBIDDEN_TICKET_PATH = r"^\.claude/tickets/.*\.md$"
CORRECT_TICKET_PATH = r"^docs/work-logs/v.*/tickets/.*\.md$"


# ============================================================================
# 路徑檢查
# ============================================================================

def normalize_path(file_path: str, logger) -> str:
    """正規化檔案路徑"""
    normalized = file_path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_forbidden_ticket_path(file_path: str, logger) -> bool:
    """檢查是否為禁止路徑 (.claude/tickets/)"""
    normalized_path = normalize_path(file_path, logger)
    return bool(re.match(FORBIDDEN_TICKET_PATH, normalized_path))


def is_correct_ticket_path(file_path: str, logger) -> bool:
    """檢查是否為正確的 Ticket 路徑 (docs/work-logs/*/tickets/)"""
    normalized_path = normalize_path(file_path, logger)
    return bool(re.match(CORRECT_TICKET_PATH, normalized_path))


# ============================================================================
# 權限檢查
# ============================================================================

def check_write_permission(file_path: str, logger) -> Tuple[bool, str]:
    """檢查 Write 操作權限"""
    if is_forbidden_ticket_path(file_path, logger):
        # TODO: add TICKET_PATH_FORBIDDEN_WRITE template to GateMessages
        reason = (
            "禁止在 .claude/tickets/ 路徑下建立檔案\n"
            "\n"
            "錯誤位置: .claude/tickets/\n"
            "正確位置: docs/work-logs/v{version}/tickets/\n"
            "\n"
            "為什麼: 統一 Ticket 存放位置，確保編號正確且易於追蹤\n"
            "\n"
            "建議操作:\n"
            "  使用 /ticket create 命令建立新 Ticket\n"
            "  這將自動存放到正確位置並產出有效的 ID\n"
            "\n"
            "詳見: .claude/rules/flows/ticket-lifecycle.md"
        )
        logger.warning(f"阻止在禁止路徑建立 Ticket: {file_path}")
        return False, reason

    return True, "路徑檢查通過"


def check_edit_permission(file_path: str, logger) -> Tuple[bool, str]:
    """檢查 Edit 操作權限"""
    if is_forbidden_ticket_path(file_path, logger):
        # TODO: add TICKET_PATH_FORBIDDEN_EDIT template to GateMessages
        reason = (
            "禁止直接編輯 .claude/tickets/ 路徑下的檔案\n"
            "\n"
            "錯誤位置: .claude/tickets/\n"
            "正確位置: docs/work-logs/v{version}/tickets/\n"
            "\n"
            "為什麼: 防止在錯誤位置建立或修改 Ticket\n"
            "\n"
            "建議操作:\n"
            "  如果需要編輯 Ticket，請確認它在正確位置:\n"
            "  docs/work-logs/v{version}/tickets/{id}.md\n"
            "\n"
            "  使用 /ticket track 指令管理 Ticket:\n"
            "  /ticket track claim {id}    - 認領 Ticket\n"
            "  /ticket track append-log {id} ... - 追加執行日誌\n"
            "  /ticket track complete {id} - 完成 Ticket\n"
            "\n"
            "詳見: .claude/rules/flows/ticket-lifecycle.md"
        )
        logger.warning(f"阻止直接編輯禁止路徑的 Ticket: {file_path}")
        return False, reason

    return True, "路徑檢查通過"


# ============================================================================
# Hook 輸出生成
# ============================================================================

def generate_hook_output(is_allowed: bool, reason: str, logger) -> Dict[str, Any]:
    """生成 Hook 輸出"""
    permission = GateMessages.TICKET_PATH_ALLOWED if is_allowed else GateMessages.TICKET_PATH_DENIED
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
    """主入口點"""
    logger = setup_hook_logging("ticket-path-guard")

    try:
        logger.info(CoreMessages.HOOK_START.format(hook_name="Ticket Path Guard Hook"))

        # 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)
        if not input_data:
            logger.warning("輸入為空或解析失敗，返回預設允許")
            error_output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "輸入為空或解析失敗，預設允許"
                }
            }
            print(json.dumps(error_output, ensure_ascii=False))
            return EXIT_ALLOW

        logger.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False)[:200]}...")

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        # 只檢查 Write, Edit 工具
        if tool_name not in ["Write", "Edit"]:
            logger.debug(f"跳過: 工具類型 {tool_name} 不在檢查範圍內")
            result = generate_hook_output(True, f"工具 {tool_name} 不在檢查範圍")
            print(json.dumps(result, ensure_ascii=False))
            return EXIT_ALLOW

        file_path = tool_input.get("file_path", "")
        logger.info(f"檢查工具: {tool_name}, 檔案: {file_path}")

        # 根據工具類型檢查權限
        if tool_name == "Write":
            is_allowed, reason = check_write_permission(file_path, logger)
        elif tool_name == "Edit":
            is_allowed, reason = check_edit_permission(file_path, logger)
        else:
            is_allowed, reason = True, "未知工具類型，預設允許"

        hook_output = generate_hook_output(is_allowed, reason, logger)
        print(json.dumps(hook_output, ensure_ascii=False))

        log_entry = f"""[{datetime.now().isoformat()}]
  Tool: {tool_name}
  FilePath: {file_path}
  Permission: {"ALLOWED" if is_allowed else "BLOCKED"}

"""
        save_check_log("ticket-path-guard", log_entry, logger)

        exit_code = EXIT_ALLOW if is_allowed else EXIT_BLOCK
        logger.info(f"Hook 檢查完成，exit code: {exit_code}")
        return exit_code

    except Exception as e:
        logger.error(f"Hook 執行錯誤: {type(e).__name__}: {e}")
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"Hook 執行錯誤，預設允許: {str(e)}"
            }
        }
        print(json.dumps(error_output, ensure_ascii=False))
        return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "ticket-path-guard"))
