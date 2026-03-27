#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Handoff 提醒 Hook — WARN 模式

在用戶每次提交 Prompt 時檢查是否有待恢復的 handoff 任務。
僅提供提醒訊息，不自動接手或修改檔案。PM 透過 /ticket resume 手動決定。

功能:
1. 掃描 .claude/handoff/pending/ 目錄
2. 讀取所有 JSON handoff 檔案，跳過已接手的任務（resumed_at 非 null）
3. 顯示待恢復任務提醒（不修改任何檔案）
4. 防重複觸發：同一 session 只提醒一次

使用方式:
    UserPromptSubmit Hook 自動觸發，或手動測試:
    echo '{}' | uv run .claude/hooks/handoff-prompt-reminder-hook.py

輸入格式:
    UserPromptSubmit Hook 提供的 JSON (stdin)

防重複觸發:
    使用父進程 PID 作為 session 識別符
    flag 檔案: /tmp/claude-handoff-reminded-{ppid}
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin, parse_ticket_frontmatter, get_project_root
from lib.hook_messages import WorkflowMessages, CoreMessages, format_message

EXIT_SUCCESS = 0
EXIT_ERROR = 1

def get_session_flag_file(logger) -> Path:
    """
    取得 session flag 檔案路徑

    使用父進程 PID 作為 session 識別符

    Args:
        logger: Logger 實例

    Returns:
        Path - flag 檔案路徑
    """
    ppid = os.getppid()
    return Path(f"/tmp/claude-handoff-reminded-{ppid}")

def has_reminded_this_session(logger) -> bool:
    """
    檢查此 session 是否已提醒過

    Args:
        logger: Logger 實例

    Returns:
        bool - 是否已提醒
    """
    flag_file = get_session_flag_file(logger)
    return flag_file.exists()

def mark_reminded_this_session(logger) -> None:
    """
    標記此 session 已提醒過

    Args:
        logger: Logger 實例
    """
    flag_file = get_session_flag_file(logger)
    try:
        flag_file.touch()
        logger.debug(f"建立 session flag: {flag_file}")
    except Exception as e:
        logger.warning(f"建立 session flag 失敗: {e}")

def is_ticket_completed(project_root: Path, ticket_id: str, logger) -> bool:
    """
    檢查 Ticket 是否已完成（status: completed）

    Args:
        project_root: 專案根目錄
        ticket_id: Ticket ID
        logger: Logger 實例

    Returns:
        bool - 是否已完成
    """
    try:
        # 解析版本號
        parts = ticket_id.split('-')
        if not parts:
            return False

        version = parts[0]
        ticket_path = project_root / "docs" / "work-logs" / f"v{version}" / "tickets" / f"{ticket_id}.md"

        if not ticket_path.exists():
            return False

        # 解析 frontmatter
        frontmatter = parse_ticket_frontmatter(ticket_path, logger)
        if not frontmatter:
            return False

        status = frontmatter.get('status', '').lower()
        return status == 'completed'

    except Exception as e:
        logger.warning(f"檢查 Ticket 完成狀態失敗 ({ticket_id}): {e}")
        return False

def resolve_ticket_path(project_root: Path, ticket_id: str, logger) -> Path:
    """
    從 ticket_id 解析版本號並組合 Ticket 檔案路徑

    ticket_id 格式例如：
    - 0.31.0-W13-003 → docs/work-logs/v0.31.0/tickets/0.31.0-W13-003.md
    - 0.31.0-W13-003.1 → docs/work-logs/v0.31.0/tickets/0.31.0-W13-003.1.md

    Args:
        project_root: 專案根目錄
        ticket_id: Ticket ID (格式：version-wave-seq 或 version-wave-seq.n)
        logger: Logger 實例

    Returns:
        Path - Ticket 檔案路徑
    """
    try:
        # 解析版本號（前三段 0.31.0）
        parts = ticket_id.split('-')
        if len(parts) >= 1:
            version = parts[0]  # e.g., "0.31.0"
            ticket_path = project_root / "docs" / "work-logs" / f"v{version}" / "tickets" / f"{ticket_id}.md"
            logger.debug(f"解析 Ticket 路徑: {ticket_id} → {ticket_path.relative_to(project_root)}")
            return ticket_path
        else:
            logger.warning(f"無效的 Ticket ID 格式: {ticket_id}")
            return None
    except Exception as e:
        logger.warning(f"解析 Ticket 路徑失敗 ({ticket_id}): {e}")
        return None

def read_ticket_content(ticket_path: Optional[Path], logger) -> Optional[str]:
    """
    讀取 Ticket 檔案完整內容

    Args:
        ticket_path: Ticket 檔案路徑
        logger: Logger 實例

    Returns:
        str - Ticket 檔案完整內容，若檔案不存在或讀取失敗則回傳 None
    """
    if not ticket_path:
        return None

    try:
        if not ticket_path.exists():
            logger.debug(f"Ticket 檔案不存在: {ticket_path}")
            return None

        with open(ticket_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.debug(f"成功讀取 Ticket 檔案: {ticket_path.name}")
        return content

    except Exception as e:
        logger.warning(f"讀取 Ticket 檔案失敗 ({ticket_path}): {e}")
        return None

def scan_handoff_pending_directory(project_root: Path, logger) -> List[Dict[str, Any]]:
    """
    掃描 .claude/handoff/pending/ 目錄中的所有待恢復任務

    跳過已有 resumed_at 的任務以及已完成的 Ticket（status: completed）

    Args:
        project_root: 專案根目錄
        logger: Logger 實例

    Returns:
        list - 待恢復任務列表 (按 ticket_id 反向排序)
    """
    pending_tasks = []
    handoff_dir = project_root / ".claude" / "handoff" / "pending"

    if not handoff_dir.exists():
        logger.info(f"handoff/pending 目錄不存在: {handoff_dir}")
        return pending_tasks

    if not handoff_dir.is_dir():
        logger.warning(f"handoff/pending 不是目錄: {handoff_dir}")
        return pending_tasks

    try:
        for file_path in sorted(handoff_dir.glob("*.json")):
            logger.debug(f"掃描檔案: {file_path.name}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    handoff_data = json.load(f)

                # 跳過已接手的任務（有 resumed_at 時間戳）
                resumed_at = handoff_data.get("resumed_at")
                if resumed_at is not None:
                    logger.debug(f"跳過已接手任務: {file_path.stem}")
                    continue

                # 提取必要欄位
                ticket_id = handoff_data.get("ticket_id", file_path.stem)
                title = handoff_data.get("title", "無標題")
                direction = handoff_data.get("direction", "unknown")

                # 前置驗證：確認 Ticket 檔案存在
                ticket_path = resolve_ticket_path(project_root, ticket_id, logger)
                if not ticket_path or not ticket_path.exists():
                    logger.debug(f"跳過：Ticket 檔案不存在 ({ticket_id})")
                    continue

                # 檢查 Ticket 是否已完成
                if is_ticket_completed(project_root, ticket_id, logger):
                    logger.debug(f"跳過已完成任務: {ticket_id}")
                    continue

                pending_tasks.append({
                    "ticket_id": ticket_id,
                    "title": title,
                    "direction": direction,
                    "file_path": str(file_path),  # 保留原始檔案路徑用於日誌
                    "ticket_path": str(ticket_path),  # 暫存 ticket_path 避免重複解析
                })

                logger.debug(f"找到待恢復任務: {ticket_id}")

            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失敗 ({file_path.name}): {e}")
            except Exception as e:
                logger.warning(f"讀取檔案失敗 ({file_path.name}): {e}")

    except Exception as e:
        logger.error(f"掃描 handoff/pending 失敗: {e}")

    logger.info(f"找到 {len(pending_tasks)} 個待恢復任務")

    pending_tasks.sort(key=lambda t: t.get("ticket_id", ""), reverse=True)
    return pending_tasks

def generate_reminder_message(
    pending_tasks: List[Dict[str, Any]],
    project_root: Path,
    logger
) -> str:
    """
    生成 Handoff 提醒訊息（WARN 模式，不修改檔案）

    僅列出待恢復任務供 PM 參考，不自動接手或寫入 resumed_at。
    PM 透過 /ticket resume 手動決定是否恢復。

    Args:
        pending_tasks: 待恢復任務列表 (已通過前置驗證)
        project_root: 專案根目錄
        logger: Logger 實例

    Returns:
        str - 格式化的提醒訊息
    """
    if not pending_tasks:
        return ""

    message = "============================================================\n"
    message += f"[Handoff 提醒] 有 {len(pending_tasks)} 個待恢復的任務\n"
    message += "============================================================\n\n"

    message += "待恢復任務：\n"
    for idx, task in enumerate(pending_tasks, 1):
        ticket_id = task["ticket_id"]
        title = task["title"]
        direction = task["direction"]
        message += f"  {idx}. {ticket_id}: {title}\n"
        message += f"     方向: {direction}\n\n"

    message += "執行提醒：\n"
    message += "  /ticket resume <id>        恢復指定任務 context\n"
    message += "  /ticket resume --list      查看完整清單\n\n"
    message += "============================================================\n"

    return message

def generate_hook_output(
    pending_tasks: List[Dict[str, Any]],
    project_root: Path,
    logger,
    input_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    生成 Hook 輸出格式（WARN 模式）

    若有待恢復任務且此 session 尚未提醒過，則顯示提醒訊息。
    不修改任何檔案，PM 透過 /ticket resume 手動決定。

    Args:
        pending_tasks: 待恢復任務列表
        project_root: 專案根目錄
        logger: Logger 實例
        input_data: 用戶輸入資料（選擇性），用於檢查 startup-check SKILL 指令

    Returns:
        dict - Hook 輸出 JSON
    """
    # 無待恢復任務時，靜默跳過
    if not pending_tasks:
        logger.info("無待恢復任務")
        return {"suppressOutput": True}

    # 檢查用戶輸入是否為 startup-check SKILL（SKILL 會自行處理 handoff 恢復）
    if input_data:
        user_input = input_data.get("userInput", "") or input_data.get("prompt", "")
        if "startup-check" in user_input.lower():
            logger.info("偵測到 startup-check SKILL 指令，跳過 Hook 注入（SKILL 會自行處理）")
            return {"suppressOutput": True}

    # 檢查此 session 是否已提醒過
    if has_reminded_this_session(logger):
        logger.info("此 session 已提醒過，跳過")
        return {"suppressOutput": True}

    # 生成提醒訊息（含 Ticket 內容注入）並標記已提醒
    reminder_message = generate_reminder_message(pending_tasks, project_root, logger)
    mark_reminded_this_session(logger)

    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": reminder_message
        },
        "suppressOutput": False
    }

def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化 logger
    2. 讀取 JSON 輸入
    3. 取得專案根目錄
    4. 掃描 .claude/handoff/pending/ 目錄
    5. 嘗試讀取並注入 Ticket 內容（若找不到檔案則 fallback）
    6. 產生 Hook 輸出（防重複觸發）
    7. 輸出 JSON 結果

    Returns:
        int - Exit code (0 = 成功，不中斷流程)
    """
    logger = setup_hook_logging("handoff-prompt-reminder")

    try:
        logger.info("Handoff 提醒 Hook 啟動（WARN 模式）")

        input_data = read_json_from_stdin(logger)

        project_root = get_project_root()
        logger.info(f"專案根目錄: {project_root}")

        pending_tasks = scan_handoff_pending_directory(project_root, logger)

        hook_output = generate_hook_output(pending_tasks, project_root, logger, input_data)

        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        logger.info("Hook 執行完成")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS

if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "handoff-prompt-reminder"))
