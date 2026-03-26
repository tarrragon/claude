#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
技術債務提醒 Hook

在 Session 啟動時檢查當前版本是否有待處理的技術債務。

功能:
1. 從 docs/todolist.yaml 取得當前版本（專案類型無關）
2. 掃描 docs/work-logs/v{version}/tickets/ 目錄
3. 檢查所有 TD Ticket 的 frontmatter status
4. 若有 pending 的 TD → 顯示警告

使用方式:
    SessionStart Hook 自動觸發，或手動測試:
    uv run .claude/hooks/tech-debt-reminder.py

輸入格式:
    SessionStart Hook 提供的 JSON (stdin)

環境變數:
    CLAUDE_PROJECT_DIR: 專案根目錄
    HOOK_DEBUG: 啟用詳細日誌 (true/false)
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    get_current_version_from_todolist,
)

# 全域常數
EXIT_SUCCESS = 0
EXIT_ERROR = 1

def find_tickets_directory(
    project_root: Path,
    version: str,
    logger
) -> Optional[Path]:
    """
    尋找版本的 tickets 目錄

    Args:
        project_root: 專案根目錄
        version: 版本號（如 "0.2.0"）

    Returns:
        Path - tickets 目錄路徑，若找不到則回傳 None
    """
    work_logs_dir = project_root / "docs" / "work-logs"

    if not work_logs_dir.exists():
        logger.info(f"work-logs 目錄不存在: {work_logs_dir}")
        return None

    tickets_dir = work_logs_dir / f"v{version}" / "tickets"

    if tickets_dir.exists() and tickets_dir.is_dir():
        logger.info(f"找到 tickets 目錄: {tickets_dir}")
        return tickets_dir

    logger.info(f"tickets 目錄不存在: {tickets_dir}")
    return None

def extract_frontmatter(file_path: Path, logger) -> Optional[Dict[str, Any]]:
    """
    從 Markdown 檔案提取 frontmatter

    格式:
    ---
    ticket_id: 0.20.0-TD-001
    ticket_type: "tech-debt"
    status: pending
    ...
    ---

    Args:
        file_path: Markdown 檔案路徑

    Returns:
        dict - Frontmatter 內容，若失敗則回傳 None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取 frontmatter (--- ... ---)
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not match:
            logger.debug(f"檔案不包含 frontmatter: {file_path.name}")
            return None

        frontmatter_text = match.group(1)

        # 解析 YAML
        frontmatter = yaml.safe_load(frontmatter_text)
        return frontmatter

    except Exception as e:
        logger.warning(f"提取 frontmatter 失敗 ({file_path.name}): {e}")
        return None

def scan_tech_debt_tickets(tickets_dir: Path, logger) -> List[Dict[str, Any]]:
    """
    掃描目錄中的所有 Tech Debt Ticket

    過濾條件:
    1. 檔案副檔名為 .md
    2. 檔案名稱包含 "TD" (例如 0.20.0-TD-001.md)
    3. frontmatter 中 ticket_type == "tech-debt"
    4. frontmatter 中 status == "pending"

    Args:
        tickets_dir: Tickets 目錄

    Returns:
        list - 符合條件的 TD Ticket 列表
    """
    pending_tickets = []

    if not tickets_dir.exists():
        logger.info(f"tickets 目錄不存在: {tickets_dir}")
        return pending_tickets

    for file_path in sorted(tickets_dir.glob("*.md")):
        # 檔案名稱檢查
        if "TD" not in file_path.name:
            continue

        # 提取 frontmatter
        frontmatter = extract_frontmatter(file_path, logger)
        if not frontmatter:
            continue

        # 檢查 ticket_type 和 status
        ticket_type = frontmatter.get("ticket_type", "")
        status = frontmatter.get("status", "")

        if ticket_type == "tech-debt" and status == "pending":
            ticket_id = frontmatter.get("ticket_id", file_path.stem)
            pending_tickets.append({
                "ticket_id": ticket_id,
                "file_path": str(file_path),
                "status": status,
                "risk_level": frontmatter.get("risk_level", "unknown"),
                "target": frontmatter.get("target", "unknown"),
                "version": frontmatter.get("version", "unknown")
            })

            logger.debug(f"找到 pending TD Ticket: {ticket_id}")

    logger.info(f"掃描完成，找到 {len(pending_tickets)} 個 pending TD Ticket")
    return pending_tickets

def generate_warning_message(pending_tickets: List[Dict[str, Any]], version: str) -> str:
    """
    生成技術債務警告訊息

    Args:
        pending_tickets: 待處理 TD Ticket 列表
        version: 當前版本

    Returns:
        str - 格式化的警告訊息
    """
    if not pending_tickets:
        return ""

    # 解析版本系列
    version_parts = version.split('.')
    version_series = f"{version_parts[0]}.{version_parts[1]}.x" if len(version_parts) >= 2 else version

    message = f"""⚠️ 技術債務提醒

當前版本 v{version_series} 有 {len(pending_tickets)} 個待處理技術債務：

"""

    for i, ticket in enumerate(pending_tickets, 1):
        ticket_id = ticket["ticket_id"]
        target = ticket["target"]
        risk_level = ticket["risk_level"]

        message += f"  {i}. {ticket_id}: {target} (風險等級: {risk_level})\n"

    message += f"""
建議：
  1. 在開始新功能開發前處理這些技術債務
  2. 或使用 /ticket track 將目標版本延後
  3. 查看詳細 Ticket: docs/work-logs/v*/tickets/

---

_此提醒由 tech-debt-reminder Hook 自動生成_
"""

    return message

def generate_hook_output(
    pending_tickets: List[Dict[str, Any]],
    version: str,
    logger
) -> Dict[str, Any]:
    """
    生成 Hook 輸出格式

    Args:
        pending_tickets: 待處理 TD Ticket 列表
        version: 當前版本
        logger: 日誌物件

    Returns:
        dict - Hook 輸出 JSON
    """
    # 若無 pending tickets，靜默跳過（不輸出任何訊息）
    if not pending_tickets:
        logger.info("無 pending 技術債務，不產生輸出")
        return {
            "suppressOutput": True
        }

    # 生成警告訊息
    warning_message = generate_warning_message(pending_tickets, version)

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": warning_message
        },
        "suppressOutput": False
    }

def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化日誌
    2. 讀取 JSON 輸入（Session 資訊）
    3. 從 todolist.yaml 取得版本號
    4. 尋找 tickets 目錄
    5. 掃描 pending TD Ticket
    6. 產生 Hook 輸出
    7. 輸出 JSON 結果

    Returns:
        int - Exit code (0 = 成功)
    """
    logger = setup_hook_logging("tech-debt-reminder")
    try:
        # 步驟 1: 初始化日誌
        logger.info("技術債務提醒 Hook 啟動")

        # 靜默跳過時的統一輸出（確保 stdout 不為空）
        suppress_json = json.dumps({"suppressOutput": True})

        # 步驟 2: 讀取 JSON 輸入
        try:
            input_data = read_json_from_stdin(logger)
        except ValueError:
            logger.info("無 stdin 輸入，靜默跳過")
            print(suppress_json)
            return EXIT_SUCCESS

        # 步驟 3: 取得專案根目錄
        project_root = get_project_root()
        logger.info(f"專案根目錄: {project_root}")

        # 步驟 4: 從 todolist.yaml 取得版本（專案類型無關）
        version = get_current_version_from_todolist(project_root, logger)
        if not version:
            logger.info("無法取得版本號，靜默跳過")
            print(suppress_json)
            return EXIT_SUCCESS

        # 步驟 5: 尋找 tickets 目錄
        tickets_dir = find_tickets_directory(project_root, version, logger)
        if not tickets_dir:
            logger.info("tickets 目錄不存在，靜默跳過")
            print(suppress_json)
            return EXIT_SUCCESS

        # 步驟 6: 掃描 pending TD Ticket
        pending_tickets = scan_tech_debt_tickets(tickets_dir, logger)

        # 步驟 7: 產生 Hook 輸出
        hook_output = generate_hook_output(pending_tickets, version, logger)

        # 步驟 10: 輸出 JSON 結果
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
    sys.exit(run_hook_safely(main, "tech-debt-reminder"))
