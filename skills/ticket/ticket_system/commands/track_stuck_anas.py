"""
ticket track stuck-anas 命令（W17-008.15 方案 D 第 1 項）

掃描 ANA type + status=in_progress + 全 spawned_tickets 已 completed 的 ticket，
協助 PM 識別「衍生子任務全完成但 source ANA 未 complete」的卡住情境。

設計約束：
- version-agnostic（不接受 --version；可選 --wave 過濾、--all 跨版本）
- 註冊於 track.py _create_version_agnostic_handlers() 字典
- 復用 ticket_loader.list_tickets / get_active_versions
"""

from __future__ import annotations

import argparse
from typing import Dict, List, Optional

from ticket_system.constants import (
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
)
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.version import get_active_versions


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------

def _is_ana_in_progress(ticket: Dict) -> bool:
    """ANA type 且 status=in_progress。"""
    return (
        ticket.get("type") == "ANA"
        and ticket.get("status") == STATUS_IN_PROGRESS
    )


def _all_spawned_completed(
    ticket: Dict, ticket_index: Dict[str, Dict]
) -> bool:
    """ticket 的所有 spawned_tickets 是否皆 completed（且至少存在 1 個）。"""
    spawned_ids = ticket.get("spawned_tickets") or []
    if not spawned_ids:
        return False
    for sid in spawned_ids:
        spawned = ticket_index.get(sid)
        if not spawned:
            # spawned ticket 不存在 → 不視為已完成
            return False
        if spawned.get("status") != STATUS_COMPLETED:
            return False
    return True


def _collect_stuck_anas(
    tickets: List[Dict], wave: Optional[int]
) -> List[Dict]:
    """過濾卡住的 ANA。"""
    ticket_index = {t.get("id"): t for t in tickets if t.get("id")}
    stuck: List[Dict] = []
    for ticket in tickets:
        if not _is_ana_in_progress(ticket):
            continue
        if wave is not None and ticket.get("wave") != wave:
            continue
        if _all_spawned_completed(ticket, ticket_index):
            stuck.append(ticket)
    return stuck


def _gather_tickets(
    explicit_version: Optional[str], all_versions: bool
) -> List[Dict]:
    """依 --all / 自動偵測 active versions 收集 ticket 清單。"""
    versions: List[str]
    if explicit_version:
        versions = [explicit_version]
    elif all_versions:
        versions = get_active_versions() or []
    else:
        versions = get_active_versions() or []

    aggregated: List[Dict] = []
    for version in versions:
        aggregated.extend(list_tickets(version) or [])
    return aggregated


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _render(stuck: List[Dict], wave: Optional[int]) -> str:
    lines: List[str] = []
    lines.append("─" * 60)
    header = "卡住的 ANA（in_progress 且 spawned 全 completed）"
    if wave is not None:
        header += f"  wave={wave}"
    lines.append(header)
    lines.append("─" * 60)

    if not stuck:
        lines.append("（無卡住的 ANA）")
        return "\n".join(lines)

    for idx, ticket in enumerate(stuck, start=1):
        tid = ticket.get("id", "<unknown>")
        title = ticket.get("title") or ""
        spawned = ticket.get("spawned_tickets") or []
        lines.append(
            f"  {idx}. {tid}  {title}"
        )
        lines.append(
            f"      spawned={len(spawned)} 全 completed → 可考慮 "
            f"ticket track complete {tid}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def execute_stuck_anas(args: argparse.Namespace) -> int:
    """執行 track stuck-anas 命令（version-agnostic）。"""
    wave = getattr(args, "wave", None)
    all_versions = bool(getattr(args, "all", False))
    explicit_version = getattr(args, "version", None)

    tickets = _gather_tickets(explicit_version, all_versions)
    stuck = _collect_stuck_anas(tickets, wave)
    print(_render(stuck, wave))
    return 0


def register_stuck_anas(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 stuck-anas 子命令 parser。"""
    p = subparsers.add_parser(
        "stuck-anas",
        help=(
            "列出卡住的 ANA："
            "type=ANA + status=in_progress + spawned 全 completed"
        ),
    )
    p.add_argument(
        "--wave",
        type=int,
        default=None,
        help="僅列出指定 wave 的 ANA",
    )
    p.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="跨所有 active 版本掃描（預設僅當前 active 版本）",
    )
    p.add_argument(
        "--version",
        default=None,
        help="指定版本（覆蓋自動偵測；與 --all 互斥）",
    )
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
