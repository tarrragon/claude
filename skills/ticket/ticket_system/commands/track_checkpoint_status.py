"""ticket track checkpoint-status 命令（W10-017.1 v2 新增）。

純報告型命令：輸出當前 Checkpoint 編號 + phase_id + ready_for_clear + 資料源狀態。
退出碼：永遠 exit 0（純報告）；內部錯誤 exit 1。

設計依據：
- v2.1 §1.3 / §1.7 mockup
- v2.2 Q3 fail-open data_sources 顯示完整 traceback (內含於 state.data_sources error str)
- Phase 3a §4 execute_checkpoint_status 偽碼骨架
"""

from __future__ import annotations

import argparse
import sys

from ticket_system.lib.checkpoint_state import (
    IO_ERRORS,
    checkpoint_state,
    format_next_action,
    format_phase_label,
)
from ticket_system.lib.checkpoint_view import format_local_time


def execute_checkpoint_status(args: argparse.Namespace) -> int:
    """執行 checkpoint-status 命令（純報告型）。

    Returns:
        0: 正常或 fail-open；1: 內部錯誤（非 IO_ERRORS）
    """

    ticket_id = getattr(args, "ticket_id", None)

    try:
        state = checkpoint_state(
            ticket_id=ticket_id,
            caller="checkpoint-status",
            log_metrics=True,
        )
    except IO_ERRORS as e:
        # v2.2 Q3: fail-open 純報告型，stderr 警告 + exit 0
        sys.stderr.write(f"WARN: data source(s) unavailable: {e}\n")
        print("=== Checkpoint Status ===")
        print(f"Ticket: {ticket_id or '全域'}")
        print(f"資料源異常: {type(e).__name__}: {e}")
        return 0
    except Exception as e:
        sys.stderr.write(f"checkpoint-status internal error: {e}\n")
        return 1

    print("=== Checkpoint Status ===")
    print(f"時間: {format_local_time(state)}")
    print(f"Ticket: {ticket_id or '全域'}")
    print()
    print(f"Checkpoint: {format_phase_label(state)}")
    print(f"phase_id: {state.current_phase}")
    print(f"ready_for_clear: {str(state.ready_for_clear).lower()}")
    print()
    print(f"下一步: {format_next_action(state)}")
    print()
    print("資料來源狀態:")
    for src, status in state.data_sources.items():
        print(f"  {src}: {status}")

    return 0


def register_checkpoint_status(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 checkpoint-status 子命令。"""
    p = subparsers.add_parser(
        "checkpoint-status",
        help="檢視當前 Checkpoint 詳情（純報告型）",
    )
    p.add_argument(
        "--ticket-id",
        "-t",
        dest="ticket_id",
        default=None,
        help="可選 ticket ID；指定時影響 in_progress_tickets 自身判定",
    )
    return p
