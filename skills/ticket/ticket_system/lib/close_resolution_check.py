"""close 與 set-closed-by 共用的 closed_by 檢查入口。

值域判定委派 `.claude/lib/close_resolution.py`（hook 也呼叫同一個函式，
三個端點值域一致）；本模組只補上 CLI 端才做的 I/O 檢查：值為 Ticket ID
時，該票須存在。

共用模組載入失敗時回傳錯誤（不放行）：值域檢查是關票的前置條件，
檢查本身無法執行時保守拒絕，並在訊息中寫出缺的檔案。
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ticket_system.constants import TICKET_ID_RE
from ticket_system.lib.claude_lib_loader import load_claude_lib

SHARED_MODULE_PATH = ".claude/lib/close_resolution.py"


def check_closed_by(
    close_reason: Optional[str],
    value: Optional[str],
    load_ticket: Callable[[str, str], Any],
) -> Optional[str]:
    """檢查 closed_by 值：先驗值域，再驗 Ticket ID 指向的票存在。

    Args:
        close_reason: 該票的 close_reason
        value: 欲寫入的 closed_by 值
        load_ticket: 呼叫端模組的 `load_ticket`（由呼叫端傳入，讓呼叫端模組
            層級的替換在測試中生效）

    Returns:
        不合法時回傳錯誤訊息（含 `[Error]` 前綴）；合法時回傳 None。
    """
    shared = load_claude_lib("close_resolution")
    if shared is None:
        return (
            f"[Error] 無法載入 closed_by 值域驗證模組 {SHARED_MODULE_PATH}，"
            "為避免寫入未驗證的值，本操作不執行"
        )

    domain_error = shared.validate_closed_by(close_reason, value)
    if domain_error:
        return f"[Error] {domain_error}"

    if shared.classify_closed_by(value) == shared.KIND_TICKET_ID:
        ticket_id = (value or "").strip()
        match = TICKET_ID_RE.match(ticket_id)
        if not match or not load_ticket(match.group(1), ticket_id):
            return f"[Error] closed_by 指向的 Ticket 不存在：{ticket_id}"

    return None
