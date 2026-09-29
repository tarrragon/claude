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

import sys
from typing import Any, Dict, List, Optional

from ticket_system.lib.constants import STATUS_COMPLETED, STATUS_CLOSED
from ticket_system.lib.ticket_loader import get_project_root, load_ticket
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id

VERSION_STATUS_COMPLETED = "completed"


def resolve_blocker(
    blocker_id: str, ticket_map: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """取得 blocker 票：先查版本內 ticket_map，查無再以 ID 自身版本前綴載入。

    跨版本 blocker 不在呼叫端的版本內全集裡。取不到版本前綴或載入失敗回傳
    None，呼叫端據此保守判定為未解除。
    """
    hit = ticket_map.get(blocker_id)
    if hit is not None:
        return hit
    version = extract_version_from_ticket_id(blocker_id)
    if not version:
        return None
    try:
        return load_ticket(version, blocker_id)
    except Exception as err:
        sys.stderr.write(
            f"[blocker_resolution] WARNING: 載入 blocker {blocker_id} 失敗"
            f"（{err}），視為未解除\n"
        )
        return None


def list_open_versions() -> List[str]:
    """回傳 todolist 中尚未 completed 的版本（供跨版本反向解鎖掃描）。

    todolist 不存在或解析失敗回傳空清單（僅退化為同版本掃描）。
    """
    path = get_project_root() / "docs" / "todolist.yaml"
    if not path.exists():
        return []
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return [
            str(v["version"])
            for v in data.get("versions", [])
            if v.get("status") != VERSION_STATUS_COMPLETED
        ]
    except Exception as err:
        sys.stderr.write(
            f"[blocker_resolution] WARNING: 解析 todolist.yaml 失敗（{err}），"
            "跨版本反向解鎖退化為僅掃同版本（略過）\n"
        )
        return []


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
        blocker = resolve_blocker(blocker_id, ticket_map)
        if blocker is None:
            return False
        if blocker.get("status") not in resolved_statuses:
            return False
    return True
