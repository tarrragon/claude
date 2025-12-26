#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
CSV 式 Ticket 追蹤系統

主線程和代理人共用的 Ticket 狀態追蹤工具。
透過 CSV 檔案儲存狀態，提供輕量級的查詢和更新功能。

使用方式:
    uv run .claude/hooks/ticket-tracker.py <command> [options]

命令:
    init <version>          初始化版本資料夾
    add --id ... --who ...  新增 Ticket
    claim <ticket_id>       接手 Ticket
    complete <ticket_id>    標記完成
    release <ticket_id>     放棄 Ticket
    query <ticket_id>       查詢單一 Ticket
    list [--filter]         列出 Tickets
    summary [--version]     快速摘要
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# 常數定義
WORK_LOGS_DIR = Path("docs/work-logs")
CSV_FILENAME = "tickets.csv"
TICKETS_DIR = "tickets"  # YAML 定義檔目錄

# CSV 欄位定義（Atomic Ticket v3.0 - 單一職責格式）
CSV_HEADERS = [
    "ticket_id",      # 唯一識別碼 (格式: {Version}-W{Wave}-{Seq})
    "action",         # 動作 (Fix, Implement, Add, Refactor, Remove)
    "target",         # 目標 (單一職責)
    "agent",          # 執行代理人
    "wave",           # Wave 層級 (1, 2, 3)
    "dependencies",   # 依賴的 Tickets (分號分隔)
    "assigned",       # 是否已接手 (true/false)
    "started_at",     # 開始時間
    "completed",      # 是否已完成 (true/false)
]

# 狀態常數（相容舊格式）
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


def get_csv_path(version: Optional[str] = None) -> Path:
    """取得 CSV 檔案路徑"""
    if version is None:
        version = get_current_version()

    if version is None:
        raise ValueError("無法偵測版本，請使用 --version 指定")

    root = get_project_root()
    return root / WORK_LOGS_DIR / version / CSV_FILENAME


def read_tickets(csv_path: Path) -> list[dict]:
    """讀取所有 Tickets"""
    if not csv_path.exists():
        return []

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_tickets(csv_path: Path, tickets: list[dict]) -> None:
    """寫入所有 Tickets"""
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(tickets)


def find_ticket(tickets: list[dict], ticket_id: str) -> Optional[dict]:
    """找到指定的 Ticket"""
    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id:
            return ticket
    return None


def get_status_icon(ticket: dict) -> str:
    """取得狀態圖示（支援新舊格式）"""
    # 新格式: assigned/completed 布林值
    assigned = ticket.get("assigned", "false").lower() == "true"
    completed = ticket.get("completed", "false").lower() == "true"
    # 舊格式: status 字串
    status = ticket.get("status", "")

    if completed or status == STATUS_COMPLETED:
        return "✅"
    elif assigned or status == STATUS_IN_PROGRESS:
        return "🔄"
    else:
        return "⏸️"


def load_ticket_yaml(version: str, ticket_id: str) -> Optional[dict]:
    """從 YAML 載入 Ticket 詳細資訊"""
    root = get_project_root()

    # 確保版本號有 'v' 前綴
    version_dir = version if version.startswith("v") else f"v{version}"
    yaml_path = root / WORK_LOGS_DIR / version_dir / TICKETS_DIR / f"{ticket_id}.yaml"

    if not yaml_path.exists():
        return None

    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("ticket", data) if data else None
    except ImportError:
        # 如果沒有 yaml 模組，返回 None
        return None
    except Exception:
        return None


def get_ticket_what(ticket: dict, version: str) -> str:
    """取得 Ticket 的 what 描述（優先從 CSV 讀取，再從 YAML 讀取）"""
    ticket_id = ticket.get("ticket_id", "")

    # 優先從 CSV 讀取（新格式）
    action = ticket.get("action", "")
    target = ticket.get("target", "")
    if action and target:
        return f"{action} {target}"

    # 嘗試從 YAML 載入（舊格式相容）
    yaml_data = load_ticket_yaml(version, ticket_id)
    if yaml_data:
        action = yaml_data.get("action", "")
        target = yaml_data.get("target", "")
        if action and target:
            return f"{action} {target}"

    # 回退：從 ticket_id 推測
    return ticket_id


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

def cmd_init(args: argparse.Namespace) -> int:
    """初始化版本資料夾"""
    version = args.version
    root = get_project_root()
    version_dir = root / WORK_LOGS_DIR / version
    csv_path = version_dir / CSV_FILENAME

    if csv_path.exists():
        print(f"⚠️  {version} 已存在 tickets.csv")
        return 1

    # 建立資料夾和空的 CSV
    version_dir.mkdir(parents=True, exist_ok=True)
    write_tickets(csv_path, [])

    print(f"✅ 已初始化 {version}")
    print(f"   📁 {version_dir}")
    print(f"   📄 {csv_path}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """新增 Ticket 到 CSV 追蹤（精簡版）"""
    csv_path = get_csv_path(args.version)
    tickets = read_tickets(csv_path)

    # 檢查 ID 是否重複
    if find_ticket(tickets, args.id):
        print(f"❌ Ticket {args.id} 已存在")
        return 1

    # 解析版本號
    version = args.version
    if version is None:
        # 從 ticket_id 解析版本
        parts = args.id.split("-W")
        version = parts[0] if len(parts) == 2 else "unknown"

    # 建立新 Ticket（精簡版 - 只追蹤狀態）
    new_ticket = {
        "ticket_id": args.id,
        "version": version,
        "status": STATUS_PENDING,
        "started_at": "",
        "completed_at": "",
        "agent": args.agent,
    }

    tickets.append(new_ticket)
    write_tickets(csv_path, tickets)

    print(f"✅ 已新增 {args.id}")
    print(f"   Agent: {args.agent}")
    print(f"   Status: {STATUS_PENDING}")
    print(f"   💡 5W1H 詳細資訊請在 YAML 定義檔中設定")
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    """接手 Ticket"""
    csv_path = get_csv_path(args.version)
    tickets = read_tickets(csv_path)

    ticket = find_ticket(tickets, args.ticket_id)
    if not ticket:
        print(f"❌ 找不到 Ticket {args.ticket_id}")
        return 1

    # 支援新格式 (assigned/completed) 和舊格式 (status)
    assigned = ticket.get("assigned", "false").lower() == "true"
    completed = ticket.get("completed", "false").lower() == "true"
    status = ticket.get("status", "")

    if assigned or status == STATUS_IN_PROGRESS:
        print(f"⚠️  {args.ticket_id} 已被接手")
        return 1
    if completed or status == STATUS_COMPLETED:
        print(f"⚠️  {args.ticket_id} 已完成")
        return 1

    # 更新為新格式
    ticket["assigned"] = "true"
    ticket["started_at"] = datetime.now().isoformat(timespec="seconds")
    # 保留舊格式相容
    if "status" in ticket:
        ticket["status"] = STATUS_IN_PROGRESS

    write_tickets(csv_path, tickets)

    print(f"✅ 已接手 {args.ticket_id}")
    print(f"   開始時間: {ticket['started_at']}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """標記完成"""
    csv_path = get_csv_path(args.version)
    tickets = read_tickets(csv_path)

    ticket = find_ticket(tickets, args.ticket_id)
    if not ticket:
        print(f"❌ 找不到 Ticket {args.ticket_id}")
        return 1

    # 支援新格式和舊格式
    completed = ticket.get("completed", "false").lower() == "true"
    status = ticket.get("status", "")

    if completed or status == STATUS_COMPLETED:
        print(f"⚠️  {args.ticket_id} 已完成")
        return 1

    # 更新為新格式
    ticket["completed"] = "true"
    # 保留舊格式相容
    if "status" in ticket:
        ticket["status"] = STATUS_COMPLETED
    if "completed_at" in ticket:
        ticket["completed_at"] = datetime.now().isoformat(timespec="seconds")

    write_tickets(csv_path, tickets)

    elapsed = get_elapsed_time(ticket.get("started_at", ""))
    print(f"✅ 已完成 {args.ticket_id} {elapsed}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    """放棄 Ticket"""
    csv_path = get_csv_path(args.version)
    tickets = read_tickets(csv_path)

    ticket = find_ticket(tickets, args.ticket_id)
    if not ticket:
        print(f"❌ 找不到 Ticket {args.ticket_id}")
        return 1

    # 支援新格式和舊格式
    assigned = ticket.get("assigned", "false").lower() == "true"
    completed = ticket.get("completed", "false").lower() == "true"
    status = ticket.get("status", "")

    if not assigned and status != STATUS_IN_PROGRESS:
        print(f"⚠️  {args.ticket_id} 尚未被接手")
        return 1
    if completed or status == STATUS_COMPLETED:
        print(f"⚠️  {args.ticket_id} 已完成，無法放棄")
        return 1

    # 更新為新格式
    ticket["assigned"] = "false"
    ticket["started_at"] = ""
    # 保留舊格式相容
    if "status" in ticket:
        ticket["status"] = STATUS_PENDING

    write_tickets(csv_path, tickets)

    print(f"✅ 已放棄 {args.ticket_id}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """查詢單一 Ticket（從 CSV 和 YAML 整合資訊）"""
    csv_path = get_csv_path(args.version)
    tickets = read_tickets(csv_path)

    ticket = find_ticket(tickets, args.ticket_id)
    if not ticket:
        print(f"❌ 找不到 Ticket {args.ticket_id}")
        return 1

    icon = get_status_icon(ticket)
    elapsed = get_elapsed_time(ticket.get("started_at", ""))
    version = ticket.get("version", args.version or "unknown")

    # 從 YAML 載入詳細資訊
    yaml_data = load_ticket_yaml(version, args.ticket_id)

    what = get_ticket_what(ticket, version)
    print(f"{icon} {ticket['ticket_id']} | {what} {elapsed}")
    print(f"   Agent: {ticket.get('agent', '?')}")
    print(f"   Status: {ticket.get('status', STATUS_PENDING)}")

    if yaml_data:
        print(f"   Who: {yaml_data.get('who', '?')}")
        print(f"   What: {yaml_data.get('what', '?')}")
        print(f"   When: {yaml_data.get('when', '?')}")
        print(f"   Where: {yaml_data.get('where', '?')}")
        print(f"   Why: {yaml_data.get('why', '?')}")
        print(f"   How: {yaml_data.get('how', '?')}")
    else:
        print(f"   💡 YAML 定義檔不存在，使用 /ticket-create 建立")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """列出 Tickets"""
    csv_path = get_csv_path(args.version)
    tickets = read_tickets(csv_path)

    if not tickets:
        print("📋 沒有 Tickets")
        return 0

    # 過濾
    filtered = tickets
    if args.in_progress:
        filtered = [t for t in tickets if t.get("status") == STATUS_IN_PROGRESS]
    elif args.pending:
        filtered = [t for t in tickets if t.get("status") == STATUS_PENDING]
    elif args.completed:
        filtered = [t for t in tickets if t.get("status") == STATUS_COMPLETED]

    if not filtered:
        print("📋 沒有符合條件的 Tickets")
        return 0

    version = args.version or get_current_version() or "unknown"
    for ticket in filtered:
        icon = get_status_icon(ticket)
        elapsed = get_elapsed_time(ticket.get("started_at", ""))
        agent = ticket.get("agent", "?")
        agent_short = agent.split("-")[0] if "-" in agent else agent
        what = get_ticket_what(ticket, version)
        print(f"{ticket['ticket_id']} | {icon} | {agent_short} | {what} {elapsed}")

    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """快速摘要"""
    version = args.version or get_current_version()
    if not version:
        print("❌ 無法偵測版本，請使用 --version 指定")
        return 1

    csv_path = get_csv_path(version)
    tickets = read_tickets(csv_path)

    if not tickets:
        print(f"📊 Ticket 摘要 {version} (0/0 完成)")
        print("   沒有 Tickets")
        return 0

    completed_count = sum(1 for t in tickets if t.get("status") == STATUS_COMPLETED)
    total_count = len(tickets)

    print(f"📊 Ticket 摘要 {version} ({completed_count}/{total_count} 完成)")

    for ticket in tickets:
        icon = get_status_icon(ticket)
        elapsed = get_elapsed_time(ticket.get("started_at", ""))
        agent = ticket.get("agent", "?")
        agent_short = agent.split("-")[0] if "-" in agent else agent
        what = get_ticket_what(ticket, version)
        print(f"{ticket['ticket_id']} | {icon} | {agent_short} | {what} {elapsed}")

    return 0


# ============ 主程式 ============

def main() -> int:
    parser = argparse.ArgumentParser(
        description="CSV 式 Ticket 追蹤系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="初始化版本資料夾")
    p_init.add_argument("version", help="版本號 (e.g., v0.15.15)")

    # add（精簡版 - 只追蹤狀態，5W1H 在 YAML 中定義）
    p_add = subparsers.add_parser("add", help="新增 Ticket 到 CSV 追蹤")
    p_add.add_argument("--id", required=True, help="票號 (e.g., 0.15.16-W1-001)")
    p_add.add_argument("--agent", required=True, help="執行代理人")
    p_add.add_argument("--version", help="版本號（自動偵測）")

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
        if args.command == "init":
            return cmd_init(args)
        elif args.command == "add":
            return cmd_add(args)
        elif args.command == "claim":
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
