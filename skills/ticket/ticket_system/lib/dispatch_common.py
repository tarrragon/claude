"""共用 dispatch-* CLI 前置處理（0.18.0-W17-213 DRY 抽取）。

`dispatch-validate` 與 `dispatch-readiness` 兩命令前置 boilerplate 高度重複：

1. 從 argparse Namespace 取 ticket_id（缺值報錯）
2. `load_ticket(version, ticket_id)` 並判斷 None / `_yaml_error`
3. 解包 `_body` / `where.files` / `acceptance` 三欄

W17-053 linux 審查建議 1 指出「等第三個 dispatch-* 命令出現時可抽 helper」；
本 ticket 提前落地避免後續重複（已有兩個呼叫端，符合 DRY 三次法則的 N=2 預警）。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any, List, Optional

from ticket_system.lib.parser import load_ticket


@dataclass
class DispatchLoadResult:
    """`_load_and_unpack` 統一回傳結構。

    `error_exit_code` 為 None 時代表載入成功；否則呼叫端應直接 `return error_exit_code`。
    """

    ticket: Optional[dict]
    body: str
    where_files: List[str]
    acceptance: List[Any]
    error_exit_code: Optional[int]


def load_and_unpack(args: argparse.Namespace, version: str) -> DispatchLoadResult:
    """讀取 ticket 並解包 dispatch-* 共用欄位。

    錯誤情境（缺 ticket_id / load 失敗 / YAML error）會將訊息寫入 stderr，
    呼叫端依 `error_exit_code` 決定是否直接結束。

    Args:
        args: argparse.Namespace，需含 `ticket_id` 屬性。
        version: ticket 版本字串（如 "0.18.0"）。

    Returns:
        DispatchLoadResult；`error_exit_code` 為 None 代表成功可繼續。
    """
    ticket_id = getattr(args, "ticket_id", None)
    if not ticket_id:
        sys.stderr.write("[FAIL] 缺少 ticket_id 參數\n")
        return DispatchLoadResult(None, "", [], [], 2)

    ticket = load_ticket(version, ticket_id)
    if ticket is None:
        sys.stderr.write(f"[FAIL] ticket {ticket_id} 不存在或無法讀取\n")
        return DispatchLoadResult(None, "", [], [], 2)
    if ticket.get("_yaml_error"):
        sys.stderr.write(
            f"[FAIL] ticket {ticket_id} YAML 解析失敗: {ticket['_yaml_error']}\n"
        )
        return DispatchLoadResult(None, "", [], [], 2)

    body = ticket.get("_body", "") or ""
    where = ticket.get("where") or {}
    where_files = where.get("files") if isinstance(where, dict) else []
    acceptance = ticket.get("acceptance") or []

    return DispatchLoadResult(
        ticket=ticket,
        body=body,
        where_files=where_files or [],
        acceptance=acceptance,
        error_exit_code=None,
    )
