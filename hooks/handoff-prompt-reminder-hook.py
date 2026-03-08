#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Handoff 自動接手 Hook（注入即接手）

在用戶每次提交 Prompt 時檢查是否有待恢復的 handoff 任務。
設計哲學：與 Plan Mode 一致，注入 context 即代表開始工作。

功能:
1. 掃描 .claude/handoff/pending/ 目錄
2. 讀取所有 JSON handoff 檔案，跳過已接手的任務（resumed_at 非 null）
3. 對未接手任務寫入 resumed_at 時間戳（樂觀鎖，防止多 CLI 重複領取）
4. 自動讀取對應的 Ticket 檔案內容
5. 注入 Ticket 完整內容到 additionalContext（Fallback 到簡單提醒模式）
6. 防重複觸發：同一 session 只注入一次

使用方式:
    UserPromptSubmit Hook 自動觸發，或手動測試:
    echo '{}' | uv run .claude/hooks/handoff-prompt-reminder-hook.py

輸入格式:
    UserPromptSubmit Hook 提供的 JSON (stdin)

防重複領取:
    寫入 resumed_at 時間戳到 handoff JSON，後續 session 掃描時自動跳過

防重複觸發:
    使用父進程 PID 作為 session 識別符
    flag 檔案: /tmp/claude-handoff-reminded-{ppid}

Ticket 內容注入:
    - 從 ticket_id 解析版本號（e.g., 0.31.0-W13-003 → 0.31.0）
    - 讀取 docs/work-logs/v{version}/tickets/{ticket_id}.md
    - 注入完整內容到 additionalContext
    - Fallback: 若檔案不存在，則顯示簡單提醒訊息
"""

import sys
import json
import os
import fcntl
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

def write_session_state(ticket_id: str, logger) -> None:
    """
    將任務 ID 寫入 session 狀態檔案

    用於 Stop hook 查詢當前 session 鎖定的任務

    Args:
        ticket_id: 任務 ID
        logger: Logger 實例
    """
    try:
        ppid = os.getppid()
        state_file = Path(f"/tmp/claude-handoff-state-{ppid}.json")

        state_data = {
            "locked_ticket_id": ticket_id,
            "locked_at": datetime.now().isoformat()
        }

        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)

        logger.debug(f"寫入 session 狀態: {state_file} → {ticket_id}")

    except Exception as e:
        logger.warning(f"寫入 session 狀態失敗: {e}")

def mark_task_resumed(file_path: str, logger) -> bool:
    """
    將 handoff JSON 的 resumed_at 欄位寫入當前時間戳

    使用 fcntl.flock() 排他鎖確保原子性，防止多個 CLI session 重複領取同一任務。
    寫入時機在 context 注入之前，確保最早的 session 鎖定任務。

    Args:
        file_path: handoff JSON 檔案的絕對路徑
        logger: Logger 實例

    Returns:
        bool - 是否成功寫入
    """
    try:
        path = Path(file_path)
        with open(path, 'r+', encoding='utf-8') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                data = json.load(f)

                # 再次檢查：若已被其他 session 接手，放棄
                if data.get("resumed_at") is not None:
                    logger.info(f"任務已被其他 session 接手: {path.stem}")
                    return False

                data["resumed_at"] = datetime.now().isoformat()

                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=2)

                logger.info(f"標記任務已接手: {path.stem} (resumed_at: {data['resumed_at']})")

                # 寫入 session 狀態檔案（用於 Stop hook）
                ticket_id = data.get("ticket_id", path.stem)
                write_session_state(ticket_id, logger)

                return True
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    except Exception as e:
        logger.warning(f"標記任務接手失敗 ({file_path}): {e}")
        return False

def generate_reminder_message(
    pending_tasks: List[Dict[str, Any]],
    project_root: Path,
    logger
) -> str:
    """
    生成 Handoff 自動接手訊息（含 Ticket 內容注入、支援多任務）

    注入即接手：自動寫入 resumed_at 鎖定任務，防止多 CLI 重複領取。
    嘗試讀取並注入 Ticket 完整內容。若檔案不存在，則退回簡單提醒模式。

    多任務時按順序注入所有任務內容。

    Args:
        pending_tasks: 待恢復任務列表 (已通過前置驗證，ticket_path 已暫存)
        project_root: 專案根目錄
        logger: Logger 實例

    Returns:
        str - 格式化的接手訊息和 Ticket 內容
    """
    if not pending_tasks:
        return ""

    # 先鎖定所有任務（寫入 resumed_at），再注入 context
    resumed_tasks = []
    skipped_tasks = []

    for task in pending_tasks:
        if mark_task_resumed(task["file_path"], logger):
            resumed_tasks.append(task)
        else:
            skipped_tasks.append(task)

    if skipped_tasks:
        logger.info(f"跳過 {len(skipped_tasks)} 個已被其他 session 接手的任務")

    if not resumed_tasks:
        return ""

    message = "============================================================\n"
    message += f"[Handoff 自動接手] 已接手 {len(resumed_tasks)} 個任務，開始工作\n"
    message += "============================================================\n\n"

    ticket_count_with_content = 0
    ticket_count_without_content = 0

    # 處理每個已接手的任務
    for idx, task in enumerate(resumed_tasks, 1):
        ticket_id = task["ticket_id"]
        title = task["title"]
        direction = task["direction"]

        # 使用掃描時已驗證和暫存的 ticket_path
        ticket_path = Path(task.get("ticket_path", ""))
        ticket_content = read_ticket_content(ticket_path if ticket_path.exists() else None, logger)

        # 多任務時加上序號
        if len(resumed_tasks) > 1:
            message += f"[{idx}/{len(resumed_tasks)}] === Ticket: {ticket_id} - {title} ===\n"
        else:
            message += f"=== Ticket: {ticket_id} - {title} ===\n"

        message += f"方向: {direction}\n\n"

        if ticket_content:
            message += ticket_content
            message += "\n\n"
            ticket_count_with_content += 1
        else:
            message += "（Ticket 檔案未找到，請手動確認任務內容）\n\n"
            ticket_count_without_content += 1

        message += "-" * 60 + "\n\n"

    message += "============================================================\n"
    message += "重要指令：這是 Handoff 自動恢復。你必須立即開始處理上述 Ticket，\n"
    message += "不要詢問用戶是否開始，不要列出待辦清單，直接認領並執行任務。\n"
    message += "用戶的輸入即為開始信號，請立即閱讀 Ticket 內容並開始工作。\n"
    message += "============================================================\n"

    return message

def generate_hook_output(
    pending_tasks: List[Dict[str, Any]],
    project_root: Path,
    logger,
    input_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    生成 Hook 輸出格式

    若有待恢復任務且此 session 尚未處理過，則自動接手並注入 Ticket 內容。
    接手流程：寫入 resumed_at（鎖定）→ 注入 context → 標記 session 已處理

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
        logger.info("Handoff 自動接手 Hook 啟動（注入即接手）")

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
