#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Handoff 待恢復任務提醒 Hook

在 Session 啟動時檢查是否有待恢復的 handoff 任務。

功能:
1. 掃描 .claude/handoff/pending/ 目錄
2. 讀取所有 JSON handoff 檔案
3. 提取 ticket_id 和 title
4. 若有待恢復任務 → 顯示提醒訊息

使用方式:
    SessionStart Hook 自動觸發，或手動測試:
    python3 .claude/hooks/handoff-reminder-hook.py

輸入格式:
    SessionStart Hook 提供的 JSON (stdin，可選)

環境變數:
    CLAUDE_PROJECT_DIR: 專案根目錄
    HOOK_DEBUG: 啟用詳細日誌 (true/false)
"""

import sys
import json
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin, get_project_root

import re
from datetime import datetime
from typing import Dict, Any, List, Optional

# 全域常數
EXIT_SUCCESS = 0
EXIT_ERROR = 1

def scan_handoff_pending_directory(project_root: Path, logger) -> List[Dict[str, Any]]:
    """
    掃描 .claude/handoff/pending/ 目錄中的所有待恢復任務

    目錄結構:
    .claude/handoff/
      └── pending/
          ├── 0.31.0-W4-001.1.json
          ├── 0.31.0-W4-002.json
          └── ...

    JSON 檔案格式:
    {
        "ticket_id": "0.31.0-W4-001.1",
        "title": "任務標題",
        "what": "工作內容描述",
        "direction": "to-parent|to-child",
        "timestamp": "ISO8601 時間戳",
        "resumed_at": null,
        "chain": {...},
        ...
    }

    Args:
        project_root: 專案根目錄

    Returns:
        list - 待恢復任務列表 (按 timestamp 排序)
    """
    pending_tasks = []

    handoff_dir = project_root / ".claude" / "handoff" / "pending"

    if not handoff_dir.exists():
        logger.info(f"handoff/pending 目錄不存在: {handoff_dir}")
        return pending_tasks

    if not handoff_dir.is_dir():
        logger.warning(f"handoff/pending 不是目錄: {handoff_dir}")
        return pending_tasks

    # 掃描所有 .json 檔案
    try:
        for file_path in sorted(handoff_dir.glob("*.json")):
            logger.debug(f"掃描檔案: {file_path.name}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 檢查是否已被接手（有 resumed_at 時間戳表示已接手）
                resumed_at = data.get("resumed_at")
                if resumed_at is not None:
                    logger.debug(f"跳過已接手的任務: {file_path.stem} (resumed_at: {resumed_at})")
                    continue

                # 提取必要欄位
                ticket_id = data.get("ticket_id", file_path.stem)
                title = data.get("title", "無標題")
                direction = data.get("direction", "unknown")

                pending_tasks.append({
                    "ticket_id": ticket_id,
                    "title": title,
                    "direction": direction,
                    "file_path": str(file_path),
                    "timestamp": data.get("timestamp", "unknown"),
                    "what": data.get("what", ""),
                    "chain": data.get("chain", {}),
                    "from_status": data.get("from_status", "unknown"),
                })

                logger.debug(f"找到待恢復任務: {ticket_id} - {title}")

            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失敗 ({file_path.name}): {e}")
            except Exception as e:
                logger.warning(f"讀取檔案失敗 ({file_path.name}): {e}")

    except Exception as e:
        logger.error(f"掃描 handoff/pending 目錄失敗: {e}")

    logger.info(f"掃描完成，找到 {len(pending_tasks)} 個待恢復任務")

    # 按 timestamp 排序（最新優先）
    pending_tasks.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
    return pending_tasks

def mark_handoff_as_resumed(ticket_id: str, project_root: Path, logger) -> None:
    """
    標記 handoff 檔案為已接手（更新 resumed_at 欄位）

    Args:
        ticket_id: Ticket ID
        project_root: 專案根目錄
        logger: 日誌物件
    """
    handoff_dir = project_root / ".claude" / "handoff" / "pending"
    handoff_file = handoff_dir / f"{ticket_id}.json"

    if not handoff_file.exists():
        logger.warning(f"Handoff 檔案不存在: {handoff_file}")
        return

    try:
        with open(handoff_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 更新 resumed_at 欄位
        data["resumed_at"] = datetime.now().isoformat()

        with open(handoff_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"已標記 Handoff 為已接手: {ticket_id}")
    except Exception as e:
        logger.warning(f"標記 Handoff 失敗 ({ticket_id}): {e}")

def generate_auto_resume_message(selected_task: Dict[str, Any], all_tasks: List[Dict[str, Any]], logger) -> str:
    """
    生成完整的自動恢復訊息

    包含任務描述、任務鏈資訊、建議動作

    Args:
        selected_task: 選定的任務
        all_tasks: 所有待恢復任務
        logger: 日誌物件

    Returns:
        str - 格式化的恢復訊息
    """
    ticket_id = selected_task.get("ticket_id", "unknown")
    title = selected_task.get("title", "")
    what = selected_task.get("what", "")
    direction = selected_task.get("direction", "unknown")
    chain = selected_task.get("chain", {})

    message = "============================================================\n"
    message += "[自動恢復任務 Context]\n"
    message += "============================================================\n\n"

    message += f"任務: {ticket_id}\n"
    message += f"標題: {title}\n"
    message += f"方向: {direction}\n\n"

    if what:
        message += "--- 任務描述 ---\n"
        message += what + "\n\n"

    chain_root = chain.get("root", "N/A")
    chain_parent = chain.get("parent", "N/A")
    chain_depth = chain.get("depth", 0)

    message += "--- 任務鏈資訊 ---\n"
    message += f"Root: {chain_root}\n"
    message += f"Parent: {chain_parent}\n"
    message += f"Depth: {chain_depth}\n\n"

    message += "--- 建議動作 ---\n"
    message += f"/ticket track claim {ticket_id}\n\n"

    # 若有多個待恢復任務，顯示清單
    if len(all_tasks) > 1:
        message += "--- 其他待恢復任務 ---\n"
        for i, task in enumerate(all_tasks[1:5], 1):  # 最多顯示 4 個其他任務
            other_id = task.get("ticket_id", "unknown")
            other_title = task.get("title", "")
            message += f"  {i}. {other_id}: {other_title}\n"
        if len(all_tasks) > 5:
            message += f"  ... 還有 {len(all_tasks) - 5} 個任務\n"
        message += "\n"

    message += "============================================================\n"

    return message

def generate_reminder_message(pending_tasks: List[Dict[str, Any]], logger) -> str:
    """
    生成 Handoff 待恢復任務提醒訊息

    Args:
        pending_tasks: 待恢復任務列表
        logger: 日誌物件

    Returns:
        str - 格式化的提醒訊息
    """
    if not pending_tasks:
        return ""

    message = "============================================================\n"
    message += f"[Handoff 提醒] 有 {len(pending_tasks)} 個待恢復的任務\n"
    message += "============================================================\n\n"

    message += "待恢復任務：\n"
    for i, task in enumerate(pending_tasks, 1):
        ticket_id = task["ticket_id"]
        title = task["title"]
        direction = task["direction"]

        message += f"  {i}. {ticket_id}: {title}\n"
        message += f"     方向: {direction}\n"

    message += "\n執行提醒：\n"
    message += "  /ticket resume <id>        恢復指定任務 context\n"
    message += "  /ticket resume --list      查看完整清單\n\n"

    message += "============================================================\n"

    return message

def generate_hook_output(pending_tasks: List[Dict[str, Any]], project_root: Path, logger) -> Dict[str, Any]:
    """
    生成 Hook 輸出格式

    若有待恢復任務，顯示提醒訊息（純提醒模式，不自動標記）

    Args:
        pending_tasks: 待恢復任務列表
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        dict - Hook 輸出 JSON
    """
    # 若無待恢復任務，靜默跳過（不輸出任何訊息）
    if not pending_tasks:
        logger.info("無待恢復任務，不產生輸出")
        return {
            "suppressOutput": True
        }

    # 生成提醒訊息
    reminder_message = generate_reminder_message(pending_tasks, logger)

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": reminder_message
        },
        "suppressOutput": False
    }

def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化日誌
    2. 讀取 JSON 輸入（可選，SessionStart 可能無 stdin）
    3. 取得專案根目錄
    4. 掃描 .claude/handoff/pending/ 目錄
    5. 產生 Hook 輸出（自動載入或提醒）
    6. 輸出 JSON 結果

    Returns:
        int - Exit code (0 = 成功)
    """
    logger = setup_hook_logging("handoff-reminder-hook")

    try:
        # 步驟 1: 初始化日誌
        logger.info("Handoff 提醒 Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入（可選）
        input_data = read_json_from_stdin(logger)

        # 步驟 3: 取得專案根目錄
        project_root = get_project_root()
        logger.info(f"專案根目錄: {project_root}")

        # 步驟 4: 掃描待恢復任務
        pending_tasks = scan_handoff_pending_directory(project_root, logger)

        # 步驟 5: 產生 Hook 輸出（自動載入最新任務或靜默跳過）
        hook_output = generate_hook_output(pending_tasks, project_root, logger)

        # 步驟 6: 輸出 JSON 結果
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        logger.info("Hook 執行完成")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        # 錯誤時也靜默跳過（非阻塊）
        print(json.dumps({
            "suppressOutput": True
        }, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS  # 不中斷 Session 啟動

if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "handoff-reminder"))
