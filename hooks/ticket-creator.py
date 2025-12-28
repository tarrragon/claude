#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Atomic Ticket Creator - 建立符合單一職責原則的 Ticket

使用方式:
  uv run .claude/hooks/ticket-creator.py create --version 0.16.0 --wave 1 --seq 1 \\
    --action "實作" --target "startScan() 方法" --agent "parsley-flutter-developer"

  uv run .claude/hooks/ticket-creator.py list --version 0.16.0
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# 導入 frontmatter_parser
sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_parser import list_tickets as fp_list_tickets

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 工作日誌目錄
WORK_LOGS_DIR = PROJECT_ROOT / "docs" / "work-logs"

# 模板檔案路徑
TEMPLATE_PATH = PROJECT_ROOT / ".claude" / "templates" / "ticket.md.template"

# 狀態定義
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"


def get_version_dir(version: str) -> Path:
    """取得版本目錄路徑"""
    return WORK_LOGS_DIR / f"v{version}"


def get_tickets_dir(version: str) -> Path:
    """取得 Tickets Markdown 目錄路徑"""
    return get_version_dir(version) / "tickets"


def ensure_directories(version: str) -> None:
    """確保目錄存在"""
    get_version_dir(version).mkdir(parents=True, exist_ok=True)
    get_tickets_dir(version).mkdir(parents=True, exist_ok=True)


def format_ticket_id(version: str, wave: int, seq: int) -> str:
    """格式化 Ticket ID"""
    return f"{version}-W{wave}-{seq:03d}"


def load_template() -> str:
    """載入 ticket.md.template 模板"""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"模板檔案不存在: {TEMPLATE_PATH}")

    return TEMPLATE_PATH.read_text(encoding='utf-8')


def format_acceptance_list(acceptance: Optional[list]) -> str:
    """將驗收條件列表格式化為 YAML 清單格式"""
    if not acceptance:
        acceptance = [
            "任務實作完成",
            "相關測試通過",
            "代碼品質檢查無警告",
        ]

    lines = []
    for item in acceptance:
        lines.append(f"  - {item}")
    return "\n".join(lines) if lines else "  []"


def format_files_list(files: Optional[list]) -> str:
    """將相關檔案列表格式化為 YAML 清單格式"""
    if not files:
        return "  []"

    lines = []
    for item in files:
        lines.append(f"  - {item}")
    return "\n".join(lines) if lines else "  []"


def format_dependencies_list(dependencies: Optional[list]) -> str:
    """將依賴列表格式化為 YAML 清單格式"""
    if not dependencies:
        return "  []"

    lines = []
    for item in dependencies:
        lines.append(f"  - {item}")
    return "\n".join(lines) if lines else "  []"


def create_ticket_markdown(
    ticket_id: str,
    version: str,
    wave: int,
    action: str,
    target: str,
    agent: str,
    who: str = "",
    what: str = "",
    when: str = "",
    where: str = "",
    why: str = "",
    how: str = "",
    acceptance: Optional[list] = None,
    files: Optional[list] = None,
    dependencies: Optional[list] = None,
    task_summary: str = "",
) -> str:
    """使用模板產生完整的 Markdown + frontmatter 內容"""
    template = load_template()

    # 準備替換資料
    replacements = {
        "${ticket_id}": ticket_id,
        "${version}": version,
        "${wave}": str(wave),
        "${action}": action,
        "${target}": target,
        "${agent}": agent,
        "${who}": who or agent,
        "${what}": what or f"{action} {target}",
        "${when}": when or "待定義",
        "${where}": where or "待定義",
        "${why}": why or "待定義",
        "${how}": how or "待定義",
        "${acceptance}": format_acceptance_list(acceptance),
        "${files}": format_files_list(files),
        "${dependencies}": format_dependencies_list(dependencies),
        "${task_summary}": task_summary or f"{action} {target}",
    }

    content = template
    for key, value in replacements.items():
        content = content.replace(key, value)

    return content


# ============================================================
# CLI 命令實作
# ============================================================


def cmd_create(args: argparse.Namespace) -> int:
    """建立新的 Atomic Ticket"""
    ensure_directories(args.version)

    ticket_id = format_ticket_id(args.version, args.wave, args.seq)

    # 產生 Markdown 內容
    try:
        content = create_ticket_markdown(
            ticket_id=ticket_id,
            version=args.version,
            wave=args.wave,
            action=args.action,
            target=args.target,
            agent=args.agent,
            who=args.who or args.agent,
            what=args.what or f"{args.action} {args.target}",
            when=args.when or "",
            where=args.where or "",
            why=args.why or "",
            how=args.how or "",
        )
    except FileNotFoundError as e:
        print(f"❌ 錯誤: {e}")
        return 1

    # 寫入 Markdown 檔案
    md_path = get_tickets_dir(args.version) / f"{ticket_id}.md"
    try:
        md_path.write_text(content, encoding='utf-8')
    except Exception as e:
        print(f"❌ 寫入檔案失敗: {e}")
        return 1

    print(f"✅ 已建立 Ticket: {ticket_id}")
    print(f"   位置: {md_path}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """列出所有 Tickets（使用 frontmatter_parser）"""
    tickets_dir = get_tickets_dir(args.version)

    if not tickets_dir.exists():
        print(f"📋 v{args.version} 沒有 Tickets 目錄")
        return 0

    try:
        tickets = fp_list_tickets(tickets_dir)
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return 1

    if not tickets:
        print(f"📋 v{args.version} 沒有 Tickets")
        return 0

    print(f"📋 v{args.version} Tickets ({len(tickets)} 個)")
    print("-" * 80)

    for ticket in tickets:
        ticket_id = ticket.ticket_id
        action = ticket.action
        target = ticket.target
        agent = ticket.agent[:15]
        status = ticket.status

        status_icon = "✓" if status == "completed" else "→" if status == "in_progress" else "○"
        print(f"{status_icon} {ticket_id} | {action} {target} | {agent}")

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """顯示 Ticket 詳細資訊（使用 frontmatter_parser）"""
    # 解析 ticket_id 取得 version
    parts = args.id.split("-W")
    if len(parts) != 2:
        print(f"❌ 無效的 Ticket ID 格式: {args.id}")
        print("   正確格式: {VERSION}-W{WAVE}-{SEQ}, 例如: 0.16.0-W1-001")
        return 1

    version = parts[0]
    md_path = get_tickets_dir(version) / f"{args.id}.md"

    if not md_path.exists():
        print(f"❌ 找不到 Ticket: {args.id}")
        return 1

    try:
        from frontmatter_parser import read_ticket
        ticket = read_ticket(md_path)
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return 1

    print(f"📋 Ticket: {ticket.ticket_id}")
    print("-" * 60)
    print(f"Action: {ticket.action}")
    print(f"Target: {ticket.target}")
    print(f"Agent: {ticket.agent}")
    print(f"Wave: {ticket.wave}")
    print(f"Status: {ticket.status}")
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
    print()
    print("Files:")
    for f in ticket.files:
        print(f"  - {f}")
    print()
    print("Dependencies:")
    if ticket.dependencies:
        for d in ticket.dependencies:
            print(f"  - {d}")
    else:
        print("  (無)")

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """初始化版本目錄"""
    ensure_directories(args.version)

    print(f"✅ 已初始化 v{args.version}")
    print(f"   目錄: {get_version_dir(args.version)}")
    print(f"   Tickets: {get_tickets_dir(args.version)}")

    return 0


# ============================================================
# 主程式
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Atomic Ticket Creator - 建立符合單一職責原則的 Ticket（Markdown + Frontmatter 格式）"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化版本目錄")
    init_parser.add_argument("version", help="版本號 (例如: 0.16.0)")

    # create 命令
    create_parser = subparsers.add_parser("create", help="建立新的 Atomic Ticket")
    create_parser.add_argument("--version", required=True, help="版本號")
    create_parser.add_argument("--wave", type=int, required=True, help="Wave 編號")
    create_parser.add_argument("--seq", type=int, required=True, help="序號")
    create_parser.add_argument("--action", required=True, help="動詞 (實作/修復/新增/重構)")
    create_parser.add_argument("--target", required=True, help="單一目標")
    create_parser.add_argument("--agent", required=True, help="執行代理人")
    create_parser.add_argument("--who", help="5W1H - Who")
    create_parser.add_argument("--what", help="5W1H - What")
    create_parser.add_argument("--when", help="5W1H - When")
    create_parser.add_argument("--where", help="5W1H - Where")
    create_parser.add_argument("--why", help="5W1H - Why")
    create_parser.add_argument("--how", help="5W1H - How")

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
        "list": cmd_list,
        "show": cmd_show,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
