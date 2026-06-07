"""Blocker 解除狀態判定共用 predicate（W8-043）。

抽出原 `commands/lifecycle.py._is_fully_unblocked`，使 lifecycle（cascade
unblock / 建議列表）與 track_runqueue（list 視圖可執行判定）共用同一 AND 語義，
避免 commands 模組互相 import 形成耦合（對齊 W10-121「抽共用 lib」方向）。

語義（AND）：ticket 的所有 blocker 皆已解除才視為可執行。

設計背景（W8-042 ANA）：
    runqueue list 視圖原以字面 `len(blockedBy)==0` 判定可執行，遺漏 blocker
    已完成但 blockedBy 欄位未清理的 ticket（W8-001.5 / W8-027 實證），導致 PM
    在 runqueue 看不到實際可接手的 ticket，排程判斷失準。
"""

from __future__ import annotations

from typing import Any, Dict

from ticket_system.lib.constants import STATUS_COMPLETED, STATUS_CLOSED


def is_fully_unblocked(
    ticket: Dict[str, Any],
    ticket_map: Dict[str, Any],
    *,
    include_closed_as_resolved: bool,
) -> bool:
    """判斷 ticket 的所有 blocker 是否皆已解除（AND 語義）。

    - blockedBy 為空 → True（無阻塞即視為解除）。
    - 找不到 blocker（ticket_map 無此 id）→ False（資料不一致時保守保留
      blocked，不建議解鎖）。
    - include_closed_as_resolved=True：blocker status 為 completed 或 closed
      皆視為已解除（cascade unblock / scheduler 場景，與 lifecycle skip 規則
      一致）。
    - include_closed_as_resolved=False：僅 completed 視為已解除（建議列表場景，
      保留原有 conservative 行為）。

    Args:
        ticket: 待檢查的 ticket dict（需含 blockedBy）。
        ticket_map: 版本內所有 ticket 的 id → dict 映射。
        include_closed_as_resolved: 是否將 closed 也視為解除狀態。

    Returns:
        True 表示所有 blocker 皆已解除。
    """
    blocked_by = ticket.get("blockedBy") or []
    if not blocked_by:
        return True
    resolved_statuses = (
        (STATUS_COMPLETED, STATUS_CLOSED)
        if include_closed_as_resolved
        else (STATUS_COMPLETED,)
    )
    for blocker_id in blocked_by:
        blocker = ticket_map.get(blocker_id)
        if blocker is None:
            return False
        if blocker.get("status") not in resolved_statuses:
            return False
    return True
