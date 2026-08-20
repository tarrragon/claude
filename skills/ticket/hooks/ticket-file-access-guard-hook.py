#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

r"""
Ticket File Access Guard Hook - PreToolUse Hook

功能: 阻止直接 Read/Edit/Write ticket 檔案，引導使用 /ticket 指令
- 阻止 Read 整個 ticket 檔案 -> 引導使用 /ticket track query 或 full
- 阻止 Edit frontmatter 欄位 -> 引導使用 /ticket track set-* 或 claim/complete
- 阻止 Write 建立/覆寫 ticket -> 引導使用 /ticket create
- 允許 ticket-tracker.py / ticket-creator.py 內部呼叫
- 允許 Edit 執行日誌區段 (## Problem Analysis, ## Solution 等 body 部分)

觸發時機: 執行 Read/Edit/Write 工具時

目標路徑:
  ^\.claude/tickets/.*\.md$
  ^docs/work-logs/.*/tickets/.*\.md$

行為:
  - Read ticket 檔案: 阻止，返回 exit code 2
  - Edit frontmatter: 阻止，返回 exit code 2
  - Edit body 區段: 允許，返回 exit code 0
  - Write ticket 檔案: 阻止，返回 exit code 2（強制使用 /ticket create）
  - 內部呼叫: 允許，返回 exit code 0

設計理由:
  - ticket SKILL 使用 Python 直接 I/O 寫檔，不觸發 Claude Hook
  - 主線程直接使用 Write 工具會觸發 Hook，應被阻止
  - 這確保所有 Ticket 都透過 /ticket create 建立，編號正確
"""

import json
import os
import sys
import re
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging, run_hook_safely, get_project_root, save_check_log,
    read_json_from_stdin, emit_hook_output
)

from datetime import datetime
from typing import Dict, Any, Tuple

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0
EXIT_ALLOW = 0
EXIT_BLOCK = 2

# Ticket 檔案路徑模式
TICKET_PATH_PATTERNS = [
    r"^\.claude/tickets/.*\.md$",
    r"^docs/work-logs/.*/tickets/.*\.md$",
]

# 允許 Edit 的 body 區段標題（不含 frontmatter）
ALLOWED_BODY_SECTIONS = [
    "## Problem Analysis",
    "## Solution",
    "## Test Results",
    "## Execution Log",
    "## Notes",
    "## Phase",
    "## 問題分析",
    "## 解決方案",
    "## 測試結果",
    "## 執行日誌",
    "## 備註",
    "## 階段",
]

# Frontmatter 欄位模式
FRONTMATTER_FIELD_PATTERN = r"^(id|title|type|status|version|priority|parent_id|children|blockedBy|who|what|when|where|why|how|assigned|started_at|completed_at|created|updated):"


# ============================================================================
# 路徑和內容檢查
# ============================================================================

def normalize_path(file_path: str) -> str:
    """正規化檔案路徑為相對於專案根目錄的路徑

    絕對路徑會被轉換為相對於專案根目錄的路徑，使 TICKET_PATH_PATTERNS
    （以 ^docs/ 或 ^\\.claude/ 錨定）能正確比對。harness 系統指令要求 subagent
    一律使用絕對路徑，若不轉換則所有絕對路徑形式的 Read/Edit/Write 都會被
    is_ticket_file() 誤判為非 ticket 檔案而完全繞過本守衛（絕對路徑未轉換破口）。
    既有相對路徑（含 ./ 前綴）行為不變。
    """
    normalized = file_path.replace("\\", "/")

    project_root = str(get_project_root()).replace("\\", "/")
    if normalized.startswith(project_root):
        normalized = normalized[len(project_root):]
        if normalized.startswith("/"):
            normalized = normalized[1:]

    if normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized


def is_ticket_file(file_path: str) -> bool:
    """檢查是否為 ticket 檔案"""
    normalized_path = normalize_path(file_path)

    for pattern in TICKET_PATH_PATTERNS:
        if re.match(pattern, normalized_path):
            return True

    return False


def is_internal_call() -> bool:
    """檢查是否為內部呼叫（透過環境變數）"""
    return os.getenv("TICKET_TRACKER_INTERNAL") == "1"


# 共用 lib.is_handoff_recovery_mode() 只檢查 pending 目錄有無任何 handoff，
# 命中即對所有 ticket 全域放行，範圍過廣（未恢復 handoff 為常態非例外，見
# Problem Analysis）。本檔改用下列兩個本地函式，將放行範圍收窄至該 handoff
# 實際指向的 ticket。共用函式仍由 task-dispatch-readiness-check.py 和
# agent-ticket-validation-hook.py 使用，本票不變更其行為（不處理其他 hook）。

def extract_ticket_id_from_path(file_path: str) -> str:
    """從 ticket 檔案路徑萃取 ticket ID（檔名去除副檔名）"""
    return Path(file_path).stem


def get_handoff_recovery_ticket_ids(logger) -> set:
    """掃描 handoff pending 目錄，回傳目前有效恢復流程涉及的 ticket ID 集合

    每筆 handoff 記錄同時納入來源 ticket_id 與 target_ticket_id：恢復流程可能
    需要讀取來源 ticket（已完成，作為交接背景）或目標 ticket（待接手），兩者
    都屬合法恢復範圍；範圍外的 ticket 一律視為與本次恢復無關。
    """
    project_root = get_project_root()
    handoff_pending_dir = project_root / ".claude" / "handoff" / "pending"
    ticket_ids = set()

    if not handoff_pending_dir.exists() or not handoff_pending_dir.is_dir():
        return ticket_ids

    for handoff_file in handoff_pending_dir.glob("*.json"):
        try:
            with open(handoff_file, "r", encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"讀取 handoff 檔案失敗，略過: {handoff_file.name}: {e}")
            continue

        for key in ("ticket_id", "target_ticket_id"):
            value = record.get(key)
            if value:
                ticket_ids.add(value)

    return ticket_ids


def is_body_section_edit(old_string: str, logger) -> bool:
    """
    檢查 Edit 操作是否為 body 區段編輯

    允許編輯的情況：
    - 編輯的內容是 body 區段標題後的內容
    - 不是 frontmatter 欄位
    """
    if not old_string:
        return False

    # 檢查是否在 frontmatter 區域（以 --- 開頭的區塊）
    stripped = old_string.strip()

    # 如果編輯的是 frontmatter 欄位
    if re.match(FRONTMATTER_FIELD_PATTERN, stripped):
        logger.debug(f"偵測到 frontmatter 欄位編輯: {stripped[:50]}")
        return False

    # 如果編輯的內容包含 body 區段標題，允許
    for section in ALLOWED_BODY_SECTIONS:
        if section in old_string:
            logger.debug(f"偵測到 body 區段編輯: {section}")
            return True

    # 如果是非 frontmatter 的一般內容，也允許（但記錄警告）
    # 這裡採用寬鬆策略：只阻止明確的 frontmatter 欄位編輯
    if ":" in stripped and stripped.split(":")[0].isalpha():
        # 可能是 frontmatter 欄位
        field_name = stripped.split(":")[0].strip()
        if field_name in ["id", "title", "type", "status", "version", "priority",
                          "parent_id", "children", "blockedBy", "who", "what",
                          "when", "where", "why", "how", "assigned", "started_at",
                          "completed_at", "created", "updated"]:
            return False

    # 其他情況視為 body 內容，允許編輯
    return True


def is_new_file_write(file_path: str) -> bool:
    """檢查是否為新檔案寫入"""
    project_dir = get_project_root()
    full_path = project_dir / file_path
    return not full_path.exists()


# ============================================================================
# 權限檢查
# ============================================================================

def check_read_permission(file_path: str, logger) -> Tuple[bool, str]:
    """檢查 Read 操作權限"""
    if is_internal_call():
        return True, "內部呼叫允許"

    if not is_ticket_file(file_path):
        return True, "非 ticket 檔案，允許讀取"

    ticket_id = extract_ticket_id_from_path(file_path)
    recovery_ticket_ids = get_handoff_recovery_ticket_ids(logger)
    if ticket_id and ticket_id in recovery_ticket_ids:
        logger.debug(f"Handoff 恢復模式（限定 {ticket_id}）: 允許讀取 {file_path}")
        return True, f"Handoff 恢復模式允許（限定 {ticket_id}）"

    reason = (
        "禁止直接讀取 ticket 檔案。\n"
        "請使用以下指令：\n"
        "  - /ticket track query {id}  - 查詢 ticket 資訊\n"
        "  - /ticket track full {id}   - 輸出完整 ticket 內容\n"
        "  - /ticket track log {id}    - 輸出執行日誌"
    )
    logger.warning(f"阻止讀取 ticket 檔案: {file_path}")
    return False, reason


def check_edit_permission(file_path: str, old_string: str, logger) -> Tuple[bool, str]:
    """檢查 Edit 操作權限"""
    if is_internal_call():
        return True, "內部呼叫允許"

    if not is_ticket_file(file_path):
        return True, "非 ticket 檔案，允許編輯"

    # 檢查是否為 body 區段編輯
    if is_body_section_edit(old_string, logger):
        logger.info(f"允許編輯 ticket body 區段: {file_path}")
        return True, "body 區段編輯允許"

    # 阻止 frontmatter 欄位編輯
    reason = (
        "禁止直接編輯 ticket frontmatter 欄位。\n"
        "常用指令（完整清單見 `ticket track --help`）：\n"
        "  - /ticket track claim {id}       - 認領 ticket\n"
        "  - /ticket track complete {id}    - 完成 ticket\n"
        "  - /ticket track set-title {id} {value} - 更新 title（清單顯示用短標籤）\n"
        "  - /ticket track set-what {id} {value}  - 更新 what（完整任務敘述）\n"
        "  - /ticket track set-who {id} {value}   - 更新 who 欄位\n"
        "  - /ticket track set-priority {id} {value} - 更新優先級\n"
        "  - /ticket track append-log {id} --section {section} {content} - 追加執行日誌\n"
        "\n"
        "若 `ticket track --help` 也找不到對應該欄位的命令，代表該欄位缺少合法\n"
        "更新途徑（PC-BAL-047）——請建 ticket 回報，不要繞道直接改檔。"
    )
    logger.warning(f"阻止編輯 ticket frontmatter: {file_path}")
    return False, reason


def check_write_permission(file_path: str, logger) -> Tuple[bool, str]:
    """檢查 Write 操作權限"""
    if is_internal_call():
        return True, "內部呼叫允許"

    if not is_ticket_file(file_path):
        return True, "非 ticket 檔案，允許寫入"

    # 完全阻止直接建立/覆寫 ticket
    # ticket 使用 Python 直接 I/O，不受此 Hook 影響
    # 這裡阻止的是主線程直接使用 Write 工具建立 ticket
    reason = (
        "禁止直接建立或覆寫 ticket 檔案。\n"
        "請使用以下指令建立新 Ticket：\n"
        "  ticket create --version X --wave Y --action \"動詞\" --target \"目標\"\n"
        "或使用 SKILL：\n"
        "  /ticket create ...\n"
        "\n"
        "這將確保編號正確且符合規範。"
    )
    logger.warning(f"阻止直接 Write ticket 檔案: {file_path}")
    return False, reason


# ============================================================================
# Hook 輸出生成
# ============================================================================

def _emit_permission_output(is_allowed: bool, reason: str) -> None:
    """生成並輸出 Hook 權限決策 JSON"""
    decision = "allow" if is_allowed else "deny"
    emit_hook_output("PreToolUse", permission_decision=decision, permission_decision_reason=reason)




# ============================================================================
# 主入口點
# ============================================================================

def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("ticket-file-access-guard")
    try:
        logger.info("Ticket File Access Guard Hook 啟動")

        # 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)
        if not input_data:
            logger.warning("輸入為空或解析失敗，返回預設允許")
            emit_hook_output(
                "PreToolUse",
                permission_decision="allow",
                permission_decision_reason="輸入為空或解析失敗，預設允許",
            )
            return EXIT_ALLOW

        logger.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False)[:200]}...")

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        # 只檢查 Read, Edit, Write 工具
        if tool_name not in ["Read", "Edit", "Write"]:
            logger.debug(f"跳過: 工具類型 {tool_name} 不在檢查範圍內")
            _emit_permission_output(True, f"工具 {tool_name} 不在檢查範圍")
            return EXIT_ALLOW

        file_path = tool_input.get("file_path", "")
        logger.info(f"檢查工具: {tool_name}, 檔案: {file_path}")

        # 根據工具類型檢查權限
        if tool_name == "Read":
            is_allowed, reason = check_read_permission(file_path, logger)
        elif tool_name == "Edit":
            old_string = tool_input.get("old_string", "")
            is_allowed, reason = check_edit_permission(file_path, old_string, logger)
        elif tool_name == "Write":
            is_allowed, reason = check_write_permission(file_path, logger)
        else:
            is_allowed, reason = True, "未知工具類型，預設允許"

        _emit_permission_output(is_allowed, reason)

        log_entry = f"""[{datetime.now().isoformat()}]
  Tool: {tool_name}
  FilePath: {file_path}
  Permission: {"ALLOWED" if is_allowed else "BLOCKED"}
  Reason: {reason}

"""
        save_check_log("ticket-file-access-guard", log_entry, logger)

        exit_code = EXIT_ALLOW if is_allowed else EXIT_BLOCK
        logger.info(f"Hook 檢查完成，exit code: {exit_code}")
        return exit_code

    except Exception as e:
        logger.error(f"Hook 執行錯誤: {type(e).__name__}: {e}")
        emit_hook_output(
            "PreToolUse",
            permission_decision="allow",
            permission_decision_reason=f"Hook 執行錯誤，預設允許: {str(e)}",
        )
        return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "ticket-file-access-guard"))
