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
from lib.frontmatter_parser import list_tickets as fp_list_tickets

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


def format_ticket_id(version: str, wave: int, seq: int, parent_id: str = None, child_seq: int = None) -> str:
    """格式化 Ticket ID

    Args:
        version: 版本號
        wave: 波次
        seq: 序號（根任務）
        parent_id: 父任務 ID（建立子任務時）
        child_seq: 子任務序號（建立子任務時）

    Returns:
        格式化的 Ticket ID
    """
    if parent_id and child_seq:
        # 子任務：parent_id.child_seq
        return f"{parent_id}.{child_seq}"
    else:
        # 根任務：version-W{wave}-{seq}
        return f"{version}-W{wave}-{seq:03d}"


def check_id_exists(ticket_id: str, tickets_dir: Path) -> bool:
    """檢查 Ticket ID 是否已存在

    Args:
        ticket_id: Ticket ID
        tickets_dir: Tickets 目錄路徑

    Returns:
        True 如果已存在，False 否則
    """
    md_path = tickets_dir / f"{ticket_id}.md"
    return md_path.exists()


def get_next_root_seq(version: str, wave: int, tickets_dir: Path) -> int:
    """取得下一個可用的根任務序號

    掃描 tickets_dir 中所有符合 {version}-W{wave}-XXX 格式的 Ticket，
    找出最大序號並 +1

    Args:
        version: 版本號
        wave: 波次
        tickets_dir: Tickets 目錄路徑

    Returns:
        下一個可用的根任務序號
    """
    existing = []
    prefix = f"{version}-W{wave}-"

    for ticket_file in tickets_dir.glob("*.md"):
        if ticket_file.stem.startswith(prefix):
            # 提取根序號部分
            suffix = ticket_file.stem[len(prefix):]
            # 只取第一個數字部分（忽略子任務序號如 .1.2）
            parts = suffix.split(".")
            if parts[0].isdigit():
                existing.append(int(parts[0]))

    return max(existing, default=0) + 1


def get_next_child_seq(parent_id: str, tickets_dir: Path) -> int:
    """取得父任務下一個可用的子任務序號

    Args:
        parent_id: 父任務 ID
        tickets_dir: Tickets 目錄路徑

    Returns:
        下一個可用的子任務序號
    """
    existing = []

    for ticket_file in tickets_dir.glob("*.md"):
        if ticket_file.stem.startswith(parent_id + "."):
            # 提取子序號
            suffix = ticket_file.stem[len(parent_id) + 1:]
            parts = suffix.split(".")
            if parts[0].isdigit():
                existing.append(int(parts[0]))

    return max(existing, default=0) + 1


def parse_ticket_id(ticket_id: str) -> dict:
    """解析 Ticket ID 為結構化資訊

    Args:
        ticket_id: Ticket ID 字串

    Returns:
        dict 包含 version, wave, root_seq, sequence 陣列, depth
    """
    import re

    # 匹配模式：版本-W波次-序號[.子序號...]
    pattern = r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)$"
    match = re.match(pattern, ticket_id)

    if not match:
        raise ValueError(f"無效的 Ticket ID 格式: {ticket_id}")

    version = match.group(1)
    wave = int(match.group(2))
    seq_part = match.group(3)

    # 解析序號部分
    seq_parts = [int(s) for s in seq_part.split(".")]
    root_seq = seq_parts[0]
    depth = len(seq_parts) - 1  # 根任務 depth=0

    return {
        "version": version,
        "wave": wave,
        "root_seq": root_seq,
        "sequence": seq_parts,
        "depth": depth
    }


def get_chain_info(ticket_id: str, parent_id: str = None) -> dict:
    """計算任務鏈資訊

    Args:
        ticket_id: 當前 Ticket ID
        parent_id: 父任務 ID（如果是子任務）

    Returns:
        dict 包含 root, parent, depth, sequence
    """
    parsed = parse_ticket_id(ticket_id)

    # 根任務 ID
    root_id = f"{parsed['version']}-W{parsed['wave']}-{parsed['root_seq']:03d}"

    return {
        "root": root_id,
        "parent": parent_id,
        "depth": parsed["depth"],
        "sequence": parsed["sequence"]
    }


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
    parent_id: str = None,
) -> str:
    """使用模板產生完整的 Markdown + frontmatter 內容"""
    template = load_template()

    # 計算任務鏈資訊
    chain_info = get_chain_info(ticket_id, parent_id)

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
        # 任務鏈欄位
        "${chain_root}": chain_info["root"],
        "${chain_parent}": f'"{chain_info["parent"]}"' if chain_info["parent"] else "null",
        "${chain_depth}": str(chain_info["depth"]),
        "${chain_sequence}": ", ".join(str(s) for s in chain_info["sequence"]),
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

    parent_id = getattr(args, 'parent', None)
    tickets_dir = get_tickets_dir(args.version)
    use_auto_seq = getattr(args, 'auto_seq', False)
    use_force = getattr(args, 'force', False)
    seq = getattr(args, 'seq', None)

    # 驗證根任務的序號參數
    if not parent_id and not use_auto_seq and seq is None:
        print("❌ 錯誤: 根任務必須指定 --seq 或使用 --auto-seq")
        print()
        print("   使用方式:")
        print("   1. 指定序號: --seq 1")
        print("   2. 自動序號: --auto-seq")
        return 1

    # 計算 ticket_id
    if parent_id:
        # 子任務：自動取得下一個子序號
        # 對於子任務，seq 參數被忽略
        child_seq = get_next_child_seq(parent_id, tickets_dir)
        ticket_id = format_ticket_id(args.version, args.wave, seq or 0, parent_id, child_seq)
    else:
        # 根任務：處理自動序號或編號衝突檢查
        if use_auto_seq:
            # 自動取得下一個可用序號
            seq = get_next_root_seq(args.version, args.wave, tickets_dir)
            ticket_id = format_ticket_id(args.version, args.wave, seq)
        else:
            # 使用指定的序號
            ticket_id = format_ticket_id(args.version, args.wave, seq)

            # 檢查 ID 是否已存在
            if check_id_exists(ticket_id, tickets_dir):
                if not use_force:
                    print(f"❌ 錯誤: Ticket ID 已存在: {ticket_id}")
                    print(f"   位置: {tickets_dir / f'{ticket_id}.md'}")
                    print()
                    print("   建議選項:")
                    print("   1. 使用 --auto-seq 自動取得下一個可用序號")
                    print(f"      下一個序號為: {get_next_root_seq(args.version, args.wave, tickets_dir)}")
                    print("   2. 使用 --seq N 指定其他序號")
                    print("   3. 使用 --force 強制覆蓋（不建議）")
                    return 1
                else:
                    # 強制覆蓋時輸出警告
                    print(f"⚠️  警告: 將覆蓋既有的 Ticket: {ticket_id}")
                    print(f"   位置: {tickets_dir / f'{ticket_id}.md'}")

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
            parent_id=parent_id,
        )
    except FileNotFoundError as e:
        print(f"❌ 錯誤: {e}")
        return 1

    # 寫入 Markdown 檔案
    md_path = tickets_dir / f"{ticket_id}.md"
    try:
        md_path.write_text(content, encoding='utf-8')
    except Exception as e:
        print(f"❌ 寫入檔案失敗: {e}")
        return 1

    print(f"✅ 已建立 Ticket: {ticket_id}")
    print(f"   位置: {md_path}")
    if parent_id:
        print(f"   父任務: {parent_id}")
    if use_force and check_id_exists(ticket_id, tickets_dir):
        # 已在上面的警告消息中提示，這裡只是補充說明
        pass

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
    create_parser.add_argument("--seq", type=int, required=False, help="序號（不指定時與 --auto-seq 一起使用）")
    create_parser.add_argument("--action", required=True, help="動詞 (實作/修復/新增/重構)")
    create_parser.add_argument("--target", required=True, help="單一目標")
    create_parser.add_argument("--agent", required=True, help="執行代理人")
    create_parser.add_argument("--parent", help="父任務 ID（建立子任務時使用，如 0.31.0-W3-002）")
    create_parser.add_argument("--auto-seq", action="store_true",
                              help="自動取得下一個可用序號（忽略 --seq）")
    create_parser.add_argument("--force", "-f", action="store_true",
                              help="強制覆蓋既有 Ticket（不建議）")
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
