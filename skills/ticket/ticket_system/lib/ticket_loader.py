"""
Ticket 載入和解析模組（統一入口）

提供向後相容的統一入口，聚合以下三個獨立模組：
- paths: 路徑管理
- version: 版本管理
- parser: 格式解析

此模組保持向後相容性，所有現有的導入都可以繼續使用。

索引快取：
為了避免每次 list_tickets() 都重新建立索引，使用模組層級的快取。
快取以版本號為鍵，確保不同版本的索引隔離。
"""
# 防止直接執行此模組
# 匯入路徑管理功能
from .paths import (
    get_project_root,
    get_tickets_dir,
    get_ticket_path,
)

# 匯入版本管理功能
from .version import (
    get_current_version,
    resolve_version,
    require_version,
)

# 匯入格式解析功能
from .parser import (
    parse_frontmatter,
    load_ticket,
    save_ticket,
)

# 匯入索引管理
from .ticket_chain_index import TicketChainIndex

# 匯入 list_tickets 的實作（仍然在此模組中定義）
import re
from typing import Dict, Any

# 匯入 Ticket ID 格式常數
from .constants import TICKET_ID_PATTERN


# 索引快取：版本號 → TicketChainIndex
_chain_index_cache: Dict[str, TicketChainIndex] = {}


def list_tickets(version: str) -> list[Dict[str, Any]]:
    """
    列出版本的所有 Tickets

    掃描 Tickets 目錄，載入所有 .md 和 .yaml 檔案。
    按檔名排序，跳過無法載入的檔案。

    演算法:
    1. 取得版本的 Tickets 目錄
    2. 檢查目錄是否存在
    3. 掃描所有 .md 和 .yaml 檔案（按檔名排序）
    4. 使用 load_ticket 載入每個檔案
    5. 只加入成功載入的 Ticket
    6. 建立任務鏈索引並快取

    Args:
        version: 版本號（如 "0.31.0" 或 "v0.31.0"）

    Returns:
        list[Dict]: Ticket 資料列表（按檔名排序）

    Examples:
        >>> tickets = list_tickets("0.31.0")
        >>> isinstance(tickets, list)
        True
        >>> all('id' in t for t in tickets)
        True
    """
    # 取得 Tickets 目錄路徑
    tickets_dir = get_tickets_dir(version)

    # Guard Clause：目錄不存在時返回空列表
    if not tickets_dir.exists():
        return []

    tickets = []

    # 同時掃描 .md 和 .yaml 檔案，分別排序後合併
    # 這樣可以支援多種格式的 Ticket 檔案
    all_ticket_files = sorted(tickets_dir.glob("*.md")) + sorted(tickets_dir.glob("*.yaml"))

    for ticket_file in all_ticket_files:
        # 從檔名（不含副檔名）提取 Ticket ID
        ticket_id = ticket_file.stem
        # 跳過不符合 Ticket ID 格式的檔案（如驗收報告）
        if not re.match(TICKET_ID_PATTERN, ticket_id):
            continue
        # 載入 Ticket 資料（load_ticket 會安全處理不存在或格式錯誤的檔案）
        ticket = load_ticket(version, ticket_id)
        # 只加入成功載入的 Ticket，跳過失敗的檔案
        if ticket:
            tickets.append(ticket)

    # 建立並快取任務鏈索引
    index = TicketChainIndex()
    index.build_from_tickets(tickets)
    _chain_index_cache[version] = index

    return tickets


def get_chain_index(version: str) -> TicketChainIndex:
    """
    取得版本的任務鏈索引

    如果索引未快取，則先呼叫 list_tickets() 建立索引。
    這確保索引與 Tickets 保持同步。

    演算法：
    1. 檢查快取中是否存在此版本的索引
    2. 若無，呼叫 list_tickets() 建立索引
    3. 返回索引（無論是快取還是新建的）

    Args:
        version: 版本號（如 "0.31.0" 或 "v0.31.0"）

    Returns:
        TicketChainIndex: 任務鏈索引物件

    Examples:
        >>> index = get_chain_index("0.31.0")
        >>> index.get_children("0.31.0-W4-001")
        ['0.31.0-W4-001.1', '0.31.0-W4-001.2']
    """
    # Guard Clause：快取中不存在此版本
    if version not in _chain_index_cache:
        # 呼叫 list_tickets() 建立索引並快取
        list_tickets(version)

    return _chain_index_cache.get(version, TicketChainIndex())


__all__ = [
    # 路徑管理
    "get_project_root",
    "get_tickets_dir",
    "get_ticket_path",
    # 版本管理
    "get_current_version",
    "resolve_version",
    "require_version",
    # 格式解析
    "parse_frontmatter",
    "load_ticket",
    "save_ticket",
    # Ticket 列表和索引
    "list_tickets",
    "get_chain_index",
]


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
