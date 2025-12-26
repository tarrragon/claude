#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
Atomic Ticket Creator - 建立符合單一職責原則的 Ticket

使用方式:
  uv run .claude/hooks/ticket-creator.py create --version 0.15.16 --wave 1 --seq 1 \\
    --action "實作" --target "startScan() 方法" --agent "parsley-flutter-developer"

  uv run .claude/hooks/ticket-creator.py add-to-csv --id 0.15.16-W1-001

  uv run .claude/hooks/ticket-creator.py list --version 0.15.16
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 工作日誌目錄
WORK_LOGS_DIR = PROJECT_ROOT / "docs" / "work-logs"

# CSV 欄位定義（精簡版 - 只追蹤狀態）
CSV_HEADERS = [
    "ticket_id",
    "version",
    "status",
    "started_at",
    "completed_at",
    "agent",
]

# 狀態定義
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"


def get_version_dir(version: str) -> Path:
    """取得版本目錄路徑"""
    return WORK_LOGS_DIR / f"v{version}"


def get_tickets_dir(version: str) -> Path:
    """取得 Tickets YAML 目錄路徑"""
    return get_version_dir(version) / "tickets"


def get_csv_path(version: str) -> Path:
    """取得 CSV 路徑"""
    return get_version_dir(version) / "tickets.csv"


def ensure_directories(version: str) -> None:
    """確保目錄存在"""
    get_version_dir(version).mkdir(parents=True, exist_ok=True)
    get_tickets_dir(version).mkdir(parents=True, exist_ok=True)


def format_ticket_id(version: str, wave: int, seq: int) -> str:
    """格式化 Ticket ID"""
    return f"{version}-W{wave}-{seq:03d}"


def create_ticket_yaml(
    version: str,
    wave: int,
    seq: int,
    action: str,
    target: str,
    agent: str,
    when: str = "",
    where: str = "",
    why: str = "",
    how: str = "",
    acceptance: Optional[list] = None,
    files: Optional[list] = None,
    dependencies: Optional[list] = None,
    references: Optional[list] = None,
) -> dict:
    """建立 Ticket YAML 資料結構"""
    ticket_id = format_ticket_id(version, wave, seq)

    return {
        "ticket": {
            "id": ticket_id,
            "version": version,
            "wave": wave,
            "action": action,
            "target": target,
            "agent": agent,
            "who": agent,
            "what": f"{action} {target}",
            "when": when or "待定義",
            "where": where or "待定義",
            "why": why or "待定義",
            "how": how or "待定義",
            "acceptance": acceptance or [
                f"{target} 實作完成",
                "相關測試通過",
                "dart analyze 無警告",
            ],
            "files": files or [],
            "dependencies": dependencies or [],
            "references": references or [],
        }
    }


def save_ticket_yaml(version: str, ticket_data: dict) -> Path:
    """儲存 Ticket YAML 檔案"""
    ensure_directories(version)
    ticket_id = ticket_data["ticket"]["id"]
    yaml_path = get_tickets_dir(version) / f"{ticket_id}.yaml"

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(ticket_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return yaml_path


def read_csv(csv_path: Path) -> list:
    """讀取 CSV 檔案"""
    if not csv_path.exists():
        return []

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(csv_path: Path, tickets: list) -> None:
    """寫入 CSV 檔案"""
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(tickets)


def add_to_csv(version: str, ticket_id: str, agent: str) -> None:
    """新增 Ticket 到 CSV 追蹤"""
    csv_path = get_csv_path(version)
    tickets = read_csv(csv_path)

    # 檢查是否已存在
    for ticket in tickets:
        if ticket.get("ticket_id") == ticket_id:
            print(f"⚠️  {ticket_id} 已存在於 CSV")
            return

    # 新增 Ticket
    new_ticket = {
        "ticket_id": ticket_id,
        "version": version,
        "status": STATUS_PENDING,
        "started_at": "",
        "completed_at": "",
        "agent": agent,
    }
    tickets.append(new_ticket)

    write_csv(csv_path, tickets)
    print(f"✅ 已新增 {ticket_id} 到 CSV 追蹤")


def load_ticket_yaml(version: str, ticket_id: str) -> Optional[dict]:
    """讀取 Ticket YAML"""
    yaml_path = get_tickets_dir(version) / f"{ticket_id}.yaml"
    if not yaml_path.exists():
        return None

    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_tickets(version: str) -> list:
    """列出版本的所有 Tickets"""
    tickets_dir = get_tickets_dir(version)
    if not tickets_dir.exists():
        return []

    tickets = []
    for yaml_file in sorted(tickets_dir.glob("*.yaml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data and "ticket" in data:
                tickets.append(data["ticket"])

    return tickets


# ============================================================
# CLI 命令實作
# ============================================================


def cmd_create(args: argparse.Namespace) -> int:
    """建立新的 Atomic Ticket"""
    ticket_data = create_ticket_yaml(
        version=args.version,
        wave=args.wave,
        seq=args.seq,
        action=args.action,
        target=args.target,
        agent=args.agent,
        when=args.when or "",
        where=args.where or "",
        why=args.why or "",
        how=args.how or "",
    )

    yaml_path = save_ticket_yaml(args.version, ticket_data)
    ticket_id = ticket_data["ticket"]["id"]

    print(f"✅ 已建立 Ticket: {ticket_id}")
    print(f"   YAML: {yaml_path}")

    # 連動 CSV（除非指定 --no-track）
    if not args.no_track:
        add_to_csv(args.version, ticket_id, args.agent)
        csv_path = get_csv_path(args.version)
        print(f"   CSV: {csv_path}")
    else:
        print("   CSV: (跳過連動)")

    return 0


def cmd_add_to_csv(args: argparse.Namespace) -> int:
    """將 Ticket 新增到 CSV 追蹤"""
    # 解析 ticket_id 取得 version
    parts = args.id.split("-W")
    if len(parts) != 2:
        print(f"❌ 無效的 Ticket ID 格式: {args.id}")
        print("   正確格式: {VERSION}-W{WAVE}-{SEQ}, 例如: 0.15.16-W1-001")
        return 1

    version = parts[0]

    # 讀取 YAML 取得 agent
    ticket_data = load_ticket_yaml(version, args.id)
    if not ticket_data:
        print(f"❌ 找不到 Ticket YAML: {args.id}")
        return 1

    agent = ticket_data.get("agent", "unknown")
    add_to_csv(version, args.id, agent)

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """列出所有 Tickets"""
    tickets = list_tickets(args.version)

    if not tickets:
        print(f"📋 v{args.version} 沒有 Tickets")
        return 0

    print(f"📋 v{args.version} Tickets ({len(tickets)} 個)")
    print("-" * 60)

    for ticket in tickets:
        ticket_id = ticket.get("id", "?")
        action = ticket.get("action", "?")
        target = ticket.get("target", "?")
        agent = ticket.get("agent", "?")[:10]

        print(f"{ticket_id} | {action} {target} | {agent}")

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """顯示 Ticket 詳細資訊"""
    # 解析 ticket_id 取得 version
    parts = args.id.split("-W")
    if len(parts) != 2:
        print(f"❌ 無效的 Ticket ID 格式: {args.id}")
        return 1

    version = parts[0]
    ticket_data = load_ticket_yaml(version, args.id)

    if not ticket_data:
        print(f"❌ 找不到 Ticket: {args.id}")
        return 1

    ticket = ticket_data["ticket"] if "ticket" in ticket_data else ticket_data

    print(f"📋 Ticket: {ticket.get('id', '?')}")
    print("-" * 40)
    print(f"Action: {ticket.get('action', '?')}")
    print(f"Target: {ticket.get('target', '?')}")
    print(f"Agent: {ticket.get('agent', '?')}")
    print(f"Wave: {ticket.get('wave', '?')}")
    print()
    print("5W1H:")
    print(f"  Who: {ticket.get('who', '?')}")
    print(f"  What: {ticket.get('what', '?')}")
    print(f"  When: {ticket.get('when', '?')}")
    print(f"  Where: {ticket.get('where', '?')}")
    print(f"  Why: {ticket.get('why', '?')}")
    print(f"  How: {ticket.get('how', '?')}")
    print()
    print("Acceptance:")
    for ac in ticket.get("acceptance", []):
        print(f"  - {ac}")
    print()
    print("Files:")
    for f in ticket.get("files", []):
        print(f"  - {f}")
    print()
    print("Dependencies:")
    deps = ticket.get("dependencies", [])
    if deps:
        for d in deps:
            print(f"  - {d}")
    else:
        print("  (無)")

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """初始化版本目錄"""
    ensure_directories(args.version)

    # 建立空的 CSV
    csv_path = get_csv_path(args.version)
    if not csv_path.exists():
        write_csv(csv_path, [])
        print(f"✅ 已初始化 v{args.version}")
        print(f"   目錄: {get_version_dir(args.version)}")
        print(f"   Tickets: {get_tickets_dir(args.version)}")
        print(f"   CSV: {csv_path}")
    else:
        print(f"⚠️  v{args.version} 已存在")

    return 0


# ============================================================
# 主程式
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Atomic Ticket Creator - 建立符合單一職責原則的 Ticket"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化版本目錄")
    init_parser.add_argument("version", help="版本號 (例如: 0.15.16)")

    # create 命令
    create_parser = subparsers.add_parser("create", help="建立新的 Atomic Ticket")
    create_parser.add_argument("--version", required=True, help="版本號")
    create_parser.add_argument("--wave", type=int, required=True, help="Wave 編號")
    create_parser.add_argument("--seq", type=int, required=True, help="序號")
    create_parser.add_argument("--action", required=True, help="動詞 (實作/修復/新增/重構)")
    create_parser.add_argument("--target", required=True, help="單一目標")
    create_parser.add_argument("--agent", required=True, help="執行代理人")
    create_parser.add_argument("--when", help="觸發時機")
    create_parser.add_argument("--where", help="檔案位置")
    create_parser.add_argument("--why", help="原因")
    create_parser.add_argument("--how", help="實作策略")
    create_parser.add_argument("--no-track", action="store_true", help="不連動 CSV")

    # add-to-csv 命令
    add_csv_parser = subparsers.add_parser("add-to-csv", help="將 Ticket 新增到 CSV")
    add_csv_parser.add_argument("--id", required=True, help="Ticket ID")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有 Tickets")
    list_parser.add_argument("--version", required=True, help="版本號")

    # show 命令
    show_parser = subparsers.add_parser("show", help="顯示 Ticket 詳細資訊")
    show_parser.add_argument("--id", required=True, help="Ticket ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "create": cmd_create,
        "add-to-csv": cmd_add_to_csv,
        "list": cmd_list,
        "show": cmd_show,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
