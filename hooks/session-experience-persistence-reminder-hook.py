#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Session 經驗持久化提醒 Hook (v1.0.0)

Stop hook — 在 session 結束前提醒 Claude 評估是否有未持久化的重要 context。

目的:
    對沖 /clear 建議。當 session 中建立了審查/分析/review 類型的 Ticket，
    這些 Ticket 的執行可能需要當前 session 的 context 作為輸入。
    此 hook 提醒 Claude（非使用者）在結束前評估 context 保存需求。

運作方式:
    1. 掃描今天建立的 pending 狀態 Ticket
    2. 識別「context 敏感」的 Ticket（審查、分析、review 類型）
    3. 若有，透過 reason 欄位提醒 Claude 評估 context 保存需求
    4. 若無，靜默通過

設計原則:
    - 提醒對象是 Claude（系統），不是使用者
    - 不阻止退出（僅在有 context 敏感 Ticket 時輸出提醒）
    - 與 handoff-auto-resume-stop-hook 互補，不衝突

來源: 0.16.3-W4-001
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime

# 加入 hook_utils 路徑
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    get_project_root,
    find_ticket_files,
    parse_ticket_frontmatter,
)

# --- 常數 ---

# 判定為「context 敏感」的關鍵詞（出現在 title 或 what 欄位）
# 只含「需要當前 session context 作為輸入」的審查/分析類型
# 排除「驗證」（通常是獨立的測試操作，不依賴 session context）
CONTEXT_SENSITIVE_KEYWORDS = [
    "審查", "review", "audit",
    "分析", "analysis",
    "多視角", "code review",
    "檢討", "評估報告",
]

# 判定為「context 敏感」的 Ticket 類型
CONTEXT_SENSITIVE_TYPES = {"ANA", "analysis"}

# 只檢查這些狀態的 Ticket（尚未執行的）
PENDING_STATUSES = {"pending", "in_progress"}


def is_created_today(frontmatter: dict) -> bool:
    """
    檢查 Ticket 是否今天建立。

    Args:
        frontmatter: Ticket frontmatter 字典

    Returns:
        bool - 是否今天建立
    """
    created_str = frontmatter.get("created", "")
    if not created_str:
        return False

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        # created 欄位可能是 '2026-04-01' 或 '2026-04-01T12:00:00'
        return str(created_str).startswith(today)
    except Exception:
        return False


def is_context_sensitive(frontmatter: dict) -> bool:
    """
    判斷 Ticket 是否為「context 敏感」類型 — 執行時可能需要建立它的 session context。

    判斷依據:
    1. Ticket 類型是 ANA/analysis
    2. title 或 what 欄位包含審查/review/分析等關鍵詞

    Args:
        frontmatter: Ticket frontmatter 字典

    Returns:
        bool - 是否為 context 敏感
    """
    ticket_type = str(frontmatter.get("type", "")).upper()
    if ticket_type in CONTEXT_SENSITIVE_TYPES:
        return True

    # 檢查 title 和 what 欄位
    title = str(frontmatter.get("title", "")).lower()
    what = str(frontmatter.get("what", "")).lower()
    text_to_check = f"{title} {what}"

    for keyword in CONTEXT_SENSITIVE_KEYWORDS:
        if keyword.lower() in text_to_check:
            return True

    return False


def scan_context_sensitive_tickets(project_root: Path, logger) -> list:
    """
    掃描今天建立、尚未執行、且為 context 敏感類型的 Ticket。

    跨版本掃描所有 ticket 目錄，不依賴 todolist 的 active 版本。

    Args:
        project_root: 專案根目錄
        logger: 日誌記錄器

    Returns:
        list[dict] - context 敏感 Ticket 清單，各含 id、title、type
    """
    sensitive_tickets = []

    ticket_files = find_ticket_files(project_root, logger=logger)
    if not ticket_files:
        logger.debug("無 Ticket 檔案")
        return sensitive_tickets

    for ticket_path in ticket_files:
        try:
            frontmatter = parse_ticket_frontmatter(ticket_path, logger)
            if not frontmatter:
                continue

            status = str(frontmatter.get("status", "")).lower()
            if status not in PENDING_STATUSES:
                continue

            if not is_created_today(frontmatter):
                continue

            if not is_context_sensitive(frontmatter):
                continue

            ticket_id = frontmatter.get("id", ticket_path.stem)
            title = frontmatter.get("title", "無標題")
            ticket_type = frontmatter.get("type", "unknown")

            sensitive_tickets.append({
                "id": ticket_id,
                "title": title,
                "type": ticket_type,
            })
            logger.info(f"偵測到 context 敏感 Ticket: {ticket_id} ({title})")

        except Exception as e:
            logger.warning(f"解析 Ticket 失敗 ({ticket_path.name}): {e}")

    return sensitive_tickets


def format_reminder_reason(tickets: list) -> str:
    """
    格式化提醒訊息（reason 欄位，Claude 讀取）。

    Args:
        tickets: context 敏感 Ticket 清單

    Returns:
        str - 提醒訊息
    """
    ticket_list = "\n".join(
        f"  - {t['id']}: {t['title']} (type: {t['type']})"
        for t in tickets
    )

    return (
        f"[Session Context 保護提醒]\n"
        f"偵測到 {len(tickets)} 個今天建立的 context 敏感 Ticket（審查/分析類）尚未完成：\n"
        f"{ticket_list}\n\n"
        f"這些 Ticket 的執行可能需要當前 session 的 context（決策脈絡、分析依據、討論背景）。\n"
        f"請評估：\n"
        f"1. 這些 Ticket 是否需要當前 session 的 context 作為輸入？\n"
        f"2. 若需要，相關 context 是否已持久化到 memory/ticket/worklog？\n"
        f"3. 若未持久化，應先記錄關鍵 context 再結束 session。\n"
        f"禁止在未評估的情況下直接建議使用者 /clear。"
    )


def generate_hook_output(logger) -> dict:
    """
    生成 Hook 輸出。

    Returns:
        dict - Hook 輸出 JSON
    """
    try:
        project_root = get_project_root()
        logger.debug(f"專案根目錄: {project_root}")

        sensitive_tickets = scan_context_sensitive_tickets(project_root, logger)

        if not sensitive_tickets:
            logger.info("無 context 敏感的待執行 Ticket，靜默通過")
            return {"suppressOutput": True}

        reason = format_reminder_reason(sensitive_tickets)
        logger.info(f"輸出 context 保護提醒（{len(sensitive_tickets)} 個 Ticket）")

        # 輸出到 stderr（系統可見）
        print(f"\n{reason}", file=sys.stderr)

        # 不阻止退出，只輸出提醒
        return {"suppressOutput": True}

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        return {"suppressOutput": True}


def main() -> int:
    """主入口點。"""
    logger = setup_hook_logging("session-experience-persistence-reminder")

    try:
        logger.info("Session 經驗持久化提醒 Hook 啟動")

        hook_output = generate_hook_output(logger)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        logger.info("Hook 執行完成")
        return 0

    except Exception as e:
        logger.critical(f"Hook 主程序執行錯誤: {e}", exc_info=True)
        print(json.dumps({"suppressOutput": True}))
        return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-experience-persistence-reminder"))
