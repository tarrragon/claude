#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Handoff 自動恢復 Stop Hook (v2.2.0)

在對話終止時，檢查是否有未完成的 handoff 任務並阻止退出。

功能:
1. 檢查 stop flag 檔案是否存在且未過期（防重複觸發）
2. 讀取 session 狀態，若有 locked_ticket_id，提示用戶恢復
3. 掃描 .claude/handoff/pending/ 查找未恢復任務
   - GC：自動刪除已完成 Ticket 的 stale pending JSON
   - GC 例外：to-sibling / to-parent / to-child 類型保留（來源完成是預期狀態）
4. 有任務就阻止退出，無任務就靜默通過
5. 建立 stop flag 防止同一 session 重複觸發

v2.2.0 變更 (W3-005):
    - 修復 GC bug：to-sibling / to-parent / to-child 類型的 handoff，
      來源 Ticket completed 是預期狀態，不應被 GC 刪除
    - 新增 should_preserve_pending_json() 函式判斷是否保留
    - 改善 GC 日誌訊息，區分保留和刪除的原因

v2.1.0 變更:
    - 移除 scan_in_progress_tickets（不再主動建立 pending JSON）
    - 新增 GC：掃描時自動刪除已完成 Ticket 的 stale pending JSON
    - pending JSON 只由 /ticket handoff 明確建立

防重複觸發:
    使用固定的 flag 檔案路徑 .claude/handoff/.stop-blocked
    flag 檔案內容包含時間戳，過期時間為 300 秒（5 分鐘）
    同一 session 內的多次觸發在 5 分鐘內被抑制，新 session 時 flag 已過期
"""

import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, parse_ticket_frontmatter

EXIT_SUCCESS = 0

# 常數定義
STOP_FLAG_FILE = ".claude/handoff/.stop-blocked"
STOP_FLAG_EXPIRY_SECONDS = 300  # 5 分鐘過期
STATE_FILE_TEMPLATE = "/tmp/claude-handoff-state-{ppid}.json"
PENDING_DIR_NAME = ".claude/handoff/pending"
LOG_DIR_NAME = ".claude/hook-logs/handoff-auto-resume"
LOG_FILE_PREFIX = "stop-hook"
WORK_LOGS_DIR_NAME = "docs/work-logs"
TICKETS_SUBDIR_NAME = "tickets"
TODOLIST_FILE_NAME = "docs/todolist.yaml"


def get_project_root() -> Path:
    """
    取得專案根目錄

    Returns:
        Path - 專案根目錄
    """
    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if project_dir:
        return Path(project_dir)

    try:
        result = __import__("subprocess").run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except Exception:
        return Path.cwd()


def get_session_stop_flag() -> Path:
    """
    取得 session stop flag 檔案路徑

    使用固定的專案內 flag 檔案，相對於專案根目錄

    Returns:
        Path - flag 檔案的絕對路徑
    """
    project_root = get_project_root()
    return project_root / STOP_FLAG_FILE


def get_session_state_file() -> Path:
    """
    取得 session 狀態檔案路徑

    Returns:
        Path - 狀態檔案路徑
    """
    ppid = os.getppid()
    return Path(STATE_FILE_TEMPLATE.format(ppid=ppid))


def has_been_triggered_this_session(logger) -> bool:
    """
    檢查此 session 是否已觸發過 Stop hook，考慮 flag 過期時間

    如果 flag 檔案存在且未過期（< STOP_FLAG_EXPIRY_SECONDS），則認為已觸發
    如果 flag 已過期，則刪除並回傳 False（視為新 session）

    Returns:
        bool - 是否已觸發（且未過期）
    """
    flag_file = get_session_stop_flag()
    if not flag_file.exists():
        return False

    try:
        with open(flag_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        created_at_str = data.get("created_at")
        if not created_at_str:
            # flag 格式異常，移除它
            flag_file.unlink()
            return False

        created_at = datetime.fromisoformat(created_at_str)
        elapsed = (datetime.now() - created_at).total_seconds()

        if elapsed > STOP_FLAG_EXPIRY_SECONDS:
            # flag 已過期，移除它
            logger.debug(f"Stop flag 已過期 ({elapsed:.1f}s > {STOP_FLAG_EXPIRY_SECONDS}s)，刪除")
            flag_file.unlink()
            return False

        logger.debug(f"Stop flag 仍有效 ({elapsed:.1f}s 內)")
        return True

    except Exception as e:
        logger.warning(f"檢查 stop flag 失敗: {e}")
        return False


def mark_triggered_this_session(logger) -> None:
    """
    標記此 session 已觸發過 Stop hook，並記錄時間戳

    寫入固定 flag 檔案，包含建立時間，用於之後的過期檢查
    """
    flag_file = get_session_stop_flag()
    try:
        # 確保目錄存在
        flag_file.parent.mkdir(parents=True, exist_ok=True)

        # 寫入時間戳
        flag_data = {
            "created_at": datetime.now().isoformat(),
            "reason": "stop_hook_triggered"
        }
        with open(flag_file, 'w', encoding='utf-8') as f:
            json.dump(flag_data, f, ensure_ascii=False)

        logger.debug(f"建立 session stop flag: {flag_file}")
    except Exception as e:
        logger.warning(f"建立 session stop flag 失敗: {e}")


def read_session_state(logger) -> Optional[Dict[str, Any]]:
    """
    讀取 session 狀態檔案

    Returns:
        dict - session 狀態，若檔案不存在則回傳 None
    """
    state_file = get_session_state_file()

    if not state_file.exists():
        logger.debug(f"session 狀態檔案不存在: {state_file}")
        return None

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        logger.debug(f"讀取 session 狀態成功: {json.dumps(state)}")
        return state
    except json.JSONDecodeError as e:
        logger.warning(f"解析 session 狀態 JSON 失敗: {e}")
        return None
    except Exception as e:
        logger.warning(f"讀取 session 狀態檔案失敗: {e}")
        return None


def get_active_version(project_root: Path, logger) -> Optional[str]:
    """
    從 docs/todolist.yaml 取得活躍版本號

    Fallback：掃描 docs/work-logs/ 目錄取最新版本號。

    Args:
        project_root: 專案根目錄
        logger: 日誌記錄器

    Returns:
        str - 活躍版本號（如 "0.31.0"）；無法取得時回傳 None
    """
    todolist_file = project_root / TODOLIST_FILE_NAME

    # 嘗試從 todolist.yaml 讀取
    if todolist_file.exists():
        try:
            content = todolist_file.read_text(encoding='utf-8')
            # 簡易搜尋 status: "active" 的版本
            for line in content.split('\n'):
                if 'version:' in line:
                    current_version = None
                    version_match = re.search(r'"([\d.]+)"', line)
                    if version_match:
                        current_version = version_match.group(1)
                    else:
                        version_match = re.search(r"'([\d.]+)'", line)
                        if version_match:
                            current_version = version_match.group(1)

                    # 若未找到版本則跳過
                    if not current_version:
                        continue

                    # 接下來檢查 status 行
                    for next_line in content[content.index(line):].split('\n')[1:5]:
                        if 'status:' in next_line:
                            if 'active' in next_line:
                                logger.debug(f"從 todolist.yaml 找到活躍版本: {current_version}")
                                return current_version
                            break

        except Exception as e:
            logger.warning(f"解析 todolist.yaml 失敗: {e}")

    # Fallback：掃描 docs/work-logs/ 目錄
    work_logs_dir = project_root / WORK_LOGS_DIR_NAME
    if work_logs_dir.exists():
        try:
            version_dirs = sorted(
                [d for d in work_logs_dir.iterdir() if d.is_dir() and d.name.startswith('v')],
                reverse=True
            )
            if version_dirs:
                version = version_dirs[0].name[1:]  # 移除 'v' 前綴
                logger.debug(f"Fallback：掃描 work-logs 找到版本: {version}")
                return version
        except Exception as e:
            logger.warning(f"掃描 work-logs 目錄失敗: {e}")

    return None


def is_ticket_completed(project_root: Path, ticket_id: str, logger) -> bool:
    """
    檢查 Ticket 是否已完成（status: completed）

    Args:
        project_root: 專案根目錄
        ticket_id: Ticket ID
        logger: 日誌記錄器

    Returns:
        bool - 是否已完成
    """
    try:
        # 解析版本號
        parts = ticket_id.split('-')
        if not parts:
            return False

        version = parts[0]
        ticket_path = project_root / WORK_LOGS_DIR_NAME / f"v{version}" / TICKETS_SUBDIR_NAME / f"{ticket_id}.md"

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


def scan_in_progress_tickets(project_root: Path, logger) -> list:
    """
    [DEPRECATED] 掃描 in_progress 的 Tickets 並為其建立 pending JSON

    v2.1.0 起不再由 Stop hook 呼叫。
    原因：此函式為所有 in_progress Ticket 建立 pending JSON，
    不分是否與當前 session 相關，導致 Stop hook 誤阻塞。
    pending JSON 應只由 /ticket handoff 明確建立。

    Args:
        project_root: 專案根目錄
        logger: 日誌記錄器

    Returns:
        list - 建立的 pending JSON 的 ticket_id 列表
    """
    active_version = get_active_version(project_root, logger)
    if not active_version:
        logger.warning("無法取得活躍版本")
        return []

    tickets_dir = project_root / WORK_LOGS_DIR_NAME / f"v{active_version}" / TICKETS_SUBDIR_NAME
    created_tickets = []

    if not tickets_dir.exists():
        logger.debug(f"Tickets 目錄不存在: {tickets_dir}")
        return created_tickets

    try:
        for file_path in sorted(tickets_dir.glob("*.md")):
            try:
                # 解析 frontmatter
                frontmatter = parse_ticket_frontmatter(file_path, logger)
                if not frontmatter:
                    continue

                # 檢查狀態是否為 in_progress
                status = frontmatter.get('status', '').lower()
                if status != 'in_progress':
                    continue

                ticket_id = frontmatter.get('id')
                if not ticket_id:
                    continue

                # 檢查 pending JSON 是否已存在
                pending_dir = project_root / PENDING_DIR_NAME
                pending_file = pending_dir / f"{ticket_id}.json"

                if pending_file.exists():
                    logger.debug(f"Pending JSON 已存在: {ticket_id}")
                    continue

                # 建立 pending JSON
                pending_dir.mkdir(parents=True, exist_ok=True)
                title = frontmatter.get('title', '')
                what = frontmatter.get('what', '')

                pending_data = {
                    "ticket_id": ticket_id,
                    "title": title,
                    "direction": "continuation",
                    "timestamp": datetime.now().isoformat(),
                    "from_status": "in_progress",
                    "what": what,
                    "resumed_at": None
                }

                with open(pending_file, "w", encoding="utf-8") as f:
                    json.dump(pending_data, f, ensure_ascii=False, indent=2)

                logger.info(f"為 in_progress ticket 建立 pending JSON: {ticket_id}")
                created_tickets.append(ticket_id)

            except Exception as e:
                logger.warning(f"處理 Ticket 檔案失敗 ({file_path.name}): {e}")

    except Exception as e:
        logger.error(f"掃描 in_progress Tickets 失敗: {e}")

    return created_tickets


def should_preserve_pending_json(direction: str, logger) -> bool:
    """
    判斷是否應保留 pending JSON，即使來源 Ticket 已完成

    direction 為 to-sibling / to-parent / to-child 的 handoff，
    來源 Ticket 已 completed 是預期狀態，應保留 pending JSON。

    direction 格式：
    - "to-sibling" (無目標) 或 "to-sibling:TARGET_ID" (帶目標 ID)
    - "to-parent" (無目標) 或 "to-parent:TARGET_ID" (帶目標 ID)
    - "to-child" (無目標) 或 "to-child:TARGET_ID" (帶目標 ID)

    Args:
        direction: handoff 的 direction 欄位
        logger: 日誌記錄器

    Returns:
        bool - 是否應保留 pending JSON
    """
    # 任務鏈類型（來源已完成是預期狀態）
    # direction 格式為 "to-sibling" 或 "to-sibling:TARGET_ID"
    chain_directions = {"to-sibling", "to-parent", "to-child"}
    direction_type = direction.split(":")[0]

    if direction_type in chain_directions:
        logger.debug(f"handoff 類型 '{direction}' 應保留已完成 Ticket 的 pending JSON")
        return True

    return False


def scan_pending_handoff_tasks(project_root: Path, logger) -> list:
    """
    掃描待恢復的 handoff 任務（resumed_at == null 的任務）

    過濾已完成的 Ticket（status: completed），並自動清理 stale JSON。

    GC 機制：
    - resumed_at 不為 null → 已接手，跳過
    - Ticket 已 completed + direction 不是 to-sibling/to-parent/to-child
      → 刪除 pending JSON（GC）
    - Ticket 已 completed + direction 是任務鏈類型
      → 保留 pending JSON（來源完成是預期狀態）
    - Ticket 未完成且 resumed_at 為 null → 收集為待恢復

    Args:
        project_root: 專案根目錄
        logger: 日誌記錄器

    Returns:
        list - 待恢復任務的 dict 列表，含 ticket_id、title、direction
    """
    pending_dir = project_root / PENDING_DIR_NAME
    pending_tasks = []

    if not pending_dir.exists():
        logger.debug(f"pending 目錄不存在: {pending_dir}")
        return pending_tasks

    try:
        for file_path in sorted(pending_dir.glob("*.json")):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 只收集未恢復的任務
                if data.get("resumed_at") is None:
                    ticket_id = data.get("ticket_id", file_path.stem)
                    title = data.get("title", "無標題")
                    direction = data.get("direction", "unknown")

                    # 檢查對應 Ticket 是否已完成
                    if is_ticket_completed(project_root, ticket_id, logger):
                        # GC：檢查 direction，判斷是否應保留
                        if should_preserve_pending_json(direction, logger):
                            pending_tasks.append({
                                "ticket_id": ticket_id,
                                "title": title,
                                "direction": direction
                            })
                            logger.debug(
                                f"保留任務鏈類型 handoff 的 pending JSON "
                                f"({ticket_id}, direction={direction})"
                            )
                        else:
                            # 刪除已完成 Ticket 的 stale pending JSON
                            file_path.unlink()
                            logger.info(
                                f"GC: 刪除已完成 Ticket 的 pending JSON "
                                f"({ticket_id}, direction={direction})"
                            )
                    else:
                        pending_tasks.append({
                            "ticket_id": ticket_id,
                            "title": title,
                            "direction": direction
                        })
                        logger.debug(f"找到待恢復任務: {ticket_id}")

            except Exception as e:
                logger.warning(f"讀取 handoff 檔案失敗 ({file_path.name}): {e}")

    except Exception as e:
        logger.error(f"掃描 pending 目錄失敗: {e}")

    return pending_tasks


def format_pending_tasks_list(pending_tasks: list) -> str:
    """
    格式化待恢復任務清單供 stderr 輸出

    Args:
        pending_tasks: 待恢復任務列表 (dict with ticket_id, title, direction)

    Returns:
        str - 格式化的任務清單
    """
    if not pending_tasks:
        return ""

    message = "\n" + "=" * 70 + "\n"
    message += "[Handoff] 偵測到多個未完成任務，請選擇要恢復的任務：\n"
    message += "=" * 70 + "\n\n"

    for i, task in enumerate(pending_tasks, 1):
        ticket_id = task.get("ticket_id", "unknown")
        title = task.get("title", "無標題")
        direction = task.get("direction", "unknown")

        message += f"{i}. [{ticket_id}] {title}\n"
        message += f"   方向: {direction}\n"
        message += f"   恢復命令: /ticket resume {ticket_id}\n\n"

    message += "=" * 70 + "\n"
    message += "請執行上述恢復命令之一以選擇要恢復的任務。\n"
    message += "=" * 70 + "\n"

    return message


def generate_hook_output(logger) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    邏輯:
    1. 若此 session 已觸發過，直接跳過（防重複）
    2. 讀取 session 狀態，若有 locked_ticket_id，提示恢復
    3. 掃描 pending 目錄，找未恢復任務（含 GC 清理已完成 Ticket）
    4. 有任務就阻塊：
       - 單任務時：回傳恢復命令
       - 多任務時：stderr 列出清單，exit 2 阻止停止
    5. 無任務就靜默通過
    6. 建立 stop flag

    注意: pending JSON 只由 /ticket handoff 明確建立，
    Stop hook 不主動建立（避免為不相關的 in_progress Ticket 產生假陽性）。

    Returns:
        dict - Hook 輸出 JSON
    """
    try:
        # Step 1: 防重複觸發
        if has_been_triggered_this_session(logger):
            logger.info("此 session 已觸發過 Stop hook，跳過")
            return {"suppressOutput": True}

        project_root = get_project_root()
        logger.debug(f"專案根目錄: {project_root}")

        # Step 2: 讀取 session 狀態
        session_state = read_session_state(logger)
        pending_tasks = None

        if session_state and session_state.get("locked_ticket_id"):
            ticket_id = session_state["locked_ticket_id"]
            logger.info(f"從 session 狀態找到鎖定任務: {ticket_id}")
            pending_tasks = [{"ticket_id": ticket_id, "title": "", "direction": ""}]
        else:
            # Step 3: 掃描 pending 目錄（含 GC 清理已完成 Ticket 的 stale JSON）
            pending_tasks = scan_pending_handoff_tasks(project_root, logger)
            if pending_tasks:
                logger.info(f"掃描 pending 目錄找到 {len(pending_tasks)} 個待恢復任務")

        # Step 4: 決策
        if pending_tasks:
            logger.info(f"偵測到 {len(pending_tasks)} 個未完成任務")
            mark_triggered_this_session(logger)

            # 單任務時行為不變（向後相容）
            if len(pending_tasks) == 1:
                task = pending_tasks[0]
                ticket_id = task.get("ticket_id")
                logger.info(f"單任務，提示恢復: {ticket_id}")
                return {
                    "decision": "block",
                    "reason": f"/ticket resume {ticket_id}"
                }
            else:
                # 多任務時：列出清單到 stderr，exit 2 阻止停止
                tasks_list = format_pending_tasks_list(pending_tasks)
                logger.warning(f"多任務清單:\n{tasks_list}")

                # 輸出到 stderr（exit 2）
                print(tasks_list, file=sys.stderr)

                return {
                    "decision": "block",
                    "reason": "多個待恢復任務，請選擇要恢復的任務"
                }
        else:
            logger.info("無未完成任務，允許對話終止")
            return {"suppressOutput": True}

    except Exception as e:
        logger.critical(f"Stop hook 執行錯誤: {e}", exc_info=True)
        return {"suppressOutput": True}


def main() -> int:
    """
    主入口點

    Returns:
        int - Exit code (0 = 成功)
    """
    logger = setup_hook_logging("handoff-auto-resume-stop")

    try:
        logger.info("Handoff 自動恢復 Stop Hook 啟動")

        hook_output = generate_hook_output(logger)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        logger.info("Hook 執行完成")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 主程序執行錯誤: {e}", exc_info=True)
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "handoff-auto-resume-stop"))
