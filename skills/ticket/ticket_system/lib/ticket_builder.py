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

import sys
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
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id


# 預設驗收條件（依 Ticket 類型）
# 注意：所有條件都應包含量化佔位符或可客觀驗證的標準，禁止使用模糊詞
DEFAULT_ACCEPTANCE_CRITERIA = {
    "IMP": [
        "指定功能（{feature_name}）實作符合設計規格",
        "相關測試 100% 通過（flutter test / uv run pytest）",
        "dart analyze / ruff check 0 issues"
    ],
    "TST": [
        "設計 N 個測試案例，覆蓋正常/邊界/異常路徑",
        "所有測試案例執行通過（通過率 100%）",
        "測試覆蓋率達 {coverage_target}%（由 SA 或代理人指定）"
    ],
    "ADJ": [
        "調整內容（{adjustment_target}）符合規格",
        "相關測試通過（通過率 100%）",
        "lint 檢查 0 critical issues"
    ],
    "RES": [
        "研究報告已撰寫（含背景、方法、發現、結論 4 部分）",
        "結論明確且可行（避免「可能」「似乎」等模糊詞）",
        "至少提出 N 個可行的改善建議"
    ],
    "ANA": [
        "分析報告已撰寫（含問題敘述、根因分析、改善方案 3 部分）",
        "根因已通過 5W1H 或因果鏈分析確認",
        "改善方案至少包含症狀修復和根因防護兩個方向",
        "[ ] 分析結論已建立修復 Ticket（症狀修復），Ticket ID 已記錄在 spawned_tickets",
        "[ ] 根因已建立防護 Ticket（機制防護），Ticket ID 已記錄在 spawned_tickets",
        "[ ] 若無後續 Ticket 需建立，需說明理由"
    ],
    "INV": [
        "調查報告已撰寫（含調查範圍、發現、驗證過程 3 部分）",
        "事實已通過實驗/測試/文件驗證確認（不依賴推測）",
        "後續行動已定義：建立 {N} 個相關 Ticket，IDs 已記錄"
    ],
    "DOC": [
        "文件內容完整：包含標題、背景、正文、結論、附錄等 {N} 部分",
        "格式符合規範：遵守 CLAUDE.md 的文件格式規則",
        "內容無遺漏：所有預期的小節都已填寫（無 TODO 或空白區段）"
    ],
    # 問題 5 修正：移除未在 TICKET_TYPES 中註冊的類型
    # SEC、PERF、INFRA 類型未在 constants.py 的 TICKET_TYPES 中定義
    # 若需支援這些類型，請先在 TICKET_TYPES 中註冊
}


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

    # 決策樹路徑（1 個欄位）
    decision_tree_path: Optional[Dict[str, str]]  # {"entry_point": ..., "final_decision": ..., "rationale": ...}


def get_default_acceptance_criteria(ticket_type: str) -> List[str]:
    """取得預設驗收條件（依 Ticket 類型）。

    Args:
        ticket_type: Ticket 類型（IMP, TST, ADJ, RES, ANA, INV, DOC）

    Returns:
        預設驗收條件清單

    Examples:
        >>> get_default_acceptance_criteria("IMP")
        ["任務實作完成", "相關測試通過", "無程式碼品質警告"]

        >>> get_default_acceptance_criteria("ANA")
        ["分析報告完成", "根因已識別", "改善方案已提出",
         "[ ] 分析結論已建立修復 Ticket（症狀修復）",
         "[ ] 根因已建立防護 Ticket（機制防護）",
         "[ ] 後續 Ticket 已記錄在 children 或 spawned_tickets"]

        >>> get_default_acceptance_criteria("UNKNOWN")
        ["任務實作完成", "相關測試通過", "無程式碼品質警告"]
    """
    return DEFAULT_ACCEPTANCE_CRITERIA.get(
        ticket_type,
        DEFAULT_ACCEPTANCE_CRITERIA["IMP"]  # 預設為 IMP 類型
    )


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


def _extract_direct_child_seq(child_id: str, parent_id: str) -> Optional[int]:
    """從子任務 ID 中提取直接子任務序號。

    只提取直接子任務（深度 = parent_depth + 1），
    忽略更深層的子任務（如 001.1.1）。

    Args:
        child_id: 子任務 ID（如 "0.31.0-W5-001.2"）
        parent_id: 父任務 ID（如 "0.31.0-W5-001"）

    Returns:
        直接子任務序號，若非直接子任務則返回 None
    """
    prefix = parent_id + "."
    if not child_id.startswith(prefix):
        return None
    remainder = child_id[len(prefix):]
    # 直接子任務的 remainder 不含點號
    if "." in remainder:
        return None
    try:
        return int(remainder)
    except ValueError:
        return None


def _scan_child_files_max_seq(tickets_dir: Path, parent_id: str) -> int:
    """掃描檔案系統中已存在的子 Ticket 檔案，找出最大直接子任務序號。

    這是防止父 Ticket 的 children 欄位未同步時的安全機制，
    確保不會覆蓋已存在的子 Ticket 檔案。

    Args:
        tickets_dir: Ticket 檔案目錄
        parent_id: 父任務 ID

    Returns:
        最大直接子任務序號，無子 Ticket 檔案時返回 0
    """
    if not tickets_dir.exists():
        return 0

    max_seq = 0
    # 掃描 {parent_id}.*.md 檔案
    pattern = f"{parent_id}.*.md"
    for f in tickets_dir.glob(pattern):
        seq = _extract_direct_child_seq(f.stem, parent_id)
        if seq is not None:
            max_seq = max(max_seq, seq)
    return max_seq


def _normalize_children(raw: Any) -> List[str]:
    """將 children 欄位正規化為字串清單。

    防禦性型別處理：children 可能因手動編輯變成字串（換行分隔），
    或因序列化問題變成非預期型別。

    Args:
        raw: children 欄位的原始值（list、str 或其他型別）

    Returns:
        正規化後的子任務 ID 清單
    """
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return [c.strip() for c in raw.split("\n") if c.strip()]
    return []


def get_next_child_seq(parent_id: str) -> int:
    """取得下一個子任務序號。

    同時檢查父 Ticket 的 children 欄位和檔案系統中的子 Ticket 檔案，
    取兩者的最大序號 + 1，確保不會覆蓋已存在的子 Ticket。

    Args:
        parent_id: 父 Ticket ID（如 "0.31.0-W5-001"）

    Returns:
        下一個子任務序號（正整數，從 1 開始）

    Examples:
        若父 Ticket 有 children: ["0.31.0-W5-001.1", "0.31.0-W5-001.2"]：
        >>> get_next_child_seq("0.31.0-W5-001")
        3

        若父 Ticket 無 children 但檔案系統有 0.31.0-W5-001.1.md：
        >>> get_next_child_seq("0.31.0-W5-001")
        2

        若父 Ticket 無 children 且無檔案：
        >>> get_next_child_seq("0.31.0-W5-001")
        1
    """
    version = extract_version_from_ticket_id(parent_id)
    if version is None:
        return 1

    # 來源 1：父 Ticket 的 children 欄位（single source of truth）
    max_seq_from_children = 0
    parent = load_ticket(version, parent_id)
    if parent:
        children_list = _normalize_children(parent.get("children", []))
        for child_id in children_list:
            seq = _extract_direct_child_seq(child_id, parent_id)
            if seq is not None:
                max_seq_from_children = max(max_seq_from_children, seq)

    # 來源 2：檔案系統掃描（fallback 安全機制，防止覆蓋已存在的子 Ticket）
    tickets_dir = get_tickets_dir(version)
    max_seq_from_files = _scan_child_files_max_seq(tickets_dir, parent_id)

    # 不一致時輸出 warning，便於追蹤 update_parent_children 失敗
    if max_seq_from_children != max_seq_from_files and max_seq_from_children > 0 and max_seq_from_files > 0:
        print(
            f"[WARNING] 父 Ticket {parent_id} 的 children 欄位（max_seq={max_seq_from_children}）"
            f"與檔案系統（max_seq={max_seq_from_files}）不一致",
            file=sys.stderr,
        )

    # 取兩者最大值，確保不覆蓋
    max_seq = max(max_seq_from_children, max_seq_from_files)
    return max_seq + 1


def create_ticket_frontmatter(config: TicketConfig) -> Dict[str, Any]:
    """建立 Ticket frontmatter。

    使用 TypedDict 配置參數簡化函式簽名，從 15 個參數減至 1 個。

    Args:
        config: 包含所有 Ticket 配置資訊的 TicketConfig 字典

    Returns:
        包含 frontmatter 資訊的字典

    Frontmatter 欄位清單（28 個欄位）:
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
        - decision_tree_path: config.get("decision_tree_path")（決策樹路徑，可選）
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

    預設驗收條件（依 Ticket 類型）:
        - IMP: ["任務實作完成", "相關測試通過", "無程式碼品質警告"]
        - ANA: ["分析報告完成", "根因已識別", "改善方案已提出",
                "[ ] 分析結論已建立修復 Ticket（症狀修復）",
                "[ ] 根因已建立防護 Ticket（機制防護）",
                "[ ] 後續 Ticket 已記錄在 children 或 spawned_tickets"]
        - 其他類型: 參考 DEFAULT_ACCEPTANCE_CRITERIA

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
        "decision_tree_path": config.get("decision_tree_path"),
        "who": {"current": config["who"], "history": {}},
        "what": config["what"],
        "when": config["when"],
        "where": {"layer": config["where_layer"], "files": config.get("where_files", [])},
        "why": config["why"],
        "how": {"task_type": config["how_task_type"], "strategy": config["how_strategy"]},
        "acceptance": [
            f"[ ] {item}" if not (item.startswith("[") and "]" in item) else item
            for item in (config.get("acceptance") or get_default_acceptance_criteria(config["ticket_type"]))
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
        結構化的問題分析區段，包含根因、影響範圍和相關錯誤模式

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

### 問題根因

（待填寫：問題發生的直接原因是什麼？）

### 影響範圍

（待填寫：哪些檔案、模組或功能受影響？）

### 相關 Error Pattern

（待填寫：是否有相關的已知錯誤模式？執行 /error-pattern query 確認）

<!-- 調查過程記錄（可選）：
搜尋指令：grep -rn "pattern" path/ --include="*.py"
確認的位置：
- file1.py:123
注意：接手者應獨立重新驗證數量/範圍（PC-007）
-->

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

    version 參數為向後相容保留，實際使用從 parent_id 提取的版本號。
    這確保跨版本建立子 Ticket 時不會因版本不符而找不到父 Ticket。

    Args:
        version: 版本號（向後相容保留，實際不使用）
        parent_id: 父 Ticket ID（如 "0.31.0-W5-001"）
        child_id: 子 Ticket ID（如 "0.31.0-W5-001.1"）

    Returns:
        bool: 成功更新返回 True，失敗返回 False

    Implementation:
        1. 從 parent_id 提取版本號（不依賴 version 參數）
        2. 載入 parent Ticket（使用 load_ticket）
        3. 若 parent 不存在，返回 False
        4. 取得 children 欄位，確保為 list 型別
        5. 若 child_id 不在 children 中，加入
        6. 更新 parent["children"]
        7. 儲存 parent Ticket（使用 save_ticket）
        8. 返回 True

    Examples:
        >>> update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.1")
        True

        >>> update_parent_children("0.31.0", "invalid-id", "0.31.0-W5-001.1")
        False

    Side Effects:
        - 修改父 Ticket 檔案
        - 更新 parent["children"] 清單
    """
    # 從 parent_id 提取版本，避免 version 參數與 parent_id 版本不一致
    # （根因：create 命令傳入 current_version，但 parent 可能屬於不同版本）
    resolved_version: Optional[str] = extract_version_from_ticket_id(parent_id)
    if resolved_version is None:
        return False

    parent: Optional[Dict[str, Any]] = load_ticket(resolved_version, parent_id)
    if not parent:
        return False

    # 防禦性型別檢查：children 可能因手動編輯變成字串
    raw_children = parent.get("children", [])
    if isinstance(raw_children, str):
        print(
            f"[WARNING] 父 Ticket {parent_id} 的 children 欄位為字串而非清單，"
            f"已自動修正",
            file=sys.stderr,
        )
    children: List[str] = _normalize_children(raw_children)

    if child_id not in children:
        children.append(child_id)
        parent["children"] = children

        parent_path: Path = Path(parent.get("_path", get_ticket_path(resolved_version, parent_id)))
        save_ticket(parent, parent_path)

    return True
