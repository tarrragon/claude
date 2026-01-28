#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Ticket 追蹤系統 v2.1 - 欄位化操作與批量處理

支援功能:
- READ: query, list, summary, version, tree, agent, who, what, when, where, why, how,
        full, log, batch-status
- UPDATE: claim, complete, release, phase, add-child, set-who, set-what, set-where,
          set-why, set-how, set-version, set-priority, batch-claim, batch-complete,
          append-log, check-acceptance

使用方式:
    uv run .claude/skills/ticket-track/scripts/ticket-tracker.py <command> [options]

環境變數:
    TICKET_TRACKER_INTERNAL=1  - 內部呼叫標記，繞過 Hook 檢查
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

import yaml


# 常數定義
WORK_LOGS_DIR = Path("docs/work-logs")
TICKETS_DIR = "tickets"

# 狀態常數
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_BLOCKED = "blocked"


def get_project_root() -> Path:
    """取得專案根目錄"""
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

    version_pattern = re.compile(r"^v\d+\.\d+\.\d+$")
    versions = [
        d.name for d in work_logs.iterdir()
        if d.is_dir() and version_pattern.match(d.name)
    ]

    if not versions:
        return None

    def version_key(v: str) -> tuple:
        parts = v[1:].split(".")
        return tuple(int(p) for p in parts)

    versions.sort(key=version_key, reverse=True)
    return versions[0]


def get_tickets_dir(version: str) -> Path:
    """取得 Tickets 目錄路徑"""
    root = get_project_root()
    version_dir = version if version.startswith("v") else f"v{version}"
    return root / WORK_LOGS_DIR / version_dir / TICKETS_DIR


def get_ticket_path(version: str, ticket_id: str) -> Path:
    """取得 Ticket 檔案路徑"""
    tickets_dir = get_tickets_dir(version)
    # 支援 .md 和 .yaml 格式
    md_path = tickets_dir / f"{ticket_id}.md"
    yaml_path = tickets_dir / f"{ticket_id}.yaml"
    if md_path.exists():
        return md_path
    return yaml_path


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 Markdown frontmatter"""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].strip()
        return frontmatter or {}, body
    except yaml.YAMLError:
        return {}, content


def load_ticket(version: str, ticket_id: str) -> Optional[dict]:
    """載入 Ticket 資料"""
    ticket_path = get_ticket_path(version, ticket_id)

    if not ticket_path.exists():
        return None

    with open(ticket_path, "r", encoding="utf-8") as f:
        content = f.read()

    if ticket_path.suffix == ".md":
        frontmatter, body = parse_frontmatter(content)
        frontmatter["_body"] = body
        frontmatter["_path"] = str(ticket_path)
        return frontmatter
    else:
        data = yaml.safe_load(content)
        if data:
            data["_path"] = str(ticket_path)
            # 支援 ticket 包裝格式
            if "ticket" in data:
                data = data["ticket"]
                data["_path"] = str(ticket_path)
        return data


def save_ticket(ticket: dict, ticket_path: Path) -> None:
    """儲存 Ticket 資料"""
    body = ticket.pop("_body", "")
    path_str = ticket.pop("_path", None)

    if ticket_path.suffix == ".md":
        # Markdown 格式
        frontmatter = yaml.dump(ticket, allow_unicode=True, default_flow_style=False, sort_keys=False)
        content = f"---\n{frontmatter}---\n\n{body}"
    else:
        # YAML 格式
        content = yaml.dump({"ticket": ticket}, allow_unicode=True, default_flow_style=False, sort_keys=False)

    with open(ticket_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 恢復 _body 和 _path
    if body:
        ticket["_body"] = body
    if path_str:
        ticket["_path"] = path_str


def list_tickets(version: str) -> list[dict]:
    """列出版本的所有 Tickets"""
    tickets_dir = get_tickets_dir(version)
    if not tickets_dir.exists():
        return []

    tickets = []
    for ticket_file in sorted(tickets_dir.glob("*.md")) + sorted(tickets_dir.glob("*.yaml")):
        ticket_id = ticket_file.stem
        ticket = load_ticket(version, ticket_id)
        if ticket:
            tickets.append(ticket)

    return tickets


def get_status_icon(status: str) -> str:
    """取得狀態圖示"""
    icons = {
        STATUS_PENDING: "[待處理]",
        STATUS_IN_PROGRESS: "[進行中]",
        STATUS_COMPLETED: "[已完成]",
        STATUS_BLOCKED: "[被阻塞]",
    }
    return icons.get(status, "[?]")


def format_elapsed_time(started_at: str) -> str:
    """計算經過時間"""
    if not started_at:
        return ""

    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        elapsed = datetime.now() - start.replace(tzinfo=None)

        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)

        if hours > 0:
            return f"(已 {hours}h{minutes}m)"
        return f"(已 {minutes}m)"
    except (ValueError, TypeError):
        return ""


def get_ticket_what(ticket: dict) -> str:
    """取得 Ticket 的 what 描述"""
    # 優先使用 what 欄位
    if ticket.get("what"):
        return ticket["what"]

    # 次選：action + target
    action = ticket.get("action", "")
    target = ticket.get("target", "")
    if action and target:
        return f"{action} {target}"

    # 最後：title 或 id
    return ticket.get("title", ticket.get("id", ticket.get("ticket_id", "?")))


def get_nested_value(data: dict, key: str) -> Any:
    """取得巢狀字典的值"""
    if not data:
        return None

    if "." in key:
        parts = key.split(".", 1)
        return get_nested_value(data.get(parts[0], {}), parts[1])

    return data.get(key)


def set_nested_value(data: dict, key: str, value: Any) -> None:
    """設定巢狀字典的值"""
    if "." in key:
        parts = key.split(".", 1)
        if parts[0] not in data:
            data[parts[0]] = {}
        set_nested_value(data[parts[0]], parts[1], value)
    else:
        data[key] = value


# ============ READ 命令 ============

def cmd_query(args: argparse.Namespace) -> int:
    """查詢單一 Ticket"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    status = ticket.get("status", STATUS_PENDING)
    icon = get_status_icon(status)
    elapsed = format_elapsed_time(ticket.get("started_at", ""))
    what = get_ticket_what(ticket)

    print(f"{icon} {args.ticket_id} | {what} {elapsed}")
    print(f"   Status: {status}")
    print(f"   Version: {ticket.get('version', version)}")
    print(f"   Priority: {ticket.get('priority', 'P2')}")
    print()
    print("5W1H:")

    # who 欄位可能是字串或物件
    who = ticket.get("who", "?")
    if isinstance(who, dict):
        print(f"   Who (current): {who.get('current', '?')}")
        history = who.get("history", {})
        if history:
            print(f"   Who (history): {history}")
    else:
        print(f"   Who: {who}")

    print(f"   What: {ticket.get('what', '?')}")
    print(f"   When: {ticket.get('when', '?')}")

    # where 欄位可能是字串或物件
    where = ticket.get("where", "?")
    if isinstance(where, dict):
        print(f"   Where (layer): {where.get('layer', '?')}")
        files = where.get("files", [])
        if files:
            print(f"   Where (files): {files}")
    else:
        print(f"   Where: {where}")

    print(f"   Why: {ticket.get('why', '?')}")

    # how 欄位可能是字串或物件
    how = ticket.get("how", "?")
    if isinstance(how, dict):
        print(f"   How (task_type): {how.get('task_type', '?')}")
        print(f"   How (strategy): {how.get('strategy', '?')}")
    else:
        print(f"   How: {how}")

    # 關係欄位
    parent_id = ticket.get("parent_id")
    children = ticket.get("children", [])
    blocked_by = ticket.get("blockedBy", [])

    if parent_id or children or blocked_by:
        print()
        print("Relations:")
        if parent_id:
            print(f"   Parent: {parent_id}")
        if children:
            print(f"   Children: {children}")
        if blocked_by:
            print(f"   Blocked by: {blocked_by}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """列出 Tickets"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    tickets = list_tickets(version)

    if not tickets:
        print(f"[Info] {version} 沒有 Tickets")
        return 0

    # 過濾
    if args.in_progress:
        tickets = [t for t in tickets if t.get("status") == STATUS_IN_PROGRESS]
    elif args.pending:
        tickets = [t for t in tickets if t.get("status") == STATUS_PENDING]
    elif args.completed:
        tickets = [t for t in tickets if t.get("status") == STATUS_COMPLETED]
    elif args.blocked:
        tickets = [t for t in tickets if t.get("status") == STATUS_BLOCKED]

    if not tickets:
        print("[Info] 沒有符合條件的 Tickets")
        return 0

    for ticket in tickets:
        ticket_id = ticket.get("id", ticket.get("ticket_id", "?"))
        status = ticket.get("status", STATUS_PENDING)
        icon = get_status_icon(status)
        elapsed = format_elapsed_time(ticket.get("started_at", ""))
        what = get_ticket_what(ticket)

        # who 可能是物件
        who = ticket.get("who", "?")
        if isinstance(who, dict):
            who = who.get("current", "?")
        who_short = who.split("-")[0] if "-" in str(who) else str(who)

        print(f"{ticket_id} | {icon} | {who_short} | {what} {elapsed}")

    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """快速摘要"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    tickets = list_tickets(version)

    if not tickets:
        print(f"[Summary] {version} (0/0 完成)")
        print("   沒有 Tickets")
        return 0

    completed = sum(1 for t in tickets if t.get("status") == STATUS_COMPLETED)
    in_progress = sum(1 for t in tickets if t.get("status") == STATUS_IN_PROGRESS)
    pending = sum(1 for t in tickets if t.get("status") == STATUS_PENDING)
    blocked = sum(1 for t in tickets if t.get("status") == STATUS_BLOCKED)
    total = len(tickets)

    print(f"[Summary] {version} ({completed}/{total} 完成)")
    print(f"   [已完成]: {completed} | [進行中]: {in_progress} | [待處理]: {pending} | [被阻塞]: {blocked}")
    print("-" * 80)

    for ticket in tickets:
        ticket_id = ticket.get("id", ticket.get("ticket_id", "?"))
        status = ticket.get("status", STATUS_PENDING)
        icon = get_status_icon(status)
        elapsed = format_elapsed_time(ticket.get("started_at", ""))
        what = get_ticket_what(ticket)

        who = ticket.get("who", "?")
        if isinstance(who, dict):
            who = who.get("current", "?")
        who_short = who.split("-")[0] if "-" in str(who) else str(who)

        print(f"{ticket_id} | {icon} | {who_short:10} | {what} {elapsed}")

    return 0


def cmd_version_query(args: argparse.Namespace) -> int:
    """版本進度查詢"""
    version = args.target_version
    if not version.startswith("v"):
        version = f"v{version}"

    tickets = list_tickets(version)

    if not tickets:
        print(f"[Version] {version} 沒有 Tickets")
        return 0

    # 按小版本分組
    version_groups: dict[str, list] = {}
    for ticket in tickets:
        ticket_version = ticket.get("version", "unknown")
        if ticket_version not in version_groups:
            version_groups[ticket_version] = []
        version_groups[ticket_version].append(ticket)

    print(f"[Version] {version} 進度報告")
    print("=" * 60)

    for ver in sorted(version_groups.keys()):
        group = version_groups[ver]
        completed = sum(1 for t in group if t.get("status") == STATUS_COMPLETED)
        total = len(group)

        print(f"\n{ver} ({completed}/{total} 完成)")
        print("-" * 40)

        for ticket in group:
            ticket_id = ticket.get("id", ticket.get("ticket_id", "?"))
            status = ticket.get("status", STATUS_PENDING)
            icon = get_status_icon(status)
            what = get_ticket_what(ticket)
            print(f"  {ticket_id} | {icon} | {what}")

    return 0


def cmd_tree(args: argparse.Namespace) -> int:
    """樹狀查詢"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    print(f"[Tree] {args.ticket_id}")
    print("=" * 40)

    # 顯示父 Ticket
    parent_id = ticket.get("parent_id")
    if parent_id:
        parent = load_ticket(version, parent_id)
        if parent:
            status = get_status_icon(parent.get("status", STATUS_PENDING))
            what = get_ticket_what(parent)
            print(f"Parent: {parent_id} {status} - {what}")
        else:
            print(f"Parent: {parent_id} (not found)")
    else:
        print("Parent: (none)")

    print()

    # 顯示當前 Ticket
    status = get_status_icon(ticket.get("status", STATUS_PENDING))
    what = get_ticket_what(ticket)
    print(f"Current: {args.ticket_id} {status} - {what}")

    print()

    # 顯示子 Tickets
    children = ticket.get("children", [])
    if children:
        print("Children:")
        for child_id in children:
            child = load_ticket(version, child_id)
            if child:
                status = get_status_icon(child.get("status", STATUS_PENDING))
                what = get_ticket_what(child)
                print(f"  - {child_id} {status} - {what}")
            else:
                print(f"  - {child_id} (not found)")
    else:
        print("Children: (none)")

    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """代理人進度查詢"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    agent_name = args.agent_name.lower()
    tickets = list_tickets(version)

    # 過濾屬於該代理人的 Tickets
    agent_tickets = []
    for ticket in tickets:
        who = ticket.get("who", "")
        if isinstance(who, dict):
            current = who.get("current", "")
            history = who.get("history", {})
            # 檢查當前或歷史中是否有該代理人
            if agent_name in current.lower():
                agent_tickets.append(ticket)
            elif any(agent_name in str(v).lower() for v in history.values()):
                agent_tickets.append(ticket)
        elif agent_name in str(who).lower():
            agent_tickets.append(ticket)
        # 也檢查 agent 欄位
        elif agent_name in str(ticket.get("agent", "")).lower():
            agent_tickets.append(ticket)

    if not agent_tickets:
        print(f"[Agent] {args.agent_name} 沒有相關 Tickets")
        return 0

    completed = sum(1 for t in agent_tickets if t.get("status") == STATUS_COMPLETED)
    in_progress = sum(1 for t in agent_tickets if t.get("status") == STATUS_IN_PROGRESS)
    pending = sum(1 for t in agent_tickets if t.get("status") == STATUS_PENDING)
    total = len(agent_tickets)

    print(f"[Agent] {args.agent_name} ({completed}/{total} 完成)")
    print(f"   [已完成]: {completed} | [進行中]: {in_progress} | [待處理]: {pending}")
    print("-" * 60)

    for ticket in agent_tickets:
        ticket_id = ticket.get("id", ticket.get("ticket_id", "?"))
        status = ticket.get("status", STATUS_PENDING)
        icon = get_status_icon(status)
        what = get_ticket_what(ticket)
        print(f"{ticket_id} | {icon} | {what}")

    return 0


def cmd_5w1h_query(args: argparse.Namespace, field: str) -> int:
    """5W1H 單欄位查詢"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    value = ticket.get(field, "?")

    print(f"[{field.upper()}] {args.ticket_id}")

    if isinstance(value, dict):
        for k, v in value.items():
            print(f"   {k}: {v}")
    elif isinstance(value, list):
        for item in value:
            print(f"   - {item}")
    else:
        print(f"   {value}")

    return 0


def cmd_full(args: argparse.Namespace) -> int:
    """輸出完整 Ticket 內容（取代直接 Read）"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket_path = get_ticket_path(version, args.ticket_id)
    if not ticket_path.exists():
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    with open(ticket_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"=== {args.ticket_id} ===")
    print(content)
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    """輸出執行日誌（body only）"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    body = ticket.get("_body", "")
    if not body:
        print(f"[Info] {args.ticket_id} 沒有執行日誌")
        return 0

    print(f"=== {args.ticket_id} 執行日誌 ===")
    print(body)
    return 0


def cmd_batch_status(args: argparse.Namespace) -> int:
    """批量查詢狀態"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket_ids = args.ticket_ids.split(",")

    print(f"[Batch Status] {len(ticket_ids)} Tickets")
    print("-" * 60)

    for ticket_id in ticket_ids:
        ticket_id = ticket_id.strip()
        ticket = load_ticket(version, ticket_id)
        if ticket:
            status = ticket.get("status", STATUS_PENDING)
            icon = get_status_icon(status)
            what = get_ticket_what(ticket)
            print(f"{ticket_id} | {icon} | {what}")
        else:
            print(f"{ticket_id} | [錯誤] | 找不到 Ticket")

    return 0


# ============ UPDATE 命令 ============

def cmd_claim(args: argparse.Namespace) -> int:
    """接手 Ticket"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    status = ticket.get("status", STATUS_PENDING)

    if status == STATUS_IN_PROGRESS:
        print(f"[Warning] {args.ticket_id} 已被接手")
        return 1
    if status == STATUS_COMPLETED:
        print(f"[Warning] {args.ticket_id} 已完成")
        return 1

    ticket["status"] = STATUS_IN_PROGRESS
    ticket["assigned"] = True
    ticket["started_at"] = datetime.now().isoformat(timespec="seconds")

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    print(f"[OK] 已接手 {args.ticket_id}")
    print(f"   開始時間: {ticket['started_at']}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """標記完成"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    status = ticket.get("status", STATUS_PENDING)

    if status == STATUS_COMPLETED:
        print(f"[Warning] {args.ticket_id} 已完成")
        return 1

    ticket["status"] = STATUS_COMPLETED
    ticket["completed_at"] = datetime.now().isoformat(timespec="seconds")

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    elapsed = format_elapsed_time(ticket.get("started_at", ""))
    print(f"[OK] 已完成 {args.ticket_id} {elapsed}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    """放棄 Ticket"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    status = ticket.get("status", STATUS_PENDING)

    if status == STATUS_PENDING:
        print(f"[Warning] {args.ticket_id} 尚未被接手")
        return 1
    if status == STATUS_COMPLETED:
        print(f"[Warning] {args.ticket_id} 已完成，無法放棄")
        return 1

    ticket["status"] = STATUS_PENDING
    ticket["assigned"] = False
    ticket["started_at"] = None

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    print(f"[OK] 已放棄 {args.ticket_id}")
    return 0


def cmd_phase(args: argparse.Namespace) -> int:
    """更新 Phase（記錄 who.history）"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    # 確保 who 是物件格式
    who = ticket.get("who", {})
    if not isinstance(who, dict):
        who = {"current": who, "history": {}}

    if "history" not in who:
        who["history"] = {}

    # 更新 history 和 current
    who["history"][args.phase] = args.agent
    who["current"] = args.agent
    ticket["who"] = who

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    print(f"[OK] 已更新 {args.ticket_id} Phase {args.phase} -> {args.agent}")
    return 0


def cmd_add_child(args: argparse.Namespace) -> int:
    """添加子 Ticket"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    parent = load_ticket(version, args.parent_id)
    if not parent:
        print(f"[Error] 找不到 Parent Ticket {args.parent_id}")
        return 1

    child = load_ticket(version, args.child_id)
    if not child:
        print(f"[Error] 找不到 Child Ticket {args.child_id}")
        return 1

    # 更新 parent 的 children 欄位
    children = parent.get("children", [])
    if args.child_id not in children:
        children.append(args.child_id)
        parent["children"] = children

    # 更新 child 的 parent_id 欄位
    child["parent_id"] = args.parent_id

    # 儲存
    parent_path = Path(parent.get("_path", get_ticket_path(version, args.parent_id)))
    child_path = Path(child.get("_path", get_ticket_path(version, args.child_id)))

    save_ticket(parent, parent_path)
    save_ticket(child, child_path)

    print(f"[OK] 已添加 {args.child_id} 為 {args.parent_id} 的子 Ticket")
    return 0


def cmd_set_field(args: argparse.Namespace, field: str) -> int:
    """設定 5W1H 單欄位"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    # 取得值
    value = args.value

    # 特殊處理：who 欄位更新 current
    if field == "who":
        who = ticket.get("who", {})
        if not isinstance(who, dict):
            who = {"current": who, "history": {}}
        who["current"] = value
        ticket["who"] = who
    # 特殊處理：where 欄位更新 layer
    elif field == "where":
        where = ticket.get("where", {})
        if not isinstance(where, dict):
            where = {"layer": where, "files": []}
        where["layer"] = value
        ticket["where"] = where
    # 特殊處理：how 欄位更新 task_type
    elif field == "how":
        how = ticket.get("how", {})
        if not isinstance(how, dict):
            how = {"task_type": how, "strategy": ""}
        how["task_type"] = value
        ticket["how"] = how
    else:
        ticket[field] = value

    # 更新 updated 時間
    ticket["updated"] = datetime.now().strftime("%Y-%m-%d")

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    print(f"[OK] 已更新 {args.ticket_id} {field} = {value}")
    return 0


def cmd_set_version(args: argparse.Namespace) -> int:
    """更新版本"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    ticket["version"] = args.target_version
    ticket["updated"] = datetime.now().strftime("%Y-%m-%d")

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    print(f"[OK] 已更新 {args.ticket_id} version = {args.target_version}")
    return 0


def cmd_set_priority(args: argparse.Namespace) -> int:
    """更新優先級"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    # 驗證優先級格式
    priority = args.priority.upper()
    if priority not in ["P0", "P1", "P2", "P3"]:
        print(f"[Error] 無效的優先級: {args.priority}，有效值: P0, P1, P2, P3")
        return 1

    ticket["priority"] = priority
    ticket["updated"] = datetime.now().strftime("%Y-%m-%d")

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    print(f"[OK] 已更新 {args.ticket_id} priority = {priority}")
    return 0


def cmd_batch_claim(args: argparse.Namespace) -> int:
    """批量認領 Tickets"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket_ids = args.ticket_ids.split(",")
    success_count = 0
    fail_count = 0

    print(f"[Batch Claim] 認領 {len(ticket_ids)} Tickets")
    print("-" * 60)

    for ticket_id in ticket_ids:
        ticket_id = ticket_id.strip()
        ticket = load_ticket(version, ticket_id)

        if not ticket:
            print(f"{ticket_id} | [失敗] 找不到 Ticket")
            fail_count += 1
            continue

        status = ticket.get("status", STATUS_PENDING)
        if status == STATUS_IN_PROGRESS:
            print(f"{ticket_id} | [跳過] 已被接手")
            continue
        if status == STATUS_COMPLETED:
            print(f"{ticket_id} | [跳過] 已完成")
            continue

        ticket["status"] = STATUS_IN_PROGRESS
        ticket["assigned"] = True
        ticket["started_at"] = datetime.now().isoformat(timespec="seconds")

        ticket_path = Path(ticket.get("_path", get_ticket_path(version, ticket_id)))
        save_ticket(ticket, ticket_path)

        print(f"{ticket_id} | [成功] 已接手")
        success_count += 1

    print("-" * 60)
    print(f"結果: {success_count} 成功, {fail_count} 失敗")
    return 0 if fail_count == 0 else 1


def cmd_batch_complete(args: argparse.Namespace) -> int:
    """批量完成 Tickets"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket_ids = args.ticket_ids.split(",")
    success_count = 0
    fail_count = 0

    print(f"[Batch Complete] 完成 {len(ticket_ids)} Tickets")
    print("-" * 60)

    for ticket_id in ticket_ids:
        ticket_id = ticket_id.strip()
        ticket = load_ticket(version, ticket_id)

        if not ticket:
            print(f"{ticket_id} | [失敗] 找不到 Ticket")
            fail_count += 1
            continue

        status = ticket.get("status", STATUS_PENDING)
        if status == STATUS_COMPLETED:
            print(f"{ticket_id} | [跳過] 已完成")
            continue

        ticket["status"] = STATUS_COMPLETED
        ticket["completed_at"] = datetime.now().isoformat(timespec="seconds")

        ticket_path = Path(ticket.get("_path", get_ticket_path(version, ticket_id)))
        save_ticket(ticket, ticket_path)

        print(f"{ticket_id} | [成功] 已完成")
        success_count += 1

    print("-" * 60)
    print(f"結果: {success_count} 成功, {fail_count} 失敗")
    return 0 if fail_count == 0 else 1


def cmd_append_log(args: argparse.Namespace) -> int:
    """追加執行日誌到指定區段"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    body = ticket.get("_body", "")
    section_header = f"## {args.section}"
    content_to_add = args.content

    # 添加時間戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"\n[{timestamp}] {content_to_add}"

    # 查找區段並追加內容
    if section_header in body:
        # 找到區段位置
        lines = body.split("\n")
        new_lines = []
        in_target_section = False

        for i, line in enumerate(lines):
            new_lines.append(line)
            if line.strip() == section_header:
                in_target_section = True
            elif in_target_section and line.startswith("## "):
                # 進入下一個區段前插入內容
                new_lines.insert(-1, log_entry)
                in_target_section = False

        # 如果區段在末尾
        if in_target_section:
            new_lines.append(log_entry)

        body = "\n".join(new_lines)
    else:
        # 區段不存在，新增區段
        body = body.rstrip() + f"\n\n{section_header}\n{log_entry}"

    ticket["_body"] = body
    ticket["updated"] = datetime.now().strftime("%Y-%m-%d")

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    print(f"[OK] 已追加到 {args.ticket_id} 的 {args.section} 區段")
    return 0


def cmd_check_acceptance(args: argparse.Namespace) -> int:
    """勾選驗收條件"""
    version = args.version or get_current_version()
    if not version:
        print("[Error] 無法偵測版本，請使用 --version 指定")
        return 1

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(f"[Error] 找不到 Ticket {args.ticket_id}")
        return 1

    body = ticket.get("_body", "")
    index = args.index

    # 查找驗收條件（格式：- [ ] 或 - [x]）
    lines = body.split("\n")
    checkbox_count = 0
    target_line_idx = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            if checkbox_count == index:
                target_line_idx = i
                break
            checkbox_count += 1

    if target_line_idx == -1:
        print(f"[Error] 找不到索引 {index} 的驗收條件（共 {checkbox_count} 個）")
        return 1

    # 勾選
    old_line = lines[target_line_idx]
    if "- [ ]" in old_line:
        lines[target_line_idx] = old_line.replace("- [ ]", "- [x]", 1)
        action = "勾選"
    else:
        lines[target_line_idx] = old_line.replace("- [x]", "- [ ]", 1)
        action = "取消勾選"

    ticket["_body"] = "\n".join(lines)
    ticket["updated"] = datetime.now().strftime("%Y-%m-%d")

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    condition_text = lines[target_line_idx].strip()
    print(f"[OK] 已{action}驗收條件 #{index}: {condition_text}")
    return 0


# ============ 主程式 ============

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ticket 追蹤系統 v2.1 - 欄位化操作與批量處理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # === READ 命令 ===

    # query
    p_query = subparsers.add_parser("query", help="查詢單一 Ticket")
    p_query.add_argument("ticket_id", help="票號")
    p_query.add_argument("--version", help="版本號（自動偵測）")

    # list
    p_list = subparsers.add_parser("list", help="列出 Tickets")
    p_list.add_argument("--in-progress", action="store_true", help="只顯示進行中")
    p_list.add_argument("--pending", action="store_true", help="只顯示待處理")
    p_list.add_argument("--completed", action="store_true", help="只顯示已完成")
    p_list.add_argument("--blocked", action="store_true", help="只顯示被阻塞")
    p_list.add_argument("--version", help="版本號（自動偵測）")

    # summary
    p_summary = subparsers.add_parser("summary", help="快速摘要")
    p_summary.add_argument("--version", help="版本號（自動偵測）")

    # version (版本進度查詢)
    p_version = subparsers.add_parser("version", help="版本進度查詢")
    p_version.add_argument("target_version", help="目標版本號")

    # tree (樹狀查詢)
    p_tree = subparsers.add_parser("tree", help="樹狀查詢")
    p_tree.add_argument("ticket_id", help="票號")
    p_tree.add_argument("--version", help="版本號（自動偵測）")

    # agent (代理人進度查詢)
    p_agent = subparsers.add_parser("agent", help="代理人進度查詢")
    p_agent.add_argument("agent_name", help="代理人名稱")
    p_agent.add_argument("--version", help="版本號（自動偵測）")

    # 5W1H 單欄位查詢
    for field in ["who", "what", "when", "where", "why", "how"]:
        p = subparsers.add_parser(field, help=f"查詢 {field} 欄位")
        p.add_argument("ticket_id", help="票號")
        p.add_argument("--version", help="版本號（自動偵測）")

    # full (完整內容輸出)
    p_full = subparsers.add_parser("full", help="輸出完整 Ticket 內容")
    p_full.add_argument("ticket_id", help="票號")
    p_full.add_argument("--version", help="版本號（自動偵測）")

    # log (執行日誌輸出)
    p_log = subparsers.add_parser("log", help="輸出執行日誌")
    p_log.add_argument("ticket_id", help="票號")
    p_log.add_argument("--version", help="版本號（自動偵測）")

    # batch-status (批量查詢狀態)
    p_batch_status = subparsers.add_parser("batch-status", help="批量查詢狀態")
    p_batch_status.add_argument("ticket_ids", help="票號列表（逗號分隔）")
    p_batch_status.add_argument("--version", help="版本號（自動偵測）")

    # === UPDATE 命令 ===

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

    # phase (更新 Phase)
    p_phase = subparsers.add_parser("phase", help="更新 Phase")
    p_phase.add_argument("ticket_id", help="票號")
    p_phase.add_argument("phase", help="Phase 名稱 (phase1, phase2, phase3a, phase3b, phase4)")
    p_phase.add_argument("agent", help="代理人名稱")
    p_phase.add_argument("--version", help="版本號（自動偵測）")

    # add-child (添加子 Ticket)
    p_add_child = subparsers.add_parser("add-child", help="添加子 Ticket")
    p_add_child.add_argument("parent_id", help="父 Ticket ID")
    p_add_child.add_argument("child_id", help="子 Ticket ID")
    p_add_child.add_argument("--version", help="版本號（自動偵測）")

    # set-* (設定 5W1H 欄位)
    for field in ["who", "what", "when", "where", "why", "how"]:
        p = subparsers.add_parser(f"set-{field}", help=f"設定 {field} 欄位")
        p.add_argument("ticket_id", help="票號")
        p.add_argument("value", help=f"{field} 的值")
        p.add_argument("--version", help="版本號（自動偵測）")

    # set-version (更新版本)
    p_set_version = subparsers.add_parser("set-version", help="更新版本")
    p_set_version.add_argument("ticket_id", help="票號")
    p_set_version.add_argument("target_version", help="目標版本號")
    p_set_version.add_argument("--version", help="版本號（自動偵測）")

    # set-priority (更新優先級)
    p_set_priority = subparsers.add_parser("set-priority", help="更新優先級")
    p_set_priority.add_argument("ticket_id", help="票號")
    p_set_priority.add_argument("priority", help="優先級 (P0/P1/P2/P3)")
    p_set_priority.add_argument("--version", help="版本號（自動偵測）")

    # batch-claim (批量認領)
    p_batch_claim = subparsers.add_parser("batch-claim", help="批量認領 Tickets")
    p_batch_claim.add_argument("ticket_ids", help="票號列表（逗號分隔）")
    p_batch_claim.add_argument("--version", help="版本號（自動偵測）")

    # batch-complete (批量完成)
    p_batch_complete = subparsers.add_parser("batch-complete", help="批量完成 Tickets")
    p_batch_complete.add_argument("ticket_ids", help="票號列表（逗號分隔）")
    p_batch_complete.add_argument("--version", help="版本號（自動偵測）")

    # append-log (追加執行日誌)
    p_append_log = subparsers.add_parser("append-log", help="追加執行日誌")
    p_append_log.add_argument("ticket_id", help="票號")
    p_append_log.add_argument("--section", required=True, help="區段名稱 (Problem Analysis/Solution/Notes 等)")
    p_append_log.add_argument("content", help="日誌內容")
    p_append_log.add_argument("--version", help="版本號（自動偵測）")

    # check-acceptance (勾選驗收條件)
    p_check_acceptance = subparsers.add_parser("check-acceptance", help="勾選驗收條件")
    p_check_acceptance.add_argument("ticket_id", help="票號")
    p_check_acceptance.add_argument("index", type=int, help="驗收條件索引（從 0 開始）")
    p_check_acceptance.add_argument("--version", help="版本號（自動偵測）")

    args = parser.parse_args()

    # 執行對應命令
    try:
        if args.command == "query":
            return cmd_query(args)
        elif args.command == "list":
            return cmd_list(args)
        elif args.command == "summary":
            return cmd_summary(args)
        elif args.command == "version":
            return cmd_version_query(args)
        elif args.command == "tree":
            return cmd_tree(args)
        elif args.command == "agent":
            return cmd_agent(args)
        elif args.command in ["who", "what", "when", "where", "why", "how"]:
            return cmd_5w1h_query(args, args.command)
        elif args.command == "full":
            return cmd_full(args)
        elif args.command == "log":
            return cmd_log(args)
        elif args.command == "batch-status":
            return cmd_batch_status(args)
        elif args.command == "claim":
            return cmd_claim(args)
        elif args.command == "complete":
            return cmd_complete(args)
        elif args.command == "release":
            return cmd_release(args)
        elif args.command == "phase":
            return cmd_phase(args)
        elif args.command == "add-child":
            return cmd_add_child(args)
        elif args.command == "set-priority":
            return cmd_set_priority(args)
        elif args.command == "batch-claim":
            return cmd_batch_claim(args)
        elif args.command == "batch-complete":
            return cmd_batch_complete(args)
        elif args.command == "append-log":
            return cmd_append_log(args)
        elif args.command == "check-acceptance":
            return cmd_check_acceptance(args)
        elif args.command.startswith("set-"):
            field = args.command[4:]  # 移除 "set-" 前綴
            return cmd_set_field(args, field)
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"[Error] 發生錯誤: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
