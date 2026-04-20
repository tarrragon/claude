"""ticket track handoff-ready 命令（W10-017.1 v2 新增）。

提供 GO/NO-GO 結論用於 shell pipeline：
- exit 0: GO（ready for /clear）
- exit 1: 內部錯誤（非 IO_ERRORS 例外）
- exit 2: NO-GO（業務拒絕：有阻擋項，含 IO_ERRORS fail-open 保守判定）

設計依據：
- v2.1 §1.3 / §1.5 / §1.6 真值表 / §3.5 / §6.1
- v2.3 Q5 IO_ERRORS exit 2 (保守 NO-GO)
- Phase 3a §4 execute_handoff_ready 偽碼骨架

W10-017.12 Phase 4b P1 重構：
- AC1: _compute_blockers 上移 lib/checkpoint_view.compute_blockers；本模組僅
  決定 exit code 與渲染輸出。
- AC4: _print_go 改為複用 render_ready_check（消除手刻 checklist 重複）。
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from ticket_system.lib.checkpoint_state import (
    IO_ERRORS,
    CheckpointState,
    checkpoint_state,
)
from ticket_system.lib.checkpoint_view import (
    Blocker,
    compute_blockers,
    format_local_time,
    render_ready_check,
)


def _print_no_go(blockers: List[Blocker]) -> None:
    print(f"結論: NO-GO  尚未 ready ({len(blockers)} 項阻擋)")
    print()
    print("阻擋項目:")
    for b in blockers:
        print(f"  [ ] {b.label}")
        print(f"      → {b.fix}")


def _print_go(state: CheckpointState, ticket_id: Optional[str] = None) -> None:
    """渲染 GO 結論。

    W10-017.12 AC4：複用 render_ready_check 取代手刻 checklist，避免與 lib 層
    判定邏輯重複維護。GO 路徑下 render_ready_check 的四項判定必全綠（因 blockers
    為空通過 compute_blockers 檢查），僅視覺化該共識。
    """

    print("結論: GO  ready for /clear")
    print()
    print(render_ready_check(state, caller="handoff-ready"))
    print()
    print("下一步: /clear")


def execute_handoff_ready(args: argparse.Namespace) -> int:
    """執行 handoff-ready 命令。

    Returns:
        0: GO；1: 內部錯誤；2: NO-GO（含 IO_ERRORS 保守判定）
    """

    ticket_id = getattr(args, "ticket_id", None)

    try:
        state = checkpoint_state(
            ticket_id=ticket_id, caller="handoff-ready", log_metrics=True
        )
    except IO_ERRORS as e:
        # v2.3 Q5: IO_ERRORS 視為「無法判定」，保守回 exit 2 (NO-GO)
        # 規則 4 雙通道：stderr WARN + stdout 提示
        sys.stderr.write(f"WARN: data source(s) unavailable: {e}\n")
        print("結論: NO-GO  資料源異常無法確認 ready 狀態")
        return 2
    except Exception as e:
        # 非 IO_ERRORS：規則 4 stderr + exit 1
        sys.stderr.write(f"handoff-ready internal error: {e}\n")
        return 1

    print("=== Handoff Ready Check ===")
    print(f"時間: {format_local_time(state)}")
    print(f"Ticket: {ticket_id or '全域'}")
    print()

    blockers = compute_blockers(state, ticket_id=ticket_id)
    if blockers:
        _print_no_go(blockers)
        return 2

    _print_go(state, ticket_id=ticket_id)
    return 0


def register_handoff_ready(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 handoff-ready 子命令。

    --ticket-id 為可選 flag（v2.1 修正 6 / Phase 3a §1.1）。
    """
    p = subparsers.add_parser(
        "handoff-ready",
        help="檢查 /clear ready 狀態（GO/NO-GO/internal-error）",
    )
    p.add_argument(
        "--ticket-id",
        "-t",
        dest="ticket_id",
        default=None,
        help="可選 ticket ID；指定時影響 in_progress_tickets 自身判定",
    )
    return p
