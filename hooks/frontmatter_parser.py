#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///

"""
YAML Frontmatter 解析模組

此模組提供 Markdown 檔案的 YAML frontmatter 解析功能，
用於新的 Ticket 系統（Markdown + Frontmatter 架構）。

核心功能：
- parse_frontmatter(): 解析 Markdown 的 frontmatter
- read_ticket(): 讀取單一 Ticket 檔案
- update_frontmatter(): 更新 frontmatter 欄位
- list_tickets(): 列出目錄中所有 tickets
- detect_format(): 偵測版本格式（markdown 或 csv）
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import yaml


# ============================================================================
# 資料結構定義
# ============================================================================

@dataclass
class TicketData:
    """Ticket 資料結構"""
    # 識別資訊
    ticket_id: str
    version: str
    wave: int

    # 單一職責定義
    action: str
    target: str

    # 執行資訊
    agent: str

    # 5W1H 設計
    who: str
    what: str
    when: str
    where: str
    why: str
    how: str

    # 驗收條件、檔案、依賴
    acceptance: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    # 狀態追蹤
    status: str = "pending"
    assigned: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 檔案相關
    file_path: Optional[Path] = None
    body: str = ""


# ============================================================================
# Frontmatter 解析輔助函式
# ============================================================================

def _extract_frontmatter_and_body(content: str) -> Optional[Tuple[str, str]]:
    """
    內部函式：從 Markdown 內容分離 frontmatter 和 body

    使用分割方式而非正規表達式，以支援各種邊界情況（包括空 frontmatter）

    Args:
        content (str): 完整的 Markdown 內容

    Returns:
        Optional[Tuple[str, str]]: (frontmatter_text, body) 或 None
    """
    parts = content.split('---', 2)

    # 必須有 3 個部分：開頭空字串, frontmatter, body
    # 例如：['', 'key: value\n', '\nbody']
    if len(parts) != 3 or parts[0].strip() != '':
        return None

    frontmatter_text = parts[1].strip()
    body = parts[2].lstrip('\n')

    return frontmatter_text, body


# ============================================================================
# 核心解析函式
# ============================================================================

def parse_frontmatter(content: str) -> Dict[str, Any]:
    """
    解析 Markdown 檔案的 YAML frontmatter

    Args:
        content (str): Markdown 檔案內容

    Returns:
        Dict[str, Any]: 解析後的 frontmatter 字典

    Raises:
        ValueError: 如果 frontmatter 格式無效或 YAML 解析失敗
    """
    try:
        result = _extract_frontmatter_and_body(content)
        if result is None:
            raise ValueError("找不到有效的 frontmatter 格式（--- ... ---）")

        frontmatter_text, _ = result

        # 使用 PyYAML 解析 YAML
        # 空 frontmatter 視為空字典
        if not frontmatter_text:
            return {}

        try:
            frontmatter_dict = yaml.safe_load(frontmatter_text)
            return frontmatter_dict or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析失敗: {e}")

    except Exception as e:
        raise ValueError(f"Frontmatter 解析錯誤: {e}")


def extract_body(content: str) -> str:
    """
    從 Markdown 檔案中提取 body 內容（frontmatter 之後的部分）

    Args:
        content (str): Markdown 檔案內容

    Returns:
        str: Body 內容
    """
    result = _extract_frontmatter_and_body(content)
    if result:
        _, body = result
        return body
    return content


def read_ticket(file_path: Path) -> TicketData:
    """
    讀取 Ticket 檔案並解析 frontmatter

    Args:
        file_path (Path): Ticket 檔案路徑

    Returns:
        TicketData: 解析後的 Ticket 資料

    Raises:
        FileNotFoundError: 如果檔案不存在
        ValueError: 如果 frontmatter 解析失敗或缺少必需欄位
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Ticket 檔案不存在: {file_path}")

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        raise ValueError(f"讀取 Ticket 檔案失敗: {e}")

    # 解析 frontmatter
    try:
        frontmatter = parse_frontmatter(content)
    except ValueError as e:
        raise ValueError(f"Ticket {file_path.name} frontmatter 解析失敗: {e}")

    # 提取必需欄位（有預設值的除外）
    required_fields = [
        'ticket_id', 'version', 'wave', 'action', 'target', 'agent',
        'who', 'what', 'when', 'where', 'why', 'how'
    ]

    missing_fields = [f for f in required_fields if f not in frontmatter]
    if missing_fields:
        raise ValueError(
            f"Ticket {file_path.name} 缺少必需欄位: {', '.join(missing_fields)}"
        )

    # 轉換日期時間欄位
    started_at = None
    completed_at = None

    if frontmatter.get('started_at'):
        try:
            started_at = datetime.fromisoformat(str(frontmatter['started_at']))
        except (ValueError, TypeError):
            pass

    if frontmatter.get('completed_at'):
        try:
            completed_at = datetime.fromisoformat(str(frontmatter['completed_at']))
        except (ValueError, TypeError):
            pass

    # 構建 TicketData
    ticket_data = TicketData(
        ticket_id=frontmatter['ticket_id'],
        version=frontmatter['version'],
        wave=int(frontmatter['wave']),
        action=frontmatter['action'],
        target=frontmatter['target'],
        agent=frontmatter['agent'],
        who=frontmatter['who'],
        what=frontmatter['what'],
        when=frontmatter['when'],
        where=frontmatter['where'],
        why=frontmatter['why'],
        how=frontmatter['how'],
        acceptance=frontmatter.get('acceptance', []),
        files=frontmatter.get('files', []),
        dependencies=frontmatter.get('dependencies', []),
        status=frontmatter.get('status', 'pending'),
        assigned=frontmatter.get('assigned', False),
        started_at=started_at,
        completed_at=completed_at,
        file_path=file_path,
        body=extract_body(content)
    )

    return ticket_data


def update_frontmatter(file_path: Path, updates: Dict[str, Any]) -> bool:
    """
    更新 frontmatter 中的特定欄位，保留 body 內容

    Args:
        file_path (Path): Ticket 檔案路徑
        updates (Dict[str, Any]): 要更新的欄位字典

    Returns:
        bool: 更新成功則返回 True

    Raises:
        FileNotFoundError: 如果檔案不存在
        ValueError: 如果 frontmatter 解析或更新失敗
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Ticket 檔案不存在: {file_path}")

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        raise ValueError(f"讀取 Ticket 檔案失敗: {e}")

    # 解析現有的 frontmatter 和 body
    try:
        frontmatter = parse_frontmatter(content)
        body = extract_body(content)
    except ValueError as e:
        raise ValueError(f"解析 frontmatter 失敗: {e}")

    # 更新 frontmatter
    frontmatter.update(updates)

    # 轉換日期時間物件為 ISO 字串
    for key in ['started_at', 'completed_at']:
        if key in frontmatter and isinstance(frontmatter[key], datetime):
            frontmatter[key] = frontmatter[key].isoformat()

    # 重新組合檔案內容
    try:
        frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        # 移除末尾的換行符（YAML 會自動加）
        frontmatter_yaml = frontmatter_yaml.rstrip('\n')

        new_content = f"---\n{frontmatter_yaml}\n---\n{body}"

        # 寫回檔案
        file_path.write_text(new_content, encoding='utf-8')
        return True
    except Exception as e:
        raise ValueError(f"寫入 Ticket 檔案失敗: {e}")


def list_tickets(tickets_dir: Path) -> List[TicketData]:
    """
    遍歷目錄中所有 .md 檔案並解析

    Args:
        tickets_dir (Path): Tickets 目錄路徑

    Returns:
        List[TicketData]: Ticket 列表

    Raises:
        FileNotFoundError: 如果目錄不存在
    """
    if not tickets_dir.exists():
        raise FileNotFoundError(f"Tickets 目錄不存在: {tickets_dir}")

    if not tickets_dir.is_dir():
        raise ValueError(f"路徑不是目錄: {tickets_dir}")

    tickets = []

    # 遍歷所有 .md 檔案（按名稱排序）
    for md_file in sorted(tickets_dir.glob("*.md")):
        try:
            ticket = read_ticket(md_file)
            tickets.append(ticket)
        except (FileNotFoundError, ValueError) as e:
            # 記錄解析失敗的檔案，但繼續處理其他檔案
            print(f"警告: 解析 {md_file.name} 失敗 - {e}", file=sys.stderr)
            continue

    return tickets


def detect_format(version_dir: Path) -> str:
    """
    偵測版本使用的格式：'markdown' 或 'csv'

    判斷邏輯：
    1. 如果存在 tickets 目錄且包含 .md 檔案 → 'markdown'
    2. 如果存在 tickets.csv → 'csv'
    3. 否則 → 'unknown'

    Args:
        version_dir (Path): 版本目錄（如 docs/work-logs/v0.16.0）

    Returns:
        str: 偵測到的格式 ('markdown', 'csv', 或 'unknown')
    """
    # 檢查 Markdown 格式
    tickets_dir = version_dir / "tickets"
    if tickets_dir.exists() and tickets_dir.is_dir():
        md_files = list(tickets_dir.glob("*.md"))
        if md_files:
            return "markdown"

    # 檢查 CSV 格式
    csv_file = version_dir / "tickets.csv"
    if csv_file.exists():
        return "csv"

    return "unknown"


# ============================================================================
# 命令行介面（用於測試和除錯）
# ============================================================================

def cmd_parse(file_path: str) -> None:
    """命令行：解析單一檔案的 frontmatter"""
    try:
        path = Path(file_path)
        frontmatter = parse_frontmatter(path.read_text(encoding='utf-8'))
        print(yaml.dump(frontmatter, default_flow_style=False))
    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_read(file_path: str) -> None:
    """命令行：讀取 Ticket 檔案"""
    try:
        ticket = read_ticket(Path(file_path))
        print(f"Ticket ID: {ticket.ticket_id}")
        print(f"版本: {ticket.version}")
        print(f"Wave: {ticket.wave}")
        print(f"Action: {ticket.action}")
        print(f"Target: {ticket.target}")
        print(f"Agent: {ticket.agent}")
        print(f"狀態: {ticket.status}")
    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(tickets_dir: str) -> None:
    """命令行：列出目錄中所有 tickets"""
    try:
        tickets = list_tickets(Path(tickets_dir))
        for ticket in tickets:
            status_icon = "✓" if ticket.status == "completed" else "→" if ticket.status == "in_progress" else "○"
            print(f"{status_icon} {ticket.ticket_id} [{ticket.agent}] {ticket.action}")
    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_detect(version_dir: str) -> None:
    """命令行：偵測版本格式"""
    try:
        fmt = detect_format(Path(version_dir))
        print(f"格式: {fmt}")
    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: frontmatter_parser.py <command> [args]")
        print("命令:")
        print("  parse <file>        - 解析 frontmatter")
        print("  read <file>         - 讀取 Ticket 檔案")
        print("  list <directory>    - 列出目錄中所有 tickets")
        print("  detect <directory>  - 偵測版本格式")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "parse" and len(sys.argv) > 2:
        cmd_parse(sys.argv[2])
    elif cmd == "read" and len(sys.argv) > 2:
        cmd_read(sys.argv[2])
    elif cmd == "list" and len(sys.argv) > 2:
        cmd_list(sys.argv[2])
    elif cmd == "detect" and len(sys.argv) > 2:
        cmd_detect(sys.argv[2])
    else:
        print(f"未知命令或參數不足: {cmd}", file=sys.stderr)
        sys.exit(1)
