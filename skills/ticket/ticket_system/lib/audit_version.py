"""
Ticket 版本審計模組

提供版本歸屬、重複偵測等審計功能，確保 Ticket 版本號和檔案位置一致。
由 W15-001 並行任務實作：
  - W15-001.1: scan_all_tickets() + detect_mismatches()
  - W15-001.2: detect_duplicates()
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

from .id_parser import extract_core_ticket_id, extract_id_components
from .parser import parse_frontmatter
from .paths import get_project_root


@dataclass(frozen=True)
class TicketVersionInfo:
    """
    Ticket 版本資訊記錄。

    記錄單個 Ticket 檔案的版本相關資訊，用於審計重複偵測和版本不匹配檢查。

    Attributes:
        file_path: Ticket 檔案的完整路徑
        ticket_id: 從檔案名提取的 Ticket ID（可能帶後綴）
        id_version: 從 ID 提取的版本號（Ticket ID 中的版本部分，如 0.1.0）
        frontmatter_version: Ticket frontmatter 中的 version 欄位值
        directory_version: Ticket 所在目錄的版本號（從路徑提取，如 v0.1.0）

    注意：
        - ticket_id 是原始值，可能包含描述後綴（如 -phase1-design）
        - id_version 是從 ID 提取的核心版本號，用於與目錄版本比較
        - 核心 ID 可由 extract_core_ticket_id(ticket_id) 獲得
        - 資料類別是不可變的（frozen=True）
    """

    file_path: str
    ticket_id: str
    id_version: str
    frontmatter_version: str
    directory_version: str


@dataclass
class VersionMismatch:
    """
    版本不一致記錄資料類別

    記錄發現的版本不一致情況。
    目錄版本作為 source of truth（因為目錄結構是由系統建立和管理的）。

    Attributes:
        ticket_info: 原始的 TicketVersionInfo 物件
        mismatch_type: 不一致的類型
                      - "id_vs_directory": Ticket ID 版本與目錄版本不同
                      - "frontmatter_vs_directory": Frontmatter 版本與目錄版本不同
                      - "id_vs_frontmatter": Ticket ID 版本與 frontmatter 版本不同
        expected_version: 目錄版本（作為 source of truth）
        actual_version: 不一致的版本值
    """

    ticket_info: "TicketVersionInfo"
    mismatch_type: str
    expected_version: str
    actual_version: str


@dataclass
class DuplicateTicket:
    """
    重複 Ticket 記錄。

    記錄同一核心 Ticket ID 出現在多個版本目錄的情況。

    Attributes:
        ticket_id: 核心 Ticket ID（去後綴）
        locations: 該 ID 出現的所有位置清單
        recommended_version: 根據 ID 版本號推薦的正確所在版本
    """

    ticket_id: str
    locations: List[TicketVersionInfo]
    recommended_version: str


# ============================================================================
# 常數定義
# ============================================================================

# 工作日誌目錄相對路徑
WORK_LOGS_RELATIVE_PATH = "docs/work-logs"

# 目錄版本前綴
VERSION_PREFIX = "v"

# Glob pattern 用於掃描所有版本目錄
TICKET_GLOB_PATTERN = "v*/v*/v*/tickets/*.md"
# 向後相容舊結構
TICKET_GLOB_PATTERN_FLAT = "v*/tickets/*.md"


# ============================================================================
# 版本提取工具函式
# ============================================================================

def _extract_version_from_directory_path(path: Path) -> str:
    """
    從目錄路徑提取版本號

    從 "docs/work-logs/v{version}/tickets/" 格式的路徑中提取版本號。
    例如：docs/work-logs/v0.1.0/tickets/ → "0.1.0"

    Args:
        path: Ticket 檔案路徑

    Returns:
        str: 提取的版本號（如 "0.1.0"），無法提取時返回空字串

    Examples:
        >>> from pathlib import Path
        >>> p = Path("/home/user/project/docs/work-logs/v0.1.0/tickets/file.md")
        >>> _extract_version_from_directory_path(p)
        '0.1.0'
    """
    # 尋找 "v" 字首後的版本目錄
    try:
        parts = path.parts
        for i, part in enumerate(parts):
            if part.startswith(VERSION_PREFIX) and i + 1 < len(parts):
                # 檢查下一個目錄是否為 "tickets"
                if parts[i + 1] == "tickets":
                    # 去掉 "v" 前綴
                    version = part[len(VERSION_PREFIX):]
                    return version
    except (IndexError, AttributeError):
        pass
    return ""


def _get_frontmatter_version(file_path: Path) -> Optional[str]:
    """
    從 Ticket 檔案的 frontmatter 提取版本號

    安全讀取檔案並解析 YAML frontmatter，提取 version 欄位。
    如果檔案不存在、frontmatter 解析失敗或無 version 欄位，則返回 None。

    Args:
        file_path: Ticket 檔案完整路徑

    Returns:
        Optional[str]: version 欄位值（如 "0.1.0"），不存在時返回 None

    Examples:
        >>> from pathlib import Path
        >>> version = _get_frontmatter_version(Path("/path/to/0.1.0-W1-001.md"))
        >>> version  # Returns "0.1.0" if present, None otherwise
    """
    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        frontmatter, _ = parse_frontmatter(content)
        return frontmatter.get("version")
    except (IOError, OSError):
        # 檔案讀取或解析失敗
        return None


# ============================================================================
# 核心掃描函式
# ============================================================================

def scan_all_tickets() -> List[TicketVersionInfo]:
    """
    掃描所有版本目錄的 Ticket，收集版本相關資訊

    遍歷 docs/work-logs/v*/tickets/ 目錄下所有 .md 檔案，
    對每個 Ticket 收集版本資訊的三個來源：
    1. id_version: 從 Ticket ID 提取
    2. frontmatter_version: 從 YAML frontmatter 讀取
    3. directory_version: 從目錄路徑提取

    演算法：
    1. 取得專案根目錄
    2. 找到 docs/work-logs 目錄
    3. 使用 glob pattern 掃描所有 v*/tickets/*.md 檔案
    4. 對每個檔案：
       a. 從檔名提取核心 Ticket ID
       b. 從 Ticket ID 提取版本號（如 "0.1.0-W1-001" → "0.1.0"）
       c. 從目錄路徑提取版本號
       d. 從 frontmatter 讀取版本欄位
       e. 建立 TicketVersionInfo 物件
    5. 返回所有掃描結果

    Returns:
        List[TicketVersionInfo]: 掃描到的所有 Ticket 版本資訊

    Examples:
        >>> tickets = scan_all_tickets()
        >>> isinstance(tickets, list)
        True
        >>> all(isinstance(t, TicketVersionInfo) for t in tickets)
        True
        >>> len(tickets) > 0
        True
    """
    root = get_project_root()
    work_logs_dir = root / WORK_LOGS_RELATIVE_PATH

    # Guard Clause：work-logs 目錄不存在
    if not work_logs_dir.exists():
        return []

    results = []

    # 掃描所有 ticket 檔案（新式階層 + 舊式平行）
    all_ticket_files = set(work_logs_dir.glob(TICKET_GLOB_PATTERN))
    all_ticket_files.update(work_logs_dir.glob(TICKET_GLOB_PATTERN_FLAT))
    for ticket_file in sorted(all_ticket_files):
        # 從檔名（不含副檔名）提取原始 ID（可能帶後綴）
        ticket_id_raw = ticket_file.stem

        # 提取核心 Ticket ID（去掉描述後綴）
        core_ticket_id = extract_core_ticket_id(ticket_id_raw)

        # 跳過無法解析的非 Ticket 檔案
        if core_ticket_id is None:
            continue

        # 從 Ticket ID 提取版本號
        id_components = extract_id_components(core_ticket_id)
        id_version = id_components["version"] if id_components else ""

        # 從目錄路徑提取版本號
        directory_version = _extract_version_from_directory_path(ticket_file)

        # 從 frontmatter 讀取版本號
        frontmatter_version = _get_frontmatter_version(ticket_file)

        # 建立資訊物件
        ticket_info = TicketVersionInfo(
            file_path=str(ticket_file),
            ticket_id=core_ticket_id,
            id_version=id_version,
            frontmatter_version=frontmatter_version or "",
            directory_version=directory_version,
        )

        results.append(ticket_info)

    return results


# ============================================================================
# 不一致偵測函式
# ============================================================================

def detect_mismatches(tickets: List[TicketVersionInfo]) -> List[VersionMismatch]:
    """
    比對 Ticket 的三個版本來源，偵測不一致

    對每個 Ticket，比對以下三個版本值：
    1. id_version: 來自 Ticket ID
    2. frontmatter_version: 來自 YAML frontmatter（可能為空字串）
    3. directory_version: 來自目錄路徑（source of truth）

    不一致判斷：
    - id_version 與 directory_version 不同 → "id_vs_directory"
    - frontmatter_version 非空且與 directory_version 不同 → "frontmatter_vs_directory"
    - frontmatter_version 非空且與 id_version 不同 → "id_vs_frontmatter"

    演算法：
    1. 遍歷所有 Ticket 資訊
    2. 比對版本值
    3. 記錄任何不一致（期望值為 directory_version）
    4. 返回所有發現的不一致

    Args:
        tickets: TicketVersionInfo 列表

    Returns:
        List[VersionMismatch]: 發現的版本不一致清單

    Examples:
        >>> info = TicketVersionInfo(
        ...     file_path="/test.md",
        ...     ticket_id="0.1.0-W1-001",
        ...     id_version="0.1.0",
        ...     frontmatter_version="0.1.1",
        ...     directory_version="0.1.0"
        ... )
        >>> mismatches = detect_mismatches([info])
        >>> len(mismatches) == 1
        True
        >>> mismatches[0].mismatch_type
        'frontmatter_vs_directory'
    """
    mismatches = []

    for ticket in tickets:
        # 比對 id_version 與 directory_version
        if ticket.id_version != ticket.directory_version:
            mismatch = VersionMismatch(
                ticket_info=ticket,
                mismatch_type="id_vs_directory",
                expected_version=ticket.directory_version,
                actual_version=ticket.id_version,
            )
            mismatches.append(mismatch)

        # 比對 frontmatter_version 與 directory_version（如果 frontmatter 中有版本）
        if ticket.frontmatter_version:
            if ticket.frontmatter_version != ticket.directory_version:
                mismatch = VersionMismatch(
                    ticket_info=ticket,
                    mismatch_type="frontmatter_vs_directory",
                    expected_version=ticket.directory_version,
                    actual_version=ticket.frontmatter_version,
                )
                mismatches.append(mismatch)

            # 比對 id_version 與 frontmatter_version
            if ticket.id_version != ticket.frontmatter_version:
                mismatch = VersionMismatch(
                    ticket_info=ticket,
                    mismatch_type="id_vs_frontmatter",
                    expected_version=ticket.directory_version,
                    actual_version=ticket.frontmatter_version,
                )
                mismatches.append(mismatch)

    return mismatches


def detect_duplicates(tickets: List[TicketVersionInfo]) -> List[DuplicateTicket]:
    """
    偵測同一 Ticket ID 在多個版本目錄出現的重複情況。

    按核心 Ticket ID 分組，識別出現在 2+ 個不同目錄版本的 Ticket。
    並根據 Ticket ID 中的版本號判斷推薦位置。

    算法：
      1. 按核心 ID（去後綴）分組
      2. 找出 directory_version 不同的分組
      3. 使用 ID 版本號作為 source of truth 確定推薦位置

    Args:
        tickets: TicketVersionInfo 清單，來自 scan_all_tickets()

    Returns:
        DuplicateTicket 清單，每項代表一個重複的核心 ID 及其所有出現位置。
                如無重複則返回空清單。

    Examples:
        >>> # 掃描結果中有以下 Ticket：
        >>> # docs/work-logs/v0.1.0/tickets/0.1.0-W1-001.md
        >>> # docs/work-logs/v0.2.0/tickets/0.1.0-W1-001-phase1-design.md
        >>> # 都對應核心 ID "0.1.0-W1-001"，出現在不同版本
        >>>
        >>> results = detect_duplicates(tickets)
        >>> len(results)
        1
        >>> dup = results[0]
        >>> dup.ticket_id
        '0.1.0-W1-001'
        >>> len(dup.locations)
        2
        >>> dup.recommended_version
        '0.1.0'
    """
    # 步驟 1: 按核心 ID 分組
    # 使用 defaultdict(list) 將所有帶後綴的 Ticket 映射到核心 ID
    id_to_tickets: Dict[str, List[TicketVersionInfo]] = defaultdict(list)

    for ticket in tickets:
        # 從 Ticket ID 提取核心 ID（去後綴）
        core_id = extract_core_ticket_id(ticket.ticket_id)

        # 防守式編程：無效的 ID 格式記錄但跳過
        if core_id is None:
            continue

        id_to_tickets[core_id].append(ticket)

    # 步驟 2: 篩選重複（directory_version 不同的分組）
    duplicates: List[DuplicateTicket] = []

    for core_id, ticket_group in id_to_tickets.items():
        # 統計不同的目錄版本數量
        unique_directory_versions = {t.directory_version for t in ticket_group}

        # 只有 2+ 個不同的目錄版本才算重複
        if len(unique_directory_versions) >= 2:
            # 步驟 3: 推薦版本 = ID 版本號（source of truth）
            # 所有同組的 Ticket 在同一 core_id，所以 id_version 相同
            recommended_version = ticket_group[0].id_version

            duplicate = DuplicateTicket(
                ticket_id=core_id,
                locations=ticket_group,
                recommended_version=recommended_version,
            )
            duplicates.append(duplicate)

    return duplicates


if __name__ == "__main__":
    from .messages import print_not_executable_and_exit

    print_not_executable_and_exit()
