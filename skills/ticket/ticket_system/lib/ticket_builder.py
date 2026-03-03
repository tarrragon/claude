"""
Ticket 建構模組

從 create.py 提取的 Ticket 建構相關函式，提供公開 API 供 create 和 generate 命令重用。
提取函式：
  - format_ticket_id(): 格式化根任務 ID
  - format_child_ticket_id(): 格式化子任務 ID
  - get_next_seq(): 取得下一個根任務序號
  - get_next_child_seq(): 取得下一個子任務序號
  - create_ticket_frontmatter(): 建立 Ticket frontmatter
  - create_ticket_body(): 建立 Ticket body
  - update_parent_children(): 更新父 Ticket 的 children

使用 TypedDict 減少函式參數數量，提高程式碼可讀性。
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from ticket_system.lib.constants import STATUS_PENDING
from ticket_system.lib.ticket_loader import (
    get_tickets_dir,
    save_ticket,
    load_ticket,
    get_ticket_path,
)


class TicketConfig(TypedDict, total=False):
    """Ticket 建立配置。

    使用 TypedDict 減少函式參數數量，提高程式碼可讀性。
    total=False 表示所有欄位都是可選的。
    """

    # 基本資訊（6 個欄位）
    ticket_id: str              # Ticket ID（如 0.31.0-W5-001）
    version: str                # 版本號（如 0.31.0）
    wave: int                   # Wave 編號（如 5）
    title: str                  # 標題（「動詞 + 目標」格式）
    ticket_type: str            # 類型（IMP/TST/ADJ/RES/ANA/INV/DOC）
    priority: str               # 優先級（P0/P1/P2/P3）

    # 5W1H 資訊（7 個欄位）
    who: str                    # 執行代理人（如 parsley-flutter-developer）
    what: str                   # 任務描述
    when: str                   # 觸發時機
    where_layer: str            # 架構層級（Domain/Application/Infrastructure/Presentation）
    where_files: List[str]      # 影響檔案清單
    why: str                    # 需求依據
    how_task_type: str          # Task Type（Implementation/Analysis/etc.）
    how_strategy: str           # 實作策略

    # 關係資訊（3 個欄位）
    parent_id: Optional[str]    # 父 Ticket ID（子任務才有）
    blocked_by: Optional[List[str]]  # 依賴的 Ticket IDs
    related_to: Optional[List[str]]  # 相關的 Ticket IDs（多對多關聯）

    # TDD 資訊（2 個欄位）
    tdd_phase: Optional[str]    # 當前 TDD 階段（phase1/phase2/phase3a/phase3b/phase4）
    tdd_stage: Optional[List[str]]  # TDD 階段清單

    # 驗收條件（1 個欄位）
    acceptance: Optional[List[str]]  # 驗收條件清單


def format_ticket_id(version: str, wave: int, seq: int) -> str:
    """格式化根任務 Ticket ID。

    Args:
        version: 版本號（如 "v0.31.0" 或 "0.31.0"）
        wave: Wave 編號（正整數）
        seq: 序號（正整數）

    Returns:
        格式化的 Ticket ID（如 "0.31.0-W5-001"）

    Examples:
        >>> format_ticket_id("v0.31.0", 5, 1)
        '0.31.0-W5-001'
        >>> format_ticket_id("0.31.0", 5, 1)
        '0.31.0-W5-001'
        >>> format_ticket_id("0.32.0", 10, 999)
        '0.32.0-W10-999'

    Implementation:
        - 移除 version 的 "v" 前綴（若有）
        - 格式：{version}-W{wave}-{seq:03d}
        - seq 使用 3 位數補零（如 001, 015, 123）
    """
    # 移除 v 前綴
    v: str = version[1:] if version.startswith("v") else version
    return f"{v}-W{wave}-{seq:03d}"


def format_child_ticket_id(parent_id: str, child_seq: int) -> str:
    """格式化子任務 Ticket ID。

    Args:
        parent_id: 父 Ticket ID（如 "0.31.0-W5-001"）
        child_seq: 子任務序號（正整數）

    Returns:
        子任務 ID（如 "0.31.0-W5-001.1"）

    Examples:
        >>> format_child_ticket_id("0.31.0-W5-001", 1)
        '0.31.0-W5-001.1'
        >>> format_child_ticket_id("0.31.0-W5-001.1", 2)
        '0.31.0-W5-001.1.2'
        >>> format_child_ticket_id("0.31.0-W5-001.1.1.1", 1)
        '0.31.0-W5-001.1.1.1.1'

    Implementation:
        - 格式：{parent_id}.{child_seq}
        - 支援無限深度的子任務（如 001.1.1.1）
    """
    return f"{parent_id}.{child_seq}"


def get_next_seq(version: str, wave: int) -> int:
    """取得下一個根任務序號。

    Args:
        version: 版本號（如 "0.31.0"）
        wave: Wave 編號

    Returns:
        下一個序號（正整數，從 1 開始）

    Examples:
        若 0.31.0-W5-001.md 和 0.31.0-W5-002.md 已存在：
        >>> get_next_seq("0.31.0", 5)
        3

        若該 Wave 無任何 Ticket：
        >>> get_next_seq("0.31.0", 5)
        1

    Implementation:
        1. 取得 tickets_dir（透過 get_tickets_dir(version)）
        2. 若目錄不存在，返回 1
        3. glob 尋找 *-W{wave}-*.md 檔案
        4. 解析所有檔案名，取得最大序號
        5. 返回 max_seq + 1

    注意:
        - 只計算根任務序號（不包含子任務的點號部分）
        - 如 0.31.0-W5-001.1.md 只取 001
    """
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
            # 格式：{version}-W{wave}-{seq}.md 或 {version}-W{wave}-{seq}.{child}.md
            parts = f.stem.split("-W")
            if len(parts) == 2:
                wave_seq = parts[1].split("-", 1)
                if len(wave_seq) == 2:
                    # 只取根任務的序號（不含子任務部分）
                    seq_part = wave_seq[1].split(".")[0]
                    seq = int(seq_part)
                    max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue

    return max_seq + 1


def get_next_child_seq(parent_id: str) -> int:
    """取得下一個子任務序號。

    Args:
        parent_id: 父 Ticket ID（如 "0.31.0-W5-001"）

    Returns:
        下一個子任務序號（正整數，從 1 開始）

    Examples:
        若父 Ticket 有 children: ["0.31.0-W5-001.1", "0.31.0-W5-001.2"]：
        >>> get_next_child_seq("0.31.0-W5-001")
        3

        若父 Ticket 無 children：
        >>> get_next_child_seq("0.31.0-W5-001")
        1

    Implementation:
        1. 從 parent_id 提取 version
        2. 載入 parent Ticket（使用 load_ticket）
        3. 取得 children 欄位
        4. 解析 children IDs，只計算直接子任務
        5. 返回 max_seq + 1

    注意:
        - 只計算直接子任務（深度 = parent_depth + 1）
        - 如 parent 為 001，child 為 001.1.1，則不計入
        - 只有 001.1、001.2 會被計入
    """
    # 從 parent_id 中提取 version（如 0.31.0）
    parts = parent_id.split("-W")
    if len(parts) != 2:
        return 1

    version = parts[0]

    parent = load_ticket(version, parent_id)
    if not parent:
        return 1

    children = parent.get("children", [])
    if not children:
        return 1

    # 找出最大的直接子任務序號
    max_seq = 0
    for child_id in children:
        try:
            # 解析子任務 ID，找出直接子任務
            # parent: 0.31.0-W4-020, child: 0.31.0-W4-020.1, 0.31.0-W4-020.1.1
            # 只計算直接子任務（只有一層點）
            if child_id.startswith(parent_id + "."):
                remainder = child_id[len(parent_id) + 1:]
                # 如果 remainder 中沒有點，這是直接子任務
                if "." not in remainder:
                    seq = int(remainder)
                    max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue

    return max_seq + 1


def create_ticket_frontmatter(config: TicketConfig) -> Dict[str, Any]:
    """建立 Ticket frontmatter。

    使用 TypedDict 配置參數簡化函式簽名，從 15 個參數減至 1 個。

    Args:
        config: 包含所有 Ticket 配置資訊的 TicketConfig 字典

    Returns:
        包含 frontmatter 資訊的字典

    Frontmatter 欄位清單（27 個欄位）:
        - id: config["ticket_id"]
        - title: config["title"]
        - type: config["ticket_type"]
        - status: "pending"（固定值，來自 STATUS_PENDING 常數）
        - version: config["version"]
        - wave: config["wave"]
        - priority: config["priority"]
        - parent_id: config.get("parent_id")（可選）
        - children: []（空清單，建立時無子任務）
        - blockedBy: config.get("blocked_by") or []
        - relatedTo: config.get("related_to") or []（多對多關聯）
        - spawned_tickets: []（空清單）
        - source_ticket: None
        - dispatch_reason: ""（空字串）
        - who: {"current": config["who"], "history": {}}
        - what: config["what"]
        - when: config["when"]
        - where: {"layer": config["where_layer"], "files": config.get("where_files", [])}
        - why: config["why"]
        - how: {"task_type": config["how_task_type"], "strategy": config["how_strategy"]}
        - acceptance: config.get("acceptance") or 預設驗收條件
        - tdd_phase: config.get("tdd_phase")
        - tdd_stage: config.get("tdd_stage") or []
        - assigned: False（固定值）
        - creation_accepted: False（固定值，建立後品質驗收狀態）
        - started_at: None
        - completed_at: None
        - created: 當前日期（YYYY-MM-DD）
        - updated: 當前日期（YYYY-MM-DD）

    預設驗收條件:
        ["任務實作完成", "相關測試通過", "無程式碼品質警告"]

    Examples:
        >>> config = TicketConfig(
        ...     ticket_id="0.31.0-W5-001",
        ...     version="0.31.0",
        ...     wave=5,
        ...     title="實作功能 X",
        ...     ticket_type="IMP",
        ...     priority="P1",
        ...     who="parsley-flutter-developer",
        ...     what="實作功能 X",
        ...     when="Phase 3b",
        ...     where_layer="Application",
        ...     where_files=["lib/application/use_case.dart"],
        ...     why="需求規格要求",
        ...     how_task_type="Implementation",
        ...     how_strategy="TDD Phase 3b"
        ... )
        >>> frontmatter = create_ticket_frontmatter(config)
        >>> frontmatter["id"]
        '0.31.0-W5-001'
        >>> frontmatter["status"]
        'pending'
    """
    return {
        "id": config["ticket_id"],
        "title": config["title"],
        "type": config["ticket_type"],
        "status": STATUS_PENDING,
        "version": config["version"],
        "wave": config["wave"],
        "priority": config["priority"],
        "parent_id": config.get("parent_id"),
        "children": [],
        "blockedBy": config.get("blocked_by") or [],
        "relatedTo": config.get("related_to") or [],
        "spawned_tickets": [],
        "source_ticket": None,
        "dispatch_reason": "",
        "who": {"current": config["who"], "history": {}},
        "what": config["what"],
        "when": config["when"],
        "where": {"layer": config["where_layer"], "files": config.get("where_files", [])},
        "why": config["why"],
        "how": {"task_type": config["how_task_type"], "strategy": config["how_strategy"]},
        "acceptance": [
            f"[ ] {item}" if not (item.startswith("[") and "]" in item) else item
            for item in (config.get("acceptance") or ["任務實作完成", "相關測試通過", "無程式碼品質警告"])
        ],
        "tdd_phase": config.get("tdd_phase"),
        "tdd_stage": config.get("tdd_stage") or [],
        "assigned": False,
        "creation_accepted": False,
        "started_at": None,
        "completed_at": None,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "updated": datetime.now().strftime("%Y-%m-%d"),
    }


def create_ticket_body(what: str, who: str) -> str:
    """建立 Ticket body。

    Args:
        what: 任務描述（來自 frontmatter["what"]）
        who: 執行代理人（來自 frontmatter["who"]["current"]）

    Returns:
        Ticket body 字串（Markdown 格式）

    Body 結構:
        # Execution Log

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

    Examples:
        >>> body = create_ticket_body(
        ...     what="實作功能 X",
        ...     who="parsley-flutter-developer"
        ... )
        >>> "# Execution Log" in body
        True
        >>> "實作功能 X" in body
        True
    """
    return f"""# Execution Log

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


def update_parent_children(version: str, parent_id: str, child_id: str) -> bool:
    """更新父 Ticket 的 children 欄位。

    Args:
        version: 版本號（如 "0.31.0"）
        parent_id: 父 Ticket ID（如 "0.31.0-W5-001"）
        child_id: 子 Ticket ID（如 "0.31.0-W5-001.1"）

    Returns:
        bool: 成功更新返回 True，失敗返回 False

    Implementation:
        1. 載入 parent Ticket（使用 load_ticket）
        2. 若 parent 不存在，返回 False
        3. 取得 children 欄位（預設為空清單）
        4. 若 child_id 不在 children 中，加入
        5. 更新 parent["children"]
        6. 儲存 parent Ticket（使用 save_ticket）
        7. 返回 True

    Examples:
        >>> update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.1")
        True

        >>> update_parent_children("0.31.0", "invalid-id", "0.31.0-W5-001.1")
        False

    Side Effects:
        - 修改父 Ticket 檔案
        - 更新 parent["children"] 清單
    """
    parent: Optional[Dict[str, Any]] = load_ticket(version, parent_id)
    if not parent:
        return False

    children: List[str] = parent.get("children", [])
    if child_id not in children:
        children.append(child_id)
        parent["children"] = children

        parent_path: Path = Path(parent.get("_path", get_ticket_path(version, parent_id)))
        save_ticket(parent, parent_path)

    return True
