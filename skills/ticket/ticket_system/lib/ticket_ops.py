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


def check_reverse_source_conflict(
    target_ticket_id: str, parent_ticket_id: str
) -> Optional[str]:
    """檢查 target_ticket 的 source_ticket 是否與 parent_ticket 衝突。

    Best-effort 唯讀檢查：僅在能明確判定「target 已存在且其 source_ticket
    指向另一張與 parent 不同的既有票」時回傳警告文字；target 不存在、
    版本無法解析、或 source_ticket 未設定／恰為 parent 本身，一律回傳
    None（無衝突可報）。

    Why:
        spawned_tickets 的常見寫入路徑（add-spawned、resolve-spawn-request
        --spawned-ticket）接受任意既有 ticket ID，不驗證該 ID 是否已宣稱
        歸屬另一張票——血緣一旦寫錯，ticket md 又受 hook 禁止直讀直編，
        等於沒有合法更正路徑（remove-spawned 補的正是這條更正路徑，本
        函式補的是更前面一關：寫入當下即時提示，屬 opinionated default
        「預設路徑引導正確做法」，兩者互補不互斥）。

        僅發 WARNING 不阻擋寫入：spawned_tickets 的關聯強度本就弱於
        source_ticket，存在「刻意關聯一張已有主的既有票」的合法情境
        （如事後補記一個獨立完成、未走 --source-ticket 流程的既有票），
        故不宜升級為硬擋。

    Args:
        target_ticket_id: 即將寫入 spawned_tickets 的目標 ticket ID。
        parent_ticket_id: 執行寫入的來源（父）ticket ID。

    Returns:
        Optional[str]: 衝突時回傳可直接印出的警告文字；無衝突或無法
        判定時回傳 None。
    """
    from ticket_system.lib.ticket_validator import extract_version_from_ticket_id

    target_version = extract_version_from_ticket_id(target_ticket_id)
    if target_version is None:
        return None

    target_ticket = load_ticket(target_version, target_ticket_id)
    if not target_ticket:
        return None

    existing_source = target_ticket.get("source_ticket")
    if not existing_source or existing_source == parent_ticket_id:
        return None

    return (
        f"{target_ticket_id} 的 source_ticket 已為 {existing_source}"
        f"（非 {parent_ticket_id}）：此次寫入僅新增 spawned_tickets 關聯，"
        f"不會覆蓋 target 既有血緣。若非刻意關聯既有票，請確認 ID 是否誤植。"
    )
