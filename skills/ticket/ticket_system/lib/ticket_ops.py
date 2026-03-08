"""
Ticket 操作共用函式模組

封裝多個命令模組共用的 Ticket 驗證和路徑解析邏輯，消除重複程式碼。
此模組不同於 ticket_validator.py（純驗證邏輯）：
- ticket_validator.py：純粹驗證邏輯，無 IO 操作
- ticket_ops.py：命令層工具集，結合載入、驗證和錯誤輸出
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ticket_system.lib.ticket_loader import (
    get_ticket_path,
    load_ticket,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    format_error,
)


def resolve_id_from_ref(ref: Any) -> str:
    """
    從任務引用（字串 ID 或字典）提取 Ticket ID。

    支援兩種格式：
    - 字串：直接返回
    - 字典：返回 'id' 欄位值

    Args:
        ref: 任務引用（str 或 dict）

    Returns:
        str: Ticket ID（若無法提取返回空字串）

    Examples:
        >>> resolve_id_from_ref("0.1.0-W2-001")
        '0.1.0-W2-001'
        >>> resolve_id_from_ref({"id": "0.1.0-W2-001", "status": "pending"})
        '0.1.0-W2-001'
        >>> resolve_id_from_ref({})
        ''
        >>> resolve_id_from_ref(None)
        ''
    """
    if isinstance(ref, str):
        return ref
    elif isinstance(ref, dict):
        return ref.get("id", "")
    return ""


def load_and_validate_ticket(
    version: str,
    ticket_id: str,
    auto_print_error: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    載入並驗證 Ticket，封裝「load + not found check + yaml error check」模式。

    此函式整合了三個常見檢查步驟：
    1. 載入 Ticket
    2. 檢查是否存在（not found）
    3. 檢查 YAML 解析錯誤

    Args:
        version: Ticket 所屬版本
        ticket_id: Ticket ID
        auto_print_error: 是否自動輸出錯誤訊息（預設 True）
            - True：自動 print 錯誤並 return (None, error_msg)
            - False：不 print，由呼叫者處理

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]:
            成功：(ticket_dict, None)
            失敗：(None, error_message)

    Examples:
        >>> ticket, error = load_and_validate_ticket("0.31.0", "0.31.0-W1-001")
        >>> if error:
        ...     return 1
        >>> # 使用 ticket
    """
    # Step 1：載入 Ticket
    ticket = load_ticket(version, ticket_id)

    # Step 2：檢查是否存在
    if not ticket:
        error_msg = ErrorMessages.TICKET_NOT_FOUND
        if auto_print_error:
            print(format_error(error_msg, ticket_id=ticket_id))
        return None, error_msg

    # Step 3：檢查 YAML 解析錯誤
    if "_yaml_error" in ticket:
        error_msg = f"Ticket {ticket_id} 的 YAML 格式錯誤：{ticket['_yaml_error']}"
        if auto_print_error:
            print(format_error(error_msg))
        return None, error_msg

    return ticket, None


def resolve_ticket_path(
    ticket: Dict[str, Any],
    version: str,
    ticket_id: str,
) -> Path:
    """
    解析 Ticket 路徑，封裝 Path(ticket.get("_path", get_ticket_path(...))) 模式。

    Ticket 載入時會記錄 _path 欄位（檔案實際存放路徑）。
    此函式取得 _path，或在缺失時回退到計算的預設路徑。

    Args:
        ticket: Ticket 資料字典（必須包含 _path 或可用 version + ticket_id 計算）
        version: Ticket 所屬版本（回退時使用）
        ticket_id: Ticket ID（回退時使用）

    Returns:
        Path: Ticket 檔案路徑

    Examples:
        >>> ticket, _ = load_and_validate_ticket("0.31.0", "0.31.0-W1-001")
        >>> path = resolve_ticket_path(ticket, "0.31.0", "0.31.0-W1-001")
        >>> print(path)
        Path(.../docs/work-logs/v0.31.0/tickets/0.31.0-W1-001.md)
    """
    return Path(ticket.get("_path", get_ticket_path(version, ticket_id)))
