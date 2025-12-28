#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Frontmatter 式 Ticket 追蹤系統

主線程和代理人共用的 Ticket 狀態追蹤工具。
使用 frontmatter_parser 模組進行 Markdown Ticket 狀態管理。

使用方式:
    uv run .claude/hooks/ticket-tracker.py <command> [options]

命令:
    claim <ticket_id>       接手 Ticket
    complete <ticket_id>    標記完成
    release <ticket_id>     放棄 Ticket
    query <ticket_id>       查詢單一 Ticket
    list [--filter]         列出 Tickets
    summary [--version]     快速摘要
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 導入 frontmatter_parser
sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_parser import (
    read_ticket, update_frontmatter, list_tickets, detect_format
)


# 常數定義
WORK_LOGS_DIR = Path("docs/work-logs")
TICKETS_DIR = "tickets"  # Markdown Ticket 檔案目錄
CSV_FILENAME = "tickets.csv"  # 舊版本 CSV 檔案名稱

# 狀態常數
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"


def get_project_root() -> Path:
    """取得專案根目錄"""
    # 從當前目錄往上找 pubspec.yaml
    current = Path.cwd()
    while current != current.parent:
        if (current / "pubspec.yaml").exists():
            return current
        current = current.parent
    return Path.cwd()


def get_current_version() -> Optional[str]:
    """自動偵測當前版本（從最新的版本資料夾）"""
    root = get_project_root()
    work_logs = root / WORK_LOGS_DIR

    if not work_logs.exists():
        return None

    # 找出所有 vX.Y.Z 格式的資料夾
    version_pattern = re.compile(r"^v\d+\.\d+\.\d+$")
    versions = [
        d.name for d in work_logs.iterdir()
        if d.is_dir() and version_pattern.match(d.name)
    ]

    if not versions:
        return None

    # 按版本號排序，取最新的
    def version_key(v: str) -> tuple:
        parts = v[1:].split(".")  # 去掉 'v' 前綴
        return tuple(int(p) for p in parts)

    versions.sort(key=version_key, reverse=True)
    return versions[0]


def get_tickets_dir_path(version: Optional[str] = None) -> Path:
    """取得 Tickets 目錄路徑"""
    if version is None:
        version = get_current_version()

    if version is None:
        raise ValueError("無法偵測版本，請使用 --version 指定")

    root = get_project_root()
    return root / WORK_LOGS_DIR / version / TICKETS_DIR


def find_ticket_file(tickets_dir: Path, ticket_id: str) -> Optional[Path]:
    """在目錄中尋找 Ticket Markdown 檔案"""
    md_file = tickets_dir / f"{ticket_id}.md"
    return md_file if md_file.exists() else None


def get_status_icon(ticket) -> str:
    """取得狀態圖示（使用 TicketData 物件）"""
    if ticket.status == STATUS_COMPLETED:
        return "✅"
    elif ticket.status == STATUS_IN_PROGRESS:
        return "🔄"
    else:
        return "⏸️"


# ============ 向後相容性支援（v0.15.x 舊版本 CSV 格式唯讀） ============

def read_csv_tickets(csv_path: Path) -> list[dict]:
    """讀取舊版本 CSV 格式的 Tickets（唯讀支援）"""
    import csv
    if not csv_path.exists():
        return []

    tickets = []
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            tickets = list(reader) if reader else []
    except Exception:
        pass

    return tickets


def get_tickets_from_version(version: str) -> tuple[list, str]:
    """
    獲取版本的 Tickets，自動偵測格式（Markdown 或 CSV）

    Returns:
        (tickets, format_type) - 其中 format_type 為 'markdown', 'csv', 或 'unknown'
    """
    root = get_project_root()
    version_dir = root / WORK_LOGS_DIR / version

    # 檢查 Markdown 格式（新版本）
    tickets_dir = version_dir / TICKETS_DIR
    if tickets_dir.exists() and tickets_dir.is_dir():
        md_files = list(tickets_dir.glob("*.md"))
        if md_files:
            try:
                return list_tickets(tickets_dir), "markdown"
            except Exception:
                pass

    # 檢查 CSV 格式（舊版本）
    csv_path = version_dir / CSV_FILENAME
    if csv_path.exists():
        return read_csv_tickets(csv_path), "csv"

    return [], "unknown"


def get_elapsed_time(started_at: str) -> str:
    """計算經過時間"""
    if not started_at:
        return ""

    try:
        start = datetime.fromisoformat(started_at)
        elapsed = datetime.now() - start

        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)

        if hours > 0:
            return f"(已 {hours}h{minutes}m)"
        else:
            return f"(已 {minutes}m)"
    except ValueError:
        return ""


# ============ 命令實作 ============


def cmd_claim(args: argparse.Namespace) -> int:
    """接手 Ticket - 更新 frontmatter 的 assigned 和 started_at 欄位"""
    # 先偵測格式
    version = args.version or get_current_version()
    if not version:
        print("❌ 無法偵測版本，請使用 --version 指定")
        return 1

    root = get_project_root()
    version_dir = root / WORK_LOGS_DIR / version
    format_type = detect_format(version_dir)

    # CSV 格式（舊版本）不支援更新操作
    if format_type == "csv":
        print(f"⚠️  {version} 使用舊版 CSV 格式（唯讀模式）")
        print("   claim 命令在 v0.15.x 版本不支援")
        print("   請升級到 v0.16.0+ 以使用新的 Markdown Ticket 系統")
        return 1

    try:
        tickets_dir = get_tickets_dir_path(args.version)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    md_file = find_ticket_file(tickets_dir, args.ticket_id)
    if not md_file:
        print(f"❌ 找不到 Ticket {args.ticket_id}")
        return 1

    try:
        ticket = read_ticket(md_file)
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return 1

    # 檢查狀態
    if ticket.assigned:
        print(f"⚠️  {args.ticket_id} 已被接手")
        return 1
    if ticket.status == STATUS_COMPLETED:
        print(f"⚠️  {args.ticket_id} 已完成")
        return 1

    # 更新 frontmatter
    now = datetime.now()
    try:
        update_frontmatter(md_file, {
            "assigned": True,
            "started_at": now,
            "status": STATUS_IN_PROGRESS,
        })
    except Exception as e:
        print(f"❌ 更新失敗: {e}")
        return 1

    print(f"✅ 已接手 {args.ticket_id}")
    print(f"   開始時間: {now.isoformat()}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """標記完成 - 更新 frontmatter 的 status 和 completed_at 欄位"""
    # 先偵測格式
    version = args.version or get_current_version()
    if not version:
        print("❌ 無法偵測版本，請使用 --version 指定")
        return 1

    root = get_project_root()
    version_dir = root / WORK_LOGS_DIR / version
    format_type = detect_format(version_dir)

    # CSV 格式（舊版本）不支援更新操作
    if format_type == "csv":
        print(f"⚠️  {version} 使用舊版 CSV 格式（唯讀模式）")
        print("   complete 命令在 v0.15.x 版本不支援")
        print("   請升級到 v0.16.0+ 以使用新的 Markdown Ticket 系統")
        return 1

    try:
        tickets_dir = get_tickets_dir_path(args.version)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    md_file = find_ticket_file(tickets_dir, args.ticket_id)
    if not md_file:
        print(f"❌ 找不到 Ticket {args.ticket_id}")
        return 1

    try:
        ticket = read_ticket(md_file)
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return 1

    # 檢查狀態
    if ticket.status == STATUS_COMPLETED:
        print(f"⚠️  {args.ticket_id} 已完成")
        return 1

    # 更新 frontmatter
    now = datetime.now()
    try:
        update_frontmatter(md_file, {
            "status": STATUS_COMPLETED,
            "completed_at": now,
        })
    except Exception as e:
        print(f"❌ 更新失敗: {e}")
        return 1

    elapsed = get_elapsed_time(
        ticket.started_at.isoformat() if ticket.started_at else ""
    )
    print(f"✅ 已完成 {args.ticket_id} {elapsed}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    """放棄 Ticket - 更新 frontmatter 的 assigned 和 started_at 欄位"""
    # 先偵測格式
    version = args.version or get_current_version()
    if not version:
        print("❌ 無法偵測版本，請使用 --version 指定")
        return 1

    root = get_project_root()
    version_dir = root / WORK_LOGS_DIR / version
    format_type = detect_format(version_dir)

    # CSV 格式（舊版本）不支援更新操作
    if format_type == "csv":
        print(f"⚠️  {version} 使用舊版 CSV 格式（唯讀模式）")
        print("   release 命令在 v0.15.x 版本不支援")
        print("   請升級到 v0.16.0+ 以使用新的 Markdown Ticket 系統")
        return 1

    try:
        tickets_dir = get_tickets_dir_path(args.version)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    md_file = find_ticket_file(tickets_dir, args.ticket_id)
    if not md_file:
        print(f"❌ 找不到 Ticket {args.ticket_id}")
        return 1

    try:
        ticket = read_ticket(md_file)
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return 1

    # 檢查狀態
    if not ticket.assigned:
        print(f"⚠️  {args.ticket_id} 尚未被接手")
        return 1
    if ticket.status == STATUS_COMPLETED:
        print(f"⚠️  {args.ticket_id} 已完成，無法放棄")
        return 1

    # 更新 frontmatter
    try:
        update_frontmatter(md_file, {
            "assigned": False,
            "started_at": None,
            "status": STATUS_PENDING,
        })
    except Exception as e:
        print(f"❌ 更新失敗: {e}")
        return 1

    print(f"✅ 已放棄 {args.ticket_id}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """查詢單一 Ticket"""
    # 自動偵測版本和格式
    version = args.version or get_current_version()
    if not version:
        print("❌ 無法偵測版本，請使用 --version 指定")
        return 1

    root = get_project_root()
    version_dir = root / WORK_LOGS_DIR / version
    tickets, format_type = get_tickets_from_version(version)

    if format_type == "markdown":
        # Markdown 格式（新版本）- 完整顯示
        try:
            tickets_dir = version_dir / TICKETS_DIR
        except ValueError as e:
            print(f"❌ {e}")
            return 1

        md_file = find_ticket_file(tickets_dir, args.ticket_id)
        if not md_file:
            print(f"❌ 找不到 Ticket {args.ticket_id}")
            return 1

        try:
            ticket = read_ticket(md_file)
        except Exception as e:
            print(f"❌ 讀取失敗: {e}")
            return 1

        icon = get_status_icon(ticket)
        elapsed = get_elapsed_time(
            ticket.started_at.isoformat() if ticket.started_at else ""
        )

        print(f"{icon} {ticket.ticket_id} | {ticket.action} {ticket.target} {elapsed}")
        print(f"   Agent: {ticket.agent}")
        print(f"   Status: {ticket.status}")
        print()
        print("5W1H:")
        print(f"  Who: {ticket.who}")
        print(f"  What: {ticket.what}")
        print(f"  When: {ticket.when}")
        print(f"  Where: {ticket.where}")
        print(f"  Why: {ticket.why}")
        print(f"  How: {ticket.how}")
        print()
        print("Acceptance:")
        for ac in ticket.acceptance:
            print(f"  - {ac}")

        return 0

    elif format_type == "csv":
        # CSV 格式（舊版本）- 顯示基本資訊和提示
        csv_ticket = None
        for t in tickets:
            if t.get("ticket_id") == args.ticket_id:
                csv_ticket = t
                break

        if not csv_ticket:
            print(f"❌ 找不到 Ticket {args.ticket_id}")
            return 1

        status = csv_ticket.get("status", STATUS_PENDING)
        icon = "✅" if status == STATUS_COMPLETED else "🔄" if status == STATUS_IN_PROGRESS else "⏸️"
        action = csv_ticket.get("action", "?")
        target = csv_ticket.get("target", "?")
        agent = csv_ticket.get("agent", "?")
        started = csv_ticket.get("started_at", "")
        elapsed = get_elapsed_time(started)

        print(f"{icon} {args.ticket_id} | {action} {target} {elapsed}")
        print(f"   Agent: {agent}")
        print(f"   Status: {status}")
        print()
        print(f"ℹ️  此 Ticket 來自舊版 CSV 格式 ({version})")
        print("   只有基本資訊可用，無法顯示詳細 5W1H")
        print("   請升級到 v0.16.0+ 以查看完整 Ticket 資訊")

        return 0

    else:
        print(f"❌ {version} 版本無法找到 Tickets")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """列出 Tickets"""
    # 自動偵測版本和格式
    version = args.version or get_current_version()
    if not version:
        print("❌ 無法偵測版本，請使用 --version 指定")
        return 1

    tickets, format_type = get_tickets_from_version(version)

    if not tickets:
        print(f"📋 {version} 沒有 Tickets")
        return 0

    # CSV 格式標籤
    format_label = " [CSV 格式 - 唯讀]" if format_type == "csv" else ""

    # 過濾
    filtered = tickets
    if format_type == "markdown":
        # Markdown 格式
        if args.in_progress:
            filtered = [t for t in tickets if t.status == STATUS_IN_PROGRESS]
        elif args.pending:
            filtered = [t for t in tickets if t.status == STATUS_PENDING]
        elif args.completed:
            filtered = [t for t in tickets if t.status == STATUS_COMPLETED]

        if not filtered:
            print("📋 沒有符合條件的 Tickets")
            return 0

        print(f"📋 Tickets ({len(filtered)}/{len(tickets)}){format_label}")
        print("-" * 100)
        for ticket in filtered:
            icon = get_status_icon(ticket)
            elapsed = get_elapsed_time(
                ticket.started_at.isoformat() if ticket.started_at else ""
            )
            agent_short = ticket.agent.split("-")[0] if "-" in ticket.agent else ticket.agent
            print(f"{ticket.ticket_id} | {icon} | {agent_short:15} | {ticket.action} {ticket.target} {elapsed}")

    else:
        # CSV 格式（舊版本）
        if args.in_progress:
            filtered = [t for t in tickets if t.get("status") == STATUS_IN_PROGRESS]
        elif args.pending:
            filtered = [t for t in tickets if t.get("status") == STATUS_PENDING]
        elif args.completed:
            filtered = [t for t in tickets if t.get("status") == STATUS_COMPLETED]

        if not filtered:
            print("📋 沒有符合條件的 Tickets")
            return 0

        print(f"📋 Tickets ({len(filtered)}/{len(tickets)}){format_label}")
        print("-" * 100)
        for ticket in filtered:
            status = ticket.get("status", STATUS_PENDING)
            icon = "✅" if status == STATUS_COMPLETED else "🔄" if status == STATUS_IN_PROGRESS else "⏸️"
            ticket_id = ticket.get("ticket_id", "?")
            agent = ticket.get("agent", "?")
            agent_short = agent.split("-")[0] if "-" in agent else agent
            action = ticket.get("action", "?")
            target = ticket.get("target", "?")
            started = ticket.get("started_at", "")
            elapsed = get_elapsed_time(started)
            print(f"{ticket_id} | {icon} | {agent_short:15} | {action} {target} {elapsed}")

    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """快速摘要"""
    version = args.version or get_current_version()
    if not version:
        print("❌ 無法偵測版本，請使用 --version 指定")
        return 1

    # 自動偵測格式
    try:
        tickets, format_type = get_tickets_from_version(version)
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return 1

    # 顯示警告（舊版本 CSV 格式唯讀）
    if format_type == "csv":
        print(f"⚠️  {version} 使用舊版 CSV 格式（唯讀模式）")
        print("   狀態更新命令（claim/complete/release）在 v0.15.x 版本不支援")
        print("   請升級到 v0.16.0+ 以使用新的 Markdown Ticket 系統")
        print()

    if not tickets:
        print(f"📊 Ticket 摘要 {version} (0/0 完成)")
        print("   沒有 Tickets")
        return 0

    # 根據格式計算完成數
    if format_type == "markdown":
        completed_count = sum(1 for t in tickets if t.status == STATUS_COMPLETED)
        total_count = len(tickets)

        print(f"📊 Ticket 摘要 {version} ({completed_count}/{total_count} 完成) [{format_type}]")
        print("-" * 100)

        for ticket in tickets:
            icon = get_status_icon(ticket)
            elapsed = get_elapsed_time(
                ticket.started_at.isoformat() if ticket.started_at else ""
            )
            agent_short = ticket.agent.split("-")[0] if "-" in ticket.agent else ticket.agent
            print(f"{ticket.ticket_id} | {icon} | {agent_short:15} | {ticket.action} {ticket.target} {elapsed}")
    else:
        # CSV 格式（舊版本）
        total_count = len(tickets)
        completed_count = sum(1 for t in tickets if t.get("status") == STATUS_COMPLETED)

        print(f"📊 Ticket 摘要 {version} ({completed_count}/{total_count} 完成) [{format_type}]")
        print("-" * 100)

        for ticket in tickets:
            status = ticket.get("status", STATUS_PENDING)
            icon = "✅" if status == STATUS_COMPLETED else "🔄" if status == STATUS_IN_PROGRESS else "⏸️"
            ticket_id = ticket.get("ticket_id", "?")
            agent = ticket.get("agent", "?")
            agent_short = agent.split("-")[0] if "-" in agent else agent
            action = ticket.get("action", "?")
            target = ticket.get("target", "?")
            started = ticket.get("started_at", "")
            elapsed = get_elapsed_time(started)
            print(f"{ticket_id} | {icon} | {agent_short:15} | {action} {target} {elapsed}")

    return 0


# ============ 主程式 ============

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Frontmatter 式 Ticket 追蹤系統（Markdown Ticket 狀態管理）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # claim
    p_claim = subparsers.add_parser("claim", help="接手 Ticket")
    p_claim.add_argument("ticket_id", help="票號")
    p_claim.add_argument("--version", help="版本號（自動偵測）")

    # complete
    p_complete = subparsers.add_parser("complete", help="標記完成")
    p_complete.add_argument("ticket_id", help="票號")
    p_complete.add_argument("--version", help="版本號（自動偵測）")

    # release
    p_release = subparsers.add_parser("release", help="放棄 Ticket")
    p_release.add_argument("ticket_id", help="票號")
    p_release.add_argument("--version", help="版本號（自動偵測）")

    # query
    p_query = subparsers.add_parser("query", help="查詢單一 Ticket")
    p_query.add_argument("ticket_id", help="票號")
    p_query.add_argument("--version", help="版本號（自動偵測）")

    # list
    p_list = subparsers.add_parser("list", help="列出 Tickets")
    p_list.add_argument("--in-progress", action="store_true", help="只顯示進行中")
    p_list.add_argument("--pending", action="store_true", help="只顯示未接手")
    p_list.add_argument("--completed", action="store_true", help="只顯示已完成")
    p_list.add_argument("--version", help="版本號（自動偵測）")

    # summary
    p_summary = subparsers.add_parser("summary", help="快速摘要")
    p_summary.add_argument("--version", help="版本號（自動偵測）")

    args = parser.parse_args()

    # 執行對應命令
    try:
        if args.command == "claim":
            return cmd_claim(args)
        elif args.command == "complete":
            return cmd_complete(args)
        elif args.command == "release":
            return cmd_release(args)
        elif args.command == "query":
            return cmd_query(args)
        elif args.command == "list":
            return cmd_list(args)
        elif args.command == "summary":
            return cmd_summary(args)
        else:
            parser.print_help()
            return 1
    except ValueError as e:
        print(f"❌ {e}")
        return 1
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
