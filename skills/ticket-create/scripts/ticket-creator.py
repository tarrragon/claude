#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
Atomic Ticket Creator v2.0 - 5W1H 引導式建立與版本驅動管理

支援功能:
- create: 建立新的 Atomic Ticket（完整 5W1H 欄位）
- create-child: 建立子 Ticket 並自動關聯父 Ticket
- init: 初始化版本目錄
- list: 列出所有 Tickets
- show: 顯示 Ticket 詳細資訊

使用方式:
    uv run .claude/skills/ticket-create/scripts/ticket-creator.py <command> [options]
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# 專案根目錄 (.claude/skills/ticket-create/scripts/ -> 需要 5 層)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

# 工作日誌目錄
WORK_LOGS_DIR = PROJECT_ROOT / "docs" / "work-logs"

# 狀態定義
STATUS_PENDING = "pending"


def get_version_dir(version: str) -> Path:
    """取得版本目錄路徑"""
    v = version if version.startswith("v") else f"v{version}"
    return WORK_LOGS_DIR / v


def get_tickets_dir(version: str) -> Path:
    """取得 Tickets 目錄路徑"""
    return get_version_dir(version) / "tickets"


def ensure_directories(version: str) -> None:
    """確保目錄存在"""
    get_version_dir(version).mkdir(parents=True, exist_ok=True)
    get_tickets_dir(version).mkdir(parents=True, exist_ok=True)


def format_ticket_id(version: str, wave: int, seq: int) -> str:
    """格式化 Ticket ID"""
    # 移除 v 前綴
    v = version[1:] if version.startswith("v") else version
    return f"{v}-W{wave}-{seq:03d}"


def get_next_seq(version: str, wave: int) -> int:
    """取得下一個序號"""
    tickets_dir = get_tickets_dir(version)
    if not tickets_dir.exists():
        return 1

    pattern = f"*-W{wave}-*.md"
    existing = list(tickets_dir.glob(pattern))

    if not existing:
        return 1

    max_seq = 0
    for f in existing:
        try:
            # 格式：{version}-W{wave}-{seq}.md
            parts = f.stem.split("-W")
            if len(parts) == 2:
                wave_seq = parts[1].split("-")
                if len(wave_seq) == 2:
                    seq = int(wave_seq[1])
                    max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue

    return max_seq + 1


def create_ticket_content(
    ticket_id: str,
    version: str,
    wave: int,
    title: str,
    ticket_type: str,
    priority: str,
    # 5W1H 欄位
    who: str,
    what: str,
    when: str,
    where_layer: str,
    where_files: list,
    why: str,
    how_task_type: str,
    how_strategy: str,
    # 關係欄位
    parent_id: Optional[str] = None,
    blocked_by: Optional[list] = None,
    # 驗收條件
    acceptance: Optional[list] = None,
) -> str:
    """建立 Ticket Markdown 內容"""
    frontmatter = {
        # 識別欄位
        "id": ticket_id,
        "title": title,
        "type": ticket_type,
        "status": STATUS_PENDING,
        # 版本欄位
        "version": version,
        "wave": wave,
        "priority": priority,
        # 關係欄位
        "parent_id": parent_id,
        "children": [],
        "blockedBy": blocked_by or [],
        # 5W1H 欄位
        "who": {
            "current": who,
            "history": {}
        },
        "what": what,
        "when": when,
        "where": {
            "layer": where_layer,
            "files": where_files
        },
        "why": why,
        "how": {
            "task_type": how_task_type,
            "strategy": how_strategy
        },
        # 驗收條件
        "acceptance": acceptance or [
            "任務實作完成",
            "相關測試通過",
            "無程式碼品質警告"
        ],
        # 狀態追蹤
        "assigned": False,
        "started_at": None,
        "completed_at": None,
        # 元資料
        "created": datetime.now().strftime("%Y-%m-%d"),
        "updated": datetime.now().strftime("%Y-%m-%d"),
    }

    frontmatter_yaml = yaml.dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False
    )

    body = f"""# Execution Log

## Task Summary

{what}

---

## Problem Analysis

<!-- To be filled by executing agent -->

---

## Solution

<!-- To be filled by executing agent -->

---

## Test Results

<!-- To be filled by executing agent -->

---

## Completion Info

**Completion Time**: (pending)
**Executing Agent**: {who}
**Review Status**: pending
"""

    return f"---\n{frontmatter_yaml}---\n\n{body}"


def save_ticket(version: str, ticket_id: str, content: str) -> Path:
    """儲存 Ticket 檔案"""
    ensure_directories(version)
    ticket_path = get_tickets_dir(version) / f"{ticket_id}.md"

    with open(ticket_path, "w", encoding="utf-8") as f:
        f.write(content)

    return ticket_path


def load_ticket(version: str, ticket_id: str) -> Optional[dict]:
    """讀取 Ticket 資料"""
    ticket_path = get_tickets_dir(version) / f"{ticket_id}.md"

    if not ticket_path.exists():
        # 嘗試 yaml 格式
        ticket_path = get_tickets_dir(version) / f"{ticket_id}.yaml"
        if not ticket_path.exists():
            return None

    with open(ticket_path, "r", encoding="utf-8") as f:
        content = f.read()

    if ticket_path.suffix == ".md":
        # 解析 frontmatter
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            data = yaml.safe_load(parts[1])
            data["_path"] = str(ticket_path)
            return data
        except yaml.YAMLError:
            return None
    else:
        data = yaml.safe_load(content)
        if data and "ticket" in data:
            data = data["ticket"]
        data["_path"] = str(ticket_path)
        return data


def update_parent_children(version: str, parent_id: str, child_id: str) -> bool:
    """更新父 Ticket 的 children 欄位"""
    parent = load_ticket(version, parent_id)
    if not parent:
        return False

    children = parent.get("children", [])
    if child_id not in children:
        children.append(child_id)

    # 讀取原始檔案
    parent_path = Path(parent.get("_path"))
    with open(parent_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 更新 children
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    try:
        frontmatter = yaml.safe_load(parts[1])
        frontmatter["children"] = children
        frontmatter["updated"] = datetime.now().strftime("%Y-%m-%d")

        new_frontmatter = yaml.dump(
            frontmatter,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False
        )

        new_content = f"---\n{new_frontmatter}---\n{parts[2]}"

        with open(parent_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True
    except yaml.YAMLError:
        return False


def list_tickets(version: str) -> list:
    """列出版本的所有 Tickets"""
    tickets_dir = get_tickets_dir(version)
    if not tickets_dir.exists():
        return []

    tickets = []
    for ticket_file in sorted(tickets_dir.glob("*.md")):
        ticket = load_ticket(version, ticket_file.stem)
        if ticket:
            tickets.append(ticket)

    return tickets


# ============================================================
# CLI 命令實作
# ============================================================


def cmd_create(args: argparse.Namespace) -> int:
    """建立新的 Atomic Ticket"""
    version = args.version

    # 自動取得下一個序號
    if args.seq is None:
        seq = get_next_seq(version, args.wave)
    else:
        seq = args.seq

    ticket_id = format_ticket_id(version, args.wave, seq)

    # 處理 where_files
    where_files = []
    if args.where_files:
        where_files = [f.strip() for f in args.where_files.split(",")]

    # 處理 blocked_by
    blocked_by = []
    if args.blocked_by:
        blocked_by = [b.strip() for b in args.blocked_by.split(",")]

    # 處理 acceptance
    acceptance = None
    if args.acceptance:
        acceptance = [a.strip() for a in args.acceptance.split("|")]

    content = create_ticket_content(
        ticket_id=ticket_id,
        version=version,
        wave=args.wave,
        title=args.title or f"{args.action} {args.target}",
        ticket_type=args.type or "IMP",
        priority=args.priority or "P2",
        # 5W1H
        who=args.who or "pending",
        what=args.what or f"{args.action} {args.target}",
        when=args.when or "待定義",
        where_layer=args.where_layer or "待定義",
        where_files=where_files,
        why=args.why or "待定義",
        how_task_type=args.how_type or "Implementation",
        how_strategy=args.how_strategy or "待定義",
        # 關係
        parent_id=args.parent,
        blocked_by=blocked_by,
        # 驗收
        acceptance=acceptance,
    )

    ticket_path = save_ticket(version, ticket_id, content)

    print(f"[OK] 已建立 Ticket: {ticket_id}")
    print(f"   Location: {ticket_path}")

    # 如果有 parent，更新 parent 的 children
    if args.parent:
        if update_parent_children(version, args.parent, ticket_id):
            print(f"   Parent: {args.parent} (已更新 children)")
        else:
            print(f"   [Warning] 無法更新 Parent {args.parent} 的 children")

    return 0


def cmd_create_child(args: argparse.Namespace) -> int:
    """建立子 Ticket"""
    # 從 parent_id 解析 version
    parts = args.parent_id.split("-W")
    if len(parts) != 2:
        print(f"[Error] 無效的 Parent ID 格式: {args.parent_id}")
        return 1

    version = parts[0]

    # 確認 parent 存在
    parent = load_ticket(version, args.parent_id)
    if not parent:
        print(f"[Error] 找不到 Parent Ticket: {args.parent_id}")
        return 1

    # 自動取得下一個序號
    seq = get_next_seq(version, args.wave)
    ticket_id = format_ticket_id(version, args.wave, seq)

    # 處理 where_files
    where_files = []
    if args.where_files:
        where_files = [f.strip() for f in args.where_files.split(",")]

    content = create_ticket_content(
        ticket_id=ticket_id,
        version=version,
        wave=args.wave,
        title=args.title or f"{args.action} {args.target}",
        ticket_type=args.type or "IMP",
        priority=args.priority or parent.get("priority", "P2"),
        # 5W1H
        who=args.who or "pending",
        what=args.what or f"{args.action} {args.target}",
        when=args.when or "待定義",
        where_layer=args.where_layer or parent.get("where", {}).get("layer", "待定義"),
        where_files=where_files,
        why=args.why or parent.get("why", "待定義"),
        how_task_type=args.how_type or "Implementation",
        how_strategy=args.how_strategy or "待定義",
        # 關係
        parent_id=args.parent_id,
        blocked_by=None,
        # 驗收
        acceptance=None,
    )

    ticket_path = save_ticket(version, ticket_id, content)

    print(f"[OK] 已建立子 Ticket: {ticket_id}")
    print(f"   Location: {ticket_path}")
    print(f"   Parent: {args.parent_id}")

    # 更新 parent 的 children
    if update_parent_children(version, args.parent_id, ticket_id):
        print(f"   (已更新 parent 的 children)")
    else:
        print(f"   [Warning] 無法更新 Parent 的 children")

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """初始化版本目錄"""
    version = args.version
    ensure_directories(version)

    version_dir = get_version_dir(version)
    tickets_dir = get_tickets_dir(version)

    print(f"[OK] 已初始化 v{version}")
    print(f"   目錄: {version_dir}")
    print(f"   Tickets: {tickets_dir}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """列出所有 Tickets"""
    version = args.version
    tickets = list_tickets(version)

    if not tickets:
        print(f"[Info] v{version} 沒有 Tickets")
        return 0

    print(f"[List] v{version} Tickets ({len(tickets)} 個)")
    print("-" * 70)

    for ticket in tickets:
        ticket_id = ticket.get("id", "?")
        status = ticket.get("status", "pending")
        what = ticket.get("what", "?")
        who = ticket.get("who", {})
        if isinstance(who, dict):
            who = who.get("current", "?")
        priority = ticket.get("priority", "P2")

        status_icon = {
            "pending": "[待處理]",
            "in_progress": "[進行中]",
            "completed": "[已完成]",
            "blocked": "[被阻塞]",
        }.get(status, "[?]")

        print(f"{ticket_id} | {status_icon} | {priority} | {who[:10]:10} | {what}")

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """顯示 Ticket 詳細資訊"""
    # 從 ticket_id 解析 version
    parts = args.id.split("-W")
    if len(parts) != 2:
        print(f"[Error] 無效的 Ticket ID 格式: {args.id}")
        return 1

    version = parts[0]
    ticket = load_ticket(version, args.id)

    if not ticket:
        print(f"[Error] 找不到 Ticket: {args.id}")
        return 1

    print(f"[Ticket] {ticket.get('id', '?')}")
    print("=" * 50)
    print(f"Title: {ticket.get('title', '?')}")
    print(f"Type: {ticket.get('type', '?')}")
    print(f"Status: {ticket.get('status', '?')}")
    print(f"Version: {ticket.get('version', '?')}")
    print(f"Wave: {ticket.get('wave', '?')}")
    print(f"Priority: {ticket.get('priority', '?')}")
    print()

    print("5W1H:")
    who = ticket.get("who", {})
    if isinstance(who, dict):
        print(f"  Who (current): {who.get('current', '?')}")
        history = who.get("history", {})
        if history:
            print(f"  Who (history): {history}")
    else:
        print(f"  Who: {who}")

    print(f"  What: {ticket.get('what', '?')}")
    print(f"  When: {ticket.get('when', '?')}")

    where = ticket.get("where", {})
    if isinstance(where, dict):
        print(f"  Where (layer): {where.get('layer', '?')}")
        files = where.get("files", [])
        if files:
            print(f"  Where (files):")
            for f in files:
                print(f"    - {f}")
    else:
        print(f"  Where: {where}")

    print(f"  Why: {ticket.get('why', '?')}")

    how = ticket.get("how", {})
    if isinstance(how, dict):
        print(f"  How (task_type): {how.get('task_type', '?')}")
        print(f"  How (strategy): {how.get('strategy', '?')}")
    else:
        print(f"  How: {how}")

    print()
    print("Relations:")
    print(f"  Parent: {ticket.get('parent_id', '(none)')}")
    print(f"  Children: {ticket.get('children', [])}")
    print(f"  Blocked by: {ticket.get('blockedBy', [])}")

    print()
    print("Acceptance:")
    for ac in ticket.get("acceptance", []):
        print(f"  - {ac}")

    return 0


# ============================================================
# 主程式
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Atomic Ticket Creator v2.0 - 5W1H 引導式建立與版本驅動管理"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化版本目錄")
    init_parser.add_argument("version", help="版本號 (例如: 0.29.0)")

    # create 命令
    create_parser = subparsers.add_parser("create", help="建立新的 Atomic Ticket")
    create_parser.add_argument("--version", required=True, help="版本號")
    create_parser.add_argument("--wave", type=int, required=True, help="Wave 編號")
    create_parser.add_argument("--seq", type=int, help="序號（自動產生）")
    create_parser.add_argument("--action", required=True, help="動詞")
    create_parser.add_argument("--target", required=True, help="目標")
    create_parser.add_argument("--title", help="標題（預設: action + target）")
    create_parser.add_argument("--type", help="類型: IMP, RES, ANA, INV, DOC（預設: IMP）")
    create_parser.add_argument("--priority", help="優先級: P0, P1, P2, P3（預設: P2）")
    # 5W1H
    create_parser.add_argument("--who", help="執行代理人")
    create_parser.add_argument("--what", help="任務描述（預設: action + target）")
    create_parser.add_argument("--when", help="觸發時機")
    create_parser.add_argument("--where-layer", help="架構層級: Domain, Application, Infrastructure, Presentation")
    create_parser.add_argument("--where-files", help="影響檔案（逗號分隔）")
    create_parser.add_argument("--why", help="需求依據")
    create_parser.add_argument("--how-type", help="Task Type: Implementation, Analysis, etc.")
    create_parser.add_argument("--how-strategy", help="實作策略")
    # 關係
    create_parser.add_argument("--parent", help="父 Ticket ID")
    create_parser.add_argument("--blocked-by", help="依賴的 Ticket IDs（逗號分隔）")
    # 驗收
    create_parser.add_argument("--acceptance", help="驗收條件（| 分隔）")

    # create-child 命令
    child_parser = subparsers.add_parser("create-child", help="建立子 Ticket")
    child_parser.add_argument("--parent-id", required=True, help="父 Ticket ID")
    child_parser.add_argument("--wave", type=int, required=True, help="Wave 編號")
    child_parser.add_argument("--action", required=True, help="動詞")
    child_parser.add_argument("--target", required=True, help="目標")
    child_parser.add_argument("--title", help="標題")
    child_parser.add_argument("--type", help="類型")
    child_parser.add_argument("--priority", help="優先級")
    child_parser.add_argument("--who", help="執行代理人")
    child_parser.add_argument("--what", help="任務描述")
    child_parser.add_argument("--when", help="觸發時機")
    child_parser.add_argument("--where-layer", help="架構層級")
    child_parser.add_argument("--where-files", help="影響檔案")
    child_parser.add_argument("--why", help="需求依據")
    child_parser.add_argument("--how-type", help="Task Type")
    child_parser.add_argument("--how-strategy", help="實作策略")

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
        "create-child": cmd_create_child,
        "list": cmd_list,
        "show": cmd_show,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
