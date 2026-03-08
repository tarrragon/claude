"""
Handoff 共用判斷函式模組

封裝 resume.py 和 handoff_gc.py 共用的 stale handoff 判斷邏輯。
消除跨模組私有函式引用，遵循模組封裝原則。
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ticket_system.lib.constants import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    TASK_CHAIN_DIRECTION_TYPES,
    HANDOFF_DIR,
    HANDOFF_PENDING_SUBDIR,
)
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.ticket_ops import load_and_validate_ticket
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id

# 所有已知的 direction 值
_KNOWN_DIRECTION_VALUES = {"context-refresh", "auto"} | set(TASK_CHAIN_DIRECTION_TYPES)

# Handoff JSON 必填欄位
_HANDOFF_REQUIRED_FIELDS = ("ticket_id", "direction", "timestamp")


@dataclass
class ParsedHandoff:
    """
    解析後的 handoff 記錄

    包含完整的檔案和資料信息，支援呼叫端自訂的error處理。
    """
    file_path: Path
    ticket_id: str
    direction: str
    from_status: str
    format: str  # "json" 或 "markdown"
    data: dict  # 完整的 JSON 資料（markdown 時含預設欄位）
    parse_error: Optional[str] = None  # JSON 讀取錯誤（IOError, JSONDecodeError）
    schema_error: Optional[str] = None  # 必填欄位缺失


def is_ticket_completed(ticket_id: str) -> bool:
    """
    檢查 Ticket 是否已 completed。

    從 ticket_id 提取版本後載入 ticket 檢查狀態。
    若無法載入（不存在或格式錯誤），返回 False（保守策略：不確定時顯示）。

    Args:
        ticket_id: Ticket ID，格式如 "0.31.1-W5-004"

    Returns:
        bool: True 表示已完成，False 表示未完成或無法判斷
    """
    try:
        version = extract_version_from_ticket_id(ticket_id)
        if version is None:
            return False

        ticket, error = load_and_validate_ticket(version, ticket_id, auto_print_error=False)
        if error:
            return False

        return ticket.get("status") == STATUS_COMPLETED
    except Exception:
        return False  # 保守策略：無法判斷時顯示


def is_task_chain_direction(direction: str) -> bool:
    """
    判斷 handoff 的 direction 是否為任務鏈類型。

    任務鏈 direction（to-sibling、to-parent、to-child）中，
    來源 ticket completed 是預期狀態（先 complete 再 handoff 到下一任務），
    不應被過濾為 stale。

    格式：direction 格式可為 "to-sibling:target_id" 或 "to-sibling" 等，
    使用 split(":") 提取第一段來判斷。

    Args:
        direction: Handoff direction 字符串，可能為 "to-sibling", "to-sibling:xxx", etc.

    Returns:
        bool: True 表示為任務鏈類型，False 表示為其他類型（context-refresh 等）
    """
    if not direction:
        return False

    # 提取 direction type（split ":" 取首段）
    direction_type = direction.split(":")[0]

    return direction_type in TASK_CHAIN_DIRECTION_TYPES


def is_ticket_in_progress_or_completed(ticket_id: str) -> bool:
    """
    檢查 Ticket 是否已 in_progress 或 completed。

    用於判斷任務鏈 handoff 的目標 ticket 是否已啟動。
    若目標已啟動，表示此 handoff 已被接手，應過濾為 stale。

    若無法載入（不存在或格式錯誤），返回 False（保守策略：不確定時顯示）。

    Args:
        ticket_id: Ticket ID，格式如 "0.31.1-W5-004"

    Returns:
        bool: True 表示已啟動（in_progress 或 completed），False 表示未啟動或無法判斷
    """
    try:
        version = extract_version_from_ticket_id(ticket_id)
        if version is None:
            return False

        ticket, error = load_and_validate_ticket(version, ticket_id, auto_print_error=False)
        if error:
            return False

        return ticket.get("status") in (STATUS_IN_PROGRESS, STATUS_COMPLETED)
    except Exception:
        return False  # 保守策略：無法判斷時顯示


def extract_direction_target_id(direction: str) -> Optional[str]:
    """
    從 direction 字串提取 target_id。

    格式：direction 可為 "type:target_id"（含目標）或 "type"（無目標）。
    - "to-sibling:0.1.0-W9-002" → "0.1.0-W9-002"
    - "to-parent" → None
    - "context-refresh" → None

    Args:
        direction: Handoff direction 字符串

    Returns:
        Optional[str]: target_id 若存在且非空，否則 None
    """
    parts = direction.split(":", 1)
    if len(parts) > 1 and parts[1]:
        return parts[1]
    return None


def is_valid_direction(direction: str) -> bool:
    """
    驗證 handoff 的 direction 是否為已知類型。

    已知 direction 值（不含後綴）：to-sibling、to-parent、to-child、context-refresh、auto
    支援的格式：
    - "to-sibling"、"to-sibling:target_id"
    - "to-parent"、"to-parent:target_id"
    - "to-child"、"to-child:target_id"
    - "context-refresh"
    - "auto"

    Args:
        direction: Handoff direction 字符串

    Returns:
        bool: True 表示為已知 direction，False 表示未知
    """
    if not direction:
        return False

    # 提取 direction type（split ":" 取首段，以支援 "to-sibling:target_id" 格式）
    direction_type = direction.split(":")[0]

    return direction_type in _KNOWN_DIRECTION_VALUES


def scan_pending_handoffs() -> List[ParsedHandoff]:
    """
    掃描 pending/ 目錄，解析所有 handoff 檔案。

    實現共用的掃描邏輯，被 list_pending_handoffs() 和 _collect_stale_handoffs() 使用。
    同時掃描 .json 和 .md 檔案，進行基本解析（JSON 讀取、必填欄位驗證）。

    每個記錄包含：
    - 成功解析的檔案：parse_error=None, schema_error=None
    - JSON 讀取失敗：parse_error=<錯誤信息>, schema_error=None
    - 必填欄位缺失：schema_error=<缺失欄位清單>

    呼叫端可根據 parse_error/schema_error 決定是否統計計數或直接跳過。

    Returns:
        List[ParsedHandoff]: 解析結果清單（包含成功和失敗記錄）
    """
    root = get_project_root()
    pending_dir = root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR

    if not pending_dir.exists():
        return []

    records = []

    # 同時掃描 .json 和 .md 檔案
    for handoff_file in sorted(pending_dir.glob("*.json")) + sorted(pending_dir.glob("*.md")):
        if handoff_file.suffix == ".json":
            # JSON 格式
            try:
                with open(handoff_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                # 記錄讀取錯誤，不中斷迴圈
                records.append(ParsedHandoff(
                    file_path=handoff_file,
                    ticket_id="",
                    direction="",
                    from_status="",
                    format="json",
                    data={},
                    parse_error=str(e),
                ))
                continue

            # 驗證必填欄位
            missing_fields = [f for f in _HANDOFF_REQUIRED_FIELDS if not data.get(f)]
            if missing_fields:
                records.append(ParsedHandoff(
                    file_path=handoff_file,
                    ticket_id=data.get("ticket_id", ""),
                    direction=data.get("direction", ""),
                    from_status=data.get("from_status", ""),
                    format="json",
                    data=data,
                    schema_error=f"缺少必填欄位：{', '.join(missing_fields)}",
                ))
                continue

            # 成功解析
            records.append(ParsedHandoff(
                file_path=handoff_file,
                ticket_id=data.get("ticket_id", ""),
                direction=data.get("direction", ""),
                from_status=data.get("from_status", ""),
                format="json",
                data=data,
            ))

        elif handoff_file.suffix == ".md":
            # Markdown 格式（提取檔名作為 ticket_id）
            ticket_id = handoff_file.stem
            records.append(ParsedHandoff(
                file_path=handoff_file,
                ticket_id=ticket_id,
                direction="",
                from_status="",
                format="markdown",
                data={
                    "ticket_id": ticket_id,
                    "format": "markdown",
                    "path": str(handoff_file.relative_to(root))
                },
            ))

    return records
